"""
Heimdall Header Pattern Definitions

Pattern definitions for detecting security header issues.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Headers.models.header_models import HeaderFindingType
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class HeaderPattern:
    """Defines a pattern for detecting security header issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        finding_type: HeaderFindingType,
        severity: SecuritySeverity,
        title: str,
        description: str,
        header_name: str,
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
        self.header_name = header_name
        self.cwe_id = cwe_id
        self.remediation = remediation
        self.confidence = confidence


HEADER_PATTERNS: List[HeaderPattern] = [
    HeaderPattern(
        name="missing_x_frame_options",
        pattern=r"""(?:set_header|setHeader|add_header|addHeader|headers\[)[^;]*X-Frame-Options[^;]*(?:ALLOW-FROM|ALLOWALL)""",
        finding_type=HeaderFindingType.WEAK_X_FRAME_OPTIONS,
        severity=SecuritySeverity.MEDIUM,
        title="Weak X-Frame-Options Value",
        description="X-Frame-Options is set to a weak value that may allow clickjacking.",
        header_name="X-Frame-Options",
        cwe_id="CWE-1021",
        remediation="Set X-Frame-Options to 'DENY' or 'SAMEORIGIN' to prevent clickjacking attacks.",
        confidence=0.85,
    ),
    HeaderPattern(
        name="hsts_short_max_age",
        pattern=r"""Strict-Transport-Security[^;]*max-age\s*=\s*(\d{1,5})(?!\d)""",
        finding_type=HeaderFindingType.HSTS_SHORT_MAX_AGE,
        severity=SecuritySeverity.MEDIUM,
        title="HSTS Max-Age Too Short",
        description="Strict-Transport-Security max-age is set to less than one year.",
        header_name="Strict-Transport-Security",
        cwe_id="CWE-319",
        remediation="Set HSTS max-age to at least 31536000 (1 year) for adequate protection.",
        confidence=0.8,
    ),
    HeaderPattern(
        name="hsts_missing_subdomains",
        pattern=r"""Strict-Transport-Security[^;]*max-age\s*=\s*\d+(?![^;]*includeSubDomains)""",
        finding_type=HeaderFindingType.HSTS_MISSING_SUBDOMAINS,
        severity=SecuritySeverity.LOW,
        title="HSTS Missing includeSubDomains",
        description="Strict-Transport-Security is configured without includeSubDomains directive.",
        header_name="Strict-Transport-Security",
        cwe_id="CWE-319",
        remediation="Add 'includeSubDomains' to the HSTS header to protect all subdomains.",
        confidence=0.7,
    ),
    HeaderPattern(
        name="insecure_cookie_set",
        pattern=r"""(?:set[_-]?cookie|Set-Cookie)[^;]*(?!.*(?:Secure|secure)).*(?:;|$)""",
        finding_type=HeaderFindingType.COOKIE_MISSING_SECURE,
        severity=SecuritySeverity.HIGH,
        title="Cookie Missing Secure Flag",
        description="Cookie is set without the Secure flag, allowing transmission over HTTP.",
        header_name="Set-Cookie",
        cwe_id="CWE-614",
        remediation="Add the 'Secure' flag to all cookies to ensure they are only sent over HTTPS.",
        confidence=0.75,
    ),
    HeaderPattern(
        name="cookie_missing_httponly",
        pattern=r"""(?:set[_-]?cookie|Set-Cookie)[^;]*=\s*[^;]+(?!.*(?:HttpOnly|httponly))""",
        finding_type=HeaderFindingType.COOKIE_MISSING_HTTPONLY,
        severity=SecuritySeverity.MEDIUM,
        title="Cookie Missing HttpOnly Flag",
        description="Cookie is set without the HttpOnly flag, making it accessible to JavaScript.",
        header_name="Set-Cookie",
        cwe_id="CWE-1004",
        remediation="Add the 'HttpOnly' flag to cookies that don't need JavaScript access.",
        confidence=0.7,
    ),
    HeaderPattern(
        name="cookie_missing_samesite",
        pattern=r"""(?:set[_-]?cookie|Set-Cookie)[^;]*=\s*[^;]+(?!.*(?:SameSite|samesite))""",
        finding_type=HeaderFindingType.COOKIE_MISSING_SAMESITE,
        severity=SecuritySeverity.MEDIUM,
        title="Cookie Missing SameSite Attribute",
        description="Cookie is set without SameSite attribute, potentially vulnerable to CSRF.",
        header_name="Set-Cookie",
        cwe_id="CWE-1275",
        remediation="Add 'SameSite=Strict' or 'SameSite=Lax' to prevent CSRF attacks.",
        confidence=0.7,
    ),
]
