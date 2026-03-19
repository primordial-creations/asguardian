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
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import (
    extract_code_snippet,
    find_line_column,
    is_in_comment_or_docstring,
    is_example_or_placeholder,
    scan_directory_for_security,
)


class CredentialPattern:
    """Defines a pattern for detecting credential issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        finding_type: InfraFindingType,
        severity: SecuritySeverity,
        title: str,
        description: str,
        cwe_id: str,
        remediation: str,
        confidence: float = 0.7,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.finding_type = finding_type
        self.severity = severity
        self.title = title
        self.description = description
        self.cwe_id = cwe_id
        self.remediation = remediation
        self.confidence = confidence


CREDENTIAL_PATTERNS: List[CredentialPattern] = [
    CredentialPattern(
        name="admin_admin_credentials",
        pattern=r"""(?:username|user|login)\s*[=:]\s*['"](admin)['"]\s*(?:,|\n|;)?\s*(?:password|passwd|pwd)\s*[=:]\s*['"](admin)['"]""",
        finding_type=InfraFindingType.DEFAULT_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        title="Default Admin Credentials (admin/admin)",
        description="Default admin/admin credentials detected. This is a well-known default that attackers will try first.",
        cwe_id="CWE-798",
        remediation="Change default credentials immediately. Use strong, unique passwords.",
        confidence=0.95,
    ),
    CredentialPattern(
        name="root_password_credentials",
        pattern=r"""(?:username|user|login)\s*[=:]\s*['"]root['"]\s*(?:,|\n|;)?\s*(?:password|passwd|pwd)\s*[=:]\s*['"](?:root|password|toor)['"]""",
        finding_type=InfraFindingType.DEFAULT_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        title="Default Root Credentials",
        description="Default root credentials detected. Root access with known passwords is extremely dangerous.",
        cwe_id="CWE-798",
        remediation="Change default root credentials immediately. Consider using key-based authentication.",
        confidence=0.95,
    ),
    CredentialPattern(
        name="database_default_credentials",
        pattern=r"""(?:postgres|mysql|oracle|sa|mongodb)\s*[=:]\s*['"](?:postgres|mysql|oracle|sa|admin|password)['"]""",
        finding_type=InfraFindingType.DEFAULT_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        title="Default Database Credentials",
        description="Default database credentials detected. Database access with default credentials can lead to data breach.",
        cwe_id="CWE-798",
        remediation="Change default database credentials. Use environment variables for credential storage.",
        confidence=0.9,
    ),
    CredentialPattern(
        name="password_equals_username",
        pattern=r"""(?:password|passwd|pwd)\s*[=:]\s*(?:username|user|login)""",
        finding_type=InfraFindingType.WEAK_CREDENTIAL_PATTERN,
        severity=SecuritySeverity.HIGH,
        title="Password Equals Username Pattern",
        description="Password appears to be set equal to the username, which is a weak credential pattern.",
        cwe_id="CWE-521",
        remediation="Use strong, unique passwords that are different from the username.",
        confidence=0.8,
    ),
    CredentialPattern(
        name="simple_password_pattern",
        pattern=r"""(?:password|passwd|pwd)\s*[=:]\s*['"](?:password|123456|12345678|qwerty|abc123|111111|admin123|letmein|welcome|monkey)['"]""",
        finding_type=InfraFindingType.WEAK_CREDENTIAL_PATTERN,
        severity=SecuritySeverity.CRITICAL,
        title="Common Weak Password",
        description="A commonly used weak password was detected. These passwords are in every attacker's wordlist.",
        cwe_id="CWE-521",
        remediation="Use strong, unique passwords with mixed case, numbers, and special characters.",
        confidence=0.95,
    ),
    CredentialPattern(
        name="hardcoded_secret_key",
        pattern=r"""(?:SECRET_KEY|API_KEY|AUTH_TOKEN|PRIVATE_KEY|JWT_SECRET)\s*[=:]\s*['"][^'"]{8,}['"]""",
        finding_type=InfraFindingType.HARDCODED_SECRET_KEY,
        severity=SecuritySeverity.HIGH,
        title="Hardcoded Secret Key",
        description="A secret key appears to be hardcoded in the configuration. This should be stored securely.",
        cwe_id="CWE-798",
        remediation="Move secret keys to environment variables or a secrets manager like Vault.",
        confidence=0.8,
    ),
    CredentialPattern(
        name="django_default_secret",
        pattern=r"""SECRET_KEY\s*=\s*['"]django-insecure-[^'"]+['"]""",
        finding_type=InfraFindingType.HARDCODED_SECRET_KEY,
        severity=SecuritySeverity.CRITICAL,
        title="Django Insecure Secret Key",
        description="Django's default insecure secret key is being used. This key is predictable and not suitable for production.",
        cwe_id="CWE-330",
        remediation="Generate a new secret key using Django's get_random_secret_key() and store it in an environment variable.",
        confidence=0.99,
    ),
    CredentialPattern(
        name="empty_password",
        # Match empty password followed by end of statement, not method calls like "".join()
        pattern=r"""(?:password|passwd|pwd)\s*[=:]\s*['"]["'](?:\s*[,;\n\r]|$)""",
        finding_type=InfraFindingType.WEAK_CREDENTIAL_PATTERN,
        severity=SecuritySeverity.CRITICAL,
        title="Empty Password",
        description="An empty password was detected. This allows unauthorized access without any authentication.",
        cwe_id="CWE-258",
        remediation="Set a strong password or remove the credential if not needed.",
        confidence=0.9,
    ),
    CredentialPattern(
        name="test_credentials",
        pattern=r"""(?:username|user|login)\s*[=:]\s*['"](?:test|demo|guest|sample)['"]\s*(?:,|\n|;)?\s*(?:password|passwd|pwd)\s*[=:]\s*['"](?:test|demo|guest|sample)['"]""",
        finding_type=InfraFindingType.DEFAULT_CREDENTIALS,
        severity=SecuritySeverity.HIGH,
        title="Test/Demo Credentials",
        description="Test or demo credentials detected. These should not be present in production code.",
        cwe_id="CWE-798",
        remediation="Remove test credentials from production configurations.",
        confidence=0.85,
    ),
    CredentialPattern(
        name="basic_auth_in_url",
        pattern=r"""(?:https?://)[^:]+:[^@]+@""",
        finding_type=InfraFindingType.WEAK_CREDENTIAL_PATTERN,
        severity=SecuritySeverity.HIGH,
        title="Credentials in URL",
        description="Credentials embedded in URL detected. This exposes credentials in logs and browser history.",
        cwe_id="CWE-598",
        remediation="Remove credentials from URLs. Use proper authentication headers or environment variables.",
        confidence=0.9,
    ),
]


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

    # Patterns that indicate enum value definitions, not actual hardcoded credentials
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

                # Skip matches in comments or docstrings
                if is_in_comment_or_docstring(content, lines, line_number, match.start(), file_ext):
                    continue

                # Check for false positive enum values
                if self._is_enum_value(match.group(0)):
                    continue

                # Check if this is an example or placeholder in documentation
                context_start = max(0, match.start() - 200)
                context_end = min(len(content), match.end() + 100)
                context = content[context_start:context_end]

                # Extract the password/secret value from the match
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

                # Skip matches in comments or docstrings
                if is_in_comment_or_docstring(content, lines, line_number, password_match.start(), file_ext):
                    continue

                # Check if this appears to be an example
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
        # Extract the value part (after = or : sign)
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
