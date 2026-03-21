"""
Heimdall Datetime Scanner Service

Detects deprecated and unsafe datetime usage patterns.
"""

import ast
import fnmatch
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.datetime_models import (
    DatetimeConfig,
    DatetimeReport,
    DatetimeViolation,
)
from Asgard.Heimdall.Quality.services._datetime_visitor import DatetimeVisitor
from Asgard.Heimdall.Quality.services._datetime_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class DatetimeScanner:
    """
    Scans Python files for deprecated and unsafe datetime usage.

    Detects:
    - datetime.utcnow() - deprecated in Python 3.12+
    - datetime.now() without timezone argument
    - datetime.today() - returns naive datetime
    - datetime.utcfromtimestamp() - deprecated

    Usage:
        scanner = DatetimeScanner()
        report = scanner.analyze(Path("./src"))

        for violation in report.detected_violations:
            print(f"{violation.location}: {violation.issue_type}")
    """

    def __init__(self, config: Optional[DatetimeConfig] = None):
        """
        Initialize datetime scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or DatetimeConfig()

    def analyze(self, path: Path) -> DatetimeReport:
        """
        Analyze a file or directory for datetime issues.

        Args:
            path: Path to file or directory to analyze

        Returns:
            DatetimeReport with all detected violations

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = DatetimeReport(scan_path=str(path))

        if path.is_file():
            violations = self._analyze_file(path, path.parent)
            for violation in violations:
                report.add_violation(violation)
            report.files_scanned = 1
        else:
            self._analyze_directory(path, report)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        file_violation_counts: Dict[str, int] = defaultdict(int)
        for violation in report.detected_violations:
            file_violation_counts[violation.file_path] += 1

        report.most_problematic_files = sorted(
            file_violation_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return report

    def _is_allowed_file(self, file_path: Path) -> bool:
        """Check if file is in allowed patterns."""
        file_str = str(file_path)
        for pattern in self.config.allowed_patterns:
            if fnmatch.fnmatch(file_str, pattern):
                return True
        return False

    def _analyze_file(self, file_path: Path, root_path: Path) -> List[DatetimeViolation]:
        """
        Analyze a single file for datetime issues.

        Args:
            file_path: Path to Python file
            root_path: Root path for calculating relative paths

        Returns:
            List of detected violations
        """
        if self._is_allowed_file(file_path):
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source)

            visitor = DatetimeVisitor(
                file_path=str(file_path.absolute()),
                source_lines=source_lines,
                config=self.config,
            )
            visitor.visit(tree)

            for violation in visitor.violations:
                try:
                    violation.relative_path = str(file_path.relative_to(root_path))
                except ValueError:
                    violation.relative_path = file_path.name

            return visitor.violations

        except SyntaxError:
            return []
        except Exception:
            return []

    def _analyze_directory(self, directory: Path, report: DatetimeReport) -> None:
        """
        Analyze all Python files in a directory.

        Args:
            directory: Directory to analyze
            report: Report to add violations to
        """
        files_scanned = 0

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, pattern) for pattern in self.config.exclude_patterns)
            ]

            for file in files:
                if not file.endswith(".py"):
                    continue

                if any(self._matches_pattern(file, pattern) for pattern in self.config.exclude_patterns):
                    continue

                if not self.config.include_tests:
                    if file.startswith("test_") or file.endswith("_test.py") or "tests" in str(root_path):
                        continue

                file_path = root_path / file
                violations = self._analyze_file(file_path, directory)
                files_scanned += 1

                for violation in violations:
                    report.add_violation(violation)

        report.files_scanned = files_scanned

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def generate_report(self, report: DatetimeReport, output_format: str = "text") -> str:
        """
        Generate formatted datetime report.

        Args:
            report: DatetimeReport to format
            output_format: Report format (text, json, markdown)

        Returns:
            Formatted report string
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}")
