"""
Heimdall Security TLS Models

Pydantic models for TLS/SSL security analysis operations and results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class TLSFindingType(str, Enum):
    """Types of TLS/SSL findings."""
    DEPRECATED_TLS_VERSION = "deprecated_tls_version"
    WEAK_CIPHER = "weak_cipher"
    DISABLED_VERIFICATION = "disabled_verification"
    SELF_SIGNED_ALLOWED = "self_signed_allowed"
    WEAK_DH_PARAMS = "weak_dh_params"
    DISABLED_HOSTNAME_CHECK = "disabled_hostname_check"
    INSECURE_SSL_CONTEXT = "insecure_ssl_context"
    CERT_NONE = "cert_none"
    NO_CERT_VALIDATION = "no_cert_validation"
    HARDCODED_CERTIFICATE = "hardcoded_certificate"
    EXPIRED_CERTIFICATE = "expired_certificate"
    INSECURE_PROTOCOL = "insecure_protocol"


class TLSFinding(BaseModel):
    """A detected TLS/SSL security issue."""
    file_path: str = Field(..., description="Path to the file containing the issue")
    line_number: int = Field(..., description="Line number where the issue was found")
    column_start: int = Field(0, description="Column where the issue starts")
    column_end: int = Field(0, description="Column where the issue ends")
    finding_type: TLSFindingType = Field(..., description="Type of TLS/SSL issue")
    severity: SecuritySeverity = Field(..., description="Severity of the finding")
    title: str = Field(..., description="Short title describing the issue")
    description: str = Field(..., description="Detailed description of the TLS/SSL issue")
    code_snippet: str = Field("", description="The problematic code snippet")
    protocol_version: Optional[str] = Field(None, description="TLS/SSL protocol version if applicable")
    cipher_suite: Optional[str] = Field(None, description="Cipher suite if applicable")
    cwe_id: Optional[str] = Field(None, description="CWE ID if applicable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    remediation: str = Field("", description="Suggested remediation steps")
    references: List[str] = Field(default_factory=list, description="Reference URLs")
    mechanism_id: str = Field("", description="Normalization-engine mechanism id (plan 06).")
    confidence_bucket: str = Field("probable", description="Qualitative confidence bucket (plan 06).")
    is_hotspot: bool = Field(
        False,
        description=(
            "Plan 07.9: code-level TLS/verify signals (e.g. Python "
            "requests verify=False) are demoted to a hotspot rather than "
            "a confirmed finding -- apps legitimately terminate TLS at a "
            "proxy and use plain HTTP or verify=False internally, so "
            "config-file evidence outranks code-level guesses."
        ),
    )
    source: str = Field(
        "code",
        description="'code' (Python/JS static pattern) or 'config' (nginx/HAProxy/Terraform, max-precision).",
    )

    class Config:
        use_enum_values = True


class TLSConfig(BaseModel):
    """Configuration for TLS/SSL scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    check_protocols: bool = Field(True, description="Check for deprecated TLS/SSL protocols")
    check_ciphers: bool = Field(True, description="Check for weak cipher suites")
    check_certificates: bool = Field(True, description="Check certificate validation issues")
    check_verification: bool = Field(True, description="Check for disabled verification")
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
    deprecated_protocols: List[str] = Field(
        default_factory=lambda: [
            "SSLv2",
            "SSLv3",
            "TLSv1",
            "TLSv1.0",
            "TLSv1.1",
            "TLS_1_0",
            "TLS_1_1",
            "PROTOCOL_SSLv2",
            "PROTOCOL_SSLv3",
            "PROTOCOL_TLSv1",
            "PROTOCOL_TLSv1_1",
        ],
        description="Deprecated TLS/SSL protocol versions"
    )
    weak_ciphers: List[str] = Field(
        default_factory=lambda: [
            "DES",
            "3DES",
            "RC4",
            "RC2",
            "MD5",
            "NULL",
            "EXPORT",
            "anon",
            "ADH",
            "AECDH",
            "DES-CBC",
            "DES-CBC3",
            "RC4-SHA",
            "RC4-MD5",
            "EXP-",
        ],
        description="Weak cipher suites"
    )
    safe_protocols: List[str] = Field(
        default_factory=lambda: [
            "TLSv1.2",
            "TLSv1.3",
            "TLS_1_2",
            "TLS_1_3",
            "PROTOCOL_TLSv1_2",
            "PROTOCOL_TLSv1_3",
            "PROTOCOL_TLS",
        ],
        description="Safe TLS protocol versions"
    )

    class Config:
        use_enum_values = True


