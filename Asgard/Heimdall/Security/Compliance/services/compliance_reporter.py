"""
Heimdall Compliance Reporter Service

Maps Heimdall security findings from existing SecurityReport, VulnerabilityReport,
SecretsReport, CryptoReport, and DependencyReport objects to OWASP Top 10 (2021)
and CWE Top 25 (2024) categories and produces compliance grade reports.

Compliance grades per category:
  A: 0 findings
  B: 1-2 LOW findings only
  C: Any MEDIUM findings or 3+ LOW
  D: Any HIGH findings
  F: Any CRITICAL findings

Mapping logic:
  sql_injection            -> A03, CWE-89
  command_injection        -> A03, CWE-78, CWE-77
  xss                      -> A03, CWE-79
  path_traversal           -> A01, CWE-22
  insecure_crypto / crypto -> A02, CWE-327
  hardcoded_secret         -> A02, CWE-798
  insecure_deserialization -> A08, CWE-502
  ssrf                     -> A10, CWE-918
  missing_auth             -> A07, CWE-306
  dependency vulnerabilities (critical/high) -> A06
  cookie/session issues    -> A07, CWE-287
  weak_random              -> A02, CWE-338
  template_injection       -> A03, CWE-94
"""

from datetime import datetime
from typing import Dict, List, Optional

from Asgard.Heimdall.Security.Compliance.models.compliance_models import (
    CategoryCompliance,
    ComplianceConfig,
    ComplianceGrade,
    CWE_TOP_25_2024,
    CWEComplianceReport,
    OWASPComplianceReport,
    OWASP_CATEGORY_NAMES,
)
from Asgard.Heimdall.Security.Compliance.services._compliance_mappers import (
    map_crypto_to_cwe,
    map_crypto_to_owasp,
    map_dependencies_to_owasp,
    map_hotspots_to_cwe,
    map_hotspots_to_owasp,
    map_secrets_to_cwe,
    map_secrets_to_owasp,
    map_vulnerabilities_to_cwe,
    map_vulnerabilities_to_owasp,
)


def _compute_grade(category: CategoryCompliance) -> ComplianceGrade:
    """Compute the compliance grade for a category based on its finding counts."""
    if category.critical_count > 0:
        return ComplianceGrade.F
    elif category.high_count > 0:
        return ComplianceGrade.D
    elif category.medium_count > 0:
        return ComplianceGrade.C
    elif category.low_count > 2:
        return ComplianceGrade.C
    elif category.low_count > 0:
        return ComplianceGrade.B
    else:
        return ComplianceGrade.A


def _worst_grade(grades: List[ComplianceGrade]) -> ComplianceGrade:
    """Return the worst (lowest) compliance grade from a list."""
    order = {
        ComplianceGrade.A: 1,
        ComplianceGrade.B: 2,
        ComplianceGrade.C: 3,
        ComplianceGrade.D: 4,
        ComplianceGrade.F: 5,
    }
    if not grades:
        return ComplianceGrade.A
    return max(grades, key=lambda g: order.get(g, 1))


