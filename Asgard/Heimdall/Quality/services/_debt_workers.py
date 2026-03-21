"""
Heimdall Technical Debt Analyzer - debt analysis worker functions.

Standalone functions for each debt category analysis and related helpers.
All functions accept the config and report as explicit parameters so they
can be called from TechnicalDebtAnalyzer without holding private state.
"""

import ast
import fnmatch
import math
import os
from pathlib import Path
from typing import Dict, List, Tuple, cast

from Asgard.Heimdall.Quality.models.debt_models import (
    DebtConfig,
    DebtItem,
    DebtReport,
    DebtSeverity,
    DebtType,
)
from Asgard.Heimdall.Quality.services._technical_debt_visitor import ComplexityVisitor


def analyze_code_debt(path: Path, report: DebtReport, config: DebtConfig) -> None:
    """Analyze code quality debt."""
    for root, dirs, files in os.walk(path):
        root_path = Path(root)

        dirs[:] = [
            d for d in dirs
            if not any(matches_pattern(d, p) for p in config.exclude_patterns)
        ]

        for file in files:
            if not should_analyze_file(file, config):
                continue

            file_path = root_path / file
            try:
                items = analyze_file_complexity(file_path, config)
                for item in items:
                    report.add_debt_item(item)
            except Exception:
                pass


def analyze_file_complexity(file_path: Path, config: DebtConfig) -> List[DebtItem]:
    """Analyze complexity-related debt in a file."""
    debt_items = []

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        visitor = ComplexityVisitor()
        visitor.visit(tree)

        for func_name, complexity, line_no in visitor.complex_functions:
            severity = DebtSeverity.CRITICAL if complexity > 30 else DebtSeverity.HIGH
            effort = config.effort_models.complexity_reduction_factor * complexity

            debt_items.append(DebtItem(
                debt_type=DebtType.CODE,
                file_path=str(file_path.absolute()),
                line_number=line_no,
                description=f"High complexity function '{func_name}' (complexity: {complexity})",
                severity=severity,
                effort_hours=effort,
                business_impact=get_business_impact(str(file_path), config),
                interest_rate=config.interest_rates.high_complexity,
                remediation_strategy="Break down into smaller functions, reduce nesting, extract helper methods",
            ))

        for func_name, length, line_no in visitor.long_methods:
            effort = config.effort_models.refactoring_log_factor * math.log(length)

            debt_items.append(DebtItem(
                debt_type=DebtType.CODE,
                file_path=str(file_path.absolute()),
                line_number=line_no,
                description=f"Long method '{func_name}' ({length} lines)",
                severity=DebtSeverity.MEDIUM,
                effort_hours=effort,
                business_impact=get_business_impact(str(file_path), config),
                interest_rate=config.interest_rates.high_complexity * 0.5,
                remediation_strategy="Extract methods, simplify logic, apply single responsibility",
            ))

    except SyntaxError:
        pass
    except Exception:
        pass

    return debt_items


def analyze_design_debt(path: Path, report: DebtReport, config: DebtConfig) -> None:
    """Analyze architectural/design debt."""
    dependency_map = build_dependency_map(path, config)

    for file_path, dependencies in dependency_map.items():
        if len(dependencies) > 10:
            effort = math.log(len(dependencies)) * 3
            severity = DebtSeverity.HIGH if len(dependencies) > 15 else DebtSeverity.MEDIUM

            report.add_debt_item(DebtItem(
                debt_type=DebtType.DESIGN,
                file_path=file_path,
                line_number=1,
                description=f"High coupling: {len(dependencies)} dependencies",
                severity=severity,
                effort_hours=effort,
                business_impact=get_business_impact(file_path, config),
                interest_rate=config.interest_rates.design_issues,
                remediation_strategy="Reduce dependencies, apply dependency inversion, use interfaces",
            ))


def analyze_test_debt(path: Path, report: DebtReport, config: DebtConfig) -> None:
    """Analyze test coverage debt."""
    python_files = []
    test_files = set()

    for root, dirs, files in os.walk(path):
        dirs[:] = [
            d for d in dirs
            if not any(matches_pattern(d, p) for p in config.exclude_patterns)
        ]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                if "test" in file.lower() or file.startswith("test_"):
                    test_files.add(file_path)
                else:
                    python_files.append(file_path)

    for file_path in python_files:
        base_name = os.path.basename(file_path)
        test_variants = [
            f"test_{base_name}",
            base_name.replace(".py", "_test.py"),
        ]

        has_tests = any(
            variant in os.path.basename(tf) for tf in test_files for variant in test_variants
        )

        if not has_tests:
            loc = count_file_lines(file_path)
            if loc == 0:
                continue

            effort = config.effort_models.test_coverage_factor * loc
            severity = DebtSeverity.HIGH if loc > 100 else DebtSeverity.MEDIUM

            report.add_debt_item(DebtItem(
                debt_type=DebtType.TEST,
                file_path=file_path,
                line_number=1,
                description=f"No test coverage found ({loc} lines)",
                severity=severity,
                effort_hours=effort,
                business_impact=get_business_impact(file_path, config),
                interest_rate=config.interest_rates.no_tests,
                remediation_strategy="Write unit tests for public functions and critical paths",
            ))


