"""
CSP Analyzer helper functions.

Issue analysis and score calculation extracted from csp_analyzer.py.
"""

from Asgard.Freya.Security.models.security_header_models import CSPReport


def analyze_issues(report: CSPReport, allow_unsafe_eval: bool) -> None:
    """Analyze CSP for security issues and populate report warnings/issues."""
    if not report.default_src:
        report.warnings.append(
            "No default-src directive - consider adding one as a fallback"
        )

    script_src = report.script_src or report.default_src
    if script_src and script_src.has_unsafe_inline:
        if not report.uses_nonces and not report.uses_hashes:
            report.critical_issues.append(
                "Misconfigured Mitigation: script-src allows 'unsafe-inline' "
                "without nonces or hashes - if an XSS flaw exists, the "
                "browser will not block the injected script"
            )
            report.recommendations.append(
                "Use nonces or hashes instead of 'unsafe-inline' for scripts"
            )
        elif not report.uses_strict_dynamic:
            report.warnings.append(
                "script-src allows 'unsafe-inline' - "
                "consider using 'strict-dynamic' with nonces"
            )

    if script_src and script_src.has_unsafe_eval:
        if not allow_unsafe_eval:
            report.critical_issues.append(
                "script-src allows 'unsafe-eval' - "
                "allows dynamic code execution"
            )
            report.recommendations.append(
                "Remove 'unsafe-eval' and refactor code to avoid eval()"
            )

    style_src = report.style_src or report.default_src
    if style_src and style_src.has_unsafe_inline:
        report.warnings.append(
            "style-src allows 'unsafe-inline' - "
            "consider using hashes for inline styles"
        )

    for directive in report.directives:
        if directive.allows_any:
            if directive.name in ["script-src", "default-src"]:
                report.critical_issues.append(
                    f"{directive.name} allows any source (*) - "
                    "allows loading scripts from anywhere"
                )
            else:
                report.warnings.append(
                    f"{directive.name} allows any source (*)"
                )

    if not report.object_src and report.default_src:
        if "'none'" not in [v.lower() for v in report.default_src.values]:
            report.warnings.append(
                "object-src is not explicitly set to 'none' - "
                "consider blocking plugins"
            )
    elif report.object_src:
        if "'none'" not in [v.lower() for v in report.object_src.values]:
            report.warnings.append(
                "object-src should be 'none' to prevent plugin content"
            )

    if not report.base_uri:
        report.warnings.append("Missing Mitigation: base-uri - if markup injection exists, a <base> tag can redirect all relative URLs")
        report.recommendations.append("Add base-uri 'self' or 'none' to prevent base tag attacks")

    if not report.form_action:
        report.warnings.append("form-action not set - forms can submit to any URL")
        report.recommendations.append("Add form-action to restrict where forms can be submitted")

    if not report.frame_ancestors:
        report.warnings.append("frame-ancestors not set - use this instead of X-Frame-Options")
        report.recommendations.append("Add frame-ancestors to control embedding")

    for directive in report.directives:
        for value in directive.values:
            if value.lower() == "data:" and directive.name in ["script-src", "default-src"]:
                report.critical_issues.append(
                    f"{directive.name} allows data: URLs - can be used for XSS"
                )
            elif value.lower() == "blob:" and directive.name in ["script-src", "default-src"]:
                report.warnings.append(f"{directive.name} allows blob: URLs")

    for directive in report.directives:
        for value in directive.values:
            if value.lower().startswith("http:"):
                report.warnings.append(
                    f"{directive.name} allows insecure HTTP source: {value}"
                )


def calculate_score(report: CSPReport) -> float:
    """Calculate CSP security score (0-100)."""
    score = 100.0
    score -= len(report.critical_issues) * 20
    score -= len(report.warnings) * 5

    if report.uses_nonces or report.uses_hashes:
        score += 10
    if report.uses_strict_dynamic:
        score += 5
    if report.object_src:
        if "'none'" in [v.lower() for v in report.object_src.values]:
            score += 5
    if report.base_uri:
        score += 5
    if report.form_action:
        score += 5
    if report.frame_ancestors:
        score += 5

    return max(0, min(100, score))
