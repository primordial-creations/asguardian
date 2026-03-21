import json
from typing import Dict, List

from Asgard.Heimdall.Quality.models.type_check_models import (
    TypeCheckDiagnostic,
    TypeCheckReport,
    TypeCheckSeverity,
)


_RULE_DESCRIPTIONS: Dict[str, str] = {
    "import": "module or name cannot be found at import time",
    "import-untyped": "imported module has no type stubs",
    "import-not-found": "module or name cannot be found at import time",
    "no-redef": "name re-defined in an incompatible way",
    "name-defined": "name used that was never assigned or imported",
    "used-before-def": "name used before it is assigned",
    "arg-type": "wrong type passed as an argument",
    "call-arg": "wrong number of arguments passed to a function",
    "call-overload": "no matching overload for the given arguments",
    "misc": "miscellaneous type error",
    "return-value": "returned value is incompatible with the declared return type",
    "return": "function return type mismatch",
    "no-return": "function with NoReturn actually returns",
    "attr-defined": "accessing a member that does not exist on the type",
    "union-attr": "member access on a union type that may not have the attribute",
    "assignment": "assigning a value of an incompatible type",
    "incompatible-types": "value is incompatible with the expected type",
    "operator": "operator used with incompatible operand types",
    "override": "subclass method signature does not match the base class",
    "type-arg": "generic type used with incorrect type arguments",
    "valid-type": "type expression is not valid",
    "typeddict-item": "TypedDict key has an incompatible value type",
    "typeddict-unknown-key": "unknown key used with a TypedDict",
    "unreachable": "code path that can never execute",
    "reportMissingImports": "module or name cannot be found at import time",
    "reportMissingModuleSource": "source for an imported module cannot be located",
    "reportUndefinedVariable": "name used that was never assigned or imported",
    "reportArgumentType": "wrong type passed as an argument",
    "reportCallIssue": "incorrect function or method call",
    "reportReturnType": "returned value is incompatible with the declared return type",
    "reportAttributeAccessIssue": "accessing a member that does not exist on the type",
    "reportAssignmentType": "assigning a value of an incompatible type",
    "reportOperatorIssue": "operator used with incompatible operand types",
    "reportIncompatibleMethodOverride": "subclass method signature does not match the base class",
    "reportIncompatibleVariableOverride": "subclass variable type does not match the base class",
    "reportIndexIssue": "subscript used on a non-subscriptable type",
    "reportGeneralTypeIssues": "general type incompatibility",
    "reportUnusedImport": "imported name is never used",
    "reportUnusedVariable": "variable is assigned but never used",
    "reportDeprecated": "use of a deprecated API",
}


