"""
Heimdall Gap Analyzer Service

Analyzes test coverage gaps in the codebase.
"""

from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Coverage.models.coverage_models import (
    CoverageConfig,
    CoverageGap,
    CoverageSeverity,
    MethodInfo,
    MethodType,
)
from Asgard.Heimdall.Coverage.services._gap_analysis_helpers import (
    analyze_class_coverage,
    analyze_gaps,
)
from Asgard.Heimdall.Coverage.utilities.method_extractor import (
    extract_methods,
    find_test_methods,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


class GapAnalyzer:
    """
    Analyzes test coverage gaps in Python code.

    Identifies:
    - Uncovered methods
    - Partially covered classes
    - Complex code without tests
    - Critical paths without coverage
    """

    def __init__(self, config: Optional[CoverageConfig] = None):
        """Initialize the gap analyzer."""
        self.config = config or CoverageConfig()

    def analyze(
        self,
        scan_path: Optional[Path] = None,
        test_path: Optional[Path] = None
    ) -> tuple:
        """
        Analyze test coverage gaps.

        Args:
            scan_path: Root path to scan for source code
            test_path: Path to test files

        Returns:
            Tuple of (gaps, metrics, class_coverage)
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        test_paths = self._find_test_paths(path, test_path)
        source_methods = self._collect_source_methods(path)
        test_methods = self._collect_test_methods(test_paths)

        gaps, metrics = analyze_gaps(source_methods, test_methods)
        class_cov = analyze_class_coverage(path, test_methods, self.config)

        return gaps, metrics, class_cov

    def _find_test_paths(
        self,
        scan_path: Path,
        test_path: Optional[Path]
    ) -> List[Path]:
        """Find all test directories."""
        test_paths = list(self.config.test_paths)

        if test_path:
            test_paths.append(test_path)

        for pattern in ["tests", "test", "Tests", "Test"]:
            potential = scan_path / pattern
            if potential.exists() and potential not in test_paths:
                test_paths.append(potential)

        return test_paths

    def _collect_source_methods(self, path: Path) -> List[MethodInfo]:
        """Collect all source methods."""
        methods = []

        exclude_patterns = list(self.config.exclude_patterns)
        exclude_patterns.extend(["test_", "_test.py", "tests/", "conftest.py"])

        for file_path in scan_directory(
            path,
            exclude_patterns=exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                file_methods = extract_methods(source, str(file_path))

                for method in file_methods:
                    if not self.config.include_private and method.method_type == MethodType.PRIVATE:
                        continue
                    if not self.config.include_dunder and method.method_type == MethodType.DUNDER:
                        continue
                    methods.append(method)

            except (SyntaxError, Exception):
                continue

        return methods

    def _collect_test_methods(self, test_paths: List[Path]) -> List[MethodInfo]:
        """Collect all test methods."""
        methods = []

        for test_path in test_paths:
            if not test_path.exists():
                continue

            for file_path in scan_directory(
                test_path,
                exclude_patterns=self.config.exclude_patterns,
                include_extensions=[".py"],
            ):
                try:
                    source = file_path.read_text(encoding="utf-8", errors="ignore")
                    test_methods = find_test_methods(source, str(file_path))
                    methods.extend(test_methods)
                except (SyntaxError, Exception):
                    continue

        return methods

    def get_critical_gaps(
        self,
        scan_path: Optional[Path] = None
    ) -> List[CoverageGap]:
        """
        Get only critical and high severity gaps.

        Args:
            scan_path: Root path to scan

        Returns:
            List of critical coverage gaps
        """
        gaps, _, _ = self.analyze(scan_path)

        return [
            g for g in gaps
            if g.severity in (CoverageSeverity.CRITICAL, CoverageSeverity.HIGH)
        ]

    def get_uncovered_classes(
        self,
        scan_path: Optional[Path] = None,
        threshold: float = 50.0
    ) -> list:
        """
        Get classes with coverage below threshold.

        Args:
            scan_path: Root path to scan
            threshold: Minimum coverage percentage

        Returns:
            List of poorly covered classes
        """
        _, _, class_coverage = self.analyze(scan_path)

        return [
            c for c in class_coverage
            if c.coverage_percent < threshold
        ]
