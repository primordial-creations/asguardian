def _wrap_block(text: str, indent: str = "  ", width: int = 66) -> list:
    """Wrap a paragraph into indented lines."""
    import textwrap
    return [indent + line for line in textwrap.wrap(text, width)]


def format_security_text(result) -> str:
    """Format security headers report as text (threat-mitigation framing)."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA THREAT MITIGATION REPORT")
    lines.append("=" * 70)
    lines.append("")

    disclaimer = getattr(result, "disclaimer", "")
    if disclaimer:
        lines.extend(_wrap_block(disclaimer))
        lines.append("")

    score_label = getattr(result, "score_label", "Frontend Defense-in-Depth Score")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  {score_label}: {result.security_score:.0f}/100")
    lines.append(f"  Resilience Grade: {result.security_grade}")
    lines.append("")
    lines.append(f"  Mitigations Present:  {result.headers_present}")
    lines.append(f"  Missing Mitigations:  {result.headers_missing}")
    lines.append(f"  Weak Mitigations:     {result.headers_weak}")
    lines.append("")

    headers_to_show = [
        ("CSP", result.content_security_policy),
        ("HSTS", result.strict_transport_security),
        ("X-Frame-Options", result.x_frame_options),
        ("X-Content-Type-Options", result.x_content_type_options),
        ("Referrer-Policy", result.referrer_policy),
        ("Permissions-Policy", result.permissions_policy),
        ("COOP", result.cross_origin_opener_policy),
        ("COEP", result.cross_origin_embedder_policy),
        ("CORP", result.cross_origin_resource_policy),
    ]

    lines.append("-" * 70)
    lines.append("  MITIGATION STATUS")
    lines.append("-" * 70)
    for name, header in headers_to_show:
        if header is None:
            lines.append(f"    {name}: NOT CHECKED")
            continue
        mitigation = getattr(header, "mitigation_status", None)
        status = (
            mitigation.value.upper() if mitigation is not None
            else header.status.value.upper()
        )
        lines.append(f"    {name}: {status}")
        threat_context = getattr(header, "threat_context", None)
        if threat_context:
            lines.extend(_wrap_block(threat_context, indent="      "))
        manual = getattr(header, "manual_verification", None)
        if manual:
            lines.extend(_wrap_block(manual, indent="      "))
    lines.append("")

    if result.critical_issues:
        lines.append("-" * 70)
        lines.append("  CRITICAL FINDINGS (Missing / Misconfigured Mitigations)")
        lines.append("-" * 70)
        for issue in result.critical_issues:
            lines.append(f"    - {issue}")
        lines.append("")

    if result.recommendations:
        lines.append("-" * 70)
        lines.append("  RECOMMENDATIONS")
        lines.append("-" * 70)
        for rec in result.recommendations[:10]:
            lines.append(f"    - {rec}")
        lines.append("")

    scope_matrix = getattr(result, "scope_matrix", None) or []
    if scope_matrix:
        lines.append("-" * 70)
        lines.append("  APPENDIX: SCOPE MATRIX (observable signal vs actual posture)")
        lines.append("-" * 70)
        for row in scope_matrix:
            lines.append(f"    {row.get('control', '')}")
            lines.extend(_wrap_block(
                "Tool validates: " + row.get("tool_validates", ""), indent="      "))
            lines.extend(_wrap_block(
                "Requires DAST/manual: " + row.get("requires_manual", ""),
                indent="      "))

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_sri_text(result) -> str:
    """Format Subresource Integrity report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA SUBRESOURCE INTEGRITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    if getattr(result, "disclaimer", ""):
        lines.extend(_wrap_block(result.disclaimer))
        lines.append("")
    lines.append(f"  URL:                        {result.url}")
    lines.append(f"  Cross-origin scripts:       {result.total_cross_origin_scripts}")
    lines.append(f"  Cross-origin stylesheets:   {result.total_cross_origin_stylesheets}")
    lines.append(f"  With valid SRI:             {result.protected_count}")
    if result.dynamic_scripts_detected:
        lines.append("  NOTE: dynamically injected scripts detected — SRI cannot")
        lines.append("  cover them; this signal is observable but incomplete.")
    lines.append("")
    if result.issues:
        lines.append("-" * 70)
        lines.append("  FINDINGS")
        lines.append("-" * 70)
        for finding in result.issues:
            lines.append(f"\n  [{finding.severity.upper()}] {finding.issue_type}")
            lines.extend(_wrap_block(finding.description, indent="    "))
            if finding.manual_verification:
                lines.extend(_wrap_block(finding.manual_verification, indent="    "))
    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


