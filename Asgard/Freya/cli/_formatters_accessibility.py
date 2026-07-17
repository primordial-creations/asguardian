from Asgard.Freya.Accessibility.models.accessibility_models import ViolationSeverity
from Asgard.Freya.Scoring.services.epistemics import (
    ACCESSIBILITY_DISCLAIMER,
    NEEDS_REVIEW_NOTE,
)


def _wrap_disclaimer(text: str, width: int = 66) -> list:
    """Wrap disclaimer text into indented report lines."""
    import textwrap
    return [f"  {line}" for line in textwrap.wrap(text, width)]


SEVERITY_MARKERS = {
    ViolationSeverity.CRITICAL.value: "[CRITICAL]",
    ViolationSeverity.SERIOUS.value: "[SERIOUS]",
    ViolationSeverity.MODERATE.value: "[MODERATE]",
    ViolationSeverity.MINOR.value: "[MINOR]",
    ViolationSeverity.INFO.value: "[INFO]",
}


def format_accessibility_text(result) -> str:
    """Format accessibility result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA ACCESSIBILITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  WCAG Level:   {result.wcag_level}")
    lines.append(f"  Score:        {result.score:.1f}%")
    lines.append(f"  Tested At:    {result.tested_at}")
    lines.append("")
    lines.extend(_wrap_disclaimer(ACCESSIBILITY_DISCLAIMER))
    lines.append("")

    if result.has_violations:
        lines.append("-" * 70)
        lines.append("  VIOLATIONS - IMPACT INBOX (Axis 2: heuristic usability impact)")
        lines.append("-" * 70)
        lines.append("")

        for violation in result.violations:
            marker = SEVERITY_MARKERS.get(violation.severity, "[UNKNOWN]")
            impact = getattr(violation, "usability_impact", None)
            criticality = getattr(violation, "criticality", None)
            impact_suffix = ""
            if impact is not None and criticality is not None:
                impact_suffix = f" (impact: {getattr(impact, 'value', impact)}, context: {getattr(criticality, 'value', criticality)})"
            lines.append(f"  {marker}{impact_suffix}")
            lines.append(f"    {violation.description}")
            lines.append(f"    WCAG: {violation.wcag_reference}")
            lines.append(f"    Element: {violation.element_selector}")
            lines.append(f"    Fix: {violation.suggested_fix}")
            framing = getattr(violation, "framing", None)
            if isinstance(framing, str):
                lines.append(f"    Note: {framing}")
            lines.append("")
    else:
        lines.append("  No accessibility violations found!")
        lines.append("")

    lines.append("-" * 70)
    lines.append("  SUMMARY")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Total Violations:  {result.total_violations}")
    lines.append(f"  Critical:          {result.critical_count}")
    lines.append(f"  Serious:           {result.serious_count}")
    lines.append(f"  Moderate:          {result.moderate_count}")
    lines.append(f"  Minor:             {result.minor_count}")
    lines.append("")

    ledger = getattr(result, "conformance_ledger", None)
    if isinstance(ledger, dict) and ledger:
        counts = {}
        for status in ledger.values():
            counts[status] = counts.get(status, 0) + 1
        lines.append("-" * 70)
        lines.append("  CONFORMANCE LEDGER (Axis 1: statutory WCAG 2.1 status)")
        lines.append("-" * 70)
        lines.append("")
        lines.append(
            f"  Pass: {counts.get('pass', 0)}  Fail: {counts.get('fail', 0)}  "
            f"Needs Review: {counts.get('needs_review', 0)}  "
            f"Not Checked: {counts.get('not_checked', 0)}"
        )
        failed = sorted(k for k, v in ledger.items() if v == "fail")
        if failed:
            lines.append(f"  Failing criteria: {', '.join(failed)}")
        not_checked = sorted(k for k, v in ledger.items() if v == "not_checked")
        if not_checked:
            lines.append(f"  NOT checked by this tool: {', '.join(not_checked)}")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def format_accessibility_markdown(result) -> str:
    """Format accessibility result as Markdown."""
    lines = []
    lines.append("# Freya Accessibility Report")
    lines.append("")
    lines.append(f"- **URL:** {result.url}")
    lines.append(f"- **WCAG Level:** {result.wcag_level}")
    lines.append(f"- **Score:** {result.score:.1f}%")
    lines.append(f"- **Tested At:** {result.tested_at}")
    lines.append("")
    lines.append(f"> {ACCESSIBILITY_DISCLAIMER}")
    lines.append("")

    if result.has_violations:
        lines.append("## Violations")
        lines.append("")
        lines.append("| Severity | WCAG | Description | Element |")
        lines.append("|----------|------|-------------|---------|")

        for v in result.violations:
            lines.append(f"| {v.severity} | {v.wcag_reference} | {v.description} | `{v.element_selector}` |")

        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Violations:** {result.total_violations}")
    lines.append(f"- **Critical:** {result.critical_count}")
    lines.append(f"- **Serious:** {result.serious_count}")
    lines.append(f"- **Moderate:** {result.moderate_count}")
    lines.append(f"- **Minor:** {result.minor_count}")

    return "\n".join(lines)


def format_accessibility_html(result) -> str:
    """Format accessibility result as HTML."""
    score_class = "excellent" if result.score >= 90 else "good" if result.score >= 70 else "fair" if result.score >= 50 else "poor"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Freya Accessibility Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .score {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
        .score.excellent {{ color: #4CAF50; }}
        .score.good {{ color: #8BC34A; }}
        .score.fair {{ color: #FF9800; }}
        .score.poor {{ color: #f44336; }}
        .violation {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .violation.critical {{ border-left: 4px solid #f44336; }}
        .violation.serious {{ border-left: 4px solid #FF9800; }}
        .violation.moderate {{ border-left: 4px solid #2196F3; }}
        .violation.minor {{ border-left: 4px solid #4CAF50; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Freya Accessibility Report</h1>
        <p><strong>URL:</strong> {result.url}</p>
        <p><strong>WCAG Level:</strong> {result.wcag_level}</p>
        <p><strong>Tested At:</strong> {result.tested_at}</p>
    </div>
    <div class="score {score_class}">
        Accessibility Score: {result.score:.1f}%
    </div>
    <p style="font-size: 0.9em; color: #555;"><em>{ACCESSIBILITY_DISCLAIMER}</em></p>
"""

    if result.has_violations:
        html += "<h2>Violations</h2>"
        for v in result.violations:
            html += f"""
    <div class="violation {v.severity}">
        <h3>{v.description}</h3>
        <p><strong>Severity:</strong> {v.severity}</p>
        <p><strong>WCAG Reference:</strong> {v.wcag_reference}</p>
        <p><strong>Element:</strong> <code>{v.element_selector}</code></p>
        <p><strong>Suggested Fix:</strong> {v.suggested_fix}</p>
    </div>
"""

    html += "</body></html>"
    return html


