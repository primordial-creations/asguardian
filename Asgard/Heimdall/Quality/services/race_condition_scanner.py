"""
Heimdall Race Condition Detector Service

Detects race condition patterns in Python code using AST analysis.

Detects:
- thread.start() called before the thread reference is stored on self (unreliable join)
- self.attr assignment after thread.start() (thread may read stale state)
- Check-then-act patterns on shared self attributes without lock protection
"""

import ast
import os
import fnmatch
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.race_condition_models import (
    RaceConditionConfig,
    RaceConditionIssue,
    RaceConditionReport,
)
from Asgard.Heimdall.Quality.services._race_condition_visitor import RaceConditionVisitor
from Asgard.Heimdall.Quality.services._race_condition_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class RaceConditionScanner:
    """
    Scans Python files for race condition patterns.

    Detects common race conditions in multi-threaded Python code,
    particularly around threading.Thread lifecycle and shared state.

    Usage:
        scanner = RaceConditionScanner()
        report = scanner.analyze(Path("./src"))

        for issue in report.detected_issues:
            print(f"{issue.location}: {issue.description}")
    """

    def __init__(self, config: Optional[RaceConditionConfig] = None):
        """
        Initialize race condition scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or RaceConditionConfig()

    def analyze(self, path: Path) -> RaceConditionReport:
        """
        Analyze a file or directory for race condition patterns.

        Args:
            path: Path to file or directory to analyze

        Returns:
            RaceConditionReport with all detected issues

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = RaceConditionReport(scan_path=str(path))

        if path.is_file():
            issues = self._analyze_file(path, path.parent)
            for issue in issues:
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

    def _analyze_file(self, file_path: Path, root_path: Path) -> List[RaceConditionIssue]:
        """Analyze a single file for race condition patterns."""
        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source)

            visitor = RaceConditionVisitor(
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

    def _analyze_directory(self, directory: Path, report: RaceConditionReport) -> None:
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

    def generate_report(self, report: RaceConditionReport, output_format: str = "text") -> str:
        """
        Generate formatted race condition report.

        Args:
            report: RaceConditionReport to format
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