def format_mixed_content_text(result) -> str:
    """Format mixed-content report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA MIXED CONTENT REPORT")
    lines.append("=" * 70)
    lines.append("")
    if getattr(result, "disclaimer", ""):
        lines.extend(_wrap_block(result.disclaimer))
        lines.append("")
    lines.append(f"  URL:              {result.url}")
    if not result.page_is_https:
        lines.append("  Page is not HTTPS — mixed-content analysis does not apply;")
        lines.append("  the entire page travels unencrypted.")
        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)
    lines.append(f"  Requests observed: {result.total_requests}")
    lines.append(f"  Active mixed:      {result.active_count} (deterministic MITM exposure)")
    lines.append(f"  Passive mixed:     {result.passive_count}")
    lines.append("")
    if result.issues:
        lines.append("-" * 70)
        lines.append("  FINDINGS")
        lines.append("-" * 70)
        for finding in result.issues:
            lines.append(f"\n  [{finding.severity.upper()}] {finding.category}: {finding.url}")
            lines.extend(_wrap_block(finding.description, indent="    "))
    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


def format_csp_text(result) -> str:
    """Format CSP report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA CSP ANALYSIS REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Score:            {result.security_score:.0f}/100")
    lines.append(f"  Uses Nonces:      {'Yes' if result.uses_nonces else 'No'}")
    lines.append(f"  Uses Hashes:      {'Yes' if result.uses_hashes else 'No'}")
    lines.append(f"  Strict Dynamic:   {'Yes' if result.uses_strict_dynamic else 'No'}")
    lines.append("")

    if result.directives:
        lines.append("-" * 70)
        lines.append("  DIRECTIVES")
        lines.append("-" * 70)
        for directive in result.directives[:15]:
            values = " ".join(directive.values[:5])
            lines.append(f"    {directive.name}: {values}")
        lines.append("")

    if result.critical_issues:
        lines.append("-" * 70)
        lines.append("  CRITICAL ISSUES")
        lines.append("-" * 70)
        for issue in result.critical_issues:
            lines.append(f"    - {issue}")
        lines.append("")

    if result.warnings:
        lines.append("-" * 70)
        lines.append("  WARNINGS")
        lines.append("-" * 70)
        for warning in result.warnings:
            lines.append(f"    - {warning}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_console_text(result) -> str:
    """Format console report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA CONSOLE CAPTURE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Messages:   {result.total_messages}")
    lines.append(f"  Errors:           {result.error_count}")
    lines.append(f"  Warnings:         {result.warning_count}")
    lines.append("")

    if result.errors:
        lines.append("-" * 70)
        lines.append("  PAGE ERRORS")
        lines.append("-" * 70)
        for error in result.errors[:10]:
            lines.append(f"    [{error.name}] {error.message[:100]}")
        lines.append("")

    if result.unique_errors:
        lines.append("-" * 70)
        lines.append("  UNIQUE CONSOLE ERRORS")
        lines.append("-" * 70)
        for error in result.unique_errors[:10]:
            lines.append(f"    - {error[:80]}")
        lines.append("")

    if result.resource_errors:
        lines.append("-" * 70)
        lines.append("  FAILED RESOURCES")
        lines.append("-" * 70)
        for error in result.resource_errors[:10]:
            lines.append(f"    - {error.url}")
        lines.append("")

    if result.suggestions:
        lines.append("-" * 70)
        lines.append("  SUGGESTIONS")
        lines.append("-" * 70)
        for suggestion in result.suggestions:
            lines.append(f"    - {suggestion}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_links_text(result) -> str:
    """Format links report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA LINK VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Links:      {result.total_links}")
    lines.append(f"  Health Score:     {result.health_score:.0f}/100")
    lines.append("")
    lines.append("  STATUS")
    lines.append(f"    OK:             {result.ok_count}")
    lines.append(f"    Broken:         {result.broken_count}")
    lines.append(f"    Redirects:      {result.redirect_count}")
    lines.append(f"    Timeouts:       {result.timeout_count}")
    lines.append(f"    Errors:         {result.error_count}")
    lines.append("")

    if result.broken_links:
        lines.append("-" * 70)
        lines.append("  BROKEN LINKS")
        lines.append("-" * 70)
        for link in result.broken_links[:20]:
            status = f"({link.status_code})" if link.status_code else "(error)"
            lines.append(f"    [{link.severity.value.upper()}] {status} {link.url}")
            if link.link_text:
                lines.append(f"        Text: {link.link_text[:50]}")
        lines.append("")

    if result.redirect_chains:
        lines.append("-" * 70)
        lines.append("  REDIRECT CHAINS")
        lines.append("-" * 70)
        for chain in result.redirect_chains[:10]:
            lines.append(f"    {chain.chain_length} redirects: {chain.start_url}")
            lines.append(f"      -> {chain.final_url}")
        lines.append("")

    if result.suggestions:
        lines.append("-" * 70)
        lines.append("  SUGGESTIONS")
        lines.append("-" * 70)
        for suggestion in result.suggestions:
            lines.append(f"    - {suggestion}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
