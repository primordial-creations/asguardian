"""
Heimdall Gap Analyzer - standalone analysis helper functions.

Standalone functions for gap detection, severity calculation, and class
coverage analysis. Accept data objects as explicit parameters.
"""

from pathlib import Path
from typing import List, Optional, Set, Tuple

from Asgard.Heimdall.Coverage.models.coverage_models import (
    ClassCoverage,
    CoverageConfig,
    CoverageGap,
    CoverageMetrics,
    CoverageSeverity,
    MethodInfo,
    MethodType,
)
from Asgard.Heimdall.Coverage.utilities.method_extractor import (
    extract_classes_with_methods,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


def build_test_name_set(test_methods: List[MethodInfo]) -> Set[str]:
    """Build a set of normalized test names."""
    names: Set[str] = set()

    for method in test_methods:
        names.add(method.name.lower())

        if method.name.startswith("test_"):
            tested = method.name[5:].lower()
            names.add(tested)

    return names


def is_method_covered(method: MethodInfo, test_names: Set[str]) -> bool:
    """Check if a method appears to be covered by tests."""
    method_name = method.name.lower()
    full_name = method.full_name.lower().replace(".", "_")

    patterns = [
        f"test_{method_name}",
        f"test_{full_name}",
        method_name,
        full_name,
    ]

    for pattern in patterns:
        if pattern in test_names:
            return True

    return False


def calculate_gap_severity(method: MethodInfo) -> CoverageSeverity:
    """Calculate severity based on method characteristics."""
    score = 0

    if method.complexity > 10:
        score += 3
    elif method.complexity > 5:
        score += 2
    elif method.complexity > 2:
        score += 1

    if method.branch_count > 5:
        score += 2
    elif method.branch_count > 2:
        score += 1

    if method.method_type == MethodType.PUBLIC:
        score += 1

    if method.is_async:
        score += 1

    if score >= 5:
        return CoverageSeverity.CRITICAL
    elif score >= 3:
        return CoverageSeverity.HIGH
    elif score >= 2:
        return CoverageSeverity.MODERATE
    else:
        return CoverageSeverity.LOW


def create_gap(method: MethodInfo) -> CoverageGap:
    """Create a coverage gap for an uncovered method."""
    severity = calculate_gap_severity(method)

    gap_type = "uncovered"
    message = f"Method '{method.full_name}' has no test coverage"

    details = []
    if method.complexity > 5:
        details.append(f"High complexity: {method.complexity}")
    if method.has_branches:
        details.append(f"Has {method.branch_count} branches")
    if method.parameter_count > 3:
        details.append(f"Has {method.parameter_count} parameters")

    return CoverageGap(
        method=method,
        gap_type=gap_type,
        severity=severity,
        message=message,
        details="; ".join(details) if details else "",
    )


def analyze_gaps(
    source_methods: List[MethodInfo],
    test_methods: List[MethodInfo],
) -> Tuple[List[CoverageGap], CoverageMetrics]:
    """Analyze coverage gaps between source and test methods."""
    gaps: List[CoverageGap] = []
    metrics = CoverageMetrics()

    test_names = build_test_name_set(test_methods)

    metrics.total_methods = len(source_methods)
    covered_count = 0

    for method in source_methods:
        if is_method_covered(method, test_names):
            covered_count += 1
        else:
            gap = create_gap(method)
            gaps.append(gap)

        if method.has_branches:
            metrics.total_branches += method.branch_count

    metrics.covered_methods = covered_count

    return gaps, metrics


def analyze_class_coverage(
    path: Path,
    test_methods: List[MethodInfo],
    config: CoverageConfig,
) -> List[ClassCoverage]:
    """Analyze coverage at the class level."""
    class_coverage: List[ClassCoverage] = []
    test_names = build_test_name_set(test_methods)

    exclude_patterns = list(config.exclude_patterns)
    exclude_patterns.extend(["test_", "_test.py", "tests/"])

    for file_path in scan_directory(
        path,
        exclude_patterns=exclude_patterns,
        include_extensions=config.include_extensions,
    ):
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            classes = extract_classes_with_methods(source, str(file_path))

            for class_name, methods in classes.items():
                filtered = [
                    m for m in methods
                    if (config.include_private or m.method_type != MethodType.PRIVATE)
                    and (config.include_dunder or m.method_type != MethodType.DUNDER)
                ]

                if not filtered:
                    continue

                covered = [
                    m for m in filtered
                    if is_method_covered(m, test_names)
                ]

                uncovered = [
                    m.name for m in filtered
                    if not is_method_covered(m, test_names)
                ]

                coverage_pct = (len(covered) / len(filtered)) * 100 if filtered else 100

                class_coverage.append(ClassCoverage(
                    class_name=class_name,
                    file_path=str(file_path),
                    total_methods=len(filtered),
                    covered_methods=len(covered),
                    uncovered_methods=uncovered,
                    coverage_percent=coverage_pct,
                ))

        except (SyntaxError, Exception):
            continue

    return class_coverage
