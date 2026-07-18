"""
Heimdall Security Headers Models

Pydantic models for security header analysis operations and results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class HeaderFindingType(str, Enum):
    """Types of security header findings."""
    MISSING_CSP = "missing_csp"
    MISSING_HSTS = "missing_hsts"
    MISSING_X_FRAME = "missing_x_frame"
    MISSING_X_CONTENT_TYPE = "missing_x_content_type"
    MISSING_REFERRER_POLICY = "missing_referrer_policy"
    MISSING_PERMISSIONS_POLICY = "missing_permissions_policy"
    WEAK_CSP = "weak_csp"
    CSP_UNSAFE_INLINE = "csp_unsafe_inline"
    CSP_UNSAFE_EVAL = "csp_unsafe_eval"
    CSP_WILDCARD_SOURCE = "csp_wildcard_source"
    CSP_MISSING_DIRECTIVE = "csp_missing_directive"
    PERMISSIVE_CORS = "permissive_cors"
    CORS_WILDCARD_ORIGIN = "cors_wildcard_origin"
    CORS_CREDENTIALS_WITH_WILDCARD = "cors_credentials_with_wildcard"
    CORS_MISSING_VARY = "cors_missing_vary"
    INSECURE_COOKIE_FLAGS = "insecure_cookie_flags"
    COOKIE_MISSING_SECURE = "cookie_missing_secure"
    COOKIE_MISSING_HTTPONLY = "cookie_missing_httponly"
    COOKIE_MISSING_SAMESITE = "cookie_missing_samesite"
    WEAK_X_FRAME_OPTIONS = "weak_x_frame_options"
    HSTS_SHORT_MAX_AGE = "hsts_short_max_age"
    HSTS_MISSING_SUBDOMAINS = "hsts_missing_subdomains"


class HeaderFinding(BaseModel):
    """A detected security header issue."""
    file_path: str = Field(..., description="Path to the file containing the issue")
    line_number: int = Field(..., description="Line number where the issue was found")
    column_start: int = Field(0, description="Column where the issue starts")
    column_end: int = Field(0, description="Column where the issue ends")
    finding_type: HeaderFindingType = Field(..., description="Type of header security issue")
    severity: SecuritySeverity = Field(..., description="Severity of the finding")
    title: str = Field(..., description="Short title describing the issue")
    description: str = Field(..., description="Detailed description of the header security issue")
    code_snippet: str = Field("", description="The problematic code snippet")
    header_name: Optional[str] = Field(None, description="Name of the security header")
    header_value: Optional[str] = Field(None, description="Current value of the header")
    cwe_id: Optional[str] = Field(None, description="CWE ID if applicable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    remediation: str = Field("", description="Suggested remediation steps")
    references: List[str] = Field(default_factory=list, description="Reference URLs")
    mechanism_id: str = Field("", description="Normalization-engine mechanism id (plan 06).")
    confidence_bucket: str = Field("probable", description="Qualitative confidence bucket (plan 06).")
    context_downgraded: bool = Field(
        False,
        description=(
            "Plan 07.9/06: True when this browser-only header finding was "
            "downgraded because the scan was told the surface is API-only "
            "(HeaderConfig.is_api) -- CSP/X-Frame-Options/cookie SameSite "
            "are browser-enforced and irrelevant to a pure JSON API."
        ),
    )

    class Config:
        use_enum_values = True


# Header findings that are browser-enforced and meaningless on a pure
# API surface (no HTML/JS ever rendered by a browser against this
# origin) -- the plan 06 context modifier for HeaderConfig.is_api.
BROWSER_ONLY_FINDING_TYPES = frozenset({
    HeaderFindingType.MISSING_CSP,
    HeaderFindingType.WEAK_CSP,
    HeaderFindingType.CSP_UNSAFE_INLINE,
    HeaderFindingType.CSP_UNSAFE_EVAL,
    HeaderFindingType.CSP_WILDCARD_SOURCE,
    HeaderFindingType.CSP_MISSING_DIRECTIVE,
    HeaderFindingType.MISSING_X_FRAME,
    HeaderFindingType.WEAK_X_FRAME_OPTIONS,
    HeaderFindingType.COOKIE_MISSING_SAMESITE,
    HeaderFindingType.MISSING_PERMISSIONS_POLICY,
})


class HeaderConfig(BaseModel):
    """Configuration for security header scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    is_api: bool = Field(
        False,
        description=(
            "Plan 07.9/06 context modifier: set True for a pure JSON/API "
            "surface with no browser-rendered HTML. Downgrades (does not "
            "suppress) browser-only header findings (CSP, X-Frame-Options, "
            "cookie SameSite, Permissions-Policy) since they have no "
            "effect outside a browser context."
        ),
    )
    check_csp: bool = Field(True, description="Check Content-Security-Policy")
    check_cors: bool = Field(True, description="Check CORS configuration")
    check_hsts: bool = Field(True, description="Check Strict-Transport-Security")
    check_frame_options: bool = Field(True, description="Check X-Frame-Options")
    check_content_type: bool = Field(True, description="Check X-Content-Type-Options")
    check_cookies: bool = Field(True, description="Check cookie security flags")
    min_severity: SecuritySeverity = Field(SecuritySeverity.LOW, description="Minimum severity to report")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            ".next",
            "coverage",
            "*.min.js",
            "*.min.css",
            # Exclude Heimdall's own security detection patterns
            "Heimdall/Security",
            "Heimdall\\Security",
            "Asgard/Heimdall",
            "Asgard\\Heimdall",
            # Exclude test files
            "*_Test",
            "*Test",
            "tests",
            "test_*",
            "Ankh_Test",
            "Asgard_Test",
            "Hercules",
            # Exclude tool prototypes
            "_tool_prototypes",
            # Exclude package lock files
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "ui_dump.xml",
        ],
        description="Patterns to exclude from scanning"
    )
    min_hsts_max_age: int = Field(
        31536000,
        description="Minimum acceptable HSTS max-age in seconds (default 1 year)"
    )
    required_csp_directives: List[str] = Field(
        default_factory=lambda: [
            "default-src",
            "script-src",
            "style-src",
            "img-src",
            "object-src",
        ],
        description="CSP directives that should be present"
    )
    unsafe_csp_values: List[str] = Field(
        default_factory=lambda: [
            "'unsafe-inline'",
            "'unsafe-eval'",
            "data:",
            "blob:",
        ],
        description="CSP values considered unsafe"
    )
    header_setting_patterns: List[str] = Field(
        default_factory=lambda: [
            "set_header",
            "setHeader",
            "add_header",
            "addHeader",
            "headers",
            "response.headers",
            "res.set",
            "res.header",
            "response.header",
        ],
        description="Patterns that indicate header setting in code"
    )

    class Config:
        use_enum_values = True


