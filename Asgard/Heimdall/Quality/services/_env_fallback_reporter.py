"""
Heimdall Environment Variable Fallback Scanner - report generation helpers.

Standalone functions for generating text, JSON, and Markdown reports
from an EnvFallbackReport. Accepts the report as an explicit parameter.
"""

import json
import os

from Asgard.Heimdall.Quality.models.env_fallback_models import (
    EnvFallbackReport,
    EnvFallbackSeverity,
    EnvFallbackType,
)


def generate_text_report(report: EnvFallbackReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 70,
        "ENVIRONMENT VARIABLE FALLBACK VIOLATIONS REPORT",
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
        lines.extend(["By Severity:"])
        for severity in [EnvFallbackSeverity.HIGH, EnvFallbackSeverity.MEDIUM, EnvFallbackSeverity.LOW]:
            count = report.violations_by_severity.get(severity.value, 0)
            if count > 0:
                lines.append(f"  {severity.value.upper()}: {count}")

        lines.extend(["", "By Type:"])
        for fallback_type in EnvFallbackType:
            count = report.violations_by_type.get(fallback_type.value, 0)
            if count > 0:
                type_display = fallback_type.value.replace('_', ' ').title()
                lines.append(f"  {type_display}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} violations")

        lines.extend(["", "VIOLATIONS", "-" * 40])

        for severity in [EnvFallbackSeverity.HIGH, EnvFallbackSeverity.MEDIUM, EnvFallbackSeverity.LOW]:
            severity_violations = report.get_violations_by_severity(severity)
            if severity_violations:
                lines.extend(["", f"[{severity.value.upper()}]"])
                for violation in severity_violations:
                    lines.append(f"  {violation.location}")
                    lines.append(f"    Code: {violation.code_snippet}")
                    if violation.variable_name:
                        lines.append(f"    Variable: {violation.variable_name}")
                    if violation.default_value:
                        lines.append(f"    Default: {violation.default_value}")
                    lines.append(f"    Context: {violation.context_description}")
                    lines.append(f"    Fix: {violation.remediation}")
                    lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(report: EnvFallbackReport) -> str:
    """Generate JSON report."""
    violations_data = []
    for v in report.detected_violations:
        violations_data.append({
            "file_path": v.file_path,
            "relative_path": v.relative_path,
            "line_number": v.line_number,
            "column": v.column,
            "code_snippet": v.code_snippet,
            "variable_name": v.variable_name,
            "default_value": v.default_value,
            "fallback_type": v.fallback_type if isinstance(v.fallback_type, str) else v.fallback_type.value,
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


def generate_markdown_report(report: EnvFallbackReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Environment Variable Fallback Violations Report",
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
        for severity in [EnvFallbackSeverity.HIGH, EnvFallbackSeverity.MEDIUM, EnvFallbackSeverity.LOW]:
            count = report.violations_by_severity.get(severity.value, 0)
            lines.append(f"| {severity.value.title()} | {count} |")

        lines.extend([
            "",
            "### By Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for fallback_type in EnvFallbackType:
            count = report.violations_by_type.get(fallback_type.value, 0)
            if count > 0:
                type_display = fallback_type.value.replace('_', ' ').title()
                lines.append(f"| {type_display} | {count} |")

        if report.most_problematic_files:
            lines.extend(["", "## Most Problematic Files", ""])
            for file_path, count in report.most_problematic_files[:10]:
                filename = os.path.basename(file_path)
                lines.append(f"- `{filename}`: {count} violations")

        lines.extend(["", "## Violations", ""])

        for severity in [EnvFallbackSeverity.HIGH, EnvFallbackSeverity.MEDIUM, EnvFallbackSeverity.LOW]:
            severity_violations = report.get_violations_by_severity(severity)
            if severity_violations:
                lines.extend([f"### {severity.value.title()} Severity", ""])

                for v in severity_violations[:50]:
                    filename = os.path.basename(v.file_path)
                    lines.extend([
                        f"#### `{filename}:{v.line_number}`",
                        "",
                        f"**Code:** `{v.code_snippet}`",
                        "",
                    ])
                    if v.variable_name:
                        lines.append(f"**Variable:** `{v.variable_name}`")
                    if v.default_value:
                        lines.append(f"**Default Value:** `{v.default_value}`")
                    lines.extend([
                        "",
                        f"**Context:** {v.context_description}",
                        "",
                        f"**Remediation:** {v.remediation}",
                        "",
                    ])

    return "\n".join(lines)
