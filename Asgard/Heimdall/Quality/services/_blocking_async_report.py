import json
import os

from Asgard.Heimdall.Quality.models.blocking_async_models import (
    BlockingAsyncReport,
    BlockingCallType,
)


def generate_text_report(report: BlockingAsyncReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "BLOCKING CALL IN ASYNC CONTEXT REPORT",
        "=" * 60,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        f"Files Scanned: {report.files_scanned}",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Violations: {report.total_violations}",
        f"Compliant: {'Yes' if report.is_compliant else 'No'}",
        "",
    ]

    if report.has_violations:
        lines.extend(["By Type:"])
        for blocking_type in BlockingCallType:
            count = report.violations_by_type.get(blocking_type.value, 0)
            if count > 0:
                lines.append(f"  {blocking_type.value.replace('_', ' ').title()}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} violations")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        for call in report.detected_calls:
            filename = os.path.basename(call.file_path)
            lines.append(f"  {filename}:{call.line_number}")
            lines.append(f"    Call:         {call.call_expression}")
            lines.append(f"    Type:         {call.blocking_type}")
            lines.append(f"    Context:      {call.context_description}")
            lines.append(f"    Remediation:  {call.remediation}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: BlockingAsyncReport) -> str:
    """Generate JSON report."""
    violations_data = []
    for v in report.detected_calls:
        violations_data.append({
            "file_path": v.file_path,
            "relative_path": v.relative_path,
            "line_number": v.line_number,
            "call_expression": v.call_expression,
            "blocking_type": v.blocking_type if isinstance(v.blocking_type, str) else v.blocking_type.value,
            "severity": v.severity if isinstance(v.severity, str) else v.severity.value,
            "containing_function": v.containing_function,
            "containing_class": v.containing_class,
            "context_description": v.context_description,
            "remediation": v.remediation,
        })

    report_data = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
            "files_scanned": report.files_scanned,
        },
        "summary": {
            "total_violations": report.total_violations,
            "is_compliant": report.is_compliant,
            "violations_by_type": report.violations_by_type,
            "violations_by_severity": report.violations_by_severity,
        },
        "violations": violations_data,
        "most_problematic_files": [
            {"file": file_path, "violation_count": count}
            for file_path, count in report.most_problematic_files
        ],
    }
    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: BlockingAsyncReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Blocking Call in Async Context Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        f"**Files Scanned:** {report.files_scanned}",
        "",
        "## Summary",
        "",
        f"**Total Violations:** {report.total_violations}",
        f"**Compliant:** {'Yes' if report.is_compliant else 'No'}",
        "",
    ]

    if report.has_violations:
        lines.extend([
            "### By Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for blocking_type in BlockingCallType:
            count = report.violations_by_type.get(blocking_type.value, 0)
            if count > 0:
                lines.append(f"| {blocking_type.value.replace('_', ' ').title()} | {count} |")

        if report.most_problematic_files:
            lines.extend(["", "## Most Problematic Files", ""])
            for file_path, count in report.most_problematic_files[:10]:
                filename = os.path.basename(file_path)
                lines.append(f"- `{filename}`: {count} violations")

        lines.extend(["", "## Violations", ""])

        for v in report.detected_calls[:50]:
            filename = os.path.basename(v.file_path)
            lines.extend([
                f"#### `{filename}:{v.line_number}`",
                "",
                f"**Call:** `{v.call_expression}`",
                "",
                f"**Type:** {v.blocking_type}",
                "",
                f"**Context:** {v.context_description}",
                "",
                f"**Remediation:** {v.remediation}",
                "",
            ])

    return "\n".join(lines)
