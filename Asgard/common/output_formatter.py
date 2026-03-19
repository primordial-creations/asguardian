"""
Unified Output Formatter

Provides consistent output formatting across all Asgard modules.
Supports text, JSON, GitHub Actions, HTML, and Markdown formats.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class OutputFormat(str, Enum):
    """Supported output formats."""
    TEXT = "text"
    JSON = "json"
    GITHUB = "github"
    HTML = "html"
    MARKDOWN = "markdown"


class Severity(str, Enum):
    """Severity levels for issues."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"

    @property
    def github_level(self) -> str:
        """Get GitHub Actions annotation level."""
        if self in (Severity.CRITICAL, Severity.ERROR):
            return "error"
        elif self == Severity.WARNING:
            return "warning"
        else:
            return "notice"

    @property
    def color(self) -> str:
        """Get ANSI color code."""
        colors = {
            Severity.CRITICAL: "\033[1;31m",  # Bold red
            Severity.ERROR: "\033[0;31m",      # Red
            Severity.WARNING: "\033[0;33m",    # Yellow
            Severity.INFO: "\033[0;34m",       # Blue
            Severity.DEBUG: "\033[0;90m",      # Gray
        }
        return colors.get(self, "")

    @property
    def reset(self) -> str:
        """Get ANSI reset code."""
        return "\033[0m"


@dataclass
class FormattedResult:
    """A single formatted result/issue."""
    message: str
    severity: Severity = Severity.INFO
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None
    category: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> str:
        """Get formatted location string."""
        if not self.file_path:
            return ""
        loc = self.file_path
        if self.line_number:
            loc += f":{self.line_number}"
            if self.column:
                loc += f":{self.column}"
        return loc


