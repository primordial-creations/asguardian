"""
Heimdall Static Security Report Helpers

Report generation methods for StaticSecurityService.
"""

from Asgard.Heimdall.Security.models.security_models import SecurityReport
from Asgard.Heimdall.Security.services._static_security_report_json_md import (
    generate_json_report,
    generate_markdown_report,
)


def get_summary(report: SecurityReport) -> str:
    """
    Generate a text summary of the security report.

    Args:
        report: The security report

    Returns:
        Formatted summary string
    """
    lines = [
        "=" * 60,
        "HEIMDALL SECURITY ANALYSIS REPORT",
        "=" * 60,
        f"Scan Path: {report.scan_path}",
        f"Scanned At: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        "",
        "-" * 40,
        "SUMMARY",
        "-" * 40,
        f"Security Score: {report.security_score:.1f}/100",
        f"Total Issues: {report.total_issues}",
        f"  Critical: {report.critical_issues}",
        f"  High: {report.high_issues}",
        f"  Medium: {report.medium_issues}",
        f"  Low: {report.low_issues}",
        "",
    ]

    if report.secrets_report:
        lines.extend([
            "-" * 40,
            "SECRETS DETECTION",
            "-" * 40,
            f"Files Scanned: {report.secrets_report.total_files_scanned}",
            f"Secrets Found: {report.secrets_report.secrets_found}",
        ])

        if report.secrets_report.findings:
            lines.append("")
            groups: dict = {}
            for finding in report.secrets_report.findings:
                key = (finding.pattern_name, finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper())
                groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
            for (pattern_name, severity), locations in groups.items():
                count = len(locations)
                lines.append(f"  {pattern_name} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                for loc in locations:
                    lines.append(f"    {loc}")
        lines.append("")

    if report.dependency_report:
        lines.extend([
            "-" * 40,
            "DEPENDENCY VULNERABILITIES",
            "-" * 40,
            f"Dependencies Analyzed: {report.dependency_report.total_dependencies}",
            f"Vulnerable Packages: {report.dependency_report.vulnerable_dependencies}",
        ])

        if report.dependency_report.vulnerabilities:
            lines.append("")
            dep_groups: dict = {}
            for vuln in report.dependency_report.vulnerabilities:
                risk = vuln.risk_level.upper() if isinstance(vuln.risk_level, str) else vuln.risk_level.value.upper()
                key = (vuln.title, risk)
                dep_groups.setdefault(key, []).append((vuln.package_name, vuln.installed_version, vuln.fixed_version))
            for (title, risk), packages in dep_groups.items():
                count = len(packages)
                lines.append(f"  {title} ({risk.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                for pkg_name, installed, fixed in packages:
                    fix_str = f"  ->  fix: upgrade to {fixed}" if fixed else ""
                    lines.append(f"    {pkg_name} {installed}{fix_str}")
        lines.append("")

    if report.vulnerability_report:
        lines.extend([
            "-" * 40,
            "CODE VULNERABILITIES",
            "-" * 40,
            f"Files Scanned: {report.vulnerability_report.total_files_scanned}",
            f"Vulnerabilities Found: {report.vulnerability_report.vulnerabilities_found}",
        ])

        if report.vulnerability_report.findings:
            lines.append("")
            vuln_groups: dict = {}
            for finding in report.vulnerability_report.findings:
                severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                key = (finding.title, severity)
                vuln_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
            for (title, severity), locations in vuln_groups.items():
                count = len(locations)
                lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                for loc in locations:
                    lines.append(f"    {loc}")
        lines.append("")

    if report.crypto_report:
        lines.extend([
            "-" * 40,
            "CRYPTOGRAPHIC ISSUES",
            "-" * 40,
            f"Files Scanned: {report.crypto_report.total_files_scanned}",
            f"Issues Found: {report.crypto_report.issues_found}",
        ])

        if report.crypto_report.findings:
            lines.append("")
            crypto_groups: dict = {}
            for finding in report.crypto_report.findings:
                severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
                key = (finding.description, severity)
                crypto_groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
            for (description, severity), locations in crypto_groups.items():
                count = len(locations)
                lines.append(f"  {description} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
                for loc in locations:
                    lines.append(f"    {loc}")
        lines.append("")

    _append_optional_report_section(lines, report.access_report, "ACCESS CONTROL ISSUES")
    _append_optional_report_section(lines, report.auth_report, "AUTHENTICATION ISSUES")
    _append_optional_report_section(lines, report.headers_report, "SECURITY HEADERS ISSUES")
    _append_optional_report_section(lines, report.tls_report, "TLS/SSL ISSUES")
    _append_optional_report_section(lines, report.container_report, "CONTAINER SECURITY ISSUES")
    _append_optional_report_section(lines, report.infrastructure_report, "INFRASTRUCTURE SECURITY ISSUES")

    lines.extend([
        "=" * 60,
        f"RESULT: {'PASS' if report.is_passing else 'FAIL'}",
        "=" * 60,
    ])

    return "\n".join(lines)


def _append_optional_report_section(lines: list, sub_report: object, section_title: str) -> None:
    """Append a generic report sub-section if the report has findings."""
    if not sub_report or not hasattr(sub_report, 'findings'):
        return

    lines.extend([
        "-" * 40,
        section_title,
        "-" * 40,
        f"Files Scanned: {sub_report.total_files_scanned}",
        f"Issues Found: {sub_report.total_issues}",
    ])

    if sub_report.findings:
        lines.append("")
        groups: dict = {}
        for finding in sub_report.findings:
            severity = finding.severity.upper() if isinstance(finding.severity, str) else finding.severity.value.upper()
            key = (finding.title, severity)
            groups.setdefault(key, []).append(f"{finding.file_path}:{finding.line_number}")
        for (title, severity), locations in groups.items():
            count = len(locations)
            lines.append(f"  {title} ({severity.lower()}) -- {count} occurrence{'s' if count != 1 else ''}")
            for loc in locations:
                lines.append(f"    {loc}")
    lines.append("")


__all__ = [
    "get_summary",
    "generate_json_report",
    "generate_markdown_report",
]
