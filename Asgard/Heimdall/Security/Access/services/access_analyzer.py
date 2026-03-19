"""
Heimdall Access Analyzer Service

Unified service that orchestrates all access control analyzers.
"""

import time
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Security.Access.models.access_models import (
    AccessConfig,
    AccessReport,
)
from Asgard.Heimdall.Security.Access.services.control_analyzer import ControlAnalyzer
from Asgard.Heimdall.Security.Access.services.permission_analyzer import PermissionAnalyzer
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class AccessAnalyzer:
    """
    Unified access control analyzer that combines all access checking services.

    Orchestrates:
    - ControlAnalyzer: RBAC/ABAC pattern analysis
    - PermissionAnalyzer: Route permission analysis
    """

    def __init__(self, config: Optional[AccessConfig] = None):
        """
        Initialize the access analyzer.

        Args:
            config: Access control configuration. Uses defaults if not provided.
        """
        self.config = config or AccessConfig()
        self.control_analyzer = ControlAnalyzer(self.config)
        self.permission_analyzer = PermissionAnalyzer(self.config)

    def analyze(self, scan_path: Optional[Path] = None) -> AccessReport:
        """
        Run full access control analysis.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            AccessReport containing all findings from all analyzers
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        combined_report = AccessReport(scan_path=str(path))

        if self.config.check_rbac:
            control_report = self.control_analyzer.scan(path)
            self._merge_reports(combined_report, control_report)

        if self.config.check_routes:
            permission_report = self.permission_analyzer.scan(path)
            self._merge_reports(combined_report, permission_report)

        combined_report.scan_duration_seconds = time.time() - start_time

        combined_report.findings = list({
            (f.file_path, f.line_number, f.finding_type): f
            for f in combined_report.findings
        }.values())

        combined_report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        self._recalculate_totals(combined_report)

        return combined_report

    def scan(self, scan_path: Optional[Path] = None) -> AccessReport:
        """
        Alias for analyze() for consistency with other services.

        Args:
            scan_path: Root path to scan

        Returns:
            AccessReport containing all findings
        """
        return self.analyze(scan_path)

    def scan_rbac_only(self, scan_path: Optional[Path] = None) -> AccessReport:
        """
        Scan only for RBAC/ABAC issues.

        Args:
            scan_path: Root path to scan

        Returns:
            AccessReport with RBAC findings only
        """
        return self.control_analyzer.scan(scan_path)

    def scan_permissions_only(self, scan_path: Optional[Path] = None) -> AccessReport:
        """
        Scan only for route permission issues.

        Args:
            scan_path: Root path to scan

        Returns:
            AccessReport with permission findings only
        """
        return self.permission_analyzer.scan(scan_path)

    def _merge_reports(self, target: AccessReport, source: AccessReport) -> None:
        """
        Merge source report into target report.

        Args:
            target: Report to merge into
            source: Report to merge from
        """
        target.total_files_scanned = max(
            target.total_files_scanned,
            source.total_files_scanned
        )
        target.total_routes_analyzed += source.total_routes_analyzed
        target.routes_with_auth += source.routes_with_auth
        target.routes_without_auth += source.routes_without_auth
        target.findings.extend(source.findings)

    def _recalculate_totals(self, report: AccessReport) -> None:
        """
        Recalculate totals after deduplication.

        Args:
            report: Report to recalculate
        """
        report.total_issues = len(report.findings)
        report.critical_issues = sum(
            1 for f in report.findings if f.severity == SecuritySeverity.CRITICAL.value
        )
        report.high_issues = sum(
            1 for f in report.findings if f.severity == SecuritySeverity.HIGH.value
        )
        report.medium_issues = sum(
            1 for f in report.findings if f.severity == SecuritySeverity.MEDIUM.value
        )
        report.low_issues = sum(
            1 for f in report.findings if f.severity == SecuritySeverity.LOW.value
        )

        score = 100.0
        score -= report.critical_issues * 25
        score -= report.high_issues * 10
        score -= report.medium_issues * 5
        score -= report.low_issues * 1
        report.access_score = max(0.0, score)

    def _severity_order(self, severity: str) -> int:
        """Get sort order for severity (critical first)."""
        order = {
            SecuritySeverity.CRITICAL.value: 0,
            SecuritySeverity.HIGH.value: 1,
            SecuritySeverity.MEDIUM.value: 2,
            SecuritySeverity.LOW.value: 3,
            SecuritySeverity.INFO.value: 4,
        }
        return order.get(severity, 5)

    def get_summary(self, report: AccessReport) -> str:
        """
        Generate a text summary of the access control report.

        Args:
            report: AccessReport to summarize

        Returns:
            Formatted text summary
        """
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL ACCESS CONTROL ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:    {report.scan_path}")
        lines.append(f"  Scanned At:   {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Duration:     {report.scan_duration_seconds:.2f}s")
        lines.append("")
        lines.append("-" * 70)
        lines.append("  SUMMARY")
        lines.append("-" * 70)
        lines.append("")
        lines.append(f"  Access Score:           {report.access_score:.1f}/100")
        lines.append(f"  Total Issues:           {report.total_issues}")
        lines.append(f"    Critical:             {report.critical_issues}")
        lines.append(f"    High:                 {report.high_issues}")
        lines.append(f"    Medium:               {report.medium_issues}")
        lines.append(f"    Low:                  {report.low_issues}")
        lines.append("")
        lines.append(f"  Routes Analyzed:        {report.total_routes_analyzed}")
        lines.append(f"    With Auth:            {report.routes_with_auth}")
        lines.append(f"    Without Auth:         {report.routes_without_auth}")
        lines.append("")

        if report.has_issues:
            lines.append("-" * 70)
            lines.append("  FINDINGS")
            lines.append("-" * 70)
            lines.append("")

            for finding in report.findings[:10]:
                severity_marker = f"[{finding.severity.upper()}]"
                lines.append(f"  {severity_marker} {finding.title}")
                lines.append(f"    File: {finding.file_path}:{finding.line_number}")
                lines.append(f"    {finding.description}")
                lines.append("")

            if len(report.findings) > 10:
                lines.append(f"  ... and {len(report.findings) - 10} more findings")
                lines.append("")

        lines.append("=" * 70)
        lines.append(f"  RESULT: {'PASS' if report.is_healthy else 'FAIL'}")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)
