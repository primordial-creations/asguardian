import json

from Asgard.Heimdall.Quality.models.datetime_models import (
    DatetimeIssueType,
    DatetimeReport,
    DatetimeSeverity,
)


def generate_text_report(report: DatetimeReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "DATETIME USAGE REPORT",
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
        lines.extend(["By Issue Type:"])
        for issue_type in DatetimeIssueType:
            count = report.violations_by_type.get(issue_type.value, 0)
            if count > 0:
                lines.append(f"  {issue_type.value}: {count}")

        lines.extend(["", "By Severity:"])
        for severity in [DatetimeSeverity.HIGH, DatetimeSeverity.MEDIUM, DatetimeSeverity.LOW]:
            count = report.violations_by_severity.get(severity.value, 0)
            if count > 0:
                lines.append(f"  {severity.value.upper()}: {count}")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        for severity in [DatetimeSeverity.HIGH, DatetimeSeverity.MEDIUM, DatetimeSeverity.LOW]:
            severity_violations = report.get_violations_by_severity(severity)
            if severity_violations:
                lines.extend(["", f"[{severity.value.upper()}]"])
                for v in severity_violations:
                    lines.extend([
                        f"  {v.location}",
                        f"    Code: {v.code_snippet}",
                        f"    Issue: {v.issue_type}",
                        f"    Fix: {v.remediation}",
                        "",
                    ])

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: DatetimeReport) -> str:
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
            "violations_by_type": report.violations_by_type,
            "violations_by_severity": report.violations_by_severity,
        },
        "violations": [
            {
                "file_path": v.file_path,
                "relative_path": v.relative_path,
                "line_number": v.line_number,
                "code_snippet": v.code_snippet,
                "issue_type": v.issue_type,
                "severity": v.severity,
                "remediation": v.remediation,
                "containing_function": v.containing_function,
                "containing_class": v.containing_class,
            }
            for v in report.detected_violations
        ],
    }
    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: DatetimeReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Datetime Usage Report",
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
            "### By Issue Type",
            "",
            "| Issue | Count |",
            "|-------|-------|",
        ])
        for issue_type in DatetimeIssueType:
            count = report.violations_by_type.get(issue_type.value, 0)
            if count > 0:
                lines.append(f"| {issue_type.value} | {count} |")

        lines.extend(["", "## Violations", ""])

        for v in report.detected_violations[:50]:
            lines.extend([
                f"### `{v.location}`",
                "",
                f"**Code:** `{v.code_snippet}`",
                "",
                f"**Issue:** {v.issue_type}",
                "",
                f"**Fix:** {v.remediation}",
                "",
            ])

    return "\n".join(lines)
