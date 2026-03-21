import json
import os

from Asgard.Heimdall.Quality.models.lazy_import_models import (
    LazyImportReport,
    LazyImportSeverity,
    LazyImportType,
)


def generate_text_report(report: LazyImportReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "LAZY IMPORT VIOLATIONS REPORT",
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
        lines.extend(["By Severity:"])
        for severity in [LazyImportSeverity.HIGH, LazyImportSeverity.MEDIUM, LazyImportSeverity.LOW]:
            count = report.violations_by_severity.get(severity.value, 0)
            if count > 0:
                lines.append(f"  {severity.value.upper()}: {count}")

        lines.extend(["", "By Type:"])
        for import_type in LazyImportType:
            count = report.violations_by_type.get(import_type.value, 0)
            if count > 0:
                lines.append(f"  {import_type.value.replace('_', ' ').title()}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} violations")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        # Group by severity
        for severity in [LazyImportSeverity.HIGH, LazyImportSeverity.MEDIUM, LazyImportSeverity.LOW]:
            severity_violations = report.get_violations_by_severity(severity)
            if severity_violations:
                lines.extend(["", f"[{severity.value.upper()}]"])
                for violation in severity_violations:
                    lines.append(f"  {violation.location}")
                    lines.append(f"    Import: {violation.import_statement}")
                    lines.append(f"    Context: {violation.context_description}")
                    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: LazyImportReport) -> str:
    """Generate JSON report."""
    violations_data = []
    for v in report.detected_imports:
        violations_data.append({
            "file_path": v.file_path,
            "relative_path": v.relative_path,
            "line_number": v.line_number,
            "import_statement": v.import_statement,
            "import_type": v.import_type if isinstance(v.import_type, str) else v.import_type.value,
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
            "violations_by_severity": report.violations_by_severity,
            "violations_by_type": report.violations_by_type,
        },
        "violations": violations_data,
        "most_problematic_files": [
            {"file": file_path, "violation_count": count}
            for file_path, count in report.most_problematic_files
        ],
    }

    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: LazyImportReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Lazy Import Violations Report",
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
            "### By Severity",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ])
        for severity in [LazyImportSeverity.HIGH, LazyImportSeverity.MEDIUM, LazyImportSeverity.LOW]:
            count = report.violations_by_severity.get(severity.value, 0)
            lines.append(f"| {severity.value.title()} | {count} |")

        lines.extend([
            "",
            "### By Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for import_type in LazyImportType:
            count = report.violations_by_type.get(import_type.value, 0)
            if count > 0:
                lines.append(f"| {import_type.value.replace('_', ' ').title()} | {count} |")

        if report.most_problematic_files:
            lines.extend(["", "## Most Problematic Files", ""])
            for file_path, count in report.most_problematic_files[:10]:
                filename = os.path.basename(file_path)
                lines.append(f"- `{filename}`: {count} violations")

        lines.extend(["", "## Violations", ""])

        for severity in [LazyImportSeverity.HIGH, LazyImportSeverity.MEDIUM, LazyImportSeverity.LOW]:
            severity_violations = report.get_violations_by_severity(severity)
            if severity_violations:
                lines.extend([f"### {severity.value.title()} Severity", ""])

                for v in severity_violations[:20]:
                    filename = os.path.basename(v.file_path)
                    lines.extend([
                        f"#### `{filename}:{v.line_number}`",
                        "",
                        f"**Import:** `{v.import_statement}`",
                        "",
                        f"**Context:** {v.context_description}",
                        "",
                        f"**Remediation:** {v.remediation}",
                        "",
                    ])

    return "\n".join(lines)