class HeaderReport(BaseModel):
    """Report from security header analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    total_issues: int = Field(0, description="Total header security issues found")
    critical_issues: int = Field(0, description="Critical severity issues")
    high_issues: int = Field(0, description="High severity issues")
    medium_issues: int = Field(0, description="Medium severity issues")
    low_issues: int = Field(0, description="Low severity issues")
    findings: List[HeaderFinding] = Field(default_factory=list, description="List of findings")
    csp_issues: int = Field(0, description="CSP-related issues found")
    cors_issues: int = Field(0, description="CORS-related issues found")
    cookie_issues: int = Field(0, description="Cookie-related issues found")
    missing_headers: int = Field(0, description="Missing security headers found")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    header_score: float = Field(100.0, ge=0.0, le=100.0, description="Header security score (0-100)")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: HeaderFinding) -> None:
        """Add a header security finding to the report."""
        self.total_issues += 1
        self.findings.append(finding)
        self._increment_severity_count(finding.severity)
        self._increment_type_count(finding.finding_type)
        self._calculate_header_score()

    def _increment_severity_count(self, severity: str) -> None:
        """Increment the count for a severity level."""
        if severity == SecuritySeverity.CRITICAL.value:
            self.critical_issues += 1
        elif severity == SecuritySeverity.HIGH.value:
            self.high_issues += 1
        elif severity == SecuritySeverity.MEDIUM.value:
            self.medium_issues += 1
        elif severity == SecuritySeverity.LOW.value:
            self.low_issues += 1

    def _increment_type_count(self, finding_type: str) -> None:
        """Increment the count for a finding type category."""
        csp_types = [
            HeaderFindingType.MISSING_CSP.value,
            HeaderFindingType.WEAK_CSP.value,
            HeaderFindingType.CSP_UNSAFE_INLINE.value,
            HeaderFindingType.CSP_UNSAFE_EVAL.value,
            HeaderFindingType.CSP_WILDCARD_SOURCE.value,
            HeaderFindingType.CSP_MISSING_DIRECTIVE.value,
        ]
        cors_types = [
            HeaderFindingType.PERMISSIVE_CORS.value,
            HeaderFindingType.CORS_WILDCARD_ORIGIN.value,
            HeaderFindingType.CORS_CREDENTIALS_WITH_WILDCARD.value,
            HeaderFindingType.CORS_MISSING_VARY.value,
        ]
        cookie_types = [
            HeaderFindingType.INSECURE_COOKIE_FLAGS.value,
            HeaderFindingType.COOKIE_MISSING_SECURE.value,
            HeaderFindingType.COOKIE_MISSING_HTTPONLY.value,
            HeaderFindingType.COOKIE_MISSING_SAMESITE.value,
        ]
        missing_types = [
            HeaderFindingType.MISSING_CSP.value,
            HeaderFindingType.MISSING_HSTS.value,
            HeaderFindingType.MISSING_X_FRAME.value,
            HeaderFindingType.MISSING_X_CONTENT_TYPE.value,
            HeaderFindingType.MISSING_REFERRER_POLICY.value,
            HeaderFindingType.MISSING_PERMISSIONS_POLICY.value,
        ]

        if finding_type in csp_types:
            self.csp_issues += 1
        if finding_type in cors_types:
            self.cors_issues += 1
        if finding_type in cookie_types:
            self.cookie_issues += 1
        if finding_type in missing_types:
            self.missing_headers += 1

    def _calculate_header_score(self) -> None:
        """Calculate the overall header security score."""
        score = 100.0
        score -= self.critical_issues * 25
        score -= self.high_issues * 10
        score -= self.medium_issues * 5
        score -= self.low_issues * 1
        self.header_score = max(0.0, score)

    @property
    def has_issues(self) -> bool:
        """Check if any header security issues were found."""
        return self.total_issues > 0

    @property
    def is_healthy(self) -> bool:
        """Check if the header security scan is healthy."""
        return self.critical_issues == 0 and self.high_issues == 0

    def get_findings_by_type(self) -> Dict[str, List[HeaderFinding]]:
        """Group findings by type."""
        result: Dict[str, List[HeaderFinding]] = {}
        for finding in self.findings:
            ftype = finding.finding_type
            if ftype not in result:
                result[ftype] = []
            result[ftype].append(finding)
        return result

    def get_findings_by_severity(self) -> Dict[str, List[HeaderFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[HeaderFinding]] = {
            SecuritySeverity.CRITICAL.value: [],
            SecuritySeverity.HIGH.value: [],
            SecuritySeverity.MEDIUM.value: [],
            SecuritySeverity.LOW.value: [],
            SecuritySeverity.INFO.value: [],
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result

    def get_findings_by_header(self) -> Dict[str, List[HeaderFinding]]:
        """Group findings by header name."""
        result: Dict[str, List[HeaderFinding]] = {}
        for finding in self.findings:
            header = finding.header_name or "unknown"
            if header not in result:
                result[header] = []
            result[header].append(finding)
        return result
