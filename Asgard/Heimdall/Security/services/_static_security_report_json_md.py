"""
Heimdall Static Security Report - JSON and Markdown Generators

Standalone functions for generating JSON and Markdown security reports
from a SecurityReport instance.
"""

import json

from Asgard.Heimdall.Security.models.security_models import SecurityReport


def generate_json_report(report: SecurityReport) -> str:
    """Generate JSON formatted security report."""
    secrets_data = []
    if report.secrets_report:
        for f in report.secrets_report.findings:
            secrets_data.append({
                "file_path": f.file_path,
                "line_number": f.line_number,
                "secret_type": f.secret_type if isinstance(f.secret_type, str) else f.secret_type.value,
                "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
                "pattern_name": f.pattern_name,
                "masked_value": f.masked_value,
            })

    vulns_data = []
    if report.vulnerability_report:
        for f in report.vulnerability_report.findings:
            vulns_data.append({
                "file_path": f.file_path,
                "line_number": f.line_number,
                "vulnerability_type": f.vulnerability_type if isinstance(f.vulnerability_type, str) else f.vulnerability_type.value,
                "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
                "title": f.title,
                "description": f.description,
            })

    deps_data = []
    if report.dependency_report:
        for v in report.dependency_report.vulnerabilities:
            deps_data.append({
                "package_name": v.package_name,
                "installed_version": v.installed_version,
                "risk_level": v.risk_level if isinstance(v.risk_level, str) else v.risk_level.value,
                "title": v.title,
                "fixed_version": v.fixed_version,
            })

    crypto_data = []
    if report.crypto_report:
        for f in report.crypto_report.findings:
            crypto_data.append({
                "file_path": f.file_path,
                "line_number": f.line_number,
                "issue_type": f.issue_type,
                "severity": f.severity if isinstance(f.severity, str) else f.severity.value,
                "description": f.description,
            })

    report_data = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
        },
        "summary": {
            "security_score": report.security_score,
            "total_issues": report.total_issues,
            "critical_issues": report.critical_issues,
            "high_issues": report.high_issues,
            "medium_issues": report.medium_issues,
            "low_issues": report.low_issues,
            "is_passing": report.is_passing,
        },
        "findings": {
            "secrets": secrets_data,
            "vulnerabilities": vulns_data,
            "dependencies": deps_data,
            "crypto": crypto_data,
        },
    }
    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: SecurityReport) -> str:
    """Generate Markdown formatted security report."""
    lines = [
        "# Heimdall Security Analysis Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        "",
        "## Summary",
        "",
        f"**Security Score:** {report.security_score:.1f}/100",
        f"**Total Issues:** {report.total_issues}",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| Critical | {report.critical_issues} |",
        f"| High | {report.high_issues} |",
        f"| Medium | {report.medium_issues} |",
        f"| Low | {report.low_issues} |",
        "",
        f"**Result:** {'PASS' if report.is_passing else 'FAIL'}",
        "",
    ]

    if report.secrets_report and report.secrets_report.findings:
        lines.extend([
            "## Secrets Detection",
            "",
            f"**Files Scanned:** {report.secrets_report.total_files_scanned}",
            f"**Secrets Found:** {report.secrets_report.secrets_found}",
            "",
        ])
        for finding in report.secrets_report.findings[:10]:
            lines.append(f"- `{finding.file_path}:{finding.line_number}` [{finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()}] {finding.pattern_name}: {finding.masked_value}")
        lines.append("")

    if report.dependency_report and report.dependency_report.vulnerabilities:
        lines.extend([
            "## Dependency Vulnerabilities",
            "",
            f"**Dependencies Analyzed:** {report.dependency_report.total_dependencies}",
            f"**Vulnerable Packages:** {report.dependency_report.vulnerable_dependencies}",
            "",
        ])
        for vuln in report.dependency_report.vulnerabilities[:10]:
            lines.append(f"- **{vuln.package_name}** {vuln.installed_version}: {vuln.title}")
        lines.append("")

    if report.vulnerability_report and report.vulnerability_report.findings:
        lines.extend([
            "## Code Vulnerabilities",
            "",
            f"**Files Scanned:** {report.vulnerability_report.total_files_scanned}",
            f"**Vulnerabilities Found:** {report.vulnerability_report.vulnerabilities_found}",
            "",
        ])
        for finding in report.vulnerability_report.findings[:10]:
            lines.append(f"- `{finding.file_path}:{finding.line_number}` [{finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()}] {finding.title}")
        lines.append("")

    if report.crypto_report and report.crypto_report.findings:
        lines.extend([
            "## Cryptographic Issues",
            "",
            f"**Files Scanned:** {report.crypto_report.total_files_scanned}",
            f"**Issues Found:** {report.crypto_report.issues_found}",
            "",
        ])
        for finding in report.crypto_report.findings[:10]:
            lines.append(f"- `{finding.file_path}:{finding.line_number}` {finding.description}")
        lines.append("")

    return "\n".join(lines)
