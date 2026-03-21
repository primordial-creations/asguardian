"""
Unified Output Formatter - Per-format rendering methods

Implements text, JSON, GitHub, Markdown, and HTML format methods
used by UnifiedFormatter. Extracted to keep the main module under 300 lines.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from Asgard.common._formatter_types import FormattedResult, Severity


def format_result_text(result: FormattedResult, colorize: bool, verbose: bool) -> str:
    """Format result as text."""
    parts = []

    if colorize:
        parts.append(f"{result.severity.color}[{result.severity.value.upper()}]{result.severity.reset}")
    else:
        parts.append(f"[{result.severity.value.upper()}]")

    if result.location:
        parts.append(result.location)

    parts.append(result.message)

    line = " ".join(parts)

    if verbose and result.suggestion:
        line += f"\n  Suggestion: {result.suggestion}"

    return line


def format_results_text(
    results: List[FormattedResult],
    title: str,
    summary: Optional[Dict[str, Any]],
    colorize: bool,
    verbose: bool,
) -> str:
    """Format multiple results as text."""
    lines = [
        "=" * 60,
        f"  {title.upper()}",
        "=" * 60,
        "",
    ]

    if summary:
        lines.append(format_summary_text(summary, "Summary"))
        lines.append("")

    if results:
        lines.append("-" * 60)
        for result in results:
            lines.append(format_result_text(result, colorize, verbose))
    else:
        lines.append("No issues found.")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


def format_summary_text(stats: Dict[str, Any], title: str) -> str:
    """Format summary as text."""
    lines = [f"{title}:", "-" * 40]
    for key, value in stats.items():
        display_key = key.replace("_", " ").title()
        lines.append(f"  {display_key}: {value}")
    return "\n".join(lines)


def format_result_json(result: FormattedResult, verbose: bool) -> str:
    """Format result as JSON."""
    data: Dict[str, Any] = {
        "message": result.message,
        "severity": result.severity.value,
        "file_path": result.file_path,
        "line_number": result.line_number,
        "column": result.column,
        "code": result.code,
        "category": result.category,
        "suggestion": result.suggestion,
    }
    if verbose:
        data["metadata"] = result.metadata
    return json.dumps(data, indent=2)


def format_results_json(
    results: List[FormattedResult],
    title: str,
    summary: Optional[Dict[str, Any]],
    verbose: bool,
) -> str:
    """Format multiple results as JSON."""
    data: Dict[str, Any] = {
        "title": title,
        "timestamp": datetime.now().isoformat(),
        "count": len(results),
        "results": [
            {
                "message": r.message,
                "severity": r.severity.value,
                "file_path": r.file_path,
                "line_number": r.line_number,
                "column": r.column,
                "code": r.code,
                "category": r.category,
                "suggestion": r.suggestion,
                **({"metadata": r.metadata} if verbose else {}),
            }
            for r in results
        ],
    }
    if summary:
        data["summary"] = summary
    return json.dumps(data, indent=2, default=str)


def format_result_github(result: FormattedResult) -> str:
    """Format result as GitHub Actions annotation."""
    level = result.severity.github_level
    parts = [f"::{level}"]

    if result.file_path:
        parts.append(f" file={result.file_path}")
        if result.line_number:
            parts.append(f",line={result.line_number}")
            if result.column:
                parts.append(f",col={result.column}")

    message = result.message
    if result.code:
        message = f"[{result.code}] {message}"

    parts.append(f"::{message}")
    return "".join(parts)


def format_results_github(
    results: List[FormattedResult],
    title: str,
    summary: Optional[Dict[str, Any]],
) -> str:
    """Format multiple results as GitHub Actions annotations."""
    lines = []

    if summary:
        summary_text = ", ".join(f"{k}: {v}" for k, v in summary.items())
        lines.append(f"::notice::{title} - {summary_text}")

    for result in results:
        lines.append(format_result_github(result))

    return "\n".join(lines)


def format_summary_github(stats: Dict[str, Any], title: str) -> str:
    """Format summary as GitHub annotation."""
    summary_text = ", ".join(f"{k}: {v}" for k, v in stats.items())
    return f"::notice::{title} - {summary_text}"


def format_result_markdown(result: FormattedResult, verbose: bool) -> str:
    """Format result as Markdown."""
    severity_emoji = {
        Severity.CRITICAL: ":red_circle:",
        Severity.ERROR: ":large_orange_circle:",
        Severity.WARNING: ":yellow_circle:",
        Severity.INFO: ":blue_circle:",
        Severity.DEBUG: ":white_circle:",
    }
    emoji = severity_emoji.get(result.severity, ":white_circle:")

    parts = [f"- {emoji} **{result.severity.value.upper()}**"]

    if result.location:
        parts.append(f" `{result.location}`")

    parts.append(f": {result.message}")

    line = "".join(parts)

    if verbose and result.suggestion:
        line += f"\n  - *Suggestion:* {result.suggestion}"

    return line


def format_results_markdown(
    results: List[FormattedResult],
    title: str,
    summary: Optional[Dict[str, Any]],
    verbose: bool,
) -> str:
    """Format multiple results as Markdown."""
    lines = [f"# {title}", ""]

    if summary:
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for key, value in summary.items():
            display_key = key.replace("_", " ").title()
            lines.append(f"| {display_key} | {value} |")
        lines.append("")

    if results:
        lines.append("## Issues")
        lines.append("")
        for result in results:
            lines.append(format_result_markdown(result, verbose))
    else:
        lines.append("*No issues found.*")

    return "\n".join(lines)


def format_summary_markdown(stats: Dict[str, Any], title: str) -> str:
    """Format summary as Markdown."""
    lines = [f"## {title}", "", "| Metric | Value |", "|--------|-------|"]
    for key, value in stats.items():
        display_key = key.replace("_", " ").title()
        lines.append(f"| {display_key} | {value} |")
    return "\n".join(lines)


def format_result_html(result: FormattedResult, verbose: bool) -> str:
    """Format result as HTML."""
    severity_class = f"severity-{result.severity.value}"
    html = f'<div class="result {severity_class}">'
    html += f'<span class="severity">{result.severity.value.upper()}</span>'

    if result.location:
        html += f'<span class="location">{result.location}</span>'

    html += f'<span class="message">{result.message}</span>'

    if verbose and result.suggestion:
        html += f'<div class="suggestion">{result.suggestion}</div>'

    html += '</div>'
    return html


def format_results_html(
    results: List[FormattedResult],
    title: str,
    summary: Optional[Dict[str, Any]],
    verbose: bool,
) -> str:
    """Format multiple results as HTML."""
    html = ['<div class="asgard-report">']
    html.append(f'<h1>{title}</h1>')

    if summary:
        html.append(format_summary_html(summary, "Summary"))

    if results:
        html.append('<div class="results">')
        for result in results:
            html.append(format_result_html(result, verbose))
        html.append('</div>')
    else:
        html.append('<p class="no-issues">No issues found.</p>')

    html.append('</div>')
    return "\n".join(html)


def format_summary_html(stats: Dict[str, Any], title: str) -> str:
    """Format summary as HTML."""
    html = [f'<div class="summary"><h2>{title}</h2><table>']
    for key, value in stats.items():
        display_key = key.replace("_", " ").title()
        html.append(f'<tr><td>{display_key}</td><td>{value}</td></tr>')
    html.append('</table></div>')
    return "\n".join(html)
