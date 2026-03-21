"""
Heimdall Naming Convention Scanner Service

Enforces Python PEP 8 naming conventions by parsing source files with the AST
module and checking function, class, variable, and constant names.

Rules enforced:
- Functions and methods:  snake_case
- Classes:                PascalCase
- Module-level variables: snake_case
- Module-level constants: UPPER_CASE_WITH_UNDERSCORES
- Dunder methods:         exempt
- Type aliases (T, K, V): exempt
- Private members:        _ prefix variant of their type rule
"""

import ast
import fnmatch
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.models.naming_models import (
    NamingConfig,
    NamingConvention,
    NamingReport,
    NamingViolation,
)
from Asgard.Heimdall.Quality.services._naming_helpers import (
    _is_dunder,
    _is_pascal_case,
    _is_snake_case,
    check_ann_assignment,
    check_module_assignment,
)
from Asgard.Heimdall.Quality.services._naming_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class NamingConventionScanner:
    """
    Scans Python source files for PEP 8 naming convention violations.

    Checks functions, methods, classes, module-level variables, and constants.
    Dunder methods and type aliases are exempt from checking.

    Usage:
        scanner = NamingConventionScanner()
        report = scanner.scan(Path("./src"))

        print(f"Total violations: {report.total_violations}")
        for file_path, violations in report.file_results.items():
            for v in violations:
                print(f"  {v.file_path}:{v.line_number} {v.element_name}")
    """

    def __init__(self, config: Optional[NamingConfig] = None):
        """
        Initialize the naming convention scanner.

        Args:
            config: Configuration for the scanner. If None, uses defaults.
        """
        self.config = config or NamingConfig()

    def scan(self, scan_path: Path) -> NamingReport:
        """
        Scan a directory for naming convention violations.

        Args:
            scan_path: Path to directory to analyze

        Returns:
            NamingReport with all violations found

        Raises:
            FileNotFoundError: If scan_path does not exist
        """
        if not scan_path.exists():
            raise FileNotFoundError(f"Path does not exist: {scan_path}")

        start_time = datetime.now()
        report = NamingReport(scan_path=str(scan_path))

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
                    violations = self._analyze_file(file_path)
                    for violation in violations:
                        report.add_violation(violation)
                except Exception:
                    pass

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        return report

    def _analyze_file(self, file_path: Path) -> List[NamingViolation]:
        """Analyze a single file for naming violations."""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, Exception):
            return []

        violations: List[NamingViolation] = []
        str_path = str(file_path)

        self._check_module(tree, str_path, violations)

        return violations

    def _check_module(
        self, tree: ast.AST, file_path: str, violations: List[NamingViolation]
    ) -> None:
        """Check all definitions in a module AST."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.config.check_functions:
                    self._check_function(node, file_path, violations, in_class=False)
            elif isinstance(node, ast.ClassDef):
                if self.config.check_classes:
                    self._check_class(node, file_path, violations)
            elif isinstance(node, ast.Assign):
                self._check_module_assignment(node, file_path, violations)
            elif isinstance(node, ast.AnnAssign):
                self._check_ann_assignment(node, file_path, violations)

    def _check_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        violations: List[NamingViolation],
        in_class: bool = False,
    ) -> None:
        """Check a function or method name for snake_case compliance."""
        name = node.name

        if _is_dunder(name):
            return

        if name in self.config.allow_list:
            return

        if not _is_snake_case(name):
            element_type = "method" if in_class else "function"
            violations.append(NamingViolation(
                file_path=file_path,
                line_number=node.lineno,
                element_type=element_type,
                element_name=name,
                expected_convention=NamingConvention.SNAKE_CASE,
                description=(
                    f"{element_type.capitalize()} '{name}' does not follow snake_case convention"
                ),
            ))

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.config.check_functions:
                    self._check_function(child, file_path, violations, in_class=in_class)

    def _check_class(
        self, node: ast.ClassDef, file_path: str, violations: List[NamingViolation]
    ) -> None:
        """Check a class name for PascalCase compliance and its methods."""
        name = node.name

        if name in self.config.allow_list:
            return

        if not _is_pascal_case(name):
            violations.append(NamingViolation(
                file_path=file_path,
                line_number=node.lineno,
                element_type="class",
                element_name=name,
                expected_convention=NamingConvention.PASCAL_CASE,
                description=f"Class '{name}' does not follow PascalCase convention",
            ))

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.config.check_functions:
                    self._check_function(child, file_path, violations, in_class=True)
            elif isinstance(child, ast.ClassDef):
                if self.config.check_classes:
                    self._check_class(child, file_path, violations)

    def _check_module_assignment(
        self, node: ast.Assign, file_path: str, violations: List[NamingViolation]
    ) -> None:
        """Check module-level assignment targets for naming compliance."""
        check_module_assignment(node, file_path, violations, self.config)

    def _check_ann_assignment(
        self, node: ast.AnnAssign, file_path: str, violations: List[NamingViolation]
    ) -> None:
        """Check annotated module-level assignment targets for naming compliance."""
        check_ann_assignment(node, file_path, violations, self.config)

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

    def generate_report(self, report: NamingReport, output_format: str = "text") -> str:
        """
        Generate a formatted naming violations report string.

        Args:
            report: NamingReport to format
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
