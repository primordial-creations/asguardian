"""
Heimdall Daemon Thread Monitor Service

Detects daemon thread lifecycle issues in Python code using AST analysis.

Detects:
- daemon=True threads with no join() call (uncontrolled lifecycle)
- daemon=True threads stored only in local variables (reference may be lost)
- Event.wait() patterns where only daemon threads call .set() (potential hang)
"""

import ast
import os
import fnmatch
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.daemon_thread_models import (
    DaemonThreadConfig,
    DaemonThreadIssue,
    DaemonThreadReport,
    DaemonThreadSeverity,
)
from Asgard.Heimdall.Quality.services._daemon_thread_visitor import DaemonThreadVisitor
from Asgard.Heimdall.Quality.services._daemon_thread_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class DaemonThreadScanner:
    """
    Scans Python files for daemon thread lifecycle issues.

    Detects patterns that can lead to silent failures or resource leaks
    in daemon thread usage.

    Usage:
        scanner = DaemonThreadScanner()
        report = scanner.analyze(Path("./src"))

        for issue in report.detected_issues:
            print(f"{issue.location}: {issue.description}")
    """

    def __init__(self, config: Optional[DaemonThreadConfig] = None):
        """
        Initialize daemon thread scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or DaemonThreadConfig()

    def analyze(self, path: Path) -> DaemonThreadReport:
        """
        Analyze a file or directory for daemon thread lifecycle issues.

        Args:
            path: Path to file or directory to analyze

        Returns:
            DaemonThreadReport with all detected issues

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = DaemonThreadReport(scan_path=str(path))

        if path.is_file():
            issues = self._analyze_file(path, path.parent)
            for issue in issues:
                if self._meets_severity_filter(issue.severity):
                    report.add_violation(issue)
            report.files_scanned = 1
        else:
            self._analyze_directory(path, report)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        file_violation_counts: Dict[str, int] = defaultdict(int)
        for issue in report.detected_issues:
            file_violation_counts[issue.file_path] += 1

        report.most_problematic_files = sorted(
            file_violation_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return report

    def _analyze_file(self, file_path: Path, root_path: Path) -> List[DaemonThreadIssue]:
        """Analyze a single file for daemon thread issues."""
        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source)

            visitor = DaemonThreadVisitor(
                file_path=str(file_path.absolute()),
                source_lines=source_lines,
            )
            visitor.visit(tree)

            for issue in visitor.issues:
                try:
                    issue.relative_path = str(file_path.relative_to(root_path))
                except ValueError:
                    issue.relative_path = file_path.name

            return visitor.issues

        except SyntaxError:
            return []
        except Exception:
            return []

    def _analyze_directory(self, directory: Path, report: DaemonThreadReport) -> None:
        """Analyze all Python files in a directory."""
        files_scanned = 0

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, pattern) for pattern in self.config.exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                if any(self._matches_pattern(file, pattern) for pattern in self.config.exclude_patterns):
                    continue

                if not self.config.include_tests:
                    if file.startswith("test_") or file.endswith("_test.py") or "tests" in str(root_path):
                        continue

                file_path = root_path / file
                issues = self._analyze_file(file_path, directory)
                files_scanned += 1

                for issue in issues:
                    if self._meets_severity_filter(issue.severity):
                        report.add_violation(issue)

        report.files_scanned = files_scanned

    def _should_analyze_file(self, filename: str) -> bool:
        """Check if file should be analyzed based on extension."""
        if self.config.include_extensions:
            return any(filename.endswith(ext) for ext in self.config.include_extensions)
        return filename.endswith(".py")

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def _meets_severity_filter(self, severity) -> bool:
        """Check if severity meets the configured filter."""
        return self._severity_level(severity) >= self._severity_level(self.config.severity_filter)

    def _severity_level(self, severity) -> int:
        """Convert severity to numeric level for comparison."""
        if isinstance(severity, str):
            severity = DaemonThreadSeverity(severity)
        levels = {
            DaemonThreadSeverity.LOW: 1,
            DaemonThreadSeverity.MEDIUM: 2,
        }
        return levels.get(severity, 1)

    def generate_report(self, report: DaemonThreadReport, output_format: str = "text") -> str:
        """
        Generate formatted daemon thread report.

        Args:
            report: DaemonThreadReport to format
            output_format: Report format (text, json, markdown)

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
