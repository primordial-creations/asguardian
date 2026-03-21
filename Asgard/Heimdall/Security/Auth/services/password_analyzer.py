"""
Heimdall Password Analyzer Service

Service for detecting password handling security issues.
"""

import re
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Security.Auth.models.auth_models import (
    AuthConfig,
    AuthFinding,
    AuthReport,
)
from Asgard.Heimdall.Security.Auth.services._password_patterns import (
    ENUM_VALUE_PATTERNS,
    PASSWORD_PATTERNS,
    PasswordPattern,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    is_in_comment_or_docstring,
    scan_directory_for_security,
)


class PasswordAnalyzer:
    """
    Analyzes password handling security.

    Detects:
    - Plaintext password storage
    - Passwords in logs
    - Weak password hashing
    - Hardcoded credentials
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """
        Initialize the password analyzer.

        Args:
            config: Auth configuration. Uses defaults if not provided.
        """
        self.config = config or AuthConfig()
        self.patterns = PASSWORD_PATTERNS

    def scan(self, scan_path: Optional[Path] = None) -> AuthReport:
        """
        Scan the specified path for password security issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            AuthReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = AuthReport(scan_path=str(path))

        for file_path in scan_directory_for_security(
            path,
            exclude_patterns=self.config.exclude_patterns,
        ):
            report.total_files_scanned += 1
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

    def _scan_file(self, file_path: Path, root_path: Path) -> List[AuthFinding]:
        """
        Scan a single file for password security issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of auth findings in the file
        """
        findings: List[AuthFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")

        for pattern in self.patterns:
            for match in pattern.pattern.finditer(content):
                line_number, column = find_line_column(content, match.start())

                file_ext = file_path.suffix
                if is_in_comment_or_docstring(content, lines, line_number, match.start(), file_ext):
                    continue

                if self._is_enum_value(match.group(0)):
                    continue

                if self._is_json_example(content, match.start()):
                    continue

                if pattern.name == "password_in_log" and self._is_status_message(match.group(0)):
                    continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = AuthFinding(
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

        return findings

    def _is_enum_value(self, matched_text: str) -> bool:
        """Check if matched text is an enum value definition, not a real credential."""
        if "=" in matched_text:
            value_part = matched_text.split("=", 1)[1].strip().strip("'\"")
            for pattern in ENUM_VALUE_PATTERNS:
                if re.match(pattern, value_part, re.IGNORECASE):
                    return True
        return False

    def _is_status_message(self, matched_text: str) -> bool:
        """
        Check if the log statement just mentions 'password' in text, not logging actual value.

        Returns True for status messages like:
        - "updating password"
        - "password changed"
        - "resetting password"

        Returns False for actual password logging like:
        - f"Password: {password}"
        - f"password={user.password}"
        """
        lower_match = matched_text.lower()

        actual_password_patterns = [
            r'password\s*[=:]\s*[{"\'\[]',
            r'password\s*[=:]\s*\$',
            r'password\s*[=:]\s*%',
            r'\{[^}]*password[^}]*\}',
            r'password\s*\+',
        ]

        for pattern in actual_password_patterns:
            if re.search(pattern, lower_match):
                return False

        status_patterns = [
            r'(updating|update|changed|change|reset|resetting|rotating|rotated)\s+password',
            r'password\s+(updated|changed|reset|rotated|failed|succeeded|complete)',
            r'(new|old|current|temporary)\s+password\s+\w',
            r'password\s+(is|was|has|will)',
        ]

        for pattern in status_patterns:
            if re.search(pattern, lower_match):
                return True

        return False

    def _is_json_example(self, content: str, match_start: int) -> bool:
        """
        Check if match is inside a JSON documentation/example context.

        Detects patterns like:
        - "credential_type": "password" (JSON key definition)
        - print('''{ ... "password" ... }''') (JSON example in print)
        """
        context_start = max(0, match_start - 200)
        context_end = min(len(content), match_start + 200)
        context = content[context_start:context_end]

        if 'print(' in context and ('"""' in context or "'''" in context):
            json_indicators = [
                '"credential_type":', "'credential_type':",
                '"type":', '"field":', '"key":',
                '"example"', '"sample"', 'example:', 'sample:',
            ]
            if any(ind in context.lower() for ind in json_indicators):
                return True

        type_patterns = [
            r'"(?:credential_type|type|field_type|secret_type)":\s*"password"',
            r"'(?:credential_type|type|field_type|secret_type)':\s*'password'",
        ]
        for pattern in type_patterns:
            if re.search(pattern, context, re.IGNORECASE):
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
