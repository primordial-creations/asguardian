"""
Unified Output Formatter

Provides consistent output formatting across all Asgard modules.
Supports text, JSON, GitHub Actions, HTML, and Markdown formats.
"""

import json
from typing import Any, Dict, List, Optional

from Asgard.common._format_methods import (
    format_result_github,
    format_result_html,
    format_result_json,
    format_result_markdown,
    format_result_text,
    format_results_github,
    format_results_html,
    format_results_json,
    format_results_markdown,
    format_results_text,
    format_summary_github,
    format_summary_html,
    format_summary_markdown,
    format_summary_text,
)
from Asgard.common._formatter_types import (
    FormattedReport,
    FormattedResult,
    OutputFormat,
    Severity,
)

FormattedIssue = FormattedResult


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
            return format_result_json(result, self.verbose)
        elif self.format == OutputFormat.GITHUB:
            return format_result_github(result)
        elif self.format == OutputFormat.MARKDOWN:
            return format_result_markdown(result, self.verbose)
        elif self.format == OutputFormat.HTML:
            return format_result_html(result, self.verbose)
        else:
            return format_result_text(result, self.colorize, self.verbose)

    def format_results(
        self,
        results: List[FormattedResult],
        title: str = "Results",
        summary: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format multiple results."""
        if self.format == OutputFormat.JSON:
            return format_results_json(results, title, summary, self.verbose)
        elif self.format == OutputFormat.GITHUB:
            return format_results_github(results, title, summary)
        elif self.format == OutputFormat.MARKDOWN:
            return format_results_markdown(results, title, summary, self.verbose)
        elif self.format == OutputFormat.HTML:
            return format_results_html(results, title, summary, self.verbose)
        else:
            return format_results_text(results, title, summary, self.colorize, self.verbose)

    def format_summary(
        self,
        stats: Dict[str, Any],
        title: str = "Summary",
    ) -> str:
        """Format a summary/stats block."""
        if self.format == OutputFormat.JSON:
            return json.dumps(stats, indent=2, default=str)
        elif self.format == OutputFormat.GITHUB:
            return format_summary_github(stats, title)
        elif self.format == OutputFormat.MARKDOWN:
            return format_summary_markdown(stats, title)
        elif self.format == OutputFormat.HTML:
            return format_summary_html(stats, title)
        else:
            return format_summary_text(stats, title)


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


__all__ = [
    "FormattedIssue",
    "FormattedReport",
    "FormattedResult",
    "OutputFormat",
    "Severity",
    "UnifiedFormatter",
    "format_for_cli",
]