class TLSReport(BaseModel):
    """Report from TLS/SSL security analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    total_issues: int = Field(0, description="Total TLS/SSL issues found")
    critical_issues: int = Field(0, description="Critical severity issues")
    high_issues: int = Field(0, description="High severity issues")
    medium_issues: int = Field(0, description="Medium severity issues")
    low_issues: int = Field(0, description="Low severity issues")
    findings: List[TLSFinding] = Field(default_factory=list, description="List of findings")
    protocol_issues: int = Field(0, description="Protocol-related issues found")
    cipher_issues: int = Field(0, description="Cipher-related issues found")
    certificate_issues: int = Field(0, description="Certificate-related issues found")
    verification_issues: int = Field(0, description="Verification-related issues found")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    tls_score: float = Field(100.0, ge=0.0, le=100.0, description="TLS security score (0-100)")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: TLSFinding) -> None:
        """Add a TLS/SSL finding to the report."""
        self.total_issues += 1
        self.findings.append(finding)
        self._increment_severity_count(finding.severity)
        self._increment_type_count(finding.finding_type)
        self._calculate_tls_score()

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
        protocol_types = [
            TLSFindingType.DEPRECATED_TLS_VERSION.value,
            TLSFindingType.INSECURE_PROTOCOL.value,
        ]
        cipher_types = [
            TLSFindingType.WEAK_CIPHER.value,
            TLSFindingType.WEAK_DH_PARAMS.value,
        ]
        certificate_types = [
            TLSFindingType.SELF_SIGNED_ALLOWED.value,
            TLSFindingType.HARDCODED_CERTIFICATE.value,
            TLSFindingType.EXPIRED_CERTIFICATE.value,
        ]
        verification_types = [
            TLSFindingType.DISABLED_VERIFICATION.value,
            TLSFindingType.DISABLED_HOSTNAME_CHECK.value,
            TLSFindingType.INSECURE_SSL_CONTEXT.value,
            TLSFindingType.CERT_NONE.value,
            TLSFindingType.NO_CERT_VALIDATION.value,
        ]

        if finding_type in protocol_types:
            self.protocol_issues += 1
        elif finding_type in cipher_types:
            self.cipher_issues += 1
        elif finding_type in certificate_types:
            self.certificate_issues += 1
        elif finding_type in verification_types:
            self.verification_issues += 1

    def _calculate_tls_score(self) -> None:
        """Calculate the overall TLS security score."""
        score = 100.0
        score -= self.critical_issues * 25
        score -= self.high_issues * 10
        score -= self.medium_issues * 5
        score -= self.low_issues * 1
        self.tls_score = max(0.0, score)

    @property
    def has_issues(self) -> bool:
        """Check if any TLS/SSL issues were found."""
        return self.total_issues > 0

    @property
    def is_healthy(self) -> bool:
        """Check if the TLS scan is healthy."""
        return self.critical_issues == 0 and self.high_issues == 0

    def get_findings_by_type(self) -> Dict[str, List[TLSFinding]]:
        """Group findings by type."""
        result: Dict[str, List[TLSFinding]] = {}
        for finding in self.findings:
            ftype = finding.finding_type
            if ftype not in result:
                result[ftype] = []
            result[ftype].append(finding)
        return result

    def get_findings_by_severity(self) -> Dict[str, List[TLSFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[TLSFinding]] = {
            SecuritySeverity.CRITICAL.value: [],
            SecuritySeverity.HIGH.value: [],
            SecuritySeverity.MEDIUM.value: [],
            SecuritySeverity.LOW.value: [],
            SecuritySeverity.INFO.value: [],
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result
