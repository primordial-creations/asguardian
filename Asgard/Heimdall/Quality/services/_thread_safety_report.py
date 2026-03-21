import json
import os

from Asgard.Heimdall.Quality.models.thread_safety_models import (
    ThreadSafetyIssueType,
    ThreadSafetyReport,
    ThreadSafetySeverity,
)


def generate_text_report(report: ThreadSafetyReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "THREAD SAFETY VIOLATIONS REPORT",
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
        lines.append("By Severity:")
        for severity in [ThreadSafetySeverity.HIGH, ThreadSafetySeverity.MEDIUM]:
            count = report.violations_by_severity.get(severity.value, 0)
            if count > 0:
                lines.append(f"  {severity.value.upper()}: {count}")

        lines.extend(["", "By Type:"])
        for issue_type in ThreadSafetyIssueType:
            count = report.violations_by_type.get(issue_type.value, 0)
            if count > 0:
                lines.append(f"  {issue_type.value.replace('_', ' ').title()}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} violations")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        for severity in [ThreadSafetySeverity.HIGH, ThreadSafetySeverity.MEDIUM]:
            severity_issues = report.get_violations_by_severity(severity)
            if severity_issues:
                lines.extend(["", f"[{severity.value.upper()}]"])
                for issue in severity_issues:
                    lines.append(f"  {issue.location} ({issue.class_name})")
                    lines.append(f"    {issue.description}")
                    lines.append(f"    Fix: {issue.remediation}")
                    lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: ThreadSafetyReport) -> str:
    """Generate JSON report."""
    issues_data = []
    for issue in report.detected_issues:
        issues_data.append({
            "file_path": issue.file_path,
            "relative_path": issue.relative_path,
            "line_number": issue.line_number,
            "class_name": issue.class_name,
            "issue_type": issue.issue_type if isinstance(issue.issue_type, str) else issue.issue_type.value,
            "severity": issue.severity if isinstance(issue.severity, str) else issue.severity.value,
            "description": issue.description,
            "attribute_name": issue.attribute_name,
            "thread_target_method": issue.thread_target_method,
            "remediation": issue.remediation,
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
        "violations": issues_data,
        "most_problematic_files": [
            {"file": file_path, "violation_count": count}
            for file_path, count in report.most_problematic_files
        ],
    }

    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: ThreadSafetyReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Thread Safety Violations Report",
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
        for severity in [ThreadSafetySeverity.HIGH, ThreadSafetySeverity.MEDIUM]:
            count = report.violations_by_severity.get(severity.value, 0)
            lines.append(f"| {severity.value.title()} | {count} |")

        lines.extend([
            "",
            "### By Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for issue_type in ThreadSafetyIssueType:
            count = report.violations_by_type.get(issue_type.value, 0)
            if count > 0:
                lines.append(f"| {issue_type.value.replace('_', ' ').title()} | {count} |")

        if report.most_problematic_files:
            lines.extend(["", "## Most Problematic Files", ""])
            for file_path, count in report.most_problematic_files[:10]:
                filename = os.path.basename(file_path)
                lines.append(f"- `{filename}`: {count} violations")

        lines.extend(["", "## Violations", ""])

        for severity in [ThreadSafetySeverity.HIGH, ThreadSafetySeverity.MEDIUM]:
            severity_issues = report.get_violations_by_severity(severity)
            if severity_issues:
                lines.extend([f"### {severity.value.title()} Severity", ""])
                for issue in severity_issues[:20]:
                    filename = os.path.basename(issue.file_path)
                    lines.extend([
                        f"#### `{filename}:{issue.line_number}` ({issue.class_name})",
                        "",
                        f"**Issue:** {issue.description}",
                        "",
                        f"**Remediation:** {issue.remediation}",
                        "",
                    ])

    return "\n".join(lines)
