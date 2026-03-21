"""
Heimdall Lazy Import Scanner Service

Detects imports that are not at the top of the file, which violates
the coding standard that ALL imports MUST be at the top of the file.

Detects:
- Imports inside functions
- Imports inside class methods
- Imports inside conditional blocks (if/else)
- Imports inside try/except blocks
- Imports inside loops (for/while)
- Imports inside with blocks
"""

import ast
import os
import fnmatch
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.lazy_import_models import (
    LazyImport,
    LazyImportConfig,
    LazyImportReport,
    LazyImportSeverity,
)
from Asgard.Heimdall.Quality.services._lazy_import_visitor import LazyImportVisitor
from Asgard.Heimdall.Quality.services._lazy_import_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class LazyImportScanner:
    """
    Scans Python files for lazy imports (imports not at module level).

    Detects imports inside functions, methods, conditionals, try/except blocks,
    loops, and with blocks - all of which violate the coding standard.

    Usage:
        scanner = LazyImportScanner()
        report = scanner.analyze(Path("./src"))

        for violation in report.detected_imports:
            print(f"{violation.location}: {violation.import_statement}")
    """

    def __init__(self, config: Optional[LazyImportConfig] = None):
        """
        Initialize lazy import scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or LazyImportConfig()

    def analyze(self, path: Path) -> LazyImportReport:
        """
        Analyze a file or directory for lazy imports.

        Args:
            path: Path to file or directory to analyze

        Returns:
            LazyImportReport with all detected violations

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = LazyImportReport(scan_path=str(path))

        if path.is_file():
            violations = self._analyze_file(path, path.parent)
            for violation in violations:
                report.add_violation(violation)
            report.files_scanned = 1
        else:
            self._analyze_directory(path, report)

        # Calculate scan duration
        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        # Calculate most problematic files
        file_violation_counts: Dict[str, int] = defaultdict(int)
        for violation in report.detected_imports:
            file_violation_counts[violation.file_path] += 1

        report.most_problematic_files = sorted(
            file_violation_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return report

    def analyze_single_file(self, file_path: Path) -> LazyImportReport:
        """
        Analyze a single file for lazy imports.

        Args:
            file_path: Path to Python file

        Returns:
            LazyImportReport with detected violations
        """
        return self.analyze(file_path)

    def _analyze_file(self, file_path: Path, root_path: Path) -> List[LazyImport]:
        """
        Analyze a single file for lazy imports.

        Args:
            file_path: Path to Python file
            root_path: Root path for calculating relative paths

        Returns:
            List of detected lazy imports
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source)

            visitor = LazyImportVisitor(
                file_path=str(file_path.absolute()),
                source_lines=source_lines,
            )
            visitor.visit(tree)

            # Set relative paths
            for lazy_import in visitor.lazy_imports:
                try:
                    lazy_import.relative_path = str(file_path.relative_to(root_path))
                except ValueError:
                    lazy_import.relative_path = file_path.name

            # Filter by severity
            filtered = [
                v for v in visitor.lazy_imports
                if self._severity_level(v.severity) >= self._severity_level(self.config.severity_filter)
            ]

            return filtered

        except SyntaxError:
            # Cannot parse file - skip it
            return []
        except Exception:
            # Other errors - skip file
            return []

    def _analyze_directory(self, directory: Path, report: LazyImportReport) -> None:
        """
        Analyze all Python files in a directory.

        Args:
            directory: Directory to analyze
            report: Report to add violations to
        """
        files_scanned = 0

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            # Filter excluded directories
            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, pattern) for pattern in self.config.exclude_patterns)
            ]

            for file in files:
                # Check if file should be analyzed
                if not self._should_analyze_file(file):
                    continue

                # Check exclude patterns
                if any(self._matches_pattern(file, pattern) for pattern in self.config.exclude_patterns):
                    continue

                # Check test file inclusion
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
            severity = LazyImportSeverity(severity)
        levels = {
            LazyImportSeverity.LOW: 1,
            LazyImportSeverity.MEDIUM: 2,
            LazyImportSeverity.HIGH: 3,
        }
        return levels.get(severity, 1)

    def generate_report(self, report: LazyImportReport, output_format: str = "text") -> str:
        """
        Generate formatted lazy import report.

        Args:
            report: LazyImportReport to format
            output_format: Report format (text, json, markdown)

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report)
        elif format_lower == "markdown" or format_lower == "md":
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
