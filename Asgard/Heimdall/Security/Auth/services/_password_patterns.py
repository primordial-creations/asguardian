"""
Heimdall Password Pattern Definitions

Pattern definitions for detecting password security issues.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Auth.models.auth_models import AuthFindingType
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class PasswordPattern:
    """Defines a pattern for detecting password security issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        finding_type: AuthFindingType,
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


PASSWORD_PATTERNS: List[PasswordPattern] = [
    PasswordPattern(
        name="plaintext_password_compare",
        pattern=r"""if\s+.*password\s*[=!]=\s*(?:user|account|record)\.password""",
        finding_type=AuthFindingType.PLAINTEXT_PASSWORD,
        severity=SecuritySeverity.CRITICAL,
        title="Plaintext Password Comparison",
        description="Password appears to be compared directly without hashing.",
        cwe_id="CWE-256",
        remediation="Use bcrypt, argon2, or scrypt to hash and verify passwords.",
        confidence=0.85,
    ),
    PasswordPattern(
        name="password_in_log",
        pattern=r"""(?:log|logger|print|console\.log)\s*\([^)]*password""",
        finding_type=AuthFindingType.PASSWORD_IN_LOG,
        severity=SecuritySeverity.CRITICAL,
        title="Password Logged",
        description="Password is being written to logs.",
        cwe_id="CWE-532",
        remediation="Never log passwords or sensitive credentials. Remove password from log statements.",
        confidence=0.9,
    ),
    PasswordPattern(
        name="password_in_error",
        pattern=r"""(?:raise|throw)\s+.*password""",
        finding_type=AuthFindingType.PASSWORD_IN_LOG,
        severity=SecuritySeverity.HIGH,
        title="Password in Error Message",
        description="Password may be included in error messages.",
        cwe_id="CWE-209",
        remediation="Remove sensitive data from error messages.",
        confidence=0.7,
    ),
    PasswordPattern(
        name="md5_password_hash",
        pattern=r"""(?:hashlib\.md5|md5\s*\()\s*\([^)]*password""",
        finding_type=AuthFindingType.WEAK_PASSWORD_HASH,
        severity=SecuritySeverity.CRITICAL,
        title="MD5 Used for Password Hashing",
        description="MD5 is cryptographically broken and should not be used for passwords.",
        cwe_id="CWE-328",
        remediation="Use bcrypt, argon2, or PBKDF2 with a high iteration count.",
        confidence=0.95,
    ),
    PasswordPattern(
        name="sha1_password_hash",
        pattern=r"""(?:hashlib\.sha1|sha1\s*\()\s*\([^)]*password""",
        finding_type=AuthFindingType.WEAK_PASSWORD_HASH,
        severity=SecuritySeverity.HIGH,
        title="SHA1 Used for Password Hashing",
        description="SHA1 is deprecated for security use and should not be used for passwords.",
        cwe_id="CWE-328",
        remediation="Use bcrypt, argon2, or PBKDF2 with a high iteration count.",
        confidence=0.9,
    ),
    PasswordPattern(
        name="sha256_no_salt",
        pattern=r"""hashlib\.sha256\s*\(\s*password""",
        finding_type=AuthFindingType.WEAK_PASSWORD_HASH,
        severity=SecuritySeverity.HIGH,
        title="SHA256 Password Without Salt",
        description="Password hashed with SHA256 without visible salt, vulnerable to rainbow tables.",
        cwe_id="CWE-916",
        remediation="Use bcrypt or argon2 which include automatic salting.",
        confidence=0.75,
    ),
    PasswordPattern(
        name="hardcoded_password",
        pattern=r"""(?:password|passwd|pwd)\s*=\s*['"][^'"]{4,}['"]""",
        finding_type=AuthFindingType.HARDCODED_CREDENTIALS,
        severity=SecuritySeverity.HIGH,
        title="Hardcoded Password",
        description="Password appears to be hardcoded in source code.",
        cwe_id="CWE-798",
        remediation="Store passwords in environment variables or a secure vault.",
        confidence=0.7,
    ),
    PasswordPattern(
        name="password_in_url",
        pattern=r"""(?:url|uri|endpoint)\s*=.*password\s*=""",
        finding_type=AuthFindingType.HARDCODED_CREDENTIALS,
        severity=SecuritySeverity.HIGH,
        title="Password in URL",
        description="Password appears to be included in a URL.",
        cwe_id="CWE-598",
        remediation="Never include passwords in URLs. Use POST requests with encrypted body.",
        confidence=0.8,
    ),
    PasswordPattern(
        name="password_storage_plain",
        pattern=r"""(?:user|account)\.password\s*=\s*(?:request|form|data)\.(?:password|pwd)""",
        finding_type=AuthFindingType.PLAINTEXT_PASSWORD,
        severity=SecuritySeverity.CRITICAL,
        title="Password Stored Without Hashing",
        description="Password is being stored directly from user input without hashing.",
        cwe_id="CWE-256",
        remediation="Hash passwords using bcrypt or argon2 before storing.",
        confidence=0.85,
    ),
]

ENUM_VALUE_PATTERNS: List[str] = [
    r"^password$", r"^passwd$", r"^secret$", r"^secret[_-]?key$",
    r"^api[_-]?key$", r"^access[_-]?key$", r"^access[_-]?token$",
    r"^auth[_-]?token$", r"^oauth[_-]?token$", r"^private[_-]?key$",
    r"^client[_-]?secret$", r"^auth[_-]?secret$", r"^jwt[_-]?secret$",
    r"^not[_-]?a[_-]?password$", r"^rabbitmq[_-]?password$",
]
