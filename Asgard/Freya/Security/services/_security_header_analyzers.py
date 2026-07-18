"""Freya Security Header analyzers."""

import httpx

from Asgard.Freya.Security.models.security_header_models import (
    SecurityConfig,
    SecurityHeader,
    SecurityHeaderReport,
    SecurityHeaderSeverity,
    SecurityHeaderStatus,
)


def analyze_csp(headers: httpx.Headers, config: SecurityConfig) -> SecurityHeader:
    """Analyze Content-Security-Policy header."""
    header = SecurityHeader(name="Content-Security-Policy", status=SecurityHeaderStatus.MISSING)
    csp_value = headers.get("Content-Security-Policy")
    csp_report_only = headers.get("Content-Security-Policy-Report-Only")
    if csp_value:
        header.value = csp_value
        header.status = SecurityHeaderStatus.PRESENT
        if "'unsafe-inline'" in csp_value and not config.allow_unsafe_inline:
            header.is_secure = False
            header.issues.append("Misconfigured Mitigation: CSP contains 'unsafe-inline' (self-sabotaging: inline injection is not blocked)")
        if "'unsafe-eval'" in csp_value and not config.allow_unsafe_eval:
            header.is_secure = False
            header.issues.append("Misconfigured Mitigation: CSP contains 'unsafe-eval' (self-sabotaging: eval-based injection is not blocked)")
        if " * " in csp_value or csp_value.endswith(" *"):
            if not config.allow_wildcard_sources:
                header.is_secure = False
                header.issues.append("Misconfigured Mitigation: CSP contains a wildcard source (self-sabotaging: any origin may serve content)")
    elif csp_report_only:
        header.value = csp_report_only
        header.status = SecurityHeaderStatus.WEAK
        header.is_secure = False
        header.issues.append("CSP is report-only mode, not enforced")
        header.recommendations.append("Switch to Content-Security-Policy header for enforcement")
    else:
        header.is_secure = False
        header.issues.append("Missing Mitigation: Content-Security-Policy")
        header.recommendations.append("Add Content-Security-Policy so the browser can contain an XSS payload if one exists")
    return header


def analyze_hsts(headers: httpx.Headers, config: SecurityConfig) -> SecurityHeader:
    """Analyze Strict-Transport-Security header."""
    header = SecurityHeader(name="Strict-Transport-Security", status=SecurityHeaderStatus.MISSING)
    hsts_value = headers.get("Strict-Transport-Security")
    if hsts_value:
        header.value = hsts_value
        header.status = SecurityHeaderStatus.PRESENT
        header.is_secure = True
        if "max-age=" in hsts_value:
            try:
                max_age = int(hsts_value.split("max-age=")[1].split(";")[0].split(",")[0])
                if max_age < config.min_hsts_max_age:
                    header.status = SecurityHeaderStatus.WEAK
                    header.is_secure = False
                    header.issues.append(f"HSTS max-age ({max_age}s) is below recommended ({config.min_hsts_max_age}s)")
            except (ValueError, IndexError):
                header.issues.append("Could not parse max-age value")
        if "includeSubDomains" not in hsts_value:
            if config.require_hsts_subdomains:
                header.is_secure = False
                header.issues.append("HSTS missing includeSubDomains directive")
                header.recommendations.append("Add includeSubDomains to protect subdomains")
        if "preload" not in hsts_value:
            if config.require_hsts_preload:
                header.issues.append("HSTS missing preload directive")
                header.recommendations.append("Consider adding preload directive and submitting to HSTS preload list")
    else:
        header.is_secure = False
        header.issues.append("Missing Mitigation: Strict-Transport-Security")
        header.recommendations.append("Add HSTS so browsers refuse plain-HTTP connections after first contact")
    return header


def extract_hsts_details(headers: httpx.Headers, report: SecurityHeaderReport) -> None:
    """Extract HSTS configuration details."""
    hsts_value = headers.get("Strict-Transport-Security", "")
    if "max-age=" in hsts_value:
        try:
            max_age = int(hsts_value.split("max-age=")[1].split(";")[0].split(",")[0])
            report.hsts_max_age = max_age
        except (ValueError, IndexError):
            pass
    report.hsts_include_subdomains = "includeSubDomains" in hsts_value
    report.hsts_preload = "preload" in hsts_value


def analyze_frame_options(headers: httpx.Headers) -> SecurityHeader:
    """Analyze X-Frame-Options header."""
    header = SecurityHeader(name="X-Frame-Options", status=SecurityHeaderStatus.MISSING)
    value = headers.get("X-Frame-Options")
    if value:
        header.value = value
        header.status = SecurityHeaderStatus.PRESENT
        value_upper = value.upper()
        if value_upper in ["DENY", "SAMEORIGIN"]:
            header.is_secure = True
        elif "ALLOW-FROM" in value_upper:
            header.is_secure = True
            header.issues.append("ALLOW-FROM is deprecated and not supported by all browsers")
            header.recommendations.append("Use CSP frame-ancestors instead of ALLOW-FROM")
        else:
            header.status = SecurityHeaderStatus.INVALID
            header.is_secure = False
            header.issues.append(f"Invalid X-Frame-Options value: {value}")
    else:
        header.is_secure = False
        header.issues.append("Missing Mitigation: X-Frame-Options (clickjacking containment)")
        header.recommendations.append("Add X-Frame-Options: DENY or SAMEORIGIN to prevent clickjacking")
    return header


