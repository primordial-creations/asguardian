"""
Heimdall Static Security Analysis Service

Service for comprehensive static security analysis combining multiple
security checks into a unified analysis.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Security.models.security_models import (
    SecurityReport,
    SecurityScanConfig,
)
from Asgard.Heimdall.Security.services.secrets_detection_service import SecretsDetectionService
from Asgard.Heimdall.Security.services.dependency_vulnerability_service import DependencyVulnerabilityService
from Asgard.Heimdall.Security.services.injection_detection_service import InjectionDetectionService
from Asgard.Heimdall.Security.services.cryptographic_validation_service import CryptographicValidationService
from Asgard.Heimdall.Security.Access.services.access_analyzer import AccessAnalyzer
from Asgard.Heimdall.Security.Auth.services.auth_analyzer import AuthAnalyzer
from Asgard.Heimdall.Security.Headers.services.headers_analyzer import HeadersAnalyzer
from Asgard.Heimdall.Security.TLS.services.tls_analyzer import TLSAnalyzer
from Asgard.Heimdall.Security.Container.services.container_analyzer import ContainerAnalyzer
from Asgard.Heimdall.Security.Infrastructure.services.infra_analyzer import InfraAnalyzer


class StaticSecurityService:
    """
    Comprehensive static security analysis service.

    Combines multiple security scanning capabilities:
    - Secrets detection (API keys, passwords, tokens)
    - Dependency vulnerability scanning
    - Injection vulnerability detection (SQL, XSS, command)
    - Cryptographic implementation validation
    - Access control analysis (RBAC, permissions)
    - Authentication analysis (JWT, sessions, passwords)
    - Security headers analysis (CSP, CORS, HSTS)
    - TLS/SSL configuration analysis
    - Container security analysis (Dockerfile, docker-compose)
    - Infrastructure security analysis (credentials, config)

    Provides a unified security report with aggregated findings
    and an overall security score.
    """

    def __init__(self, config: Optional[SecurityScanConfig] = None):
        """
        Initialize the static security service.

        Args:
            config: Security scan configuration. Uses defaults if not provided.
        """
        self.config = config or SecurityScanConfig()

        self.secrets_service = SecretsDetectionService(self.config)
        self.dependency_service = DependencyVulnerabilityService(self.config)
        self.injection_service = InjectionDetectionService(self.config)
        self.crypto_service = CryptographicValidationService(self.config)
        self.access_analyzer = AccessAnalyzer()
        self.auth_analyzer = AuthAnalyzer()
        self.headers_analyzer = HeadersAnalyzer()
        self.tls_analyzer = TLSAnalyzer()
        self.container_analyzer = ContainerAnalyzer()
        self.infrastructure_analyzer = InfraAnalyzer()

    def scan(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Perform comprehensive security analysis.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            SecurityReport containing all findings from all services
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        if self.config.scan_secrets:
            try:
                report.secrets_report = self.secrets_service.scan(path)
            except Exception as e:
                pass

        if self.config.scan_dependencies:
            try:
                report.dependency_report = self.dependency_service.scan(path)
            except Exception as e:
                pass

        if self.config.scan_vulnerabilities:
            try:
                report.vulnerability_report = self.injection_service.scan(path)
            except Exception as e:
                pass

        if self.config.scan_crypto:
            try:
                report.crypto_report = self.crypto_service.scan(path)
            except Exception as e:
                pass

        if self.config.scan_access:
            try:
                report.access_report = self.access_analyzer.scan(path)
            except Exception as e:
                pass

        if self.config.scan_auth:
            try:
                report.auth_report = self.auth_analyzer.scan(path)
            except Exception as e:
                pass

        if self.config.scan_headers:
            try:
                report.headers_report = self.headers_analyzer.scan(path)
            except Exception as e:
                pass

        if self.config.scan_tls:
            try:
                report.tls_report = self.tls_analyzer.scan(path)
            except Exception as e:
                pass

        if self.config.scan_container:
            try:
                report.container_report = self.container_analyzer.scan(path)
            except Exception as e:
                pass

        if self.config.scan_infrastructure:
            try:
                report.infrastructure_report = self.infrastructure_analyzer.scan(path)
            except Exception as e:
                pass

        report.scan_duration_seconds = time.time() - start_time
        report.scanned_at = datetime.now()

        report.calculate_totals()

        return report

    def scan_secrets_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for secrets.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with secrets findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.secrets_report = self.secrets_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_dependencies_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for dependency vulnerabilities.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with dependency findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.dependency_report = self.dependency_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_vulnerabilities_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for injection vulnerabilities.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with vulnerability findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.vulnerability_report = self.injection_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_crypto_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for cryptographic issues.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with crypto findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.crypto_report = self.crypto_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_access_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for access control issues.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with access control findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.access_report = self.access_analyzer.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_auth_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for authentication issues.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with authentication findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.auth_report = self.auth_analyzer.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_headers_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for security headers issues.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with headers findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.headers_report = self.headers_analyzer.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_tls_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for TLS/SSL issues.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with TLS findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.tls_report = self.tls_analyzer.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_container_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for container security issues.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with container findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.container_report = self.container_analyzer.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_infrastructure_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Scan only for infrastructure security issues.

        Args:
            scan_path: Root path to scan

        Returns:
            SecurityReport with infrastructure findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = SecurityReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.infrastructure_report = self.infrastructure_analyzer.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def get_summary(self, report: SecurityReport) -> str:
        """
        Generate a text summary of the security report.

        Args:
            report: The security report

        Returns:
            Formatted summary string
        """
        lines = [
            "=" * 60,
            "HEIMDALL SECURITY ANALYSIS REPORT",
            "=" * 60,
            f"Scan Path: {report.scan_path}",
            f"Scanned At: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {report.scan_duration_seconds:.2f} seconds",
            "",
            "-" * 40,
            "SUMMARY",
            "-" * 40,
            f"Security Score: {report.security_score:.1f}/100",
            f"Total Issues: {report.total_issues}",
            f"  Critical: {report.critical_issues}",
            f"  High: {report.high_issues}",
            f"  Medium: {report.medium_issues}",
            f"  Low: {report.low_issues}",
            "",
        ]

        if report.secrets_report:
            lines.extend([
                "-" * 40,
                "SECRETS DETECTION",
                "-" * 40,
                f"Files Scanned: {report.secrets_report.total_files_scanned}",
                f"Secrets Found: {report.secrets_report.secrets_found}",
            ])

            if report.secrets_report.findings:
                lines.append("")
                groups: dict = {}
                for finding in report.secrets_report.findings:
                    key = (finding.pattern_name, finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper())
                    groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (pattern_name, severity), locations in groups.items():
                    count = len(locations)
                    lines.append(f"  {pattern_name} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.dependency_report:
            lines.extend([
                "-" * 40,
                "DEPENDENCY VULNERABILITIES",
                "-" * 40,
                f"Dependencies Analyzed: {report.dependency_report.total_dependencies}",
                f"Vulnerable Packages: {report.dependency_report.vulnerable_dependencies}",
            ])

            if report.dependency_report.vulnerabilities:
                lines.append("")
                dep_groups: dict = {}
                for vuln in report.dependency_report.vulnerabilities:
                    risk = vuln.risk_level.upper() if isinstance(vuln.risk_level, str) else vuln.risk_level.value.upper()
                    key = (vuln.title, risk)
                    dep_groups.setdefault(key, []).append((vuln.package_name, vuln.installed_version, vuln.fixed_version))
                for (title, risk), packages in dep_groups.items():
                    count = len(packages)
                    lines.append(f"  {title} ({risk.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for pkg_name, installed, fixed in packages:
                        fix_str = f"  ->  fix: upgrade to {fixed}" if fixed else ""
                        lines.append(f"    {pkg_name} {installed}{fix_str}")
            lines.append("")

        if report.vulnerability_report:
            lines.extend([
                "-" * 40,
                "CODE VULNERABILITIES",
                "-" * 40,
                f"Files Scanned: {report.vulnerability_report.total_files_scanned}",
                f"Vulnerabilities Found: {report.vulnerability_report.vulnerabilities_found}",
            ])

            if report.vulnerability_report.findings:
                lines.append("")
                vuln_groups: dict = {}
                for finding in report.vulnerability_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.title, severity)
                    vuln_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (title, severity), locations in vuln_groups.items():
                    count = len(locations)
                    lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.crypto_report:
            lines.extend([
                "-" * 40,
                "CRYPTOGRAPHIC ISSUES",
                "-" * 40,
                f"Files Scanned: {report.crypto_report.total_files_scanned}",
                f"Issues Found: {report.crypto_report.issues_found}",
            ])

            if report.crypto_report.findings:
                lines.append("")
                crypto_groups: dict = {}
                for finding in report.crypto_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.description, severity)
                    crypto_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (description, severity), locations in crypto_groups.items():
                    count = len(locations)
                    lines.append(f"  {description} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.access_report and hasattr(report.access_report, 'findings'):
            lines.extend([
                "-" * 40,
                "ACCESS CONTROL ISSUES",
                "-" * 40,
                f"Files Scanned: {report.access_report.total_files_scanned}",
                f"Issues Found: {report.access_report.total_issues}",
            ])

            if report.access_report.findings:
                lines.append("")
                access_groups: dict = {}
                for finding in report.access_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.title, severity)
                    access_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (title, severity), locations in access_groups.items():
                    count = len(locations)
                    lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.auth_report and hasattr(report.auth_report, 'findings'):
            lines.extend([
                "-" * 40,
                "AUTHENTICATION ISSUES",
                "-" * 40,
                f"Files Scanned: {report.auth_report.total_files_scanned}",
                f"Issues Found: {report.auth_report.total_issues}",
            ])

            if report.auth_report.findings:
                lines.append("")
                auth_groups: dict = {}
                for finding in report.auth_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.title, severity)
                    auth_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (title, severity), locations in auth_groups.items():
                    count = len(locations)
                    lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.headers_report and hasattr(report.headers_report, 'findings'):
            lines.extend([
                "-" * 40,
                "SECURITY HEADERS ISSUES",
                "-" * 40,
                f"Files Scanned: {report.headers_report.total_files_scanned}",
                f"Issues Found: {report.headers_report.total_issues}",
            ])

            if report.headers_report.findings:
                lines.append("")
                headers_groups: dict = {}
                for finding in report.headers_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.title, severity)
                    headers_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (title, severity), locations in headers_groups.items():
                    count = len(locations)
                    lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.tls_report and hasattr(report.tls_report, 'findings'):
            lines.extend([
                "-" * 40,
                "TLS/SSL ISSUES",
                "-" * 40,
                f"Files Scanned: {report.tls_report.total_files_scanned}",
                f"Issues Found: {report.tls_report.total_issues}",
            ])

            if report.tls_report.findings:
                lines.append("")
                tls_groups: dict = {}
                for finding in report.tls_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.title, severity)
                    tls_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (title, severity), locations in tls_groups.items():
                    count = len(locations)
                    lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.container_report and hasattr(report.container_report, 'findings'):
            lines.extend([
                "-" * 40,
                "CONTAINER SECURITY ISSUES",
                "-" * 40,
                f"Files Scanned: {report.container_report.total_files_scanned}",
                f"Issues Found: {report.container_report.total_issues}",
            ])

            if report.container_report.findings:
                lines.append("")
                container_groups: dict = {}
                for finding in report.container_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.title, severity)
                    container_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (title, severity), locations in container_groups.items():
                    count = len(locations)
                    lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        if report.infrastructure_report and hasattr(report.infrastructure_report, 'findings'):
            lines.extend([
                "-" * 40,
                "INFRASTRUCTURE SECURITY ISSUES",
                "-" * 40,
                f"Files Scanned: {report.infrastructure_report.total_files_scanned}",
                f"Issues Found: {report.infrastructure_report.total_issues}",
            ])

            if report.infrastructure_report.findings:
                lines.append("")
                infra_groups: dict = {}
                for finding in report.infrastructure_report.findings:
                    severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                    key = (finding.title, severity)
                    infra_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
                for (title, severity), locations in infra_groups.items():
                    count = len(locations)
                    lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                    for loc in locations:
                        lines.append(f"    {loc}")
            lines.append("")

        lines.extend([
            "=" * 60,
            f"RESULT: {'PASS' if report.is_passing else 'FAIL'}",
            "=" * 60,
        ])

        return "\n".join(lines)

    def analyze(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """
        Perform comprehensive security analysis (delegates to scan()).

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            SecurityReport containing all findings from all services
        """
        return self.scan(scan_path)

    def generate_report(self, report: SecurityReport, output_format: str = "text") -> str:
        """
        Generate formatted security report.

        Args:
            report: The security report to format
            output_format: Report format - text, json, or markdown

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return self._generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return self._generate_markdown_report(report)
        elif format_lower == "text":
            return self.get_summary(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")

    def _generate_json_report(self, report: SecurityReport) -> str:
        """Generate JSON formatted security report."""
        secrets_data = []
        if report.secrets_report:
            for f in report.secrets_report.findings:
                secrets_data.append({
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "secret_type": f.secret_type if isinstance(f.secret_type, str) else f.secret_type.value,
                    "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
                    "pattern_name": f.pattern_name,
                    "masked_value": f.masked_value,
                })

        vulns_data = []
        if report.vulnerability_report:
            for f in report.vulnerability_report.findings:
                vulns_data.append({
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "vulnerability_type": f.vulnerability_type if isinstance(f.vulnerability_type, str) else f.vulnerability_type.value,
                    "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
                    "title": f.title,
                    "description": f.description,
                })

        deps_data = []
        if report.dependency_report:
            for v in report.dependency_report.vulnerabilities:
                deps_data.append({
                    "package_name": v.package_name,
                    "installed_version": v.installed_version,
                    "risk_level": v.risk_level if isinstance(v.risk_level, str) else v.risk_level.value,
                    "title": v.title,
                    "fixed_version": v.fixed_version,
                })

        crypto_data = []
        if report.crypto_report:
            for f in report.crypto_report.findings:
                crypto_data.append({
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "issue_type": f.issue_type,
                    "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
                    "description": f.description,
                })

        report_data = {
            "scan_info": {
                "scan_path": report.scan_path,
                "scanned_at": report.scanned_at.isoformat(),
                "duration_seconds": report.scan_duration_seconds,
            },
            "summary": {
                "security_score": report.security_score,
                "total_issues": report.total_issues,
                "critical_issues": report.critical_issues,
                "high_issues": report.high_issues,
                "medium_issues": report.medium_issues,
                "low_issues": report.low_issues,
                "is_passing": report.is_passing,
            },
            "findings": {
                "secrets": secrets_data,
                "vulnerabilities": vulns_data,
                "dependencies": deps_data,
                "crypto": crypto_data,
            },
        }
        return json.dumps(report_data, indent=2)

    def _generate_markdown_report(self, report: SecurityReport) -> str:
        """Generate Markdown formatted security report."""
        lines = [
            "# Heimdall Security Analysis Report",
            "",
            f"**Scan Path:** `{report.scan_path}`",
            f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
            "",
            "## Summary",
            "",
            f"**Security Score:** {report.security_score:.1f}/100",
            f"**Total Issues:** {report.total_issues}",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| Critical | {report.critical_issues} |",
            f"| High | {report.high_issues} |",
            f"| Medium | {report.medium_issues} |",
            f"| Low | {report.low_issues} |",
            "",
            f"**Result:** {'PASS' if report.is_passing else 'FAIL'}",
            "",
        ]

        if report.secrets_report and report.secrets_report.findings:
            lines.extend([
                "## Secrets Detection",
                "",
                f"**Files Scanned:** {report.secrets_report.total_files_scanned}",
                f"**Secrets Found:** {report.secrets_report.secrets_found}",
                "",
            ])
            for finding in report.secrets_report.findings[:10]:
                lines.append(f"- `{finding.file_path}:{finding.line_number}` [{finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()}] {finding.pattern_name}: {finding.masked_value}")
            lines.append("")

        if report.dependency_report and report.dependency_report.vulnerabilities:
            lines.extend([
                "## Dependency Vulnerabilities",
                "",
                f"**Dependencies Analyzed:** {report.dependency_report.total_dependencies}",
                f"**Vulnerable Packages:** {report.dependency_report.vulnerable_dependencies}",
                "",
            ])
            for vuln in report.dependency_report.vulnerabilities[:10]:
                lines.append(f"- **{vuln.package_name}** {vuln.installed_version}: {vuln.title}")
            lines.append("")

        if report.vulnerability_report and report.vulnerability_report.findings:
            lines.extend([
                "## Code Vulnerabilities",
                "",
                f"**Files Scanned:** {report.vulnerability_report.total_files_scanned}",
                f"**Vulnerabilities Found:** {report.vulnerability_report.vulnerabilities_found}",
                "",
            ])
            for finding in report.vulnerability_report.findings[:10]:
                lines.append(f"- `{finding.file_path}:{finding.line_number}` [{finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()}] {finding.title}")
            lines.append("")

        if report.crypto_report and report.crypto_report.findings:
            lines.extend([
                "## Cryptographic Issues",
                "",
                f"**Files Scanned:** {report.crypto_report.total_files_scanned}",
                f"**Issues Found:** {report.crypto_report.issues_found}",
                "",
            ])
            for finding in report.crypto_report.findings[:10]:
                lines.append(f"- `{finding.file_path}:{finding.line_number}` {finding.description}")
            lines.append("")

        return "\n".join(lines)