class UnifiedFormatter:
    """
    Unified formatter for consistent output across Asgard modules.

    Usage:
        formatter = UnifiedFormatter(OutputFormat.TEXT)

        # Format single issue
        output = formatter.format_result(result)

        # Format multiple results
        output = formatter.format_results(results, title="Security Scan")

        # Format summary
        output = formatter.format_summary(stats)
    """

    def __init__(
        self,
        output_format: OutputFormat = OutputFormat.TEXT,
        colorize: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize the formatter.

        Args:
            output_format: Output format to use
            colorize: Enable ANSI colors for text output
            verbose: Include additional details
        """
        self.format = output_format
        self.colorize = colorize
        self.verbose = verbose

    def format_result(self, result: FormattedResult) -> str:
        """Format a single result."""
        if self.format == OutputFormat.JSON:
            return self._format_result_json(result)
        elif self.format == OutputFormat.GITHUB:
            return self._format_result_github(result)
        elif self.format == OutputFormat.MARKDOWN:
            return self._format_result_markdown(result)
        elif self.format == OutputFormat.HTML:
            return self._format_result_html(result)
        else:
            return self._format_result_text(result)

    def format_results(
        self,
        results: List[FormattedResult],
        title: str = "Results",
        summary: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format multiple results."""
        if self.format == OutputFormat.JSON:
            return self._format_results_json(results, title, summary)
        elif self.format == OutputFormat.GITHUB:
            return self._format_results_github(results, title, summary)
        elif self.format == OutputFormat.MARKDOWN:
            return self._format_results_markdown(results, title, summary)
        elif self.format == OutputFormat.HTML:
            return self._format_results_html(results, title, summary)
        else:
            return self._format_results_text(results, title, summary)

    def format_summary(
        self,
        stats: Dict[str, Any],
        title: str = "Summary",
    ) -> str:
        """Format a summary/stats block."""
        if self.format == OutputFormat.JSON:
            return json.dumps(stats, indent=2, default=str)
        elif self.format == OutputFormat.GITHUB:
            return self._format_summary_github(stats, title)
        elif self.format == OutputFormat.MARKDOWN:
            return self._format_summary_markdown(stats, title)
        elif self.format == OutputFormat.HTML:
            return self._format_summary_html(stats, title)
        else:
            return self._format_summary_text(stats, title)

    # Text format methods
    def _format_result_text(self, result: FormattedResult) -> str:
        """Format result as text."""
        parts = []

        # Severity marker
        if self.colorize:
            parts.append(f"{result.severity.color}[{result.severity.value.upper()}]{result.severity.reset}")
        else:
            parts.append(f"[{result.severity.value.upper()}]")

        # Location
        if result.location:
            parts.append(result.location)

        # Message
        parts.append(result.message)

        line = " ".join(parts)

        # Add suggestion if verbose
        if self.verbose and result.suggestion:
            line += f"\n  Suggestion: {result.suggestion}"

        return line

    def _format_results_text(
        self,
        results: List[FormattedResult],
        title: str,
        summary: Optional[Dict[str, Any]],
    ) -> str:
        """Format multiple results as text."""
        lines = [
            "=" * 60,
            f"  {title.upper()}",
            "=" * 60,
            "",
        ]

        if summary:
            lines.append(self._format_summary_text(summary, "Summary"))
            lines.append("")

        if results:
            lines.append("-" * 60)
            for result in results:
                lines.append(self._format_result_text(result))
        else:
            lines.append("No issues found.")

        lines.extend(["", "=" * 60])
        return "\n".join(lines)

    def _format_summary_text(self, stats: Dict[str, Any], title: str) -> str:
        """Format summary as text."""
        lines = [f"{title}:", "-" * 40]
        for key, value in stats.items():
            # Format key nicely
            display_key = key.replace("_", " ").title()
            lines.append(f"  {display_key}: {value}")
        return "\n".join(lines)

    # JSON format methods
    def _format_result_json(self, result: FormattedResult) -> str:
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
        if self.verbose:
            data["metadata"] = result.metadata
        return json.dumps(data, indent=2)

    def _format_results_json(
        self,
        results: List[FormattedResult],
        title: str,
        summary: Optional[Dict[str, Any]],
    ) -> str:
        """Format multiple results as JSON."""
        data = {
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
                    **({"metadata": r.metadata} if self.verbose else {}),
                }
                for r in results
            ],
        }
        if summary:
            data["summary"] = summary
        return json.dumps(data, indent=2, default=str)

    # GitHub Actions format methods
    def _format_result_github(self, result: FormattedResult) -> str:
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

    def _format_results_github(
        self,
        results: List[FormattedResult],
        title: str,
        summary: Optional[Dict[str, Any]],
    ) -> str:
        """Format multiple results as GitHub Actions annotations."""
        lines = []

        # Add summary as a notice
        if summary:
            summary_text = ", ".join(f"{k}: {v}" for k, v in summary.items())
            lines.append(f"::notice::{title} - {summary_text}")

        # Add each result
        for result in results:
            lines.append(self._format_result_github(result))

        return "\n".join(lines)

    def _format_summary_github(self, stats: Dict[str, Any], title: str) -> str:
        """Format summary as GitHub annotation."""
        summary_text = ", ".join(f"{k}: {v}" for k, v in stats.items())
        return f"::notice::{title} - {summary_text}"

    # Markdown format methods
    def _format_result_markdown(self, result: FormattedResult) -> str:
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

        if self.verbose and result.suggestion:
            line += f"\n  - *Suggestion:* {result.suggestion}"

        return line

    def _format_results_markdown(
        self,
        results: List[FormattedResult],
        title: str,
        summary: Optional[Dict[str, Any]],
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
                lines.append(self._format_result_markdown(result))
        else:
            lines.append("*No issues found.*")

        return "\n".join(lines)

    def _format_summary_markdown(self, stats: Dict[str, Any], title: str) -> str:
        """Format summary as Markdown."""
        lines = [f"## {title}", "", "| Metric | Value |", "|--------|-------|"]
        for key, value in stats.items():
            display_key = key.replace("_", " ").title()
            lines.append(f"| {display_key} | {value} |")
        return "\n".join(lines)

    # HTML format methods
    def _format_result_html(self, result: FormattedResult) -> str:
        """Format result as HTML."""
        severity_class = f"severity-{result.severity.value}"
        html = f'<div class="result {severity_class}">'
        html += f'<span class="severity">{result.severity.value.upper()}</span>'

        if result.location:
            html += f'<span class="location">{result.location}</span>'

        html += f'<span class="message">{result.message}</span>'

        if self.verbose and result.suggestion:
            html += f'<div class="suggestion">{result.suggestion}</div>'

        html += '</div>'
        return html

    def _format_results_html(
        self,
        results: List[FormattedResult],
        title: str,
        summary: Optional[Dict[str, Any]],
    ) -> str:
        """Format multiple results as HTML."""
        html = ['<div class="asgard-report">']
        html.append(f'<h1>{title}</h1>')

        if summary:
            html.append(self._format_summary_html(summary, "Summary"))

        if results:
            html.append('<div class="results">')
            for result in results:
                html.append(self._format_result_html(result))
            html.append('</div>')
        else:
            html.append('<p class="no-issues">No issues found.</p>')

        html.append('</div>')
        return "\n".join(html)

    def _format_summary_html(self, stats: Dict[str, Any], title: str) -> str:
        """Format summary as HTML."""
        html = [f'<div class="summary"><h2>{title}</h2><table>']
        for key, value in stats.items():
            display_key = key.replace("_", " ").title()
            html.append(f'<tr><td>{display_key}</td><td>{value}</td></tr>')
        html.append('</table></div>')
        return "\n".join(html)


# Backward compatibility aliases
FormattedIssue = FormattedResult


@dataclass
class FormattedReport:
    """A validation/analysis report containing multiple issues."""
    title: str = "Report"
    file_path: Optional[str] = None
    total_files: int = 0
    passed: bool = True
    score: float = 100.0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: List[FormattedResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


def format_for_cli(
    results: List[FormattedResult],
    output_format: str = "text",
    title: str = "Results",
    summary: Optional[Dict[str, Any]] = None,
    colorize: bool = True,
    verbose: bool = False,
) -> str:
    """
    Convenience function to format results for CLI output.

    Args:
        results: List of results to format
        output_format: Format string (text, json, github, markdown, html)
        title: Report title
        summary: Optional summary statistics
        colorize: Enable colors for text output
        verbose: Include additional details

    Returns:
        Formatted output string
    """
    try:
        fmt = OutputFormat(output_format.lower())
    except ValueError:
        fmt = OutputFormat.TEXT

    formatter = UnifiedFormatter(fmt, colorize, verbose)
    return formatter.format_results(results, title, summary)
