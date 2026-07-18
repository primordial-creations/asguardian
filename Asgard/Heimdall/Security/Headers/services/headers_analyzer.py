"""
Heimdall Headers Analyzer Service

Unified service that orchestrates all header security analyzers.
"""

import time
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Security.Headers.models.header_models import (
    HeaderConfig,
    HeaderFindingType,
    HeaderReport,
)
from Asgard.Heimdall.Security.Headers.services.cors_analyzer import CORSAnalyzer
from Asgard.Heimdall.Security.Headers.services.csp_analyzer import CSPAnalyzer
from Asgard.Heimdall.Security.Headers.services.header_validator import HeaderValidator
from Asgard.Heimdall.Security.Headers.services._header_context import apply_header_context
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class HeadersAnalyzer:
    """
    Unified security headers analyzer that combines all header checking services.

    Orchestrates:
    - HeaderValidator: Missing and weak header detection
    - CSPAnalyzer: Content-Security-Policy analysis
    - CORSAnalyzer: CORS configuration analysis
    """

    def __init__(self, config: Optional[HeaderConfig] = None):
        """
        Initialize the headers analyzer.

        Args:
            config: Header configuration. Uses defaults if not provided.
        """
        self.config = config or HeaderConfig()
        self.header_validator = HeaderValidator(self.config)
        self.csp_analyzer = CSPAnalyzer(self.config)
        self.cors_analyzer = CORSAnalyzer(self.config)

    def analyze(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Run full security headers analysis.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            HeaderReport containing all findings from all analyzers
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        combined_report = HeaderReport(scan_path=str(path))

        header_report = self.header_validator.scan(path)
        self._merge_reports(combined_report, header_report)

        if self.config.check_csp:
            csp_report = self.csp_analyzer.scan(path)
            self._merge_reports(combined_report, csp_report)

        if self.config.check_cors:
            cors_report = self.cors_analyzer.scan(path)
            self._merge_reports(combined_report, cors_report)

        combined_report.scan_duration_seconds = time.time() - start_time

        combined_report.findings = list({
            (f.file_path, f.line_number, f.finding_type): f
            for f in combined_report.findings
        }.values())

        apply_header_context(combined_report.findings, is_api=self.config.is_api)

        combined_report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        self._recalculate_totals(combined_report)

        return combined_report

    def scan(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Alias for analyze() for consistency with other services.

        Args:
            scan_path: Root path to scan

        Returns:
            HeaderReport containing all findings
        """
        return self.analyze(scan_path)

    def scan_headers_only(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Scan only for missing and weak headers.

        Args:
            scan_path: Root path to scan

        Returns:
            HeaderReport with header findings only
        """
        return self.header_validator.scan(scan_path)

    def scan_csp_only(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Scan only for CSP issues.

        Args:
            scan_path: Root path to scan

        Returns:
            HeaderReport with CSP findings only
        """
        return self.csp_analyzer.scan(scan_path)

    def scan_cors_only(self, scan_path: Optional[Path] = None) -> HeaderReport:
        """
        Scan only for CORS issues.

        Args:
            scan_path: Root path to scan

        Returns:
            HeaderReport with CORS findings only
        """
        return self.cors_analyzer.scan(scan_path)

    def _merge_reports(self, target: HeaderReport, source: HeaderReport) -> None:
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
        target.findings.extend(source.findings)

    def _recalculate_totals(self, report: HeaderReport) -> None:
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

        report.csp_issues = sum(1 for f in report.findings if f.finding_type in csp_types)
        report.cors_issues = sum(1 for f in report.findings if f.finding_type in cors_types)
        report.cookie_issues = sum(1 for f in report.findings if f.finding_type in cookie_types)
        report.missing_headers = sum(1 for f in report.findings if f.finding_type in missing_types)

        score = 100.0
        score -= report.critical_issues * 25
        score -= report.high_issues * 10
        score -= report.medium_issues * 5
        score -= report.low_issues * 1
        report.header_score = max(0.0, score)

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

    def get_summary(self, report: HeaderReport) -> str:
        """
        Generate a text summary of the header security report.

        Args:
            report: HeaderReport to summarize

        Returns:
            Formatted text summary
        """
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL SECURITY HEADERS ANALYSIS REPORT")
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
        lines.append(f"  Header Score:           {report.header_score:.1f}/100")
        lines.append(f"  Total Issues:           {report.total_issues}")
        lines.append(f"    Critical:             {report.critical_issues}")
        lines.append(f"    High:                 {report.high_issues}")
        lines.append(f"    Medium:               {report.medium_issues}")
        lines.append(f"    Low:                  {report.low_issues}")
        lines.append("")
        lines.append(f"  CSP Issues:             {report.csp_issues}")
        lines.append(f"  CORS Issues:            {report.cors_issues}")
        lines.append(f"  Cookie Issues:          {report.cookie_issues}")
        lines.append(f"  Missing Headers:        {report.missing_headers}")
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
                if finding.header_name:
                    lines.append(f"    Header: {finding.header_name}")
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
