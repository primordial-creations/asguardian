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
    SecurityHeader,
    SecurityHeaderReport,
    SecurityHeaderSeverity,
    SecurityHeaderStatus,
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

            # Analyze each security header
            if self.config.check_csp:
                report.content_security_policy = self._analyze_csp(response.headers)
                csp_value = response.headers.get("Content-Security-Policy")
                if csp_value:
                    report.csp_report = self.csp_analyzer.analyze(csp_value)

            if self.config.check_hsts:
                report.strict_transport_security = self._analyze_hsts(response.headers)
                self._extract_hsts_details(response.headers, report)

            if self.config.check_frame_options:
                report.x_frame_options = self._analyze_frame_options(response.headers)

            if self.config.check_content_type_options:
                report.x_content_type_options = self._analyze_content_type_options(
                    response.headers
                )

            if self.config.check_xss_protection:
                report.x_xss_protection = self._analyze_xss_protection(response.headers)

            if self.config.check_referrer_policy:
                report.referrer_policy = self._analyze_referrer_policy(response.headers)

            if self.config.check_permissions_policy:
                report.permissions_policy = self._analyze_permissions_policy(
                    response.headers
                )

            if self.config.check_cross_origin:
                report.cross_origin_opener_policy = self._analyze_coop(response.headers)
                report.cross_origin_embedder_policy = self._analyze_coep(response.headers)
                report.cross_origin_resource_policy = self._analyze_corp(response.headers)

            # Calculate summary statistics
            self._calculate_summary(report)

        except httpx.HTTPError as e:
            report.critical_issues.append(f"Failed to fetch URL: {str(e)}")

        report.analysis_duration_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return report

    def _analyze_csp(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze Content-Security-Policy header."""
        header = SecurityHeader(name="Content-Security-Policy", status=SecurityHeaderStatus.MISSING)

        csp_value = headers.get("Content-Security-Policy")
        csp_report_only = headers.get("Content-Security-Policy-Report-Only")

        if csp_value:
            header.value = csp_value
            header.status = SecurityHeaderStatus.PRESENT

            # Check for unsafe directives
            if "'unsafe-inline'" in csp_value and not self.config.allow_unsafe_inline:
                header.is_secure = False
                header.issues.append("CSP contains 'unsafe-inline'")

            if "'unsafe-eval'" in csp_value and not self.config.allow_unsafe_eval:
                header.is_secure = False
                header.issues.append("CSP contains 'unsafe-eval'")

            if " * " in csp_value or csp_value.endswith(" *"):
                if not self.config.allow_wildcard_sources:
                    header.is_secure = False
                    header.issues.append("CSP contains wildcard source")

        elif csp_report_only:
            header.value = csp_report_only
            header.status = SecurityHeaderStatus.WEAK
            header.is_secure = False
            header.issues.append(
                "CSP is report-only mode, not enforced"
            )
            header.recommendations.append(
                "Switch to Content-Security-Policy header for enforcement"
            )

        else:
            header.is_secure = False
            header.issues.append("Content-Security-Policy header is missing")
            header.recommendations.append(
                "Add Content-Security-Policy header to prevent XSS attacks"
            )

        return header

    def _analyze_hsts(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze Strict-Transport-Security header."""
        header = SecurityHeader(
            name="Strict-Transport-Security",
            status=SecurityHeaderStatus.MISSING,
        )

        hsts_value = headers.get("Strict-Transport-Security")

        if hsts_value:
            header.value = hsts_value
            header.status = SecurityHeaderStatus.PRESENT
            header.is_secure = True

            # Check max-age
            if "max-age=" in hsts_value:
                try:
                    max_age = int(
                        hsts_value.split("max-age=")[1].split(";")[0].split(",")[0]
                    )
                    if max_age < self.config.min_hsts_max_age:
                        header.status = SecurityHeaderStatus.WEAK
                        header.is_secure = False
                        header.issues.append(
                            f"HSTS max-age ({max_age}s) is below recommended "
                            f"({self.config.min_hsts_max_age}s)"
                        )
                except (ValueError, IndexError):
                    header.issues.append("Could not parse max-age value")

            # Check includeSubDomains
            if "includeSubDomains" not in hsts_value:
                if self.config.require_hsts_subdomains:
                    header.is_secure = False
                    header.issues.append("HSTS missing includeSubDomains directive")
                    header.recommendations.append(
                        "Add includeSubDomains to protect subdomains"
                    )

            # Check preload
            if "preload" not in hsts_value:
                if self.config.require_hsts_preload:
                    header.issues.append("HSTS missing preload directive")
                    header.recommendations.append(
                        "Consider adding preload directive and submitting to HSTS preload list"
                    )

        else:
            header.is_secure = False
            header.issues.append("Strict-Transport-Security header is missing")
            header.recommendations.append(
                "Add HSTS header to enforce HTTPS connections"
            )

        return header

    def _extract_hsts_details(
        self, headers: httpx.Headers, report: SecurityHeaderReport
    ) -> None:
        """Extract HSTS configuration details."""
        hsts_value = headers.get("Strict-Transport-Security", "")

        if "max-age=" in hsts_value:
            try:
                max_age = int(
                    hsts_value.split("max-age=")[1].split(";")[0].split(",")[0]
                )
                report.hsts_max_age = max_age
            except (ValueError, IndexError):
                pass

        report.hsts_include_subdomains = "includeSubDomains" in hsts_value
        report.hsts_preload = "preload" in hsts_value

    def _analyze_frame_options(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze X-Frame-Options header."""
        header = SecurityHeader(
            name="X-Frame-Options",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("X-Frame-Options")

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT

            value_upper = value.upper()
            if value_upper in ["DENY", "SAMEORIGIN"]:
                header.is_secure = True
            elif "ALLOW-FROM" in value_upper:
                header.is_secure = True
                header.issues.append(
                    "ALLOW-FROM is deprecated and not supported by all browsers"
                )
                header.recommendations.append(
                    "Use CSP frame-ancestors instead of ALLOW-FROM"
                )
            else:
                header.status = SecurityHeaderStatus.INVALID
                header.is_secure = False
                header.issues.append(f"Invalid X-Frame-Options value: {value}")

        else:
            header.is_secure = False
            header.issues.append("X-Frame-Options header is missing")
            header.recommendations.append(
                "Add X-Frame-Options: DENY or SAMEORIGIN to prevent clickjacking"
            )

        return header

    def _analyze_content_type_options(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze X-Content-Type-Options header."""
        header = SecurityHeader(
            name="X-Content-Type-Options",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("X-Content-Type-Options")

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT

            if value.lower() == "nosniff":
                header.is_secure = True
            else:
                header.status = SecurityHeaderStatus.INVALID
                header.is_secure = False
                header.issues.append(f"Invalid value: {value}, expected 'nosniff'")

        else:
            header.is_secure = False
            header.issues.append("X-Content-Type-Options header is missing")
            header.recommendations.append(
                "Add X-Content-Type-Options: nosniff to prevent MIME sniffing"
            )

        return header

    def _analyze_xss_protection(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze X-XSS-Protection header."""
        header = SecurityHeader(
            name="X-XSS-Protection",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("X-XSS-Protection")

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT

            # Modern recommendation is to disable it (0) and rely on CSP
            if value.startswith("0"):
                header.is_secure = True
                header.recommendations.append(
                    "X-XSS-Protection is deprecated; rely on CSP instead"
                )
            elif value.startswith("1"):
                header.is_secure = True
                if "mode=block" in value:
                    pass  # Good configuration
                else:
                    header.recommendations.append(
                        "Consider adding mode=block for better protection"
                    )
        else:
            # Not having this header is fine if CSP is in place
            header.is_secure = True
            header.recommendations.append(
                "X-XSS-Protection is deprecated; use CSP instead"
            )

        return header

    def _analyze_referrer_policy(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze Referrer-Policy header."""
        header = SecurityHeader(
            name="Referrer-Policy",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("Referrer-Policy")

        secure_values = [
            "no-referrer",
            "no-referrer-when-downgrade",
            "same-origin",
            "origin",
            "strict-origin",
            "origin-when-cross-origin",
            "strict-origin-when-cross-origin",
        ]

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT

            if value.lower() in [v.lower() for v in secure_values]:
                header.is_secure = True
            elif value.lower() == "unsafe-url":
                header.is_secure = False
                header.issues.append(
                    "Referrer-Policy: unsafe-url leaks full URL including path"
                )
                header.recommendations.append(
                    "Use a more restrictive policy like strict-origin-when-cross-origin"
                )
            else:
                header.status = SecurityHeaderStatus.INVALID
                header.is_secure = False
                header.issues.append(f"Unknown Referrer-Policy value: {value}")

        else:
            header.is_secure = False
            header.issues.append("Referrer-Policy header is missing")
            header.recommendations.append(
                "Add Referrer-Policy: strict-origin-when-cross-origin"
            )

        return header

    def _analyze_permissions_policy(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze Permissions-Policy header."""
        header = SecurityHeader(
            name="Permissions-Policy",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("Permissions-Policy")
        # Also check for the deprecated Feature-Policy
        legacy_value = headers.get("Feature-Policy")

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT
            header.is_secure = True
            # Could add more detailed analysis here

        elif legacy_value:
            header.value = legacy_value
            header.status = SecurityHeaderStatus.WEAK
            header.is_secure = True
            header.issues.append(
                "Using deprecated Feature-Policy header"
            )
            header.recommendations.append(
                "Migrate to Permissions-Policy header"
            )

        else:
            # Not critical but recommended
            header.is_secure = True
            header.recommendations.append(
                "Consider adding Permissions-Policy to restrict browser features"
            )

        return header

    def _analyze_coop(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze Cross-Origin-Opener-Policy header."""
        header = SecurityHeader(
            name="Cross-Origin-Opener-Policy",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("Cross-Origin-Opener-Policy")

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT
            header.is_secure = True

        else:
            header.is_secure = True  # Not critical
            header.recommendations.append(
                "Consider adding COOP for process isolation"
            )

        return header

    def _analyze_coep(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze Cross-Origin-Embedder-Policy header."""
        header = SecurityHeader(
            name="Cross-Origin-Embedder-Policy",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("Cross-Origin-Embedder-Policy")

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT
            header.is_secure = True

        else:
            header.is_secure = True  # Not critical
            header.recommendations.append(
                "Consider adding COEP for cross-origin isolation"
            )

        return header

    def _analyze_corp(self, headers: httpx.Headers) -> SecurityHeader:
        """Analyze Cross-Origin-Resource-Policy header."""
        header = SecurityHeader(
            name="Cross-Origin-Resource-Policy",
            status=SecurityHeaderStatus.MISSING,
        )

        value = headers.get("Cross-Origin-Resource-Policy")

        if value:
            header.value = value
            header.status = SecurityHeaderStatus.PRESENT
            header.is_secure = True

        else:
            header.is_secure = True  # Not critical
            header.recommendations.append(
                "Consider adding CORP to control resource loading"
            )

        return header

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
