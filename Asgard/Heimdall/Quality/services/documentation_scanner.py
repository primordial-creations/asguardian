"""
Heimdall Documentation Scanner Service

Analyzes Python source files for comment density and public API documentation
coverage. Counts comment lines (single-line # comments, multi-line docstrings),
detects undocumented public functions and classes, and produces per-file and
summary-level reports.
"""

import ast
import fnmatch
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Quality.models.documentation_models import (
    DocumentationConfig,
    DocumentationReport,
    FileDocumentation,
)
from Asgard.Heimdall.Quality.services._documentation_helpers import (
    count_lines,
    extract_documentation,
)
from Asgard.Heimdall.Quality.services._documentation_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class DocumentationScanner:
    """
    Analyzes Python source files for comment density and public API documentation.

    Counts comment lines (single-line # comments and docstrings), calculates
    comment density, identifies undocumented public functions and classes, and
    produces per-file and project-level coverage reports.

    Usage:
        scanner = DocumentationScanner()
        report = scanner.scan(Path("./src"))

        print(f"Comment density: {report.overall_comment_density:.1f}%")
        print(f"API coverage: {report.overall_api_coverage:.1f}%")
        print(f"Undocumented APIs: {report.undocumented_apis}")
    """

    def __init__(self, config: Optional[DocumentationConfig] = None):
        """
        Initialize the documentation scanner.

        Args:
            config: Configuration for the scanner. If None, uses defaults.
        """
        self.config = config or DocumentationConfig()

    def scan(self, scan_path: Path) -> DocumentationReport:
        """
        Scan a directory for documentation coverage and comment density.

        Args:
            scan_path: Path to directory to analyze

        Returns:
            DocumentationReport with per-file and summary results

        Raises:
            FileNotFoundError: If scan_path does not exist
        """
        if not scan_path.exists():
            raise FileNotFoundError(f"Path does not exist: {scan_path}")

        start_time = datetime.now()
        report = DocumentationReport(scan_path=str(scan_path))

        for root, dirs, files in os.walk(scan_path):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, p) for p in self.config.exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                file_path = root_path / file
                try:
                    file_result = self._analyze_file(file_path)
                    if file_result is not None:
                        report.file_results.append(file_result)
                        report.total_files += 1
                        report.total_public_apis += file_result.total_public_apis
                        report.undocumented_apis += file_result.undocumented_count
                except Exception:
                    pass

        if report.file_results:
            total_non_blank = sum(
                f.total_lines - f.blank_lines for f in report.file_results
            )
            total_comment = sum(f.comment_lines for f in report.file_results)
            if total_non_blank > 0:
                report.overall_comment_density = (total_comment / total_non_blank) * 100.0

            if report.total_public_apis > 0:
                documented = report.total_public_apis - report.undocumented_apis
                report.overall_api_coverage = (documented / report.total_public_apis) * 100.0

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        return report

    def _analyze_file(self, file_path: Path) -> Optional[FileDocumentation]:
        """Analyze a single Python file for documentation metrics."""
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        total_lines, code_lines, comment_lines, blank_lines = count_lines(source)

        non_blank = total_lines - blank_lines
        comment_density = (comment_lines / non_blank * 100.0) if non_blank > 0 else 0.0

        functions, classes = extract_documentation(tree)

        undocumented = 0
        for func in functions:
            if func.is_public and not func.has_docstring:
                undocumented += 1
        for cls in classes:
            if cls.is_public and not cls.has_docstring:
                undocumented += 1
            for method in cls.methods:
                if method.is_public and not method.has_docstring:
                    undocumented += 1

        total_public = sum(1 for f in functions if f.is_public)
        total_public += sum(1 for c in classes if c.is_public)
        total_public += sum(
            sum(1 for m in c.methods if m.is_public)
            for c in classes
        )

        if total_public > 0:
            documented_count = total_public - undocumented
            coverage = (documented_count / total_public) * 100.0
        else:
            coverage = 100.0

        return FileDocumentation(
            path=str(file_path),
            total_lines=total_lines,
            code_lines=code_lines,
            comment_lines=comment_lines,
            blank_lines=blank_lines,
            comment_density=round(comment_density, 2),
            public_api_coverage=round(coverage, 2),
            undocumented_count=undocumented,
            functions=functions,
            classes=classes,
        )

    def _should_analyze_file(self, filename: str) -> bool:
        """Determine whether a file should be analyzed."""
        has_valid_ext = any(filename.endswith(ext) for ext in self.config.include_extensions)
        if not has_valid_ext:
            return False

        if any(self._matches_pattern(filename, p) for p in self.config.exclude_patterns):
            return False

        if not self.config.include_tests:
            if filename.startswith("test_") or filename.endswith("_test.py"):
                return False

        return True

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if a name matches an exclude glob pattern."""
        return fnmatch.fnmatch(name, pattern)

    def generate_report(self, report: DocumentationReport, output_format: str = "text") -> str:
        """
        Generate a formatted documentation report string.

        Args:
            report: DocumentationReport to format
            output_format: Output format (text, json, markdown)

        Returns:
            Formatted report string

        Raises:
            ValueError: If output_format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(
                f"Unsupported format: {output_format}. Use: text, json, markdown"
            )