def analyze_documentation_debt(path: Path, report: DebtReport, config: DebtConfig) -> None:
    """Analyze documentation debt."""
    for root, dirs, files in os.walk(path):
        root_path = Path(root)

        dirs[:] = [
            d for d in dirs
            if not any(matches_pattern(d, p) for p in config.exclude_patterns)
        ]

        for file in files:
            if not should_analyze_file(file, config):
                continue

            file_path = root_path / file
            try:
                undocumented = find_undocumented_functions(file_path)

                if undocumented:
                    effort = config.effort_models.documentation_factor * len(undocumented)
                    severity = DebtSeverity.MEDIUM if len(undocumented) > 5 else DebtSeverity.LOW

                    report.add_debt_item(DebtItem(
                        debt_type=DebtType.DOCUMENTATION,
                        file_path=str(file_path.absolute()),
                        line_number=undocumented[0][1] if undocumented else 1,
                        description=f"{len(undocumented)} undocumented public functions",
                        severity=severity,
                        effort_hours=effort,
                        business_impact=get_business_impact(str(file_path), config),
                        interest_rate=config.interest_rates.poor_docs,
                        remediation_strategy="Add docstrings to public functions following project standards",
                    ))
            except Exception:
                pass


def analyze_dependency_debt(path: Path, report: DebtReport, config: DebtConfig) -> None:
    """Analyze dependency-related debt."""
    req_files = ["requirements.txt", "setup.py", "pyproject.toml"]

    for req_file in req_files:
        req_path = path / req_file
        if req_path.exists():
            report.add_debt_item(DebtItem(
                debt_type=DebtType.DEPENDENCIES,
                file_path=str(req_path.absolute()),
                line_number=1,
                description="Dependencies may need security updates (run pip-audit or safety)",
                severity=DebtSeverity.MEDIUM,
                effort_hours=config.effort_models.dependency_update_hours,
                business_impact=0.7,
                interest_rate=config.interest_rates.outdated_deps,
                remediation_strategy="Run security audit, update vulnerable packages, review changelogs",
            ))
            break


def get_business_impact(file_path: str, config: DebtConfig) -> float:
    """Get business impact weight for a file."""
    for pattern, weight in config.business_value_weights.items():
        if pattern in file_path:
            return cast(float, weight)

    if "core" in file_path.lower() or "main" in file_path.lower():
        return 0.9
    elif "util" in file_path.lower() or "helper" in file_path.lower():
        return 0.3
    elif "test" in file_path.lower():
        return 0.1
    else:
        return 0.5


def count_lines_of_code(path: Path, config: DebtConfig) -> int:
    """Count total lines of code in project."""
    total_lines = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [
            d for d in dirs
            if not any(matches_pattern(d, p) for p in config.exclude_patterns)
        ]

        for file in files:
            if should_analyze_file(file, config):
                file_path = os.path.join(root, file)
                total_lines += count_file_lines(file_path)
    return total_lines


def count_file_lines(file_path: str) -> int:
    """Count non-empty lines in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return len([line for line in f if line.strip()])
    except Exception:
        return 0


def build_dependency_map(path: Path, config: DebtConfig) -> Dict[str, List[str]]:
    """Build map of file dependencies."""
    dependency_map: Dict[str, List[str]] = {}

    for root, dirs, files in os.walk(path):
        dirs[:] = [
            d for d in dirs
            if not any(matches_pattern(d, p) for p in config.exclude_patterns)
        ]

        for file in files:
            if not should_analyze_file(file, config):
                continue

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    source = f.read()

                tree = ast.parse(source)
                dependencies = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            dependencies.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            dependencies.append(node.module)

                dependency_map[file_path] = dependencies
            except Exception:
                dependency_map[file_path] = []

    return dependency_map


def find_undocumented_functions(file_path: Path) -> List[Tuple[str, int]]:
    """Find public functions without docstrings."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        undocumented = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                if not ast.get_docstring(node):
                    undocumented.append((node.name, node.lineno))

        return undocumented
    except Exception:
        return []


def should_analyze_file(filename: str, config: DebtConfig) -> bool:
    """Check if file should be analyzed based on extension."""
    if config.include_extensions:
        return any(filename.endswith(ext) for ext in config.include_extensions)
    return filename.endswith(".py")


def matches_pattern(name: str, pattern: str) -> bool:
    """Check if name matches exclude pattern."""
    return fnmatch.fnmatch(name, pattern)
