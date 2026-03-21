"""
Heimdall Error Handling Coverage Scanner - report generation helpers.

Standalone functions for generating text, JSON, and Markdown reports
from an ErrorHandlingReport. Accepts the report as an explicit parameter.
"""

import json
import os

from Asgard.Heimdall.Quality.models.error_handling_models import (
    ErrorHandlingReport,
    ErrorHandlingSeverity,
    ErrorHandlingType,
)


def generate_text_report(report: ErrorHandlingReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 70,
        "ERROR HANDLING COVERAGE VIOLATIONS REPORT",
        "=" * 70,
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
        for severity in [
            ErrorHandlingSeverity.HIGH,
            ErrorHandlingSeverity.MEDIUM,
            ErrorHandlingSeverity.LOW,
        ]:
            count = report.violations_by_severity.get(severity.value, 0)
            if count > 0:
                lines.append(f"  {severity.value.upper()}: {count}")

        lines.extend(["", "By Type:"])
        for handling_type in ErrorHandlingType:
            count = report.violations_by_type.get(handling_type.value, 0)
            if count > 0:
                lines.append(f"  {handling_type.value.replace('_', ' ').title()}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} violations")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        for severity in [
            ErrorHandlingSeverity.HIGH,
            ErrorHandlingSeverity.MEDIUM,
            ErrorHandlingSeverity.LOW,
        ]:
            severity_violations = report.get_violations_by_severity(severity)
            if severity_violations:
                lines.extend(["", f"[{severity.value.upper()}]"])
                for v in severity_violations:
                    lines.append(f"  {v.location}")
                    lines.append(f"    Code: {v.code_snippet}")
                    if v.function_name:
                        lines.append(f"    Function: {v.function_name}")
                    if v.call_expression:
                        lines.append(f"    Call: {v.call_expression}")
                    lines.append(f"    Context: {v.context_description}")
                    lines.append(f"    Fix: {v.remediation}")
                    lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(report: ErrorHandlingReport) -> str:
    """Generate JSON report."""
    violations_data = []
    for v in report.detected_violations:
        violations_data.append({
            "file_path": v.file_path,
            "relative_path": v.relative_path,
            "line_number": v.line_number,
            "column": v.column,
            "code_snippet": v.code_snippet,
            "function_name": v.function_name,
            "call_expression": v.call_expression,
            "handling_type": v.handling_type if isinstance(v.handling_type, str) else v.handling_type.value,
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
            {"file": fp, "violation_count": count}
            for fp, count in report.most_problematic_files
        ],
    }

    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: ErrorHandlingReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Error Handling Coverage Violations Report",
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
        for severity in [
            ErrorHandlingSeverity.HIGH,
            ErrorHandlingSeverity.MEDIUM,
            ErrorHandlingSeverity.LOW,
        ]:
            count = report.violations_by_severity.get(severity.value, 0)
            lines.append(f"| {severity.value.title()} | {count} |")

        lines.extend([
            "",
            "### By Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for handling_type in ErrorHandlingType:
            count = report.violations_by_type.get(handling_type.value, 0)
            if count > 0:
                lines.append(f"| {handling_type.value.replace('_', ' ').title()} | {count} |")

        if report.most_problematic_files:
            lines.extend(["", "## Most Problematic Files", ""])
            for file_path, count in report.most_problematic_files[:10]:
                filename = os.path.basename(file_path)
                lines.append(f"- `{filename}`: {count} violations")

        lines.extend(["", "## Violations", ""])

        for severity in [
            ErrorHandlingSeverity.HIGH,
            ErrorHandlingSeverity.MEDIUM,
            ErrorHandlingSeverity.LOW,
        ]:
            severity_violations = report.get_violations_by_severity(severity)
            if severity_violations:
                lines.extend([f"### {severity.value.title()} Severity", ""])
                for v in severity_violations[:20]:
                    filename = os.path.basename(v.file_path)
                    lines.extend([
                        f"#### `{filename}:{v.line_number}`",
                        "",
                        f"**Code:** `{v.code_snippet}`",
                        "",
                    ])
                    if v.function_name:
                        lines.append(f"**Function:** `{v.function_name}`")
                    if v.call_expression:
                        lines.append(f"**Call:** `{v.call_expression}`")
                    lines.extend([
                        "",
                        f"**Context:** {v.context_description}",
                        "",
                        f"**Remediation:** {v.remediation}",
                        "",
                    ])

    return "\n".join(lines)
