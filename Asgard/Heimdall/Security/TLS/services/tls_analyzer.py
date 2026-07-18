"""
Heimdall TLS Analyzer Service

Unified service that orchestrates all TLS/SSL security analyzers.
"""

import time
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Security.TLS.models.tls_models import (
    TLSConfig,
    TLSFindingType,
    TLSReport,
)
from Asgard.Heimdall.Security.TLS.services.protocol_analyzer import ProtocolAnalyzer
from Asgard.Heimdall.Security.TLS.services.cipher_validator import CipherValidator
from Asgard.Heimdall.Security.TLS.services.certificate_validator import CertificateValidator
from Asgard.Heimdall.Security.TLS.services.tls_config_analyzer import analyze_config_file
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity
from Asgard.Heimdall.Security.utilities.security_utils import scan_directory_for_security

_CONFIG_EXTENSIONS = (".conf", ".cfg", ".tf")


class TLSAnalyzer:
    """
    Unified TLS/SSL analyzer that combines all TLS checking services.

    Orchestrates:
    - ProtocolAnalyzer: Deprecated protocol detection
    - CipherValidator: Weak cipher suite detection
    - CertificateValidator: Certificate validation issues
    """

    def __init__(self, config: Optional[TLSConfig] = None):
        """
        Initialize the TLS analyzer.

        Args:
            config: TLS configuration. Uses defaults if not provided.
        """
        self.config = config or TLSConfig()
        self.protocol_analyzer = ProtocolAnalyzer(self.config)
        self.cipher_validator = CipherValidator(self.config)
        self.certificate_validator = CertificateValidator(self.config)

    def analyze(self, scan_path: Optional[Path] = None) -> TLSReport:
        """
        Run full TLS/SSL security analysis.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            TLSReport containing all findings from all analyzers
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        combined_report = TLSReport(scan_path=str(path))

        if self.config.check_protocols:
            protocol_report = self.protocol_analyzer.scan(path)
            self._merge_reports(combined_report, protocol_report)

        if self.config.check_ciphers:
            cipher_report = self.cipher_validator.scan(path)
            self._merge_reports(combined_report, cipher_report)

        if self.config.check_certificates or self.config.check_verification:
            cert_report = self.certificate_validator.scan(path)
            self._merge_reports(combined_report, cert_report)

        # Plan 07.9: config-file evidence (nginx/HAProxy/Terraform ALB)
        # outranks code-level guesses -- always max-precision confidence,
        # never a hotspot.
        for file_path in scan_directory_for_security(
            path, exclude_patterns=self.config.exclude_patterns,
            include_extensions=list(_CONFIG_EXTENSIONS),
        ):
            for finding in analyze_config_file(file_path):
                combined_report.add_finding(finding)

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

    def scan(self, scan_path: Optional[Path] = None) -> TLSReport:
        """
        Alias for analyze() for consistency with other services.

        Args:
            scan_path: Root path to scan

        Returns:
            TLSReport containing all findings
        """
        return self.analyze(scan_path)

    def scan_protocols_only(self, scan_path: Optional[Path] = None) -> TLSReport:
        """
        Scan only for deprecated protocol issues.

        Args:
            scan_path: Root path to scan

        Returns:
            TLSReport with protocol findings only
        """
        return self.protocol_analyzer.scan(scan_path)

    def scan_ciphers_only(self, scan_path: Optional[Path] = None) -> TLSReport:
        """
        Scan only for weak cipher issues.

        Args:
            scan_path: Root path to scan

        Returns:
            TLSReport with cipher findings only
        """
        return self.cipher_validator.scan(scan_path)

    def scan_certificates_only(self, scan_path: Optional[Path] = None) -> TLSReport:
        """
        Scan only for certificate validation issues.

        Args:
            scan_path: Root path to scan

        Returns:
            TLSReport with certificate findings only
        """
        return self.certificate_validator.scan(scan_path)

    def _merge_reports(self, target: TLSReport, source: TLSReport) -> None:
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

    def _recalculate_totals(self, report: TLSReport) -> None:
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

        report.protocol_issues = sum(1 for f in report.findings if f.finding_type in protocol_types)
        report.cipher_issues = sum(1 for f in report.findings if f.finding_type in cipher_types)
        report.certificate_issues = sum(1 for f in report.findings if f.finding_type in certificate_types)
        report.verification_issues = sum(1 for f in report.findings if f.finding_type in verification_types)

        score = 100.0
        score -= report.critical_issues * 25
        score -= report.high_issues * 10
        score -= report.medium_issues * 5
        score -= report.low_issues * 1
        report.tls_score = max(0.0, score)

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

    def get_summary(self, report: TLSReport) -> str:
        """
        Generate a text summary of the TLS report.

        Args:
            report: TLSReport to summarize

        Returns:
            Formatted text summary
        """
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL TLS/SSL SECURITY ANALYSIS REPORT")
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
        lines.append(f"  TLS Score:              {report.tls_score:.1f}/100")
        lines.append(f"  Total Issues:           {report.total_issues}")
        lines.append(f"    Critical:             {report.critical_issues}")
        lines.append(f"    High:                 {report.high_issues}")
        lines.append(f"    Medium:               {report.medium_issues}")
        lines.append(f"    Low:                  {report.low_issues}")
        lines.append("")
        lines.append(f"  Protocol Issues:        {report.protocol_issues}")
        lines.append(f"  Cipher Issues:          {report.cipher_issues}")
        lines.append(f"  Certificate Issues:     {report.certificate_issues}")
        lines.append(f"  Verification Issues:    {report.verification_issues}")
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
                if finding.protocol_version:
                    lines.append(f"    Protocol: {finding.protocol_version}")
                if finding.cipher_suite:
                    lines.append(f"    Cipher: {finding.cipher_suite}")
                lines.append("")

            if len(report.findings) > 10:
                lines.append(f"  ... and {len(report.findings) - 10} more findings")
                lines.append("")

        lines.append("=" * 70)
        lines.append(f"  RESULT: {'PASS' if report.is_healthy else 'FAIL'}")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)
