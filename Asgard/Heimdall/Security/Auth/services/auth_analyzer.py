"""
Heimdall Auth Analyzer Service

Unified service that orchestrates all authentication analyzers.
"""

import time
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Security.Auth.models.auth_models import (
    AuthConfig,
    AuthFindingType,
    AuthReport,
)
from Asgard.Heimdall.Security.Auth.services.jwt_validator import JWTValidator
from Asgard.Heimdall.Security.Auth.services.password_analyzer import PasswordAnalyzer
from Asgard.Heimdall.Security.Auth.services.session_analyzer import SessionAnalyzer
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class AuthAnalyzer:
    """
    Unified authentication analyzer that combines all auth checking services.

    Orchestrates:
    - JWTValidator: JWT security analysis
    - SessionAnalyzer: Session management analysis
    - PasswordAnalyzer: Password handling analysis
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """
        Initialize the auth analyzer.

        Args:
            config: Auth configuration. Uses defaults if not provided.
        """
        self.config = config or AuthConfig()
        self.jwt_validator = JWTValidator(self.config)
        self.session_analyzer = SessionAnalyzer(self.config)
        self.password_analyzer = PasswordAnalyzer(self.config)

    def analyze(self, scan_path: Optional[Path] = None) -> AuthReport:
        """
        Run full authentication analysis.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            AuthReport containing all findings from all analyzers
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        combined_report = AuthReport(scan_path=str(path))

        if self.config.check_jwt:
            jwt_report = self.jwt_validator.scan(path)
            self._merge_reports(combined_report, jwt_report)

        if self.config.check_session:
            session_report = self.session_analyzer.scan(path)
            self._merge_reports(combined_report, session_report)

        if self.config.check_password:
            password_report = self.password_analyzer.scan(path)
            self._merge_reports(combined_report, password_report)

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

    def scan(self, scan_path: Optional[Path] = None) -> AuthReport:
        """
        Alias for analyze() for consistency with other services.

        Args:
            scan_path: Root path to scan

        Returns:
            AuthReport containing all findings
        """
        return self.analyze(scan_path)

    def scan_jwt_only(self, scan_path: Optional[Path] = None) -> AuthReport:
        """
        Scan only for JWT issues.

        Args:
            scan_path: Root path to scan

        Returns:
            AuthReport with JWT findings only
        """
        return self.jwt_validator.scan(scan_path)

    def scan_session_only(self, scan_path: Optional[Path] = None) -> AuthReport:
        """
        Scan only for session issues.

        Args:
            scan_path: Root path to scan

        Returns:
            AuthReport with session findings only
        """
        return self.session_analyzer.scan(scan_path)

    def scan_password_only(self, scan_path: Optional[Path] = None) -> AuthReport:
        """
        Scan only for password issues.

        Args:
            scan_path: Root path to scan

        Returns:
            AuthReport with password findings only
        """
        return self.password_analyzer.scan(scan_path)

    def _merge_reports(self, target: AuthReport, source: AuthReport) -> None:
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

    def _recalculate_totals(self, report: AuthReport) -> None:
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

        jwt_types = [
            AuthFindingType.WEAK_JWT_ALGORITHM.value,
            AuthFindingType.MISSING_TOKEN_EXPIRATION.value,
            AuthFindingType.JWT_NONE_ALGORITHM.value,
        ]
        session_types = [
            AuthFindingType.INSECURE_SESSION.value,
            AuthFindingType.SESSION_FIXATION.value,
            AuthFindingType.INSECURE_COOKIE.value,
        ]
        password_types = [
            AuthFindingType.PLAINTEXT_PASSWORD.value,
            AuthFindingType.PASSWORD_IN_LOG.value,
            AuthFindingType.WEAK_PASSWORD_HASH.value,
            AuthFindingType.HARDCODED_CREDENTIALS.value,
        ]

        report.jwt_issues = sum(1 for f in report.findings if f.finding_type in jwt_types)
        report.session_issues = sum(1 for f in report.findings if f.finding_type in session_types)
        report.password_issues = sum(1 for f in report.findings if f.finding_type in password_types)

        score = 100.0
        score -= report.critical_issues * 25
        score -= report.high_issues * 10
        score -= report.medium_issues * 5
        score -= report.low_issues * 1
        report.auth_score = max(0.0, score)

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

    def get_summary(self, report: AuthReport) -> str:
        """
        Generate a text summary of the authentication report.

        Args:
            report: AuthReport to summarize

        Returns:
            Formatted text summary
        """
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL AUTHENTICATION ANALYSIS REPORT")
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
        lines.append(f"  Auth Score:             {report.auth_score:.1f}/100")
        lines.append(f"  Total Issues:           {report.total_issues}")
        lines.append(f"    Critical:             {report.critical_issues}")
        lines.append(f"    High:                 {report.high_issues}")
        lines.append(f"    Medium:               {report.medium_issues}")
        lines.append(f"    Low:                  {report.low_issues}")
        lines.append("")
        lines.append(f"  JWT Issues:             {report.jwt_issues}")
        lines.append(f"  Session Issues:         {report.session_issues}")
        lines.append(f"  Password Issues:        {report.password_issues}")
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
