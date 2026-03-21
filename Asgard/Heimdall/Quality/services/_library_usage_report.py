import json
import os

from Asgard.Heimdall.Quality.models.library_usage_models import (
    ForbiddenImportReport,
)


def generate_text_report(report: ForbiddenImportReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "FORBIDDEN IMPORTS REPORT",
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
        lines.extend(["Forbidden Modules Found:"])
        for module, count in sorted(report.violations_by_module.items()):
            lines.append(f"  {module}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} violations")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        for violation in report.detected_violations:
            lines.extend([
                "",
                f"[{violation.severity.upper()}] {violation.location}",
                f"  Module: {violation.module_name}",
                f"  Import: {violation.import_statement}",
                f"  Remediation: {violation.remediation}",
            ])

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: ForbiddenImportReport) -> str:
    """Generate JSON report."""
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
            "violations_by_module": report.violations_by_module,
            "violations_by_severity": report.violations_by_severity,
        },
        "violations": [
            {
                "file_path": v.file_path,
                "relative_path": v.relative_path,
                "line_number": v.line_number,
                "module_name": v.module_name,
                "import_statement": v.import_statement,
                "severity": v.severity,
                "remediation": v.remediation,
            }
            for v in report.detected_violations
        ],
    }
    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: ForbiddenImportReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Forbidden Imports Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
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
            "### Forbidden Modules",
            "",
            "| Module | Count |",
            "|--------|-------|",
        ])
        for module, count in sorted(report.violations_by_module.items()):
            lines.append(f"| {module} | {count} |")

        lines.extend(["", "## Violations", ""])

        for v in report.detected_violations[:50]:
            lines.extend([
                f"### `{v.location}`",
                "",
                f"**Module:** `{v.module_name}`",
                "",
                f"**Import:** `{v.import_statement}`",
                "",
                f"**Remediation:** {v.remediation}",
                "",
            ])

    return "\n".join(lines)