def analyze_content_type_options(headers: httpx.Headers) -> SecurityHeader:
    """Analyze X-Content-Type-Options header."""
    header = SecurityHeader(name="X-Content-Type-Options", status=SecurityHeaderStatus.MISSING)
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
        header.issues.append("Missing Mitigation: X-Content-Type-Options (MIME-sniffing containment)")
        header.recommendations.append("Add X-Content-Type-Options: nosniff to prevent MIME sniffing")
    return header


def analyze_xss_protection(headers: httpx.Headers) -> SecurityHeader:
    """Analyze X-XSS-Protection header."""
    header = SecurityHeader(name="X-XSS-Protection", status=SecurityHeaderStatus.MISSING)
    value = headers.get("X-XSS-Protection")
    if value:
        header.value = value
        header.status = SecurityHeaderStatus.PRESENT
        if value.startswith("0"):
            header.is_secure = True
            header.recommendations.append("X-XSS-Protection is deprecated; rely on CSP instead")
        elif value.startswith("1"):
            header.is_secure = True
            if "mode=block" not in value:
                header.recommendations.append("Consider adding mode=block for better protection")
    else:
        header.is_secure = True
        header.recommendations.append("X-XSS-Protection is deprecated; use CSP instead")
    return header


def analyze_referrer_policy(headers: httpx.Headers) -> SecurityHeader:
    """Analyze Referrer-Policy header."""
    header = SecurityHeader(name="Referrer-Policy", status=SecurityHeaderStatus.MISSING)
    value = headers.get("Referrer-Policy")
    secure_values = [
        "no-referrer", "no-referrer-when-downgrade", "same-origin", "origin",
        "strict-origin", "origin-when-cross-origin", "strict-origin-when-cross-origin",
    ]
    if value:
        header.value = value
        header.status = SecurityHeaderStatus.PRESENT
        if value.lower() in [v.lower() for v in secure_values]:
            header.is_secure = True
        elif value.lower() == "unsafe-url":
            header.is_secure = False
            header.issues.append("Referrer-Policy: unsafe-url leaks full URL including path")
            header.recommendations.append("Use a more restrictive policy like strict-origin-when-cross-origin")
        else:
            header.status = SecurityHeaderStatus.INVALID
            header.is_secure = False
            header.issues.append(f"Unknown Referrer-Policy value: {value}")
    else:
        header.is_secure = False
        header.issues.append("Missing Mitigation: Referrer-Policy (URL leakage containment)")
        header.recommendations.append("Add Referrer-Policy: strict-origin-when-cross-origin")
    return header


def analyze_permissions_policy(headers: httpx.Headers) -> SecurityHeader:
    """Analyze Permissions-Policy header."""
    header = SecurityHeader(name="Permissions-Policy", status=SecurityHeaderStatus.MISSING)
    value = headers.get("Permissions-Policy")
    legacy_value = headers.get("Feature-Policy")
    if value:
        header.value = value
        header.status = SecurityHeaderStatus.PRESENT
        header.is_secure = True
    elif legacy_value:
        header.value = legacy_value
        header.status = SecurityHeaderStatus.WEAK
        header.is_secure = True
        header.issues.append("Using deprecated Feature-Policy header")
        header.recommendations.append("Migrate to Permissions-Policy header")
    else:
        header.is_secure = True
        header.recommendations.append("Consider adding Permissions-Policy to restrict browser features")
    return header


def _analyze_cross_origin_header(headers: httpx.Headers, name: str, recommendation: str) -> SecurityHeader:
    """Analyze a cross-origin policy header (COOP/COEP/CORP)."""
    header = SecurityHeader(name=name, status=SecurityHeaderStatus.MISSING)
    value = headers.get(name)
    if value:
        header.value = value
        header.status = SecurityHeaderStatus.PRESENT
        header.is_secure = True
    else:
        header.is_secure = True
        header.recommendations.append(recommendation)
    return header


def analyze_coop(headers: httpx.Headers) -> SecurityHeader:
    """Analyze Cross-Origin-Opener-Policy header."""
    return _analyze_cross_origin_header(headers, "Cross-Origin-Opener-Policy", "Consider adding COOP for process isolation")


def analyze_coep(headers: httpx.Headers) -> SecurityHeader:
    """Analyze Cross-Origin-Embedder-Policy header."""
    return _analyze_cross_origin_header(headers, "Cross-Origin-Embedder-Policy", "Consider adding COEP for cross-origin isolation")


def analyze_corp(headers: httpx.Headers) -> SecurityHeader:
    """Analyze Cross-Origin-Resource-Policy header."""
    return _analyze_cross_origin_header(headers, "Cross-Origin-Resource-Policy", "Consider adding CORP to control resource loading")
