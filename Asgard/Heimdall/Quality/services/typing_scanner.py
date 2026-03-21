"""
Heimdall Typing Scanner Service

Analyzes type annotation coverage in Python code.
"""

import ast
import fnmatch
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.models.typing_models import (
    AnnotationStatus,
    FileTypingStats,
    TypingConfig,
    TypingReport,
)
from Asgard.Heimdall.Quality.services._typing_visitor import TypingVisitor
from Asgard.Heimdall.Quality.services._typing_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class TypingScanner:
    """
    Scans Python files for type annotation coverage.

    Calculates coverage percentage and identifies functions
    that need type annotations.

    Usage:
        scanner = TypingScanner()
        report = scanner.analyze(Path("./src"))

        print(f"Coverage: {report.coverage_percentage:.1f}%")
        for func in report.unannotated_functions:
            print(f"  {func.qualified_name}: {func.status}")
    """

    def __init__(self, config: Optional[TypingConfig] = None):
        """
        Initialize typing scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or TypingConfig()

    def analyze(self, path: Path) -> TypingReport:
        """
        Analyze a file or directory for typing coverage.

        Args:
            path: Path to file or directory to analyze

        Returns:
            TypingReport with coverage statistics

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = TypingReport(
            scan_path=str(path),
            threshold=self.config.minimum_coverage,
        )

        if path.is_file():
            file_stats = self._analyze_file(path, path.parent)
            if file_stats:
                report.add_file_stats(file_stats)
            report.files_scanned = 1
        else:
            self._analyze_directory(path, report)

        report.calculate_coverage()
        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        return report

    def _analyze_file(self, file_path: Path, root_path: Path) -> Optional[FileTypingStats]:
        """
        Analyze a single file for typing coverage.

        Args:
            file_path: Path to Python file
            root_path: Root path for calculating relative paths

        Returns:
            FileTypingStats or None if file cannot be analyzed
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            visitor = TypingVisitor(
                file_path=str(file_path.absolute()),
                config=self.config,
            )
            visitor.visit(tree)

            if not visitor.functions:
                return None

            try:
                relative_path = str(file_path.relative_to(root_path))
            except ValueError:
                relative_path = file_path.name

            for func in visitor.functions:
                func.relative_path = relative_path

            total = len(visitor.functions)
            fully = sum(1 for f in visitor.functions if f.status == AnnotationStatus.FULLY_ANNOTATED)
            partial = sum(1 for f in visitor.functions if f.status == AnnotationStatus.PARTIALLY_ANNOTATED)
            none = sum(1 for f in visitor.functions if f.status == AnnotationStatus.NOT_ANNOTATED)

            coverage = (fully / total * 100) if total > 0 else 100.0

            return FileTypingStats(
                file_path=str(file_path.absolute()),
                relative_path=relative_path,
                total_functions=total,
                fully_annotated=fully,
                partially_annotated=partial,
                not_annotated=none,
                coverage_percentage=coverage,
                functions=visitor.functions,
            )

        except SyntaxError:
            return None
        except Exception:
            return None

    def _analyze_directory(self, directory: Path, report: TypingReport) -> None:
        """
        Analyze all Python files in a directory.

        Args:
            directory: Directory to analyze
            report: Report to add statistics to
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

                file_path = root_path / file
                if any(self._matches_pattern(str(file_path), pattern) for pattern in self.config.exclude_patterns):
                    continue

                if not self.config.include_tests:
                    if file.startswith("test_") or file.endswith("_test.py") or "tests" in str(root_path):
                        continue

                file_stats = self._analyze_file(file_path, directory)
                files_scanned += 1

                if file_stats:
                    report.add_file_stats(file_stats)

        report.files_scanned = files_scanned

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def generate_report(self, report: TypingReport, output_format: str = "text") -> str:
        """
        Generate formatted typing coverage report.

        Args:
            report: TypingReport to format
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
