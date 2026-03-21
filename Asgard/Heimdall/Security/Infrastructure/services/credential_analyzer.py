"""
Heimdall Credential Analyzer Service

Service for detecting default and weak credentials in configuration and code.
"""

import re
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Infrastructure.models.infra_models import (
    InfraConfig,
    InfraFinding,
    InfraFindingType,
    InfraReport,
)
from Asgard.Heimdall.Security.Infrastructure.services._credential_patterns import (
    CREDENTIAL_PATTERNS,
    CredentialPattern,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    is_in_comment_or_docstring,
    is_example_or_placeholder,
    scan_directory_for_security,
)


class CredentialAnalyzer:
    """
    Analyzes code and configuration for credential security issues.

    Detects:
    - Default credentials (admin/admin, root/password, etc.)
    - Weak credential patterns
    - Hardcoded secret keys
    - Test/demo credentials in production
    """

    def __init__(self, config: Optional[InfraConfig] = None):
        """
        Initialize the credential analyzer.

        Args:
            config: Infrastructure configuration. Uses defaults if not provided.
        """
        self.config = config or InfraConfig()
        self.patterns = CREDENTIAL_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> InfraReport:
        """
        Scan the specified path for credential security issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            InfraReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = InfraReport(scan_path=str(path))

        for file_path in scan_directory_for_security(
            path,
            exclude_patterns=self.config.exclude_patterns,
        ):
            report.total_files_scanned += 1

            if self._is_config_file(file_path):
                report.total_config_files += 1

            findings = self._scan_file(file_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)

        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    ENUM_VALUE_PATTERNS = [
        r"^password$", r"^passwd$", r"^pwd$",
        r"^secret$", r"^secret[_-]?key$", r"^api[_-]?key$",
        r"^access[_-]?key$", r"^access[_-]?token$", r"^auth[_-]?token$",
        r"^oauth[_-]?token$", r"^private[_-]?key$", r"^jwt[_-]?secret$",
        r"^client[_-]?secret$", r"^auth[_-]?secret$",
        r"^not[_-]?a[_-]?password$", r"^rabbitmq[_-]?password$",
        r"^database[_-]?password$", r"^db[_-]?password$",
    ]

    def _scan_file(self, file_path: Path, root_path: Path) -> List[InfraFinding]:
        """
        Scan a single file for credential security issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of infrastructure findings in the file
        """
        findings: List[InfraFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")
        file_ext = file_path.suffix.lower()

        for pattern in self.patterns:
            for match in pattern.pattern.finditer(content):
                line_number, column = find_line_column(content, match.start())

                if is_in_comment_or_docstring(content, lines, line_number, match.start(), file_ext):
                    continue

                if self._is_enum_value(match.group(0)):
                    continue

                context_start = max(0, match.start() - 200)
                context_end = min(len(content), match.end() + 100)
                context = content[context_start:context_end]

                matched_text = match.group(0)
                if "=" in matched_text or ":" in matched_text:
                    separator = "=" if "=" in matched_text else ":"
                    value_part = matched_text.split(separator, 1)[1].strip().strip("'\"")
                    if is_example_or_placeholder(value_part, context):
                        continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = InfraFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    column_start=column,
                    column_end=column + len(match.group(0)),
                    finding_type=pattern.finding_type,
                    severity=pattern.severity,
                    title=pattern.title,
                    description=pattern.description,
                    code_snippet=code_snippet,
                    cwe_id=pattern.cwe_id,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                    ],
                )

                findings.append(finding)

        findings.extend(self._check_default_credential_pairs(file_path, root_path, content, lines))

        return findings

    def _check_default_credential_pairs(
        self,
        file_path: Path,
        root_path: Path,
        content: str,
        lines: List[str],
    ) -> List[InfraFinding]:
        """
        Check for known default credential pairs in the content.

        Args:
            file_path: Path to the file being scanned
            root_path: Root path for relative path calculation
            content: File content
            lines: File content as lines

        Returns:
            List of findings for default credential pairs
        """
        findings: List[InfraFinding] = []
        file_ext = file_path.suffix.lower()

        for username, password in self.config.default_credentials:
            username_pattern = re.compile(
                rf"""(?:username|user|login)\s*[=:]\s*['"]{re.escape(username)}['"]""",
                re.IGNORECASE
            )
            password_pattern = re.compile(
                rf"""(?:password|passwd|pwd)\s*[=:]\s*['"]{re.escape(password)}['"]""",
                re.IGNORECASE
            )

            username_match = username_pattern.search(content)
            password_match = password_pattern.search(content)

            if username_match and password_match:
                line_number, column = find_line_column(content, password_match.start())

                if is_in_comment_or_docstring(content, lines, line_number, password_match.start(), file_ext):
                    continue

                context_start = max(0, password_match.start() - 200)
                context_end = min(len(content), password_match.end() + 100)
                context = content[context_start:context_end]

                if is_example_or_placeholder(password, context):
                    continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = InfraFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    column_start=column,
                    column_end=column + len(password_match.group(0)),
                    finding_type=InfraFindingType.DEFAULT_CREDENTIALS,
                    severity=SecuritySeverity.CRITICAL,
                    title=f"Default Credentials ({username}/{password})",
                    description=f"Default credentials {username}/{password} detected. This is a known default that attackers will try.",
                    code_snippet=code_snippet,
                    config_key="password",
                    current_value=f"{username}:{password}",
                    recommended_value="Use strong, unique credentials",
                    cwe_id="CWE-798",
                    confidence=0.9,
                    remediation="Change default credentials immediately. Use strong, unique passwords stored in environment variables.",
                    references=[
                        "https://cwe.mitre.org/data/definitions/798.html",
                    ],
                )

                findings.append(finding)

        return findings

    def _is_config_file(self, file_path: Path) -> bool:
        """Check if a file is a configuration file."""
        return file_path.name in self.config.config_files

    def _is_enum_value(self, matched_text: str) -> bool:
        """Check if matched text is an enum value definition, not a real credential."""
        if "=" in matched_text or ":" in matched_text:
            separator = "=" if "=" in matched_text else ":"
            value_part = matched_text.split(separator, 1)[1].strip().strip("'\"")
            for pattern in self.ENUM_VALUE_PATTERNS:
                if re.match(pattern, value_part, re.IGNORECASE):
                    return True
        return False

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if a severity level meets the configured threshold."""
        severity_order = {
            SecuritySeverity.INFO.value: 0,
            SecuritySeverity.LOW.value: 1,
            SecuritySeverity.MEDIUM.value: 2,
            SecuritySeverity.HIGH.value: 3,
            SecuritySeverity.CRITICAL.value: 4,
        }

        min_level = severity_order.get(self.config.min_severity, 1)
        finding_level = severity_order.get(severity, 1)

        return finding_level >= min_level

    def _severity_order(self, severity: str) -> int:
        """Get sort order for severity (critical first)."""
        order = {
            SecuritySeverity.CRITICAL.value: 0,
            SecuritySeverity.HIGH.value: 1,
            SecuritySeverity.MEDIUM.value: 2,
            SecuritySeverity.LOW.value: 3,
            SecuritySeverity.INFO.value: 4,
        }
        return order.get(severity, 5)
