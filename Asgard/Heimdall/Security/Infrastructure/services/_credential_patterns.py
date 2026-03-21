"""
Heimdall Credential Pattern Definitions

Pattern definitions for detecting credential security issues.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Infrastructure.models.infra_models import InfraFindingType
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


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