def format_contrast_text(result) -> str:
    """Format contrast check result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA COLOR CONTRAST REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Elements:     {result.total_elements}")
    lines.append(f"  Passing:      {result.passing_count}")
    lines.append(f"  Failing:      {result.failing_count}")
    lines.append("")

    if result.has_violations:
        lines.append("-" * 70)
        lines.append("  CONTRAST ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  Element: {issue.element_selector}")
            lines.append(f"    Foreground: {issue.foreground_color}")
            lines.append(f"    Background: {issue.background_color}")
            lines.append(f"    Ratio: {issue.contrast_ratio:.2f}:1")
            lines.append(f"    Required: {issue.required_ratio}:1")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_keyboard_text(result) -> str:
    """Format keyboard test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA KEYBOARD NAVIGATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:                    {result.url}")
    lines.append(f"  Focusable Elements:     {result.total_focusable}")
    lines.append(f"  Accessible Elements:    {result.accessible_count}")
    lines.append(f"  Issues Found:           {result.issue_count}")
    lines.append("")

    if result.has_issues:
        lines.append("-" * 70)
        lines.append("  ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"\n  {issue.issue_type}")
            lines.append(f"    Element: {issue.element_selector}")
            lines.append(f"    Description: {issue.description}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_aria_text(result) -> str:
    """Format ARIA validation result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA ARIA VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:          {result.url}")
    lines.append(f"  Elements:     {result.total_aria_elements}")

    warning_count = getattr(result, "warning_count", 0)
    needs_review_count = getattr(result, "needs_review_count", 0)
    if isinstance(warning_count, int) and isinstance(needs_review_count, int) and (
        warning_count or needs_review_count
    ):
        lines.append(
            f"  Passed: {result.valid_count}, Failed: {result.invalid_count}, "
            f"Warnings: {warning_count}, Needs Human Review: {needs_review_count}"
        )
        lines.append("")
        lines.extend(_wrap_disclaimer(NEEDS_REVIEW_NOTE))
    else:
        lines.append(f"  Valid:        {result.valid_count}")
        lines.append(f"  Invalid:      {result.invalid_count}")
    lines.append("")

    if result.has_violations:
        lines.append("-" * 70)
        lines.append("  ARIA VIOLATIONS")
        lines.append("-" * 70)
        for violation in result.violations:
            verdict = getattr(violation, "verdict", None)
            verdict_str = getattr(verdict, "value", None)
            prefix = f"[{verdict_str.upper()}] " if isinstance(verdict_str, str) else ""
            lines.append(f"\n  {prefix}Element: {violation.element_selector}")
            lines.append(f"    Issue: {violation.description}")
            lines.append(f"    Fix: {violation.suggested_fix}")

    needs_review = getattr(result, "needs_review", None)
    if isinstance(needs_review, list) and needs_review:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  NEEDS HUMAN REVIEW (automation cannot decide these)")
        lines.append("-" * 70)
        for item in needs_review:
            lines.append(f"\n  Element: {item.element_selector}")
            lines.append(f"    Claim: {item.description}")
            directive = getattr(item, "manual_test_directive", None)
            if isinstance(directive, str):
                lines.append(f"    {directive}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_screen_reader_text(result) -> str:
    """Format screen reader test result as text."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  FREYA SCREEN READER COMPATIBILITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  URL:              {result.url}")
    lines.append(f"  Total Elements:   {result.total_elements}")
    lines.append(f"  Labeled:          {result.labeled_count}")
    lines.append(f"  Missing Labels:   {result.missing_labels}")
    lines.append("")

    if result.landmark_structure:
        lines.append("-" * 70)
        lines.append("  LANDMARK STRUCTURE")
        lines.append("-" * 70)
        for landmark, count in result.landmark_structure.items():
            lines.append(f"    {landmark}: {count}")

    if result.heading_structure:
        lines.append("")
        lines.append("-" * 70)
        lines.append("  HEADING STRUCTURE")
        lines.append("-" * 70)
        for heading in result.heading_structure:
            lines.append(f"    h{heading['level']}: {heading['text'][:50]}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
