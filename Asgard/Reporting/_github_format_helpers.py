"""
GitHub Actions Formatter - Format Helper Methods

Builds annotation lists for specific report types. These helpers are used by
GitHubActionsFormatter to keep the main class under 300 lines.

Each function returns a list of (level, file, line, message, title, col) tuples
so this module has no dependency on Annotation/AnnotationLevel directly.
"""

from typing import Any, Callable, List, Optional, Tuple

AnnotationTuple = Tuple[str, str, int, str, Optional[str], Optional[int]]


def format_lazy_imports_tuples(
    report: Any,
    relative_path_func: Callable[[str], str],
    severity_to_level_func: Callable[[Any], str],
) -> List[AnnotationTuple]:
    """Build annotation tuples for a lazy import report."""
    result = []
    for violation in report.detected_imports:
        level = severity_to_level_func(violation.severity)
        result.append((
            level,
            relative_path_func(violation.file_path),
            violation.line_number,
            f"Lazy import: {violation.import_statement}",
            "Lazy Import Detected",
            None,
        ))
    return result


def format_forbidden_imports_tuples(
    report: Any,
    relative_path_func: Callable[[str], str],
) -> List[AnnotationTuple]:
    """Build annotation tuples for a forbidden imports report."""
    result = []
    for violation in report.detected_violations:
        col = violation.column if violation.column else None
        result.append((
            "error",
            relative_path_func(violation.file_path),
            violation.line_number,
            f"Forbidden import '{violation.module_name}': {violation.remediation}",
            "Forbidden Import",
            col,
        ))
    return result


def format_datetime_tuples(
    report: Any,
    relative_path_func: Callable[[str], str],
    severity_to_level_func: Callable[[Any], str],
) -> List[AnnotationTuple]:
    """Build annotation tuples for a datetime usage report."""
    result = []
    for violation in report.detected_violations:
        level = severity_to_level_func(violation.severity)
        col = violation.column if violation.column else None
        result.append((
            level,
            relative_path_func(violation.file_path),
            violation.line_number,
            f"{violation.issue_type}: {violation.remediation}",
            "Datetime Issue",
            col,
        ))
    return result


def format_typing_tuples(
    report: Any,
    relative_path_func: Callable[[str], str],
    severity_to_level_func: Callable[[Any], str],
) -> List[AnnotationTuple]:
    """Build annotation tuples for a typing coverage report."""
    result: List[AnnotationTuple] = []
    summary_level = "notice" if report.is_passing else "error"
    result.append((
        summary_level,
        ".",
        1,
        f"Typing coverage: {report.coverage_percentage:.1f}% (threshold: {report.threshold:.1f}%)",
        "Typing Coverage Summary",
        None,
    ))
    for func in report.unannotated_functions[:50]:
        level = severity_to_level_func(func.severity)
        missing = ", ".join(func.missing_parameter_names) if func.missing_parameter_names else ""
        ret_msg = " (missing return type)" if not func.has_return_annotation else ""
        param_msg = f" (missing params: {missing})" if missing else ""
        result.append((
            level,
            relative_path_func(func.file_path),
            func.line_number,
            f"Function '{func.qualified_name}' needs annotations{param_msg}{ret_msg}",
            "Missing Type Annotations",
            None,
        ))
    return result


def format_complexity_tuples(
    report: Any,
    relative_path_func: Callable[[str], str],
    complexity_to_level_func: Callable[[str], str],
) -> List[AnnotationTuple]:
    """Build annotation tuples for a complexity report."""
    result = []
    for file_analysis in report.file_analyses:
        for func in file_analysis.functions:
            if func.cyclomatic_severity not in ("low", "moderate"):
                level = complexity_to_level_func(func.cyclomatic_severity)
                result.append((
                    level,
                    relative_path_func(file_analysis.file_path),
                    func.line_number,
                    f"High cyclomatic complexity ({func.cyclomatic_complexity}) in '{func.name}'",
                    "Complex Function",
                    None,
                ))
    return result


def format_smells_tuples(
    report: Any,
    relative_path_func: Callable[[str], str],
    severity_to_level_func: Callable[[Any], str],
) -> List[AnnotationTuple]:
    """Build annotation tuples for a code smell report."""
    result = []
    for smell in report.smells:
        level = severity_to_level_func(smell.severity)
        result.append((
            level,
            relative_path_func(smell.file_path),
            smell.line_number,
            f"{smell.smell_type}: {smell.description}",
            f"Code Smell ({smell.category})",
            None,
        ))
    return result


def format_security_tuples(
    report: Any,
    relative_path_func: Callable[[str], str],
    security_to_level_func: Callable[[Any], str],
) -> List[AnnotationTuple]:
    """Build annotation tuples for a security report."""
    result = []
    for vuln in getattr(report, 'vulnerabilities', []):
        level = security_to_level_func(vuln.severity)
        result.append((
            level,
            relative_path_func(vuln.file_path),
            vuln.line_number,
            f"{vuln.vulnerability_type}: {vuln.description}",
            f"Security ({vuln.severity.upper()})",
            None,
        ))
    return result
