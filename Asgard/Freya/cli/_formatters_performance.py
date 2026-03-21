def format_performance_text(result) -> str:
    """Format performance report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA PERFORMANCE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Score:            {result.performance_score:.0f}/100")
    lines.append(f"  Grade:            {result.performance_grade.value.upper()}")
    lines.append("")

    if result.page_load_metrics:
        metrics = result.page_load_metrics
        lines.append("-" * 70)
        lines.append("  TIMING METRICS")
        lines.append("-" * 70)
        lines.append(f"    TTFB:           {metrics.time_to_first_byte:.0f}ms")
        lines.append(f"    DOM Interactive:{metrics.dom_interactive:.0f}ms")
        lines.append(f"    DOM Loaded:     {metrics.dom_content_loaded:.0f}ms")
        lines.append(f"    Page Load:      {metrics.page_load:.0f}ms")
        lines.append("")

        if metrics.largest_contentful_paint:
            lines.append("-" * 70)
            lines.append("  CORE WEB VITALS")
            lines.append("-" * 70)
            lines.append(f"    LCP:            {metrics.largest_contentful_paint:.0f}ms")
        if metrics.first_contentful_paint:
            lines.append(f"    FCP:            {metrics.first_contentful_paint:.0f}ms")
        if metrics.cumulative_layout_shift is not None:
            lines.append(f"    CLS:            {metrics.cumulative_layout_shift:.3f}")
        lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.metric_name}")
            lines.append(f"    {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_load_time_text(result) -> str:
    """Format load time metrics as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA PAGE LOAD TIMING")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append("")
    lines.append("  TIMING BREAKDOWN")
    lines.append(f"    DNS Lookup:     {result.dns_lookup:.0f}ms")
    lines.append(f"    TCP Connection: {result.tcp_connection:.0f}ms")
    lines.append(f"    SSL Handshake:  {result.ssl_handshake:.0f}ms")
    lines.append(f"    TTFB:           {result.time_to_first_byte:.0f}ms")
    lines.append(f"    Content DL:     {result.content_download:.0f}ms")
    lines.append(f"    DOM Interactive:{result.dom_interactive:.0f}ms")
    lines.append(f"    DOM Loaded:     {result.dom_content_loaded:.0f}ms")
    lines.append(f"    Page Load:      {result.page_load:.0f}ms")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_resources_text(result) -> str:
    """Format resource timing as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA RESOURCE TIMING REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Resources:  {result.total_resources}")
    lines.append(f"  Total Size:       {result.total_size_kb:.0f}KB")
    lines.append("")
    lines.append("  BY TYPE")
    lines.append(f"    Scripts:        {result.script_count} ({result.script_size / 1024:.0f}KB)")
    lines.append(f"    Stylesheets:    {result.stylesheet_count} ({result.stylesheet_size / 1024:.0f}KB)")
    lines.append(f"    Images:         {result.image_count} ({result.image_size / 1024:.0f}KB)")
    lines.append(f"    Fonts:          {result.font_count} ({result.font_size / 1024:.0f}KB)")
    lines.append("")

    if result.large_resources:
        lines.append("-" * 70)
        lines.append("  LARGE RESOURCES (>100KB)")
        lines.append("-" * 70)
        for url in result.large_resources[:10]:
            lines.append(f"    {url}")
        lines.append("")

    if result.slow_resources:
        lines.append("-" * 70)
        lines.append("  SLOW RESOURCES (>500ms)")
        lines.append("-" * 70)
        for url in result.slow_resources[:10]:
            lines.append(f"    {url}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
