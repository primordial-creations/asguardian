"""
Heimdall Config Secrets Report Helpers

Report generation methods for ConfigSecretsScanner.
"""

import json
import os

from Asgard.Heimdall.Security.models.config_secrets_models import (
    ConfigSecretSeverity,
    ConfigSecretType,
    ConfigSecretsReport,
)


def generate_text_report(report: ConfigSecretsReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 70,
        "CONFIG SECRETS FINDINGS REPORT",
        "=" * 70,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        f"Files Scanned: {report.files_scanned}",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Findings: {report.total_findings}",
        f"Clean: {'Yes' if report.is_clean else 'No'}",
        "",
    ]

    if report.has_findings:
        lines.append("By Severity:")
        for severity in [
            ConfigSecretSeverity.CRITICAL,
            ConfigSecretSeverity.HIGH,
            ConfigSecretSeverity.MEDIUM,
            ConfigSecretSeverity.LOW,
        ]:
            count = report.findings_by_severity.get(severity.value, 0)
            if count > 0:
                lines.append(f"  {severity.value.upper()}: {count}")

        lines.extend(["", "By Type:"])
        for secret_type in ConfigSecretType:
            count = report.findings_by_type.get(secret_type.value, 0)
            if count > 0:
                lines.append(f"  {secret_type.value.replace('_', ' ').title()}: {count}")

        if report.most_problematic_files:
            lines.extend(["", "Most Problematic Files:", "-" * 40])
            for file_path, count in report.most_problematic_files[:5]:
                filename = os.path.basename(file_path)
                lines.append(f"  {filename}: {count} findings")

        lines.extend(["", "FINDINGS", "-" * 40])

        for severity in [
            ConfigSecretSeverity.CRITICAL,
            ConfigSecretSeverity.HIGH,
            ConfigSecretSeverity.MEDIUM,
            ConfigSecretSeverity.LOW,
        ]:
            severity_findings = report.get_findings_by_severity(severity)
            if severity_findings:
                lines.extend(["", f"[{severity.value.upper()}]"])
                for f in severity_findings:
                    lines.append(f"  {f.location}")
                    lines.append(f"    Key: {f.key_name}")
                    lines.append(f"    Path: {f.context_path}")
                    lines.append(f"    Value: {f.masked_value}")
                    if f.entropy is not None:
                        lines.append(f"    Entropy: {f.entropy:.2f}")
                    lines.append(f"    Context: {f.context_description}")
                    lines.append(f"    Fix: {f.remediation}")
                    lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(report: ConfigSecretsReport) -> str:
    """Generate JSON report."""
    findings_data = []
    for f in report.detected_findings:
        findings_data.append({
            "file_path": f.file_path,
            "relative_path": f.relative_path,
            "line_number": f.line_number,
            "key_name": f.key_name,
            "masked_value": f.masked_value,
            "secret_type": f.secret_type if isinstance(f.secret_type, str) else f.secret_type.value,
            "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
            "entropy": f.entropy,
            "context_path": f.context_path,
            "context_description": f.context_description,
            "remediation": f.remediation,
        })

    report_data = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
            "files_scanned": report.files_scanned,
        },
        "summary": {
            "total_findings": report.total_findings,
            "is_clean": report.is_clean,
            "findings_by_severity": report.findings_by_severity,
            "findings_by_type": report.findings_by_type,
        },
        "findings": findings_data,
        "most_problematic_files": [
            {"file": fp, "finding_count": count}
            for fp, count in report.most_problematic_files
        ],
    }

    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: ConfigSecretsReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Config Secrets Findings Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        f"**Files Scanned:** {report.files_scanned}",
        "",
        "## Summary",
        "",
        f"**Total Findings:** {report.total_findings}",
        f"**Clean:** {'Yes' if report.is_clean else 'No'}",
        "",
    ]

    if report.has_findings:
        lines.extend([
            "### By Severity",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ])
        for severity in [
            ConfigSecretSeverity.CRITICAL,
            ConfigSecretSeverity.HIGH,
            ConfigSecretSeverity.MEDIUM,
            ConfigSecretSeverity.LOW,
        ]:
            count = report.findings_by_severity.get(severity.value, 0)
            lines.append(f"| {severity.value.title()} | {count} |")

        lines.extend([
            "",
            "### By Type",
            "",
            "| Type | Count |",
            "|------|-------|",
        ])
        for secret_type in ConfigSecretType:
            count = report.findings_by_type.get(secret_type.value, 0)
            if count > 0:
                lines.append(f"| {secret_type.value.replace('_', ' ').title()} | {count} |")

        if report.most_problematic_files:
            lines.extend(["", "## Most Problematic Files", ""])
            for file_path, count in report.most_problematic_files[:10]:
                filename = os.path.basename(file_path)
                lines.append(f"- `{filename}`: {count} findings")

        lines.extend(["", "## Findings", ""])

        for severity in [
            ConfigSecretSeverity.CRITICAL,
            ConfigSecretSeverity.HIGH,
            ConfigSecretSeverity.MEDIUM,
            ConfigSecretSeverity.LOW,
        ]:
            severity_findings = report.get_findings_by_severity(severity)
            if severity_findings:
                lines.extend([f"### {severity.value.title()} Severity", ""])
                for f in severity_findings[:20]:
                    filename = os.path.basename(f.file_path)
                    lines.extend([
                        f"#### `{filename}` - `{f.key_name}`",
                        "",
                        f"**Key:** `{f.key_name}`",
                        f"**Path:** `{f.context_path}`",
                        f"**Masked Value:** `{f.masked_value}`",
                    ])
                    if f.entropy is not None:
                        lines.append(f"**Entropy:** {f.entropy:.2f}")
                    lines.extend([
                        "",
                        f"**Context:** {f.context_description}",
                        "",
                        f"**Remediation:** {f.remediation}",
                        "",
                    ])

    return "\n".join(lines)
