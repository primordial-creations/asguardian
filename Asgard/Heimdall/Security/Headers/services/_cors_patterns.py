"""
Heimdall CORS Pattern Definitions

Pattern definitions for detecting CORS security issues.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Headers.models.header_models import HeaderFindingType
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class CORSPattern:
    """Defines a pattern for detecting CORS security issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        finding_type: HeaderFindingType,
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


CORS_PATTERNS: List[CORSPattern] = [
    CORSPattern(
        name="cors_wildcard_origin",
        pattern=r"""Access-Control-Allow-Origin['":\s]+\*""",
        finding_type=HeaderFindingType.CORS_WILDCARD_ORIGIN,
        severity=SecuritySeverity.HIGH,
        title="CORS Allows All Origins",
        description="Access-Control-Allow-Origin is set to * which allows any website to make cross-origin requests.",
        cwe_id="CWE-942",
        remediation="Specify allowed origins explicitly instead of using wildcard (*). Validate the Origin header against a whitelist.",
        confidence=0.9,
    ),
    CORSPattern(
        name="cors_allow_origin_star_code",
        pattern=r"""(?:allow_origin|allowOrigin|origin)\s*[:=]\s*['"]\*['"]""",
        finding_type=HeaderFindingType.CORS_WILDCARD_ORIGIN,
        severity=SecuritySeverity.HIGH,
        title="CORS Configuration Allows All Origins",
        description="CORS is configured to allow all origins (*) which permits any website to make cross-origin requests.",
        cwe_id="CWE-942",
        remediation="Configure CORS with a specific list of allowed origins.",
        confidence=0.85,
    ),
    CORSPattern(
        name="cors_credentials_with_wildcard",
        pattern=r"""(?:Access-Control-Allow-Origin['":\s]+\*[\s\S]{0,200}Access-Control-Allow-Credentials['":\s]+true|Access-Control-Allow-Credentials['":\s]+true[\s\S]{0,200}Access-Control-Allow-Origin['":\s]+\*)""",
        finding_type=HeaderFindingType.CORS_CREDENTIALS_WITH_WILDCARD,
        severity=SecuritySeverity.CRITICAL,
        title="CORS Credentials with Wildcard Origin",
        description="Access-Control-Allow-Credentials is enabled with wildcard origin. This is a severe security vulnerability.",
        cwe_id="CWE-346",
        remediation="Never use Access-Control-Allow-Credentials: true with Access-Control-Allow-Origin: *. Specify exact origins.",
        confidence=0.95,
    ),
    CORSPattern(
        name="cors_credentials_config",
        pattern=r"""(?:allow_credentials|allowCredentials|credentials)\s*[:=]\s*(?:true|True|1)""",
        finding_type=HeaderFindingType.PERMISSIVE_CORS,
        severity=SecuritySeverity.MEDIUM,
        title="CORS Credentials Enabled",
        description="CORS is configured to allow credentials. Ensure this is combined with specific origin validation.",
        cwe_id="CWE-346",
        remediation="When using credentials, ensure Access-Control-Allow-Origin is set to specific origins, not wildcard.",
        confidence=0.7,
    ),
    CORSPattern(
        name="cors_reflect_origin",
        pattern=r"""(?:origin|Origin)\s*=\s*(?:request|req)\.(?:headers|header)\.(?:get|origin)""",
        finding_type=HeaderFindingType.PERMISSIVE_CORS,
        severity=SecuritySeverity.HIGH,
        title="CORS Origin Reflection",
        description="Origin header is reflected back without validation, effectively allowing all origins.",
        cwe_id="CWE-942",
        remediation="Validate the Origin header against a whitelist before reflecting it in Access-Control-Allow-Origin.",
        confidence=0.8,
    ),
    CORSPattern(
        name="cors_allow_all_methods",
        pattern=r"""Access-Control-Allow-Methods['":\s]+\*""",
        finding_type=HeaderFindingType.PERMISSIVE_CORS,
        severity=SecuritySeverity.MEDIUM,
        title="CORS Allows All Methods",
        description="Access-Control-Allow-Methods is set to * which allows any HTTP method.",
        cwe_id="CWE-942",
        remediation="Specify only the HTTP methods that are actually needed for your API.",
        confidence=0.85,
    ),
    CORSPattern(
        name="cors_allow_all_headers",
        pattern=r"""Access-Control-Allow-Headers['":\s]+\*""",
        finding_type=HeaderFindingType.PERMISSIVE_CORS,
        severity=SecuritySeverity.LOW,
        title="CORS Allows All Headers",
        description="Access-Control-Allow-Headers is set to * which allows any request header.",
        cwe_id="CWE-942",
        remediation="Specify only the headers that are actually needed for your API.",
        confidence=0.75,
    ),
    CORSPattern(
        name="cors_flask_wildcard",
        pattern=r"""CORS\s*\([^)]*(?:origins?\s*=\s*['"]\*['"]|resources\s*=\s*[{][^}]*['"]\*['"])""",
        finding_type=HeaderFindingType.CORS_WILDCARD_ORIGIN,
        severity=SecuritySeverity.HIGH,
        title="Flask-CORS Wildcard Configuration",
        description="Flask-CORS is configured with wildcard origin, allowing any website to make requests.",
        cwe_id="CWE-942",
        remediation="Configure Flask-CORS with specific allowed origins instead of '*'.",
        confidence=0.9,
    ),
    CORSPattern(
        name="cors_express_wildcard",
        pattern=r"""cors\s*\(\s*\{[^}]*origin\s*:\s*(?:true|['"]\*['"])""",
        finding_type=HeaderFindingType.CORS_WILDCARD_ORIGIN,
        severity=SecuritySeverity.HIGH,
        title="Express CORS Wildcard Configuration",
        description="Express CORS middleware is configured to allow all origins.",
        cwe_id="CWE-942",
        remediation="Configure the origin option with specific allowed domains.",
        confidence=0.9,
    ),
]
