"""
Heimdall Security Auth Models

Pydantic models for authentication analysis operations and results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class AuthFindingType(str, Enum):
    """Types of authentication findings."""
    WEAK_JWT_ALGORITHM = "weak_jwt_algorithm"
    MISSING_TOKEN_EXPIRATION = "missing_token_expiration"
    JWT_NONE_ALGORITHM = "jwt_none_algorithm"
    INSECURE_SESSION = "insecure_session"
    SESSION_FIXATION = "session_fixation"
    PLAINTEXT_PASSWORD = "plaintext_password"
    PASSWORD_IN_LOG = "password_in_log"
    WEAK_PASSWORD_HASH = "weak_password_hash"
    HARDCODED_CREDENTIALS = "hardcoded_credentials"
    INSECURE_REMEMBER_ME = "insecure_remember_me"
    MISSING_CSRF_PROTECTION = "missing_csrf_protection"
    INSECURE_COOKIE = "insecure_cookie"
    OAUTH_INSECURE_REDIRECT = "oauth_insecure_redirect"
    MISSING_STATE_PARAM = "missing_state_param"
    TIMING_UNSAFE_COMPARE = "timing_unsafe_compare"


class AuthFinding(BaseModel):
    """A detected authentication issue."""
    file_path: str = Field(..., description="Path to the file containing the issue")
    line_number: int = Field(..., description="Line number where the issue was found")
    column_start: int = Field(0, description="Column where the issue starts")
    column_end: int = Field(0, description="Column where the issue ends")
    finding_type: AuthFindingType = Field(..., description="Type of authentication issue")
    severity: SecuritySeverity = Field(..., description="Severity of the finding")
    title: str = Field(..., description="Short title describing the issue")
    description: str = Field(..., description="Detailed description of the authentication issue")
    code_snippet: str = Field("", description="The problematic code snippet")
    cwe_id: Optional[str] = Field(None, description="CWE ID if applicable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    remediation: str = Field("", description="Suggested remediation steps")
    references: List[str] = Field(default_factory=list, description="Reference URLs")
    # Plan 07.6 / plan-06 normalization: stable mechanism id for the
    # normalization engine. Optional/best-effort -- populated by newer
    # checks (timing-unsafe compare); pre-existing checks keep passing
    # their own severity directly and are not required to set this.
    mechanism_id: Optional[str] = Field(None, description="Plan-06 normalization mechanism id")

    class Config:
        use_enum_values = True


class AuthConfig(BaseModel):
    """Configuration for authentication scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    check_jwt: bool = Field(True, description="Check JWT implementation")
    check_session: bool = Field(True, description="Check session management")
    check_password: bool = Field(True, description="Check password handling")
    check_oauth: bool = Field(True, description="Check OAuth implementation")
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
    safe_jwt_algorithms: List[str] = Field(
        default_factory=lambda: [
            "RS256", "RS384", "RS512",
            "ES256", "ES384", "ES512",
            "PS256", "PS384", "PS512",
        ],
        description="Algorithms considered safe for JWT"
    )
    weak_jwt_algorithms: List[str] = Field(
        default_factory=lambda: [
            "HS256", "HS384", "HS512",
            "none", "None", "NONE",
        ],
        description="Algorithms considered weak for JWT"
    )
    weak_hash_algorithms: List[str] = Field(
        default_factory=lambda: [
            "md5", "sha1", "sha-1",
        ],
        description="Hash algorithms considered weak for passwords"
    )

    class Config:
        use_enum_values = True


class AuthReport(BaseModel):
    """Report from authentication analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    total_issues: int = Field(0, description="Total authentication issues found")
    critical_issues: int = Field(0, description="Critical severity issues")
    high_issues: int = Field(0, description="High severity issues")
    medium_issues: int = Field(0, description="Medium severity issues")
    low_issues: int = Field(0, description="Low severity issues")
    findings: List[AuthFinding] = Field(default_factory=list, description="List of findings")
    jwt_issues: int = Field(0, description="JWT-related issues found")
    session_issues: int = Field(0, description="Session-related issues found")
    password_issues: int = Field(0, description="Password-related issues found")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    auth_score: float = Field(100.0, ge=0.0, le=100.0, description="Authentication security score (0-100)")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: AuthFinding) -> None:
        """Add an authentication finding to the report."""
        self.total_issues += 1
        self.findings.append(finding)
        self._increment_severity_count(finding.severity)
        self._increment_type_count(finding.finding_type)
        self._calculate_auth_score()

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
        jwt_types = [
            AuthFindingType.WEAK_JWT_ALGORITHM.value,
            AuthFindingType.MISSING_TOKEN_EXPIRATION.value,
            AuthFindingType.JWT_NONE_ALGORITHM.value,
        ]
        session_types = [
            AuthFindingType.INSECURE_SESSION.value,
            AuthFindingType.SESSION_FIXATION.value,
            AuthFindingType.INSECURE_COOKIE.value,
            AuthFindingType.INSECURE_REMEMBER_ME.value,
        ]
        password_types = [
            AuthFindingType.PLAINTEXT_PASSWORD.value,
            AuthFindingType.PASSWORD_IN_LOG.value,
            AuthFindingType.WEAK_PASSWORD_HASH.value,
            AuthFindingType.HARDCODED_CREDENTIALS.value,
        ]

        if finding_type in jwt_types:
            self.jwt_issues += 1
        elif finding_type in session_types:
            self.session_issues += 1
        elif finding_type in password_types:
            self.password_issues += 1

    def _calculate_auth_score(self) -> None:
        """Calculate the overall authentication security score."""
        score = 100.0
        score -= self.critical_issues * 25
        score -= self.high_issues * 10
        score -= self.medium_issues * 5
        score -= self.low_issues * 1
        self.auth_score = max(0.0, score)

    @property
    def has_issues(self) -> bool:
        """Check if any authentication issues were found."""
        return self.total_issues > 0

    @property
    def is_healthy(self) -> bool:
        """Check if the authentication scan is healthy."""
        return self.critical_issues == 0 and self.high_issues == 0

    def get_findings_by_type(self) -> Dict[str, List[AuthFinding]]:
        """Group findings by type."""
        result: Dict[str, List[AuthFinding]] = {}
        for finding in self.findings:
            ftype = finding.finding_type
            if ftype not in result:
                result[ftype] = []
            result[ftype].append(finding)
        return result

    def get_findings_by_severity(self) -> Dict[str, List[AuthFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[AuthFinding]] = {
            SecuritySeverity.CRITICAL.value: [],
            SecuritySeverity.HIGH.value: [],
            SecuritySeverity.MEDIUM.value: [],
            SecuritySeverity.LOW.value: [],
            SecuritySeverity.INFO.value: [],
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result
