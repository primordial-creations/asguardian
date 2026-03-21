def format_security_text(result) -> str:
    """Format security headers report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA SECURITY HEADERS REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Score:            {result.security_score:.0f}/100")
    lines.append(f"  Grade:            {result.security_grade}")
    lines.append("")
    lines.append(f"  Headers Present:  {result.headers_present}")
    lines.append(f"  Headers Missing:  {result.headers_missing}")
    lines.append(f"  Headers Weak:     {result.headers_weak}")
    lines.append("")

    headers_to_show = [
        ("CSP", result.content_security_policy),
        ("HSTS", result.strict_transport_security),
        ("X-Frame-Options", result.x_frame_options),
        ("X-Content-Type-Options", result.x_content_type_options),
        ("Referrer-Policy", result.referrer_policy),
    ]

    lines.append("-" * 70)
    lines.append("  HEADERS STATUS")
    lines.append("-" * 70)
    for name, header in headers_to_show:
        if header:
            status = header.status.value.upper()
            lines.append(f"    {name}: {status}")
        else:
            lines.append(f"    {name}: NOT CHECKED")
    lines.append("")

    if result.critical_issues:
        lines.append("-" * 70)
        lines.append("  CRITICAL ISSUES")
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
