def format_layout_text(result) -> str:
    """Format layout validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA LAYOUT VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Issues:       {len(result.issues)}")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  LAYOUT ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_style_text(result) -> str:
    """Format style validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA STYLE VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Issues:       {len(result.issues)}")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  STYLE ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Description: {issue.description}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_breakpoint_text(result) -> str:
    """Format breakpoint test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA BREAKPOINT TEST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Breakpoints:      {len(result.breakpoints_tested)}")
    lines.append(f"  Total Issues:     {result.total_issues}")
    lines.append("")

    for bp_result in result.results:
        lines.append(f"  {bp_result.breakpoint.name} ({bp_result.breakpoint.width}x{bp_result.breakpoint.height})")
        lines.append(f"    Issues: {len(bp_result.issues)}")
        lines.append(f"    Horizontal Scroll: {'Yes' if bp_result.has_horizontal_scroll else 'No'}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_touch_text(result) -> str:
    """Format touch target validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA TOUCH TARGET VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Interactive:      {result.total_interactive_elements}")
    lines.append(f"  Passing:          {result.passing_count}")
    lines.append(f"  Failing:          {result.failing_count}")
    lines.append(f"  Min Size:         {result.min_touch_size}px")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  TOUCH TARGET ISSUES")
        lines.append("-" * 70)
        for issue in result.issues[:10]:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.element_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Size: {issue.width:.0f}x{issue.height:.0f}px")
            lines.append(f"    Required: {issue.min_required}x{issue.min_required}px")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_viewport_text(result) -> str:
    """Format viewport test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA VIEWPORT TEST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Viewport Meta:    {result.viewport_meta or 'MISSING'}")
    lines.append(f"  Content Width:    {result.content_width}px")
    lines.append(f"  Viewport Width:   {result.viewport_width}px")
    lines.append(f"  Horizontal Scroll: {'Yes' if result.has_horizontal_scroll else 'No'}")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  VIEWPORT ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_mobile_text(result) -> str:
    """Format mobile compatibility result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA MOBILE COMPATIBILITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Devices Tested:   {', '.join(result.devices_tested)}")
    lines.append(f"  Load Time:        {result.load_time_ms}ms")
    lines.append(f"  Page Size:        {result.page_size_bytes / 1024:.1f} KB")
    lines.append(f"  Resources:        {result.resource_count}")
    lines.append(f"  Score:            {result.mobile_friendly_score:.0f}/100")
    lines.append("")

    if result.issues:
        lines.append("-" * 70)
        lines.append("  MOBILE ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  [{issue.severity.upper()}] {issue.issue_type}")
            lines.append(f"    Description: {issue.description}")
            lines.append(f"    Devices: {', '.join(issue.affected_devices)}")
            lines.append(f"    Fix: {issue.suggested_fix}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_unified_text(result) -> str:
    """Format unified test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA UNIFIED TEST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Duration:         {result.duration_ms}ms")
    lines.append(f"  Overall Score:    {result.overall_score:.0f}/100")
    lines.append("")
    lines.append("  SCORES")
    lines.append(f"    Accessibility:  {result.accessibility_score:.0f}/100")
    lines.append(f"    Visual:         {result.visual_score:.0f}/100")
    lines.append(f"    Responsive:     {result.responsive_score:.0f}/100")
    lines.append("")
    lines.append("  SUMMARY")
    lines.append(f"    Total Tests:    {result.total_tests}")
    lines.append(f"    Passed:         {result.passed}")
    lines.append(f"    Failed:         {result.failed}")
    lines.append("")
    lines.append("  BY SEVERITY")
    lines.append(f"    Critical:       {result.critical_count}")
    lines.append(f"    Serious:        {result.serious_count}")
    lines.append(f"    Moderate:       {result.moderate_count}")
    lines.append(f"    Minor:          {result.minor_count}")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
