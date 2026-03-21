"""
Heimdall JWT Pattern Definitions

Pattern definitions and constant lists for JWT security detection.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Auth.models.auth_models import AuthFindingType
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class JWTPattern:
    """Defines a pattern for detecting JWT security issues."""

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


JWT_PATTERNS: List[JWTPattern] = [
    JWTPattern(
        name="jwt_none_algorithm",
        pattern=r"""jwt\.(?:encode|decode)\s*\([^)]*algorithm\s*=\s*['"](?:none|None|NONE)['"]""",
        finding_type=AuthFindingType.JWT_NONE_ALGORITHM,
        severity=SecuritySeverity.CRITICAL,
        title="JWT None Algorithm Used",
        description="JWT is configured with 'none' algorithm which provides no signature verification.",
        cwe_id="CWE-347",
        remediation="Use a secure algorithm like RS256 or ES256. Never use 'none' algorithm.",
        confidence=0.95,
    ),
    JWTPattern(
        name="jwt_hs256_weak",
        pattern=r"""jwt\.encode\s*\([^)]*algorithm\s*=\s*['"]HS256['"]""",
        finding_type=AuthFindingType.WEAK_JWT_ALGORITHM,
        severity=SecuritySeverity.MEDIUM,
        title="JWT Uses HS256 Algorithm",
        description="JWT uses HS256 (symmetric) algorithm. Consider asymmetric algorithms for better security.",
        cwe_id="CWE-327",
        remediation="Use asymmetric algorithms like RS256, ES256, or PS256 for production systems.",
        confidence=0.6,
    ),
    JWTPattern(
        name="jwt_decode_no_verify",
        pattern=r"""jwt\.decode\s*\([^)]*(?:verify\s*=\s*False|options\s*=\s*\{[^}]*verify[^}]*False)""",
        finding_type=AuthFindingType.WEAK_JWT_ALGORITHM,
        severity=SecuritySeverity.CRITICAL,
        title="JWT Signature Verification Disabled",
        description="JWT decode is called with signature verification disabled.",
        cwe_id="CWE-347",
        remediation="Always verify JWT signatures. Never disable verification in production.",
        confidence=0.9,
    ),
    JWTPattern(
        name="jwt_secret_in_code",
        pattern=r"""(?:jwt_secret|JWT_SECRET|secret_key|SECRET_KEY)\s*=\s*['"][^'"]{8,}['"]""",
        finding_type=AuthFindingType.HARDCODED_CREDENTIALS,
        severity=SecuritySeverity.HIGH,
        title="JWT Secret Hardcoded",
        description="JWT secret key appears to be hardcoded in source code.",
        cwe_id="CWE-798",
        remediation="Store JWT secrets in environment variables or a secure vault.",
        confidence=0.75,
    ),
    JWTPattern(
        name="jwt_weak_secret",
        pattern=r"""jwt\.encode\s*\([^)]*,\s*['"](?:secret|password|key|test|dev|123|abc)['"]""",
        finding_type=AuthFindingType.HARDCODED_CREDENTIALS,
        severity=SecuritySeverity.CRITICAL,
        title="JWT Uses Weak Secret",
        description="JWT is signed with a weak or common secret key.",
        cwe_id="CWE-521",
        remediation="Use a strong, randomly generated secret key of at least 256 bits.",
        confidence=0.85,
    ),
]

ENUM_VALUE_PATTERNS: List[str] = [
    r"^secret$", r"^secret[_-]?key$", r"^jwt[_-]?secret$",
    r"^api[_-]?key$", r"^access[_-]?key$", r"^access[_-]?token$",
    r"^auth[_-]?token$", r"^oauth[_-]?token$", r"^private[_-]?key$",
    r"^client[_-]?secret$", r"^auth[_-]?secret$",
]

INTENTIONAL_NO_VERIFY_PATTERNS: List[str] = [
    r"decode_without_verification",
    r"decode_unverified",
    r"inspect_token",
    r"extract_claims",
    r"get_unverified_header",
    r"peek_token",
    r"except\s+.*Error",
    r"WARNING",
    r"debug",
    r"logging",
]