class ComplianceReporter:
    """
    Maps Heimdall security findings to OWASP Top 10 and CWE Top 25 categories
    and generates compliance grade reports.

    Usage:
        reporter = ComplianceReporter()

        owasp_report = reporter.generate_owasp_report(security_report, hotspot_report)
        cwe_report = reporter.generate_cwe_report(security_report, hotspot_report)

        print(f"OWASP overall grade: {owasp_report.overall_grade}")
        for cat_id, cat in owasp_report.categories.items():
            print(f"  {cat_id} {cat.category_name}: {cat.grade}")
    """

    def __init__(self, config: Optional[ComplianceConfig] = None):
        """
        Initialize the compliance reporter.

        Args:
            config: Configuration for compliance reporting. If None, uses defaults.
        """
        self.config = config or ComplianceConfig()

    def generate_owasp_report(
        self, security_report=None, hotspot_report=None, scan_path: str = ""
    ) -> OWASPComplianceReport:
        """
        Generate an OWASP Top 10 2021 compliance report.

        Args:
            security_report: Optional SecurityReport from StaticSecurityService
            hotspot_report: Optional HotspotReport from HotspotDetector
            scan_path: Optional scan path for metadata

        Returns:
            OWASPComplianceReport with per-category compliance grades
        """
        categories: Dict[str, CategoryCompliance] = {
            cat_id: CategoryCompliance(
                category_id=cat_id,
                category_name=name,
                grade=ComplianceGrade.A,
            )
            for cat_id, name in OWASP_CATEGORY_NAMES.items()
        }

        total_mapped = 0

        if security_report is not None:
            total_mapped += map_vulnerabilities_to_owasp(
                self._extract_vulnerability_findings(security_report), categories
            )
            total_mapped += map_secrets_to_owasp(
                self._extract_secrets(security_report), categories
            )
            total_mapped += map_crypto_to_owasp(
                self._extract_crypto_findings(security_report), categories
            )
            total_mapped += map_dependencies_to_owasp(
                self._extract_dependency_findings(security_report), categories
            )

        if hotspot_report is not None:
            hotspots = getattr(hotspot_report, "hotspots", []) or []
            total_mapped += map_hotspots_to_owasp(hotspots, categories)

        for cat in categories.values():
            cat.grade = _compute_grade(cat)

        overall = _worst_grade([cat.grade for cat in categories.values()])

        return OWASPComplianceReport(
            owasp_version=self.config.owasp_version,
            categories=categories,
            overall_grade=overall,
            total_findings_mapped=total_mapped,
            scan_path=scan_path,
            generated_at=datetime.now(),
        )

    def generate_cwe_report(
        self, security_report=None, hotspot_report=None, scan_path: str = ""
    ) -> CWEComplianceReport:
        """
        Generate a CWE Top 25 2024 compliance report.

        Args:
            security_report: Optional SecurityReport from StaticSecurityService
            hotspot_report: Optional HotspotReport from HotspotDetector
            scan_path: Optional scan path for metadata

        Returns:
            CWEComplianceReport with per-CWE compliance entries
        """
        top_25: Dict[str, CategoryCompliance] = {
            cwe_id: CategoryCompliance(
                category_id=cwe_id,
                category_name=name,
                grade=ComplianceGrade.A,
            )
            for cwe_id, name in CWE_TOP_25_2024.items()
        }

        if security_report is not None:
            map_vulnerabilities_to_cwe(
                self._extract_vulnerability_findings(security_report), top_25
            )
            map_secrets_to_cwe(self._extract_secrets(security_report), top_25)
            map_crypto_to_cwe(self._extract_crypto_findings(security_report), top_25)

        if hotspot_report is not None:
            hotspots = getattr(hotspot_report, "hotspots", []) or []
            map_hotspots_to_cwe(hotspots, top_25)

        for entry in top_25.values():
            entry.grade = _compute_grade(entry)

        overall = _worst_grade([entry.grade for entry in top_25.values()])

        return CWEComplianceReport(
            cwe_version=self.config.cwe_version,
            top_25_coverage=top_25,
            overall_grade=overall,
            scan_path=scan_path,
            generated_at=datetime.now(),
        )

    def _extract_vulnerability_findings(self, security_report) -> List:
        """Extract vulnerability findings from a SecurityReport."""
        for attr in ("vulnerability_findings", "vulnerabilities"):
            findings = getattr(security_report, attr, None) or []
            if findings:
                return list(findings)

        vuln_report = getattr(security_report, "vulnerability_report", None)
        if vuln_report is not None:
            for attr in ("findings", "vulnerabilities"):
                findings = getattr(vuln_report, attr, None) or []
                if findings:
                    return list(findings)

        return []

    def _extract_secrets(self, security_report) -> List:
        """Extract secret findings from a SecurityReport."""
        secrets_report = getattr(security_report, "secrets_report", None)
        if secrets_report is not None:
            return list(getattr(secrets_report, "findings", []) or [])

        for attr in ("secrets", "secret_findings"):
            findings = getattr(security_report, attr, None) or []
            if findings:
                return list(findings)

        return []

    def _extract_crypto_findings(self, security_report) -> List:
        """Extract cryptographic findings from a SecurityReport."""
        crypto_report = getattr(security_report, "crypto_report", None)
        if crypto_report is not None:
            return list(getattr(crypto_report, "findings", []) or [])

        for attr in ("crypto_findings", "cryptographic_findings"):
            findings = getattr(security_report, attr, None) or []
            if findings:
                return list(findings)

        return []

    def _extract_dependency_findings(self, security_report) -> List:
        """Extract dependency vulnerability findings from a SecurityReport."""
        dep_report = getattr(security_report, "dependency_report", None)
        if dep_report is not None:
            return list(getattr(dep_report, "vulnerabilities", []) or [])

        for attr in ("dependency_findings", "dependency_vulnerabilities"):
            findings = getattr(security_report, attr, None) or []
            if findings:
                return list(findings)

        return []
