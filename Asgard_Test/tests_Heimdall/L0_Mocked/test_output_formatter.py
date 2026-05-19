"""
Tests for Unified Output Formatter

Comprehensive unit tests for OutputFormat, Severity, FormattedResult,
UnifiedFormatter, and format_for_cli function.
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from Asgard.common.output_formatter import (
    FormattedResult,
    OutputFormat,
    Severity,
    UnifiedFormatter,
    format_for_cli,
)


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_enum_values(self):
        """Test enum has expected values."""
        assert OutputFormat.TEXT == "text"
        assert OutputFormat.JSON == "json"
        assert OutputFormat.GITHUB == "github"
        assert OutputFormat.HTML == "html"
        assert OutputFormat.MARKDOWN == "markdown"

    def test_string_conversion(self):
        """Test enum values are strings."""
        assert isinstance(OutputFormat.TEXT.value, str)


class TestSeverity:
    """Tests for Severity enum."""

    def test_enum_values(self):
        """Test enum has expected values."""
        assert Severity.CRITICAL == "critical"
        assert Severity.ERROR == "error"
        assert Severity.WARNING == "warning"
        assert Severity.INFO == "info"
        assert Severity.DEBUG == "debug"

    def test_github_level_critical(self):
        """Test GitHub level for critical."""
        assert Severity.CRITICAL.github_level == "error"

    def test_github_level_error(self):
        """Test GitHub level for error."""
        assert Severity.ERROR.github_level == "error"

    def test_github_level_warning(self):
        """Test GitHub level for warning."""
        assert Severity.WARNING.github_level == "warning"

    def test_github_level_info(self):
        """Test GitHub level for info."""
        assert Severity.INFO.github_level == "notice"

    def test_github_level_debug(self):
        """Test GitHub level for debug."""
        assert Severity.DEBUG.github_level == "notice"

    def test_color_critical(self):
        """Test ANSI color for critical."""
        assert Severity.CRITICAL.color == "\033[1;31m"

    def test_color_error(self):
        """Test ANSI color for error."""
        assert Severity.ERROR.color == "\033[0;31m"

    def test_color_warning(self):
        """Test ANSI color for warning."""
        assert Severity.WARNING.color == "\033[0;33m"

    def test_color_info(self):
        """Test ANSI color for info."""
        assert Severity.INFO.color == "\033[0;34m"

    def test_color_debug(self):
        """Test ANSI color for debug."""
        assert Severity.DEBUG.color == "\033[0;90m"

    def test_reset(self):
        """Test ANSI reset code."""
        assert Severity.ERROR.reset == "\033[0m"


class TestFormattedResult:
    """Tests for FormattedResult dataclass."""

    def test_initialization_minimal(self):
        """Test minimal initialization."""
        result = FormattedResult(message="Test message")

        assert result.message == "Test message"
        assert result.severity == Severity.INFO
        assert result.file_path is None
        assert result.line_number is None
        assert result.column is None
        assert result.code is None
        assert result.category is None
        assert result.suggestion is None
        assert result.metadata == {}

    def test_initialization_full(self):
        """Test full initialization."""
        metadata = {"key": "value"}
        result = FormattedResult(
            message="Test message",
            severity=Severity.ERROR,
            file_path="test.py",
            line_number=10,
            column=5,
            code="E001",
            category="security",
            suggestion="Fix this",
            metadata=metadata,
        )

        assert result.message == "Test message"
        assert result.severity == Severity.ERROR
        assert result.file_path == "test.py"
        assert result.line_number == 10
        assert result.column == 5
        assert result.code == "E001"
        assert result.category == "security"
        assert result.suggestion == "Fix this"
        assert result.metadata == metadata

    def test_location_no_file(self):
        """Test location property with no file path."""
        result = FormattedResult(message="Test")
        assert result.location == ""

    def test_location_file_only(self):
        """Test location property with file only."""
        result = FormattedResult(message="Test", file_path="test.py")
        assert result.location == "test.py"

    def test_location_file_and_line(self):
        """Test location property with file and line."""
        result = FormattedResult(message="Test", file_path="test.py", line_number=10)
        assert result.location == "test.py:10"

    def test_location_file_line_column(self):
        """Test location property with file, line, and column."""
        result = FormattedResult(
            message="Test",
            file_path="test.py",
            line_number=10,
            column=5,
        )
        assert result.location == "test.py:10:5"


class TestUnifiedFormatter:
    """Tests for UnifiedFormatter class."""

    def test_initialization_defaults(self):
        """Test formatter initialization with defaults."""
        formatter = UnifiedFormatter()

        assert formatter.format == OutputFormat.TEXT
        assert formatter.colorize is True
        assert formatter.verbose is False

    def test_initialization_custom(self):
        """Test formatter initialization with custom values."""
        formatter = UnifiedFormatter(
            output_format=OutputFormat.JSON,
            colorize=False,
            verbose=True,
        )

        assert formatter.format == OutputFormat.JSON
        assert formatter.colorize is False
        assert formatter.verbose is True

    # Text format tests
    def test_format_result_text(self):
        """Test formatting single result as text."""
        formatter = UnifiedFormatter(OutputFormat.TEXT, colorize=False)
        result = FormattedResult(
            message="Test message",
            severity=Severity.ERROR,
            file_path="test.py",
            line_number=10,
        )

        output = formatter.format_result(result)

        assert "[ERROR]" in output
        assert "test.py:10" in output
        assert "Test message" in output

    def test_format_result_text_with_color(self):
        """Test formatting text with colors."""
        formatter = UnifiedFormatter(OutputFormat.TEXT, colorize=True)
        result = FormattedResult(message="Test", severity=Severity.ERROR)

        output = formatter.format_result(result)

        assert "\033[0;31m" in output  # Red color
        assert "\033[0m" in output  # Reset

    def test_format_result_text_verbose(self):
        """Test formatting text in verbose mode."""
        formatter = UnifiedFormatter(OutputFormat.TEXT, verbose=True)
        result = FormattedResult(
            message="Test",
            suggestion="Fix this way",
        )

        output = formatter.format_result(result)

        assert "Suggestion:" in output
        assert "Fix this way" in output

    def test_format_results_text(self):
        """Test formatting multiple results as text."""
        formatter = UnifiedFormatter(OutputFormat.TEXT, colorize=False)
        results = [
            FormattedResult(message="Issue 1", severity=Severity.ERROR),
            FormattedResult(message="Issue 2", severity=Severity.WARNING),
        ]

        output = formatter.format_results(results, title="Test Report")

        assert "TEST REPORT" in output
        assert "Issue 1" in output
        assert "Issue 2" in output

    def test_format_results_text_empty(self):
        """Test formatting empty results."""
        formatter = UnifiedFormatter(OutputFormat.TEXT)
        output = formatter.format_results([], title="Test")

        assert "No issues found" in output

    def test_format_results_text_with_summary(self):
        """Test formatting results with summary."""
        formatter = UnifiedFormatter(OutputFormat.TEXT, colorize=False)
        results = [FormattedResult(message="Issue")]
        summary = {"total_issues": 1, "critical_issues": 0}

        output = formatter.format_results(results, summary=summary)

        assert "Total Issues: 1" in output
        assert "Critical Issues: 0" in output

    # JSON format tests
    def test_format_result_json(self):
        """Test formatting single result as JSON."""
        formatter = UnifiedFormatter(OutputFormat.JSON)
        result = FormattedResult(
            message="Test",
            severity=Severity.ERROR,
            file_path="test.py",
            line_number=10,
            code="E001",
        )

        output = formatter.format_result(result)
        data = json.loads(output)

        assert data["message"] == "Test"
        assert data["severity"] == "error"
        assert data["file_path"] == "test.py"
        assert data["line_number"] == 10
        assert data["code"] == "E001"

    def test_format_result_json_verbose(self):
        """Test formatting JSON in verbose mode includes metadata."""
        formatter = UnifiedFormatter(OutputFormat.JSON, verbose=True)
        result = FormattedResult(
            message="Test",
            metadata={"custom": "data"},
        )

        output = formatter.format_result(result)
        data = json.loads(output)

        assert "metadata" in data
        assert data["metadata"]["custom"] == "data"

    def test_format_results_json(self):
        """Test formatting multiple results as JSON."""
        formatter = UnifiedFormatter(OutputFormat.JSON)
        results = [
            FormattedResult(message="Issue 1"),
            FormattedResult(message="Issue 2"),
        ]

        output = formatter.format_results(results, title="Test")
        data = json.loads(output)

        assert data["title"] == "Test"
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_format_results_json_with_summary(self):
        """Test formatting JSON results with summary."""
        formatter = UnifiedFormatter(OutputFormat.JSON)
        results = [FormattedResult(message="Issue")]
        summary = {"total": 1}

        output = formatter.format_results(results, summary=summary)
        data = json.loads(output)

        assert "summary" in data
        assert data["summary"]["total"] == 1

    # GitHub Actions format tests
    def test_format_result_github_error(self):
        """Test formatting result as GitHub error annotation."""
        formatter = UnifiedFormatter(OutputFormat.GITHUB)
        result = FormattedResult(
            message="Test error",
            severity=Severity.ERROR,
            file_path="test.py",
            line_number=10,
            column=5,
        )

        output = formatter.format_result(result)

        assert output.startswith("::error")
        assert "file=test.py" in output
        assert "line=10" in output
        assert "col=5" in output
        assert "Test error" in output

    def test_format_result_github_warning(self):
        """Test formatting result as GitHub warning annotation."""
        formatter = UnifiedFormatter(OutputFormat.GITHUB)
        result = FormattedResult(
            message="Test warning",
            severity=Severity.WARNING,
        )

        output = formatter.format_result(result)

        assert output.startswith("::warning")

    def test_format_result_github_with_code(self):
        """Test GitHub format includes code in message."""
        formatter = UnifiedFormatter(OutputFormat.GITHUB)
        result = FormattedResult(
            message="Test",
            severity=Severity.ERROR,
            code="E001",
        )

        output = formatter.format_result(result)

        assert "[E001] Test" in output

    def test_format_results_github(self):
        """Test formatting multiple results as GitHub annotations."""
        formatter = UnifiedFormatter(OutputFormat.GITHUB)
        results = [
            FormattedResult(message="Issue 1", severity=Severity.ERROR),
            FormattedResult(message="Issue 2", severity=Severity.WARNING),
        ]

        output = formatter.format_results(results, title="Test")

        assert "::error" in output
        assert "::warning" in output

    def test_format_results_github_with_summary(self):
        """Test GitHub format includes summary as notice."""
        formatter = UnifiedFormatter(OutputFormat.GITHUB)
        results = []
        summary = {"total": 0}

        output = formatter.format_results(results, title="Test", summary=summary)

        assert "::notice::Test" in output
        assert "total: 0" in output

    # Markdown format tests
    def test_format_result_markdown(self):
        """Test formatting result as Markdown."""
        formatter = UnifiedFormatter(OutputFormat.MARKDOWN)
        result = FormattedResult(
            message="Test issue",
            severity=Severity.ERROR,
            file_path="test.py",
            line_number=10,
        )

        output = formatter.format_result(result)

        assert "ERROR" in output
        assert "`test.py:10`" in output
        assert "Test issue" in output

    def test_format_result_markdown_verbose(self):
        """Test Markdown format in verbose mode."""
        formatter = UnifiedFormatter(OutputFormat.MARKDOWN, verbose=True)
        result = FormattedResult(
            message="Test",
            suggestion="Fix suggestion",
        )

        output = formatter.format_result(result)

        assert "Suggestion:" in output
        assert "Fix suggestion" in output

    def test_format_results_markdown(self):
        """Test formatting multiple results as Markdown."""
        formatter = UnifiedFormatter(OutputFormat.MARKDOWN)
        results = [
            FormattedResult(message="Issue 1"),
            FormattedResult(message="Issue 2"),
        ]

        output = formatter.format_results(results, title="Test Report")

        assert "# Test Report" in output
        assert "Issue 1" in output
        assert "Issue 2" in output

    def test_format_results_markdown_with_summary(self):
        """Test Markdown format with summary table."""
        formatter = UnifiedFormatter(OutputFormat.MARKDOWN)
        results = []
        summary = {"total_issues": 5, "critical": 2}

        output = formatter.format_results(results, summary=summary, title="Test")

        assert "## Summary" in output
        assert "| Metric | Value |" in output
        assert "Total Issues" in output

    def test_format_results_markdown_empty(self):
        """Test Markdown format with no results."""
        formatter = UnifiedFormatter(OutputFormat.MARKDOWN)
        output = formatter.format_results([], title="Test")

        assert "*No issues found.*" in output

    # HTML format tests
    def test_format_result_html(self):
        """Test formatting result as HTML."""
        formatter = UnifiedFormatter(OutputFormat.HTML)
        result = FormattedResult(
            message="Test issue",
            severity=Severity.ERROR,
            file_path="test.py",
            line_number=10,
        )

        output = formatter.format_result(result)

        assert '<div class="result severity-error">' in output
        assert "ERROR" in output
        assert "test.py:10" in output
        assert "Test issue" in output

    def test_format_result_html_verbose(self):
        """Test HTML format in verbose mode."""
        formatter = UnifiedFormatter(OutputFormat.HTML, verbose=True)
        result = FormattedResult(
            message="Test",
            suggestion="Fix this",
        )

        output = formatter.format_result(result)

        assert '<div class="suggestion">' in output
        assert "Fix this" in output

    def test_format_results_html(self):
        """Test formatting multiple results as HTML."""
        formatter = UnifiedFormatter(OutputFormat.HTML)
        results = [
            FormattedResult(message="Issue 1"),
            FormattedResult(message="Issue 2"),
        ]

        output = formatter.format_results(results, title="Test Report")

        assert '<h1>Test Report</h1>' in output
        assert '<div class="results">' in output
        assert "Issue 1" in output
        assert "Issue 2" in output

    def test_format_results_html_with_summary(self):
        """Test HTML format with summary table."""
        formatter = UnifiedFormatter(OutputFormat.HTML)
        results = []
        summary = {"total": 0}

        output = formatter.format_results(results, summary=summary, title="Test")

        assert '<div class="summary">' in output
        assert "<table>" in output

    def test_format_results_html_empty(self):
        """Test HTML format with no results."""
        formatter = UnifiedFormatter(OutputFormat.HTML)
        output = formatter.format_results([], title="Test")

        assert '<p class="no-issues">No issues found.</p>' in output

    # Summary formatting tests
    def test_format_summary_text(self):
        """Test formatting summary as text."""
        formatter = UnifiedFormatter(OutputFormat.TEXT)
        stats = {"total_issues": 10, "critical_count": 2}

        output = formatter.format_summary(stats, title="Statistics")

        assert "Statistics:" in output
        assert "Total Issues: 10" in output
        assert "Critical Count: 2" in output

    def test_format_summary_json(self):
        """Test formatting summary as JSON."""
        formatter = UnifiedFormatter(OutputFormat.JSON)
        stats = {"total": 10}

        output = formatter.format_summary(stats)
        data = json.loads(output)

        assert data["total"] == 10

    def test_format_summary_github(self):
        """Test formatting summary as GitHub annotation."""
        formatter = UnifiedFormatter(OutputFormat.GITHUB)
        stats = {"total": 5}

        output = formatter.format_summary(stats, title="Stats")

        assert "::notice::Stats" in output
        assert "total: 5" in output

    def test_format_summary_markdown(self):
        """Test formatting summary as Markdown table."""
        formatter = UnifiedFormatter(OutputFormat.MARKDOWN)
        stats = {"total": 5, "errors": 2}

        output = formatter.format_summary(stats, title="Stats")

        assert "## Stats" in output
        assert "| Metric | Value |" in output
        assert "Total" in output

    def test_format_summary_html(self):
        """Test formatting summary as HTML table."""
        formatter = UnifiedFormatter(OutputFormat.HTML)
        stats = {"total": 5}

        output = formatter.format_summary(stats, title="Stats")

        assert '<div class="summary">' in output
        assert "<h2>Stats</h2>" in output
        assert "<table>" in output


class TestFormatForCli:
    """Tests for format_for_cli convenience function."""

    def test_format_for_cli_text(self):
        """Test CLI formatting with text format."""
        results = [FormattedResult(message="Test")]
        output = format_for_cli(results, output_format="text", title="Test")

        assert "TEST" in output
        assert "Test" in output

    def test_format_for_cli_json(self):
        """Test CLI formatting with JSON format."""
        results = [FormattedResult(message="Test")]
        output = format_for_cli(results, output_format="json")

        data = json.loads(output)
        assert "results" in data

    def test_format_for_cli_github(self):
        """Test CLI formatting with GitHub format."""
        results = [FormattedResult(message="Test", severity=Severity.ERROR)]
        output = format_for_cli(results, output_format="github")

        assert "::error" in output

    def test_format_for_cli_markdown(self):
        """Test CLI formatting with Markdown format."""
        results = [FormattedResult(message="Test")]
        output = format_for_cli(results, output_format="markdown")

        assert "# Results" in output

    def test_format_for_cli_html(self):
        """Test CLI formatting with HTML format."""
        results = [FormattedResult(message="Test")]
        output = format_for_cli(results, output_format="html")

        assert "<h1>" in output

    def test_format_for_cli_invalid_format(self):
        """Test CLI formatting falls back to text for invalid format."""
        results = [FormattedResult(message="Test")]
        output = format_for_cli(results, output_format="invalid")

        # Should fall back to TEXT format
        assert "RESULTS" in output

    def test_format_for_cli_with_summary(self):
        """Test CLI formatting with summary."""
        results = [FormattedResult(message="Test")]
        summary = {"total": 1}
        output = format_for_cli(results, summary=summary, output_format="text")

        assert "Total: 1" in output

    def test_format_for_cli_colorize(self):
        """Test CLI formatting respects colorize parameter."""
        results = [FormattedResult(message="Test", severity=Severity.ERROR)]

        # With color
        output_colored = format_for_cli(results, colorize=True, output_format="text")
        assert "\033[" in output_colored

        # Without color
        output_plain = format_for_cli(results, colorize=False, output_format="text")
        assert "\033[" not in output_plain

    def test_format_for_cli_verbose(self):
        """Test CLI formatting respects verbose parameter."""
        results = [FormattedResult(message="Test", suggestion="Fix")]

        # Not verbose
        output_brief = format_for_cli(results, verbose=False, output_format="text")
        assert "Suggestion:" not in output_brief

        # Verbose
        output_verbose = format_for_cli(results, verbose=True, output_format="text")
        assert "Suggestion:" in output_verbose