def generate_text_report(report: TypeCheckReport, engine: str) -> str:
    """Generate plain text report."""
    engine_label = f"{'Pyright' if engine == 'pyright' else 'mypy'} {report.pyright_version}"
    lines = [
        "=" * 70,
        f"STATIC TYPE CHECKING REPORT ({engine_label})",
        "=" * 70,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        f"Engine: {engine_label}",
        f"Mode: {report.type_checking_mode}",
        f"Files Analyzed: {report.files_scanned}",
        "",
        "SUMMARY",
        "-" * 50,
        f"Total Errors: {report.total_errors}",
        f"Total Warnings: {report.total_warnings}",
        f"Total Info: {report.total_info}",
        f"Files With Errors: {report.files_with_errors}",
        f"Status: {'PASSING' if report.is_compliant else 'FAILING'}",
        "",
    ]

    if report.errors_by_category:
        lines.extend(["ERRORS BY CATEGORY", "-" * 50])
        for cat, count in sorted(report.errors_by_category.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {cat.replace('_', ' ').title():<30} {count:>5}")
        lines.extend([
            "",
            "  CATEGORY DESCRIPTIONS",
            "  " + "-" * 47,
            "  missing_import     — Module or name cannot be found at import time",
            "  undefined_variable — Name used that was never assigned or imported",
            "  argument_error     — Wrong number or type of arguments passed to a function",
            "  return_type        — Function returns a value incompatible with its declared type",
            "  attribute_error    — Accessing a member that doesn't exist on the type",
            "  assignment_error   — Assigning a value of an incompatible type to a variable",
            "  operator_error     — Using an operator (+ - * / etc.) with incompatible types",
            "  override_error     — Subclass method signature doesn't match the base class",
            "  type_mismatch      — Value used where a different type is expected",
            "  general            — Other type errors not fitting a specific category",
            "  unreachable_code   — Code path that can never execute",
            "  deprecated         — Use of a deprecated API",
            "",
        ])

    if report.errors_by_rule:
        lines.extend(["TOP RULES / ERROR CODES", "-" * 50])
        for rule, count in sorted(report.errors_by_rule.items(), key=lambda x: x[1], reverse=True):
            desc = _RULE_DESCRIPTIONS.get(rule, "")
            desc_suffix = f"  ({desc})" if desc else ""
            lines.append(f"  {rule:<45} {count:>5}{desc_suffix}")
        lines.append("")

    problem_files = report.get_most_problematic_files(len(report.files_analyzed))
    if problem_files:
        lines.extend(["MOST PROBLEMATIC FILES", "-" * 50])
        for f in problem_files:
            lines.append(f"  {f.relative_path:<55} E:{f.error_count:>3} W:{f.warning_count:>3}")
        lines.append("")

    if report.all_diagnostics:
        lines.extend(["DIAGNOSTICS", "-" * 50])
        by_file: Dict[str, List[TypeCheckDiagnostic]] = {}
        for diag in report.all_diagnostics:
            key = diag.relative_path or diag.file_path
            if key not in by_file:
                by_file[key] = []
            by_file[key].append(diag)

        for file_path in sorted(by_file.keys()):
            lines.append(f"\n  {file_path}")
            for diag in sorted(by_file[file_path], key=lambda d: d.line):
                sev_marker = {"error": "[ERROR]", "warning": "[WARN] ", "information": "[INFO] "}.get(diag.severity, "[????] ")
                rule_suffix = f" ({diag.rule})" if diag.rule else ""
                lines.append(f"    L{diag.line}:{diag.column} {sev_marker} {diag.message}{rule_suffix}")

    lines.extend(["", "=" * 70])
    return "\n".join(lines)


def generate_json_report(report: TypeCheckReport, engine: str) -> str:
    """Generate JSON report."""
    return json.dumps({
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
            "engine": engine,
            "engine_version": report.pyright_version,
            "type_checking_mode": report.type_checking_mode,
            "files_analyzed": report.files_scanned,
        },
        "summary": {
            "total_errors": report.total_errors,
            "total_warnings": report.total_warnings,
            "total_info": report.total_info,
            "files_with_errors": report.files_with_errors,
            "is_passing": report.is_compliant,
            "errors_by_category": report.errors_by_category,
            "errors_by_rule": report.errors_by_rule,
        },
        "files": [
            {"file_path": f.file_path, "relative_path": f.relative_path,
             "error_count": f.error_count, "warning_count": f.warning_count, "info_count": f.info_count}
            for f in report.files_analyzed
        ],
        "diagnostics": [
            {"file_path": d.file_path, "relative_path": d.relative_path,
             "line": d.line, "column": d.column, "severity": d.severity,
             "message": d.message, "rule": d.rule, "category": d.category}
            for d in report.all_diagnostics
        ],
    }, indent=2)


def generate_markdown_report(report: TypeCheckReport, engine: str) -> str:
    """Generate Markdown report."""
    engine_label = f"{'Pyright' if engine == 'pyright' else 'mypy'} {report.pyright_version}"
    status = "PASS" if report.is_compliant else "FAIL"
    lines = [
        "# Static Type Checking Report",
        "",
        f"**Engine:** {engine_label}",
        f"**Mode:** `{report.type_checking_mode}`",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Files Analyzed:** {report.files_scanned}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Errors | {report.total_errors} |",
        f"| Total Warnings | {report.total_warnings} |",
        f"| Total Info | {report.total_info} |",
        f"| Files With Errors | {report.files_with_errors} |",
        f"| **Status** | **{status}** |",
        "",
    ]

    if report.errors_by_category:
        lines += ["## Issues by Category", "", "| Category | Count |", "|----------|-------|"]
        for cat, count in sorted(report.errors_by_category.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {cat.replace('_', ' ').title()} | {count} |")
        lines.append("")

    if report.errors_by_rule:
        lines += ["## Top Error Codes", "", "| Code | Count |", "|------|-------|"]
        for rule, count in sorted(report.errors_by_rule.items(), key=lambda x: x[1], reverse=True)[:20]:
            lines.append(f"| `{rule}` | {count} |")
        lines.append("")

    problem_files = report.get_most_problematic_files(20)
    if problem_files:
        lines += ["## Most Problematic Files", "", "| File | Errors | Warnings |", "|------|--------|----------|"]
        for f in problem_files:
            lines.append(f"| `{f.relative_path}` | {f.error_count} | {f.warning_count} |")
        lines.append("")

    return "\n".join(lines)
