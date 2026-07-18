"""Heimdall Security Analysis Report Models - aggregate findings from security scans."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Heimdall.Security.models.security_models_base import (
    CryptoFinding,
    DependencyRiskLevel,
    DependencyVulnerability,
    SecretFinding,
    SecurityScanConfig,
    SecuritySeverity,
    VulnerabilityFinding,
)


class SecretsReport(BaseModel):
    """Report from secrets detection scan."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    secrets_found: int = Field(0, description="Total secrets detected")
    findings: List[SecretFinding] = Field(default_factory=list, description="List of findings")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    patterns_used: List[str] = Field(default_factory=list, description="Patterns used for detection")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: SecretFinding) -> None:
        """Add a secret finding to the report."""
        self.secrets_found += 1
        self.findings.append(finding)

    @property
    def secrets(self) -> List[SecretFinding]:
        """Alias for findings for compatibility."""
        return self.findings

    @property
    def has_findings(self) -> bool:
        """Check if any secrets were found."""
        return self.secrets_found > 0

    def get_findings_by_severity(self) -> Dict[str, List[SecretFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[SecretFinding]] = {
            SecuritySeverity.CRITICAL.value: [],
            SecuritySeverity.HIGH.value: [],
            SecuritySeverity.MEDIUM.value: [],
            SecuritySeverity.LOW.value: [],
            SecuritySeverity.INFO.value: [],
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result


class VulnerabilityReport(BaseModel):
    """Report from vulnerability scanning."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    vulnerabilities_found: int = Field(0, description="Total vulnerabilities detected")
    findings: List[VulnerabilityFinding] = Field(default_factory=list, description="List of findings")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: VulnerabilityFinding) -> None:
        """Add a vulnerability finding to the report."""
        self.vulnerabilities_found += 1
        self.findings.append(finding)

    @property
    def vulnerabilities(self) -> List[VulnerabilityFinding]:
        """Alias for findings for compatibility."""
        return self.findings

    @property
    def has_findings(self) -> bool:
        """Check if any vulnerabilities were found."""
        return self.vulnerabilities_found > 0

    def get_findings_by_type(self) -> Dict[str, List[VulnerabilityFinding]]:
        """Group findings by vulnerability type."""
        result: Dict[str, List[VulnerabilityFinding]] = {}
        for finding in self.findings:
            vtype = finding.vulnerability_type
            if vtype not in result:
                result[vtype] = []
            result[vtype].append(finding)
        return result

    def get_findings_by_severity(self) -> Dict[str, List[VulnerabilityFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[VulnerabilityFinding]] = {
            SecuritySeverity.CRITICAL.value: [],
            SecuritySeverity.HIGH.value: [],
            SecuritySeverity.MEDIUM.value: [],
            SecuritySeverity.LOW.value: [],
            SecuritySeverity.INFO.value: [],
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result


class DependencyReport(BaseModel):
    """Report from dependency vulnerability scanning."""
    scan_path: str = Field(..., description="Root path that was scanned")
    requirements_files: List[str] = Field(default_factory=list, description="Requirements files found")
    total_dependencies: int = Field(0, description="Total dependencies analyzed")
    vulnerable_dependencies: int = Field(0, description="Dependencies with vulnerabilities")
    vulnerabilities: List[DependencyVulnerability] = Field(default_factory=list, description="List of vulnerabilities")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    network_checked: bool = Field(
        False,
        description=(
            "Whether the opt-in live OSV/NVD lookup ran and succeeded "
            "(enable_network=True and no network error). False when "
            "network lookup was disabled OR when it was attempted but "
            "failed -- see network_reason to distinguish the two."
        ),
    )
    network_reason: str = Field(
        "",
        description="Why network_checked is False, or a status note when True.",
    )

    class Config:
        use_enum_values = True

    def add_vulnerability(self, vuln: DependencyVulnerability) -> None:
        """Add a dependency vulnerability to the report."""
        self.vulnerabilities.append(vuln)
        unique_packages = set(v.package_name for v in self.vulnerabilities)
        self.vulnerable_dependencies = len(unique_packages)

    @property
    def has_vulnerabilities(self) -> bool:
        """Check if any vulnerabilities were found."""
        return self.vulnerable_dependencies > 0

    def get_vulnerabilities_by_risk(self) -> Dict[str, List[DependencyVulnerability]]:
        """Group vulnerabilities by risk level."""
        result: Dict[str, List[DependencyVulnerability]] = {
            DependencyRiskLevel.CRITICAL.value: [],
            DependencyRiskLevel.HIGH.value: [],
            DependencyRiskLevel.MODERATE.value: [],
            DependencyRiskLevel.LOW.value: [],
            DependencyRiskLevel.SAFE.value: [],
        }
        for vuln in self.vulnerabilities:
            result[vuln.risk_level].append(vuln)
        return result


class CryptoReport(BaseModel):
    """Report from cryptographic implementation analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    issues_found: int = Field(0, description="Total cryptographic issues detected")
    findings: List[CryptoFinding] = Field(default_factory=list, description="List of findings")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: CryptoFinding) -> None:
        """Add a cryptographic finding to the report."""
        self.issues_found += 1
        self.findings.append(finding)

    @property
    def has_findings(self) -> bool:
        """Check if any issues were found."""
        return self.issues_found > 0


class SecurityReport(BaseModel):
    """Comprehensive security analysis report."""
    scan_path: str = Field(..., description="Root path that was scanned")
    scan_config: SecurityScanConfig = Field(..., description="Configuration used for the scan")
    secrets_report: Optional[SecretsReport] = Field(None, description="Secrets detection report")
    vulnerability_report: Optional[VulnerabilityReport] = Field(None, description="Vulnerability scan report")
    dependency_report: Optional[DependencyReport] = Field(None, description="Dependency scan report")
    crypto_report: Optional[CryptoReport] = Field(None, description="Cryptographic analysis report")
    access_report: Optional[Any] = Field(None, description="Access control analysis report")
    auth_report: Optional[Any] = Field(None, description="Authentication analysis report")
    headers_report: Optional[Any] = Field(None, description="Security headers analysis report")
    tls_report: Optional[Any] = Field(None, description="TLS/SSL analysis report")
    container_report: Optional[Any] = Field(None, description="Container security analysis report")
    infrastructure_report: Optional[Any] = Field(None, description="Infrastructure security analysis report")
    total_issues: int = Field(0, description="Total security issues found")
    critical_issues: int = Field(0, description="Critical severity issues")
    high_issues: int = Field(0, description="High severity issues")
    medium_issues: int = Field(0, description="Medium severity issues")
    low_issues: int = Field(0, description="Low severity issues")
    security_score: float = Field(100.0, ge=0.0, le=100.0, description="Overall security score (0-100)")
    legacy_score: float = Field(
        100.0, ge=0.0, le=100.0,
        description="Deprecated linear-subtractive score (100-25c-10h-5m-1l); kept for one minor version"
    )
    security_score_v2: float = Field(
        100.0, ge=0.0, le=100.0,
        description="Multiplicative-decay score (size-normalized, per-category soft caps)"
    )
    total_lines_of_code: int = Field(
        0, ge=0,
        description="Total LOC scanned; used for v2 size normalization (0 = unknown, no normalization)"
    )
    scan_duration_seconds: float = Field(0.0, description="Total duration of all scans")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    # Risk-level -> severity translation for dependency vulnerabilities.
    _RISK_TO_SEVERITY = {
        DependencyRiskLevel.CRITICAL.value: "critical",
        DependencyRiskLevel.HIGH.value: "high",
        DependencyRiskLevel.MODERATE.value: "medium",
        DependencyRiskLevel.LOW.value: "low",
    }

    def calculate_totals(self) -> None:
        """Calculate total issue counts from all reports."""
        self.total_issues = 0
        self.critical_issues = 0
        self.high_issues = 0
        self.medium_issues = 0
        self.low_issues = 0
        # category -> severity -> score-weighted effective count (v2 formula).
        score_counts: Dict[str, Dict[str, float]] = {}

        categorized = [
            ("secrets", self.secrets_report),
            ("vulnerabilities", self.vulnerability_report),
            ("crypto", self.crypto_report),
            ("access", self.access_report),
            ("auth", self.auth_report),
            ("headers", self.headers_report),
            ("tls", self.tls_report),
            ("container", self.container_report),
            ("infrastructure", self.infrastructure_report),
        ]
        for category, sub_report in categorized:
            if not sub_report or not hasattr(sub_report, "findings"):
                continue
            for finding in sub_report.findings:
                self.total_issues += 1
                self._increment_severity_count(finding.severity)
                self._add_score_count(
                    score_counts, category, finding.severity,
                    getattr(finding, "confidence", None),
                )

        if self.dependency_report:
            for vuln in self.dependency_report.vulnerabilities:
                self.total_issues += 1
                self._increment_risk_count(vuln.risk_level)
                severity = self._RISK_TO_SEVERITY.get(vuln.risk_level)
                if severity:
                    # Dependency vulns carry no detection confidence: full weight.
                    self._add_score_count(score_counts, "dependencies", severity, None)

        self._calculate_security_score(score_counts)

    @staticmethod
    def _add_score_count(
        score_counts: Dict[str, Dict[str, float]],
        category: str,
        severity: str,
        confidence: Optional[float],
    ) -> None:
        """Accumulate a finding's aggregate-hygiene weight into the v2 sums."""
        from Asgard.Heimdall.Security.normalization.scoring import score_weight

        if severity not in ("critical", "high", "medium", "low"):
            return
        weight = score_weight(confidence)
        if weight <= 0.0:
            return
        bucket = score_counts.setdefault(
            category, {"critical": 0.0, "high": 0.0, "medium": 0.0, "low": 0.0}
        )
        bucket[severity] += weight

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

    def _increment_risk_count(self, risk: str) -> None:
        """Increment the count for a risk level."""
        if risk == DependencyRiskLevel.CRITICAL.value:
            self.critical_issues += 1
        elif risk == DependencyRiskLevel.HIGH.value:
            self.high_issues += 1
        elif risk == DependencyRiskLevel.MODERATE.value:
            self.medium_issues += 1
        elif risk == DependencyRiskLevel.LOW.value:
            self.low_issues += 1

    def _calculate_security_score(
        self, score_counts: Optional[Dict[str, Dict[str, float]]] = None
    ) -> None:
        """
        Calculate the overall security score.

        Both formulas are always computed and dual-reported:
        - ``legacy_score``: linear-subtractive (deprecated).
        - ``security_score_v2``: multiplicative decay with size
          normalization and per-category soft caps (see
          ``Security/normalization/scoring.py``).

        ``security_score`` follows ``scan_config.scoring_version`` ('v1'
        default for one deprecation cycle).
        """
        from Asgard.Heimdall.Security.normalization.scoring import (
            legacy_security_score,
            multiplicative_security_score,
        )

        self.legacy_score = legacy_security_score(
            self.critical_issues, self.high_issues,
            self.medium_issues, self.low_issues,
        )
        self.security_score_v2 = multiplicative_security_score(
            score_counts or {}, self.total_lines_of_code
        )
        version = getattr(self.scan_config, "scoring_version", "v1")
        if version == "v2":
            self.security_score = self.security_score_v2
        else:
            self.security_score = self.legacy_score

    @property
    def has_issues(self) -> bool:
        """Check if any security issues were found."""
        return self.total_issues > 0

    @property
    def is_passing(self) -> bool:
        """Check if the scan passes (no critical or high issues)."""
        return self.critical_issues == 0 and self.high_issues == 0

    @property
    def is_healthy(self) -> bool:
        """Check if the security scan is healthy (no critical or high issues)."""
        return self.is_passing
