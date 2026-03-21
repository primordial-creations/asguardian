import json
from typing import Dict, List

from Asgard.Heimdall.Quality.models.typing_models import (
    AnnotationStatus,
    FunctionAnnotation,
    TypingReport,
)


def generate_text_report(report: TypingReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "TYPE ANNOTATION COVERAGE REPORT",
        "=" * 60,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        f"Files Scanned: {report.files_scanned}",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Functions: {report.total_functions}",
        f"Fully Annotated: {report.fully_annotated}",
        f"Partially Annotated: {report.partially_annotated}",
        f"Not Annotated: {report.not_annotated}",
        "",
        f"Coverage: {report.coverage_percentage:.1f}%",
        f"Threshold: {report.threshold:.1f}%",
        f"Status: {'PASSING' if report.is_passing else 'FAILING'}",
        "",
    ]

    if not report.is_passing:
        files_below = report.get_files_below_threshold()
        if files_below:
            lines.extend(["FILES BELOW THRESHOLD", "-" * 40])
            for f in sorted(files_below, key=lambda x: x.coverage_percentage)[:20]:
                lines.append(f"  {f.relative_path}: {f.coverage_percentage:.1f}%")
            lines.append("")

        if report.unannotated_functions:
            lines.extend(["", "FUNCTIONS NEEDING ANNOTATIONS", "-" * 40])

            by_severity: Dict[str, List[FunctionAnnotation]] = {}
            for func in report.unannotated_functions:
                sev = func.severity if isinstance(func.severity, str) else func.severity.value
                if sev not in by_severity:
                    by_severity[sev] = []
                by_severity[sev].append(func)

            for severity in ["high", "medium", "low"]:
                funcs = by_severity.get(severity, [])
                if funcs:
                    lines.extend(["", f"[{severity.upper()}]"])
                    for func in funcs[:30]:
                        missing = ", ".join(func.missing_parameter_names) if func.missing_parameter_names else ""
                        ret = "" if func.has_return_annotation else " (missing return)"
                        params = f" (missing: {missing})" if missing else ""
                        lines.append(f"  {func.location} {func.qualified_name}{params}{ret}")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: TypingReport) -> str:
    """Generate JSON report."""
    report_data = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
            "files_scanned": report.files_scanned,
        },
        "summary": {
            "total_functions": report.total_functions,
            "fully_annotated": report.fully_annotated,
            "partially_annotated": report.partially_annotated,
            "not_annotated": report.not_annotated,
            "coverage_percentage": report.coverage_percentage,
            "threshold": report.threshold,
            "is_passing": report.is_passing,
        },
        "files": [
            {
                "file_path": f.file_path,
                "relative_path": f.relative_path,
                "total_functions": f.total_functions,
                "fully_annotated": f.fully_annotated,
                "coverage_percentage": f.coverage_percentage,
            }
            for f in report.files_analyzed
        ],
        "unannotated_functions": [
            {
                "file_path": func.file_path,
                "line_number": func.line_number,
                "function_name": func.function_name,
                "class_name": func.class_name,
                "status": func.status,
                "severity": func.severity,
                "total_parameters": func.total_parameters,
                "annotated_parameters": func.annotated_parameters,
                "has_return_annotation": func.has_return_annotation,
                "missing_parameter_names": func.missing_parameter_names,
            }
            for func in report.unannotated_functions
        ],
    }
    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: TypingReport) -> str:
    """Generate Markdown report."""
    status_label = "PASS" if report.is_passing else "FAIL"

    lines = [
        "# Type Annotation Coverage Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Files Scanned:** {report.files_scanned}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Functions | {report.total_functions} |",
        f"| Fully Annotated | {report.fully_annotated} |",
        f"| Partially Annotated | {report.partially_annotated} |",
        f"| Not Annotated | {report.not_annotated} |",
        f"| **Coverage** | **{report.coverage_percentage:.1f}%** |",
        f"| Threshold | {report.threshold:.1f}% |",
        f"| Status | **{status_label}** |",
        "",
    ]

    if not report.is_passing:
        files_below = report.get_files_below_threshold()
        if files_below:
            lines.extend([
                "## Files Below Threshold",
                "",
                "| File | Coverage |",
                "|------|----------|",
            ])
            for f in sorted(files_below, key=lambda x: x.coverage_percentage)[:20]:
                lines.append(f"| `{f.relative_path}` | {f.coverage_percentage:.1f}% |")
            lines.append("")

        if report.unannotated_functions:
            lines.extend([
                "## Functions Needing Annotations",
                "",
            ])

            for func in report.unannotated_functions[:50]:
                missing = ", ".join(func.missing_parameter_names) if func.missing_parameter_names else "none"
                lines.extend([
                    f"### `{func.qualified_name}` ({func.location})",
                    "",
                    f"- **Status:** {func.status}",
                    f"- **Missing params:** {missing}",
                    f"- **Has return type:** {'Yes' if func.has_return_annotation else 'No'}",
                    "",
                ])

    return "\n".join(lines)
