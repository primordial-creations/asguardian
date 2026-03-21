"""
Heimdall Secret Detection Patterns

Pattern definitions for detecting hardcoded secrets in source code.
"""

import re
from typing import List, Pattern

from Asgard.Heimdall.Security.models.security_models import (
    SecretType,
    SecuritySeverity,
)


class SecretPattern:
    """Defines a pattern for detecting a specific type of secret."""

    def __init__(
        self,
        name: str,
        pattern: str,
        secret_type: SecretType,
        severity: SecuritySeverity,
        description: str = "",
        min_entropy: float = 0.0,
        remediation: str = "",
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.secret_type = secret_type
        self.severity = severity
        self.description = description
        self.min_entropy = min_entropy
        self.remediation = remediation


DEFAULT_SECRET_PATTERNS: List[SecretPattern] = [
    SecretPattern(
        name="aws_access_key",
        pattern=r"(?:AKIA|ABIA|ACCA)[0-9A-Z]{16}",
        secret_type=SecretType.AWS_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        description="AWS Access Key ID",
        remediation="Move AWS credentials to environment variables or AWS credentials file. Use IAM roles when possible.",
    ),
    SecretPattern(
        name="aws_secret_key",
        pattern=r"(?:aws_secret_access_key|aws_secret_key|secret_access_key)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
        secret_type=SecretType.AWS_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        description="AWS Secret Access Key",
        min_entropy=4.0,
        remediation="Move AWS credentials to environment variables or AWS credentials file. Use IAM roles when possible.",
    ),
    SecretPattern(
        name="azure_storage_key",
        pattern=r"(?:DefaultEndpointsProtocol=https;AccountName=)[^\s;]+;AccountKey=[A-Za-z0-9+/=]{88}",
        secret_type=SecretType.AZURE_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        description="Azure Storage Account Key",
        remediation="Use Azure Key Vault or managed identities for Azure credentials.",
    ),
    SecretPattern(
        name="gcp_service_account",
        pattern=r'"type"\s*:\s*"service_account".*"private_key"\s*:\s*"-----BEGIN',
        secret_type=SecretType.GCP_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        description="GCP Service Account Key",
        remediation="Use GCP Secret Manager or workload identity federation.",
    ),
    SecretPattern(
        name="generic_api_key",
        pattern=r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{20,64})['\"]?",
        secret_type=SecretType.API_KEY,
        severity=SecuritySeverity.HIGH,
        description="Generic API Key",
        min_entropy=3.5,
        remediation="Store API keys in environment variables or a secrets manager.",
    ),
    SecretPattern(
        name="generic_secret",
        pattern=r"(?:secret|secret[_-]?key|client[_-]?secret)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,64})['\"]?",
        secret_type=SecretType.SECRET_KEY,
        severity=SecuritySeverity.HIGH,
        description="Generic Secret Key",
        min_entropy=3.5,
        remediation="Store secrets in environment variables or a secrets manager.",
    ),
    SecretPattern(
        name="password_assignment",
        pattern=r"(?:password|passwd|pwd)\s*[=:]\s*['\"]([^'\"]{8,})['\"]",
        secret_type=SecretType.PASSWORD,
        severity=SecuritySeverity.HIGH,
        description="Hardcoded Password",
        min_entropy=2.0,
        remediation="Never hardcode passwords. Use environment variables or a secrets manager.",
    ),
    SecretPattern(
        name="private_key_header",
        pattern=r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
        secret_type=SecretType.PRIVATE_KEY,
        severity=SecuritySeverity.CRITICAL,
        description="Private Key",
        remediation="Store private keys in secure key management systems. Never commit to version control.",
    ),
    SecretPattern(
        name="jwt_token",
        pattern=r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        secret_type=SecretType.JWT_TOKEN,
        severity=SecuritySeverity.HIGH,
        description="JWT Token",
        remediation="JWT tokens should not be hardcoded. Use proper token management.",
    ),
    SecretPattern(
        name="github_token",
        pattern=r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}",
        secret_type=SecretType.ACCESS_TOKEN,
        severity=SecuritySeverity.CRITICAL,
        description="GitHub Token",
        remediation="Use GitHub Actions secrets or environment variables for tokens.",
    ),
    SecretPattern(
        name="slack_token",
        pattern=r"xox[baprs]-[A-Za-z0-9-]{10,}",
        secret_type=SecretType.ACCESS_TOKEN,
        severity=SecuritySeverity.HIGH,
        description="Slack Token",
        remediation="Store Slack tokens in environment variables or secrets manager.",
    ),
    SecretPattern(
        name="stripe_key",
        pattern=r"(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{24,}",
        secret_type=SecretType.API_KEY,
        severity=SecuritySeverity.CRITICAL,
        description="Stripe API Key",
        remediation="Use environment variables for Stripe keys. Never expose live keys.",
    ),
    SecretPattern(
        name="sendgrid_key",
        pattern=r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}",
        secret_type=SecretType.API_KEY,
        severity=SecuritySeverity.HIGH,
        description="SendGrid API Key",
        remediation="Store SendGrid keys in environment variables.",
    ),
    SecretPattern(
        name="twilio_key",
        pattern=r"SK[a-f0-9]{32}",
        secret_type=SecretType.API_KEY,
        severity=SecuritySeverity.HIGH,
        description="Twilio API Key",
        remediation="Store Twilio keys in environment variables.",
    ),
    SecretPattern(
        name="database_url",
        pattern=r"(?:postgres|mysql|mongodb|redis|amqp)(?:ql)?://[^\s'\"]+:[^\s'\"]+@[^\s'\"]+",
        secret_type=SecretType.DATABASE_URL,
        severity=SecuritySeverity.CRITICAL,
        description="Database Connection String with Credentials",
        remediation="Use environment variables for database connection strings.",
    ),
    SecretPattern(
        name="ssh_private_key",
        pattern=r"-----BEGIN OPENSSH PRIVATE KEY-----",
        secret_type=SecretType.SSH_KEY,
        severity=SecuritySeverity.CRITICAL,
        description="SSH Private Key",
        remediation="Never commit SSH keys. Use SSH agent or key management systems.",
    ),
    SecretPattern(
        name="oauth_token",
        pattern=r"(?:oauth[_-]?token|access[_-]?token|bearer[_-]?token)\s*[=:]\s*['\"]?([A-Za-z0-9_\-\.]{20,})['\"]?",
        secret_type=SecretType.OAUTH_TOKEN,
        severity=SecuritySeverity.HIGH,
        description="OAuth/Bearer Token",
        min_entropy=3.0,
        remediation="Store OAuth tokens securely. Use proper token refresh mechanisms.",
    ),
    SecretPattern(
        name="heroku_api_key",
        pattern=r"(?:heroku[_-]?api[_-]?key)\s*[=:]\s*['\"]?([a-f0-9-]{36})['\"]?",
        secret_type=SecretType.API_KEY,
        severity=SecuritySeverity.HIGH,
        description="Heroku API Key",
        remediation="Use environment variables for Heroku API keys.",
    ),
    SecretPattern(
        name="mailchimp_key",
        pattern=r"[a-f0-9]{32}-us[0-9]{1,2}",
        secret_type=SecretType.API_KEY,
        severity=SecuritySeverity.MEDIUM,
        description="Mailchimp API Key",
        remediation="Store Mailchimp keys in environment variables.",
    ),
    SecretPattern(
        name="base64_encoded_secret",
        pattern=r"(?:basic|bearer)\s+[A-Za-z0-9+/]{40,}={0,2}",
        secret_type=SecretType.GENERIC_SECRET,
        severity=SecuritySeverity.MEDIUM,
        description="Base64 Encoded Authentication",
        min_entropy=4.0,
        remediation="Avoid hardcoding authentication headers.",
    ),
]

