"""
GitHub Actions Formatter

Formats analysis results in GitHub Actions workflow command format
for inline annotations in pull request diffs.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from Asgard.Reporting._github_format_helpers import (
    format_complexity_tuples,
    format_datetime_tuples,
    format_forbidden_imports_tuples,
    format_lazy_imports_tuples,
    format_security_tuples,
    format_smells_tuples,
    format_typing_tuples,
)


class AnnotationLevel(str, Enum):
    """GitHub annotation levels."""
    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"


@dataclass
class Annotation:
    """Represents a GitHub Actions annotation."""
    level: AnnotationLevel
    file: str
    line: int
    message: str
    title: Optional[str] = None
    end_line: Optional[int] = None
    col: Optional[int] = None
    end_col: Optional[int] = None

    def to_workflow_command(self) -> str:
        """Convert to GitHub Actions workflow command format."""
        parts = [f"file={self.file}", f"line={self.line}"]

        if self.end_line:
            parts.append(f"endLine={self.end_line}")
        if self.col:
            parts.append(f"col={self.col}")
        if self.end_col:
            parts.append(f"endColumn={self.end_col}")
        if self.title:
            parts.append(f"title={self.title}")

        properties = ",".join(parts)
        return f"::{self.level.value} {properties}::{self.message}"


class ReportProtocol(Protocol):
    """Protocol for report objects that can be formatted."""
    scan_path: str
    has_violations: bool


class GitHubActionsFormatter:
    """
    Formats analysis results for GitHub Actions workflow commands.

    Outputs annotations in the format:
        ::error file=path/to/file.py,line=10::Message here
        ::warning file=path/to/file.py,line=25::Message here
        ::notice file=path/to/file.py,line=50::Message here

    These annotations appear inline in pull request diffs and the
    Actions summary view.

    Usage:
        formatter = GitHubActionsFormatter()

        # From a lazy import report
        output = formatter.format_lazy_imports(report)
        print(output)

        # From a datetime report
        output = formatter.format_datetime(report)

        # Generic formatting
        annotations = [
            Annotation(AnnotationLevel.ERROR, "src/main.py", 10, "Issue found"),
        ]
        output = formatter.format_annotations(annotations)
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize the GitHub Actions formatter.

        Args:
            base_path: Base path for making file paths relative.
                      If not provided, uses current directory.
        """
        self.base_path = base_path or Path.cwd()

    def _relative_path(self, path: str) -> str:
        """Convert absolute path to relative path."""
        try:
            return str(Path(path).relative_to(self.base_path))
        except ValueError:
            return path

    def _make_annotation(self, tup: tuple) -> Annotation:
        """Build an Annotation from a helper tuple."""
        level_str, file, line, message, title, col = tup
        level = AnnotationLevel(level_str)
        return Annotation(level=level, file=file, line=line, message=message, title=title, col=col)

    def format_annotations(self, annotations: List[Annotation]) -> str:
        """
        Format a list of annotations as workflow commands.

        Args:
            annotations: List of Annotation objects

        Returns:
            Newline-separated workflow commands
        """
        return "\n".join(ann.to_workflow_command() for ann in annotations)

    def format_lazy_imports(self, report) -> str:
        """Format lazy import report for GitHub Actions."""
        tuples = format_lazy_imports_tuples(report, self._relative_path, self._severity_to_level_str)
        return self.format_annotations([self._make_annotation(t) for t in tuples])

    def format_forbidden_imports(self, report) -> str:
        """Format forbidden imports report for GitHub Actions."""
        tuples = format_forbidden_imports_tuples(report, self._relative_path)
        return self.format_annotations([self._make_annotation(t) for t in tuples])

    def format_datetime(self, report) -> str:
        """Format datetime usage report for GitHub Actions."""
        tuples = format_datetime_tuples(report, self._relative_path, self._severity_to_level_str)
        return self.format_annotations([self._make_annotation(t) for t in tuples])

    def format_typing(self, report) -> str:
        """Format typing coverage report for GitHub Actions."""
        tuples = format_typing_tuples(report, self._relative_path, self._severity_to_level_str)
        return self.format_annotations([self._make_annotation(t) for t in tuples])

    def format_complexity(self, report) -> str:
        """Format complexity report for GitHub Actions."""
        tuples = format_complexity_tuples(report, self._relative_path, self._complexity_to_level_str)
        return self.format_annotations([self._make_annotation(t) for t in tuples])

    def format_smells(self, report) -> str:
        """Format code smell report for GitHub Actions."""
        tuples = format_smells_tuples(report, self._relative_path, self._severity_to_level_str)
        return self.format_annotations([self._make_annotation(t) for t in tuples])

    def format_security(self, report) -> str:
        """Format security report for GitHub Actions."""
        tuples = format_security_tuples(report, self._relative_path, self._security_to_level_str)
        return self.format_annotations([self._make_annotation(t) for t in tuples])

    def _severity_to_level(self, severity: Any) -> AnnotationLevel:
        """Map generic severity to GitHub annotation level."""
        return AnnotationLevel(self._severity_to_level_str(severity))

    def _severity_to_level_str(self, severity: Any) -> str:
        """Map generic severity to GitHub annotation level string."""
        severity_str = severity if isinstance(severity, str) else severity.value
        if severity_str in ("high", "critical"):
            return "error"
        elif severity_str in ("medium", "moderate"):
            return "warning"
        return "notice"

    def _complexity_to_level(self, severity_str: str) -> AnnotationLevel:
        """Map complexity severity to GitHub annotation level."""
        return AnnotationLevel(self._complexity_to_level_str(severity_str))

    def _complexity_to_level_str(self, severity_str: str) -> str:
        """Map complexity severity to GitHub annotation level string."""
        if severity_str in ("critical", "very_high"):
            return "error"
        elif severity_str == "high":
            return "warning"
        return "notice"

    def _security_to_level(self, severity: Any) -> AnnotationLevel:
        """Map security severity to GitHub annotation level."""
        return AnnotationLevel(self._security_to_level_str(severity))

    def _security_to_level_str(self, severity: Any) -> str:
        """Map security severity to GitHub annotation level string."""
        severity_str = severity if isinstance(severity, str) else severity.value
        if severity_str in ("critical", "high"):
            return "error"
        elif severity_str == "medium":
            return "warning"
        return "notice"

    def format_summary(
        self,
        title: str,
        results: Dict[str, Any],
        passed: bool,
    ) -> str:
        """
        Generate a GitHub Actions job summary.

        Args:
            title: Summary title
            results: Dictionary of check results
            passed: Whether all checks passed

        Returns:
            Markdown-formatted summary for $GITHUB_STEP_SUMMARY
        """
        status_emoji = "PASS" if passed else "FAIL"

        lines = [
            f"## {title}",
            "",
            f"**Status:** {status_emoji}",
            "",
            "| Check | Result |",
            "|-------|--------|",
        ]

        for check, result in results.items():
            status = "Pass" if result.get("passed", True) else "Fail"
            count = result.get("count", 0)
            lines.append(f"| {check} | {status} ({count} issues) |")

        return "\n".join(lines)
