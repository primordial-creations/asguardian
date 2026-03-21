def format_images_text(result) -> str:
    """Format full image optimization report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA IMAGE OPTIMIZATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Images:     {result.total_images}")
    lines.append(f"  Optimization Score: {result.optimization_score:.0f}/100")
    lines.append("")
    lines.append("  ISSUE COUNTS")
    lines.append(f"    Critical:       {result.critical_count}")
    lines.append(f"    Warnings:       {result.warning_count}")
    lines.append(f"    Info:           {result.info_count}")
    lines.append("")
    lines.append("  ISSUE BREAKDOWN")
    lines.append(f"    Missing Alt:    {result.missing_alt_count}")
    lines.append(f"    No Lazy Load:   {result.missing_lazy_loading_count}")
    lines.append(f"    Non-Optimized:  {result.non_optimized_format_count}")
    lines.append(f"    No Dimensions:  {result.missing_dimensions_count}")
    lines.append(f"    Oversized:      {result.oversized_count}")
    lines.append(f"    No Srcset:      {result.missing_srcset_count}")
    lines.append("")

    if result.format_breakdown:
        lines.append("-" * 70)
        lines.append("  FORMAT BREAKDOWN")
        lines.append("-" * 70)
        for fmt, count in sorted(result.format_breakdown.items()):
            lines.append(f"    {fmt.upper():12} {count}")
        lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  ISSUES FOUND")
        lines.append("-" * 70)
        for issue in result.issues[:20]:
            severity = issue.severity.value.upper()
            lines.append(f"\n  [{severity}] {issue.issue_type.value}")
            lines.append(f"    Image: {issue.image_src[:60]}...")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix[:80]}")
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


def format_images_alt_text(result) -> str:
    """Format image alt text report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA IMAGE ALT TEXT REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Images:     {result.total_images}")
    lines.append(f"  Missing Alt:      {result.missing_alt_count}")
    lines.append(f"  Empty Alt:        {result.empty_alt_count}")
    lines.append("")

    alt_issues = [
        i for i in result.issues
        if i.issue_type.value in ["missing_alt", "empty_alt"]
    ]

    if alt_issues:
        lines.append("-" * 70)
        lines.append("  ALT TEXT ISSUES")
        lines.append("-" * 70)
        for issue in alt_issues[:20]:
            severity = issue.severity.value.upper()
            lines.append(f"\n  [{severity}] {issue.description}")
            lines.append(f"    Image: {issue.image_src[:60]}")
            if issue.wcag_reference:
                lines.append(f"    WCAG: {issue.wcag_reference}")
            lines.append(f"    Fix: {issue.suggested_fix}")
        lines.append("")
    else:
        lines.append("  No alt text issues found.")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def format_images_performance_text(result) -> str:
    """Format image performance report as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA IMAGE PERFORMANCE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Images:     {result.total_images}")
    lines.append(f"  Above Fold:       {result.images_above_fold}")
    lines.append(f"  With Lazy Load:   {result.images_with_lazy_loading}")
    lines.append(f"  With Srcset:      {result.images_with_srcset}")
    lines.append(f"  Optimized Format: {result.optimized_format_count}")
    lines.append("")
    lines.append("  PERFORMANCE ISSUES")
    lines.append(f"    No Lazy Load:   {result.missing_lazy_loading_count}")
    lines.append(f"    Non-Optimized:  {result.non_optimized_format_count}")
    lines.append(f"    No Dimensions:  {result.missing_dimensions_count}")
    lines.append(f"    Oversized:      {result.oversized_count}")
    lines.append(f"    No Srcset:      {result.missing_srcset_count}")
    lines.append("")

    perf_types = [
        "missing_lazy_loading", "non_optimized_format",
        "missing_dimensions", "oversized_image", "missing_srcset"
    ]
    perf_issues = [i for i in result.issues if i.issue_type.value in perf_types]

    if perf_issues:
        lines.append("-" * 70)
        lines.append("  PERFORMANCE ISSUES DETAIL")
        lines.append("-" * 70)
        for issue in perf_issues[:20]:
            severity = issue.severity.value.upper()
            lines.append(f"\n  [{severity}] {issue.issue_type.value.replace('_', ' ').title()}")
            lines.append(f"    Image: {issue.image_src[:60]}")
            lines.append(f"    Impact: {issue.impact}")
            lines.append(f"    Fix: {issue.suggested_fix[:80]}")
        lines.append("")
    else:
        lines.append("  No performance issues found.")
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