FALSE_POSITIVE_PATTERNS: List[Pattern] = [
    re.compile(r"example|sample|test|dummy|fake|placeholder|your[_-]?key", re.IGNORECASE),
    re.compile(r"xxx+|000+|111+|aaa+", re.IGNORECASE),
    re.compile(r"<[^>]+>"),
    re.compile(r"\$\{[^}]+\}"),
    re.compile(r"%\([^)]+\)s"),
    re.compile(r"process\.env\.[A-Z_]+"),
    re.compile(r"os\.environ\["),
    re.compile(r"getenv\("),
    re.compile(r"\{self\.\w+\}"),
    re.compile(r"\{[a-z_]+\}"),
    re.compile(r"^password$", re.IGNORECASE),
    re.compile(r"^passwd$", re.IGNORECASE),
    re.compile(r"^secret$", re.IGNORECASE),
    re.compile(r"^secret[_-]?key$", re.IGNORECASE),
    re.compile(r"^api[_-]?key$", re.IGNORECASE),
    re.compile(r"^access[_-]?key$", re.IGNORECASE),
    re.compile(r"^access[_-]?token$", re.IGNORECASE),
    re.compile(r"^auth[_-]?token$", re.IGNORECASE),
    re.compile(r"^oauth[_-]?token$", re.IGNORECASE),
    re.compile(r"^private[_-]?key$", re.IGNORECASE),
    re.compile(r"^client[_-]?secret$", re.IGNORECASE),
    re.compile(r"^auth[_-]?secret$", re.IGNORECASE),
    re.compile(r"^jwt[_-]?secret$", re.IGNORECASE),
    re.compile(r"^database[_-]?url$", re.IGNORECASE),
    re.compile(r"^connection[_-]?string$", re.IGNORECASE),
    re.compile(r"^rabbitmq[_-]?password$", re.IGNORECASE),
    re.compile(r"^not[_-]?a[_-]?password$", re.IGNORECASE),
]
