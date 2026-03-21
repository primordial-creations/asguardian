"""
Heimdall Error Handling Coverage Scanner Service

Detects functions and calls that are missing appropriate error handling,
which can cause silent failures, unhandled crashes, or hard-to-debug issues.

Detects:
- Thread target functions (threading.Thread(target=...)) that do not have
  a top-level try/except block in their body
- External calls (requests, urllib, subprocess, aiohttp) not inside a try/except
- Async functions that await external call patterns without error handling
"""

import ast
import fnmatch
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.error_handling_models import (
    ErrorHandlingConfig,
    ErrorHandlingReport,
    ErrorHandlingSeverity,
    ErrorHandlingViolation,
)
from Asgard.Heimdall.Quality.services._error_handling_reporter import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)
from Asgard.Heimdall.Quality.services._error_handling_visitor import (
    ErrorHandlingVisitor,
    ThreadTargetCollector,
)


class ErrorHandlingScanner:
    """
    Scans Python files for missing error handling around external calls
    and thread target functions.

    Usage:
        scanner = ErrorHandlingScanner()
        report = scanner.analyze(Path("./src"))

        for violation in report.detected_violations:
            print(f"{violation.location}: {violation.context_description}")
    """

    def __init__(self, config: Optional[ErrorHandlingConfig] = None):
        """
        Initialize error handling scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or ErrorHandlingConfig()

    def analyze(self, path: Path) -> ErrorHandlingReport:
        """
        Analyze a file or directory for error handling violations.

        Args:
            path: Path to file or directory to analyze

        Returns:
            ErrorHandlingReport with all detected violations

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = ErrorHandlingReport(scan_path=str(path))

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

    def _analyze_file(
        self, file_path: Path, root_path: Path
    ) -> List[ErrorHandlingViolation]:
        """
        Analyze a single Python file for error handling violations.

        Args:
            file_path: Path to Python file
            root_path: Root path for calculating relative paths

        Returns:
            List of detected violations
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source)

            target_collector = ThreadTargetCollector()
            target_collector.visit(tree)

            visitor = ErrorHandlingVisitor(
                file_path=str(file_path.absolute()),
                source_lines=source_lines,
                thread_targets=target_collector.thread_targets,
            )
            visitor.visit(tree)

            for violation in visitor.violations:
                try:
                    violation.relative_path = str(file_path.relative_to(root_path))
                except ValueError:
                    violation.relative_path = file_path.name

            filtered = [
                v for v in visitor.violations
                if self._severity_level(v.severity) >= self._severity_level(self.config.severity_filter)
            ]

            return filtered

        except SyntaxError:
            return []
        except Exception:
            return []

    def _analyze_directory(self, directory: Path, report: ErrorHandlingReport) -> None:
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
                if not any(self._matches_pattern(d, p) for p in self.config.exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                if any(self._matches_pattern(file, p) for p in self.config.exclude_patterns):
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

    def _should_analyze_file(self, filename: str) -> bool:
        """Check if file should be analyzed based on extension."""
        if self.config.include_extensions:
            return any(filename.endswith(ext) for ext in self.config.include_extensions)
        return filename.endswith(".py")

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def _severity_level(self, severity) -> int:
        """Convert severity to numeric level for comparison."""
        if isinstance(severity, str):
            severity = ErrorHandlingSeverity(severity)
        levels = {
            ErrorHandlingSeverity.LOW: 1,
            ErrorHandlingSeverity.MEDIUM: 2,
            ErrorHandlingSeverity.HIGH: 3,
        }
        return levels.get(severity, 1)

    def generate_report(self, report: ErrorHandlingReport, output_format: str = "text") -> str:
        """
        Generate formatted error handling report.

        Args:
            report: ErrorHandlingReport to format
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
