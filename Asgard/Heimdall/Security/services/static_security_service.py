"""
Heimdall Static Security Analysis Service

Service for comprehensive static security analysis combining multiple
security checks into a unified analysis.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Security.models.security_models import (
    SecurityReport,
    SecurityScanConfig,
)
from Asgard.Heimdall.Security.services._static_security_report import (
    generate_json_report,
    generate_markdown_report,
    get_summary,
)
from Asgard.Heimdall.Security.services._security_scan_helpers import (
    scan_access_only,
    scan_auth_only,
    scan_container_only,
    scan_crypto_only,
    scan_dependencies_only,
    scan_headers_only,
    scan_infrastructure_only,
    scan_secrets_only,
    scan_tls_only,
    scan_vulnerabilities_only,
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
            except Exception:
                pass

        if self.config.scan_dependencies:
            try:
                report.dependency_report = self.dependency_service.scan(path)
            except Exception:
                pass

        if self.config.scan_vulnerabilities:
            try:
                report.vulnerability_report = self.injection_service.scan(path)
            except Exception:
                pass

        if self.config.scan_crypto:
            try:
                report.crypto_report = self.crypto_service.scan(path)
            except Exception:
                pass

        if self.config.scan_access:
            try:
                report.access_report = self.access_analyzer.scan(path)
            except Exception:
                pass

        if self.config.scan_auth:
            try:
                report.auth_report = self.auth_analyzer.scan(path)
            except Exception:
                pass

        if self.config.scan_headers:
            try:
                report.headers_report = self.headers_analyzer.scan(path)
            except Exception:
                pass

        if self.config.scan_tls:
            try:
                report.tls_report = self.tls_analyzer.scan(path)
            except Exception:
                pass

        if self.config.scan_container:
            try:
                report.container_report = self.container_analyzer.scan(path)
            except Exception:
                pass

        if self.config.scan_infrastructure:
            try:
                report.infrastructure_report = self.infrastructure_analyzer.scan(path)
            except Exception:
                pass

        report.scan_duration_seconds = time.time() - start_time
        report.scanned_at = datetime.now()
        report.calculate_totals()

        return report

    def scan_secrets_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for secrets."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_secrets_only(path, self.config, self.secrets_service)

    def scan_dependencies_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for dependency vulnerabilities."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_dependencies_only(path, self.config, self.dependency_service)

    def scan_vulnerabilities_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for injection vulnerabilities."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_vulnerabilities_only(path, self.config, self.injection_service)

    def scan_crypto_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for cryptographic issues."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_crypto_only(path, self.config, self.crypto_service)

    def scan_access_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for access control issues."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_access_only(path, self.config, self.access_analyzer)

    def scan_auth_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for authentication issues."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_auth_only(path, self.config, self.auth_analyzer)

    def scan_headers_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for security header issues."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_headers_only(path, self.config, self.headers_analyzer)

    def scan_tls_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for TLS/SSL issues."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_tls_only(path, self.config, self.tls_analyzer)

    def scan_container_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for container security issues."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_container_only(path, self.config, self.container_analyzer)

    def scan_infrastructure_only(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Scan only for infrastructure security issues."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return scan_infrastructure_only(path, self.config, self.infrastructure_analyzer)

    def get_summary(self, report: SecurityReport) -> str:
        """Generate a text summary of the security report."""
        return get_summary(report)

    def analyze(self, scan_path: Optional[Path] = None) -> SecurityReport:
        """Perform comprehensive security analysis (delegates to scan())."""
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
            return generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(report)
        elif format_lower == "text":
            return get_summary(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
