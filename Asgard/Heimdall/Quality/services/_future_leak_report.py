import json
import os

from Asgard.Heimdall.Quality.models.future_leak_models import (
    FutureLeakReport,
    FutureLeakType,
)


def generate_text_report(report: FutureLeakReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "FUTURE/PROMISE LEAK VIOLATIONS REPORT",
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
        for leak_type in FutureLeakType:
            count = report.violations_by_type.get(leak_type.value, 0)
            if count > 0:
                lines.append(f"  {leak_type.value.replace('_', ' ').title()}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} violations")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        for leak in report.detected_leaks:
            filename = os.path.basename(leak.file_path)
            lines.append(f"  {filename}:{leak.line_number}")
            lines.append(f"    Variable:     {leak.variable_name}")
            lines.append(f"    Type:         {leak.leak_type}")
            lines.append(f"    Context:      {leak.context_description}")
            lines.append(f"    Remediation:  {leak.remediation}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: FutureLeakReport) -> str:
    """Generate JSON report."""
    violations_data = []
    for v in report.detected_leaks:
        violations_data.append({
            "file_path": v.file_path,
            "relative_path": v.relative_path,
            "line_number": v.line_number,
            "variable_name": v.variable_name,
            "leak_type": v.leak_type if isinstance(v.leak_type, str) else v.leak_type.value,
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


def generate_markdown_report(report: FutureLeakReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Future/Promise Leak Violations Report",
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
        for leak_type in FutureLeakType:
            count = report.violations_by_type.get(leak_type.value, 0)
            if count > 0:
                lines.append(f"| {leak_type.value.replace('_', ' ').title()} | {count} |")

        if report.most_problematic_files:
            lines.extend(["", "## Most Problematic Files", ""])
            for file_path, count in report.most_problematic_files[:10]:
                filename = os.path.basename(file_path)
                lines.append(f"- `{filename}`: {count} violations")

        lines.extend(["", "## Violations", ""])

        for v in report.detected_leaks[:50]:
            filename = os.path.basename(v.file_path)
            lines.extend([
                f"#### `{filename}:{v.line_number}` - `{v.variable_name}`",
                "",
                f"**Type:** {v.leak_type}",
                "",
                f"**Context:** {v.context_description}",
                "",
                f"**Remediation:** {v.remediation}",
                "",
            ])

    return "\n".join(lines)
