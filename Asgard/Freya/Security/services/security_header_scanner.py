"""
Freya Security Header Scanner

Scans HTTP response headers for security configuration including
CSP, HSTS, X-Frame-Options, and other security headers.
"""

from datetime import datetime
from typing import Dict, Optional

import httpx

from Asgard.Freya.Security.models.security_header_models import (
    SecurityConfig,
    SecurityHeaderReport,
    SecurityHeaderStatus,
)
from Asgard.Freya.Security.services._security_header_analyzers import (
    analyze_coep,
    analyze_coop,
    analyze_corp,
    analyze_content_type_options,
    analyze_csp,
    analyze_frame_options,
    analyze_hsts,
    analyze_permissions_policy,
    analyze_referrer_policy,
    analyze_xss_protection,
    extract_hsts_details,
)
from Asgard.Freya.Security.services.csp_analyzer import CSPAnalyzer


class SecurityHeaderScanner:
    """
    Scans security headers for a URL.

    Checks for presence and proper configuration of security headers.
    """

    # List of security headers to check
    SECURITY_HEADERS = [
        "Content-Security-Policy",
        "Content-Security-Policy-Report-Only",
        "Strict-Transport-Security",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Embedder-Policy",
        "Cross-Origin-Resource-Policy",
    ]

    def __init__(self, config: Optional[SecurityConfig] = None):
        """
        Initialize the security header scanner.

        Args:
            config: Security configuration
        """
        self.config = config or SecurityConfig()
        self.csp_analyzer = CSPAnalyzer(config)
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            )
        return self._http_client

    async def scan(self, url: str) -> SecurityHeaderReport:
        """
        Scan security headers for a URL.

        Args:
            url: URL to scan

        Returns:
            SecurityHeaderReport with analysis results
        """
        start_time = datetime.now()

        report = SecurityHeaderReport(url=url)

        try:
            client = await self._get_client()
            response = await client.get(url)

            # Store all headers
            report.all_headers = dict(response.headers)

            if self.config.check_csp:
                report.content_security_policy = analyze_csp(response.headers, self.config)
                csp_value = response.headers.get("Content-Security-Policy")
                if csp_value:
                    report.csp_report = self.csp_analyzer.analyze(csp_value)

            if self.config.check_hsts:
                report.strict_transport_security = analyze_hsts(response.headers, self.config)
                extract_hsts_details(response.headers, report)

            if self.config.check_frame_options:
                report.x_frame_options = analyze_frame_options(response.headers)

            if self.config.check_content_type_options:
                report.x_content_type_options = analyze_content_type_options(response.headers)

            if self.config.check_xss_protection:
                report.x_xss_protection = analyze_xss_protection(response.headers)

            if self.config.check_referrer_policy:
                report.referrer_policy = analyze_referrer_policy(response.headers)

            if self.config.check_permissions_policy:
                report.permissions_policy = analyze_permissions_policy(response.headers)

            if self.config.check_cross_origin:
                report.cross_origin_opener_policy = analyze_coop(response.headers)
                report.cross_origin_embedder_policy = analyze_coep(response.headers)
                report.cross_origin_resource_policy = analyze_corp(response.headers)

            # Calculate summary statistics
            self._calculate_summary(report)

        except httpx.HTTPError as e:
            report.critical_issues.append(f"Failed to fetch URL: {str(e)}")

        report.analysis_duration_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return report

    def _calculate_summary(self, report: SecurityHeaderReport) -> None:
        """Calculate summary statistics for the report."""
        headers = [
            report.content_security_policy,
            report.strict_transport_security,
            report.x_frame_options,
            report.x_content_type_options,
            report.x_xss_protection,
            report.referrer_policy,
            report.permissions_policy,
            report.cross_origin_opener_policy,
            report.cross_origin_embedder_policy,
            report.cross_origin_resource_policy,
        ]

        report.total_headers_checked = len([h for h in headers if h is not None])

        for header in headers:
            if header is None:
                continue

            if header.status == SecurityHeaderStatus.PRESENT:
                report.headers_present += 1
            elif header.status == SecurityHeaderStatus.MISSING:
                report.headers_missing += 1
            elif header.status == SecurityHeaderStatus.WEAK:
                report.headers_weak += 1

            # Collect issues
            if not header.is_secure:
                for issue in header.issues:
                    if "missing" in issue.lower():
                        report.warnings.append(f"{header.name}: {issue}")
                    else:
                        report.critical_issues.append(f"{header.name}: {issue}")

            report.recommendations.extend(
                f"{header.name}: {rec}" for rec in header.recommendations
            )

        # Calculate score and grade
        report.security_score = self._calculate_score(report)
        report.security_grade = self._score_to_grade(report.security_score)

    def _calculate_score(self, report: SecurityHeaderReport) -> float:
        """Calculate security score (0-100)."""
        score: float = 0
        max_score = 100

        # CSP: 25 points
        if report.content_security_policy:
            if report.content_security_policy.status == SecurityHeaderStatus.PRESENT:
                if report.content_security_policy.is_secure:
                    score += 25
                else:
                    score += 15
            elif report.content_security_policy.status == SecurityHeaderStatus.WEAK:
                score += 10

        # HSTS: 25 points
        if report.strict_transport_security:
            if report.strict_transport_security.status == SecurityHeaderStatus.PRESENT:
                if report.strict_transport_security.is_secure:
                    score += 25
                else:
                    score += 15

        # X-Frame-Options: 15 points
        if report.x_frame_options:
            if report.x_frame_options.status == SecurityHeaderStatus.PRESENT:
                score += 15

        # X-Content-Type-Options: 10 points
        if report.x_content_type_options:
            if report.x_content_type_options.status == SecurityHeaderStatus.PRESENT:
                score += 10

        # Referrer-Policy: 10 points
        if report.referrer_policy:
            if report.referrer_policy.status == SecurityHeaderStatus.PRESENT:
                if report.referrer_policy.is_secure:
                    score += 10
                else:
                    score += 5

        # Permissions-Policy: 5 points
        if report.permissions_policy:
            if report.permissions_policy.status == SecurityHeaderStatus.PRESENT:
                score += 5

        # Cross-origin policies: 10 points total
        cross_origin_score: float = 0
        for header in [
            report.cross_origin_opener_policy,
            report.cross_origin_embedder_policy,
            report.cross_origin_resource_policy,
        ]:
            if header and header.status == SecurityHeaderStatus.PRESENT:
                cross_origin_score += 3.33
        score += min(10, cross_origin_score)

        return min(100, score)

    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
