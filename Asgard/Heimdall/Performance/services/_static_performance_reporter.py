"""
Heimdall Static Performance Service - Report Generation Helper

Standalone function for generating a text summary report from a PerformanceReport.
"""

from Asgard.Heimdall.Performance.models.performance_models import PerformanceReport


def generate_summary(report: PerformanceReport) -> str:
    """
    Generate a text summary of the performance report.

    Args:
        report: The performance report

    Returns:
        Formatted summary string
    """
    lines = [
        "=" * 60,
        "HEIMDALL PERFORMANCE ANALYSIS REPORT",
        "=" * 60,
        f"Scan Path: {report.scan_path}",
        f"Scanned At: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        "",
        "-" * 40,
        "SUMMARY",
        "-" * 40,
        f"Performance Score: {report.performance_score:.1f}/100",
        f"Total Issues: {report.total_issues}",
        f"  Critical: {report.critical_issues}",
        f"  High: {report.high_issues}",
        f"  Medium: {report.medium_issues}",
        f"  Low: {report.low_issues}",
        "",
    ]

    if report.memory_report:
        lines.extend([
            "-" * 40,
            "MEMORY ANALYSIS",
            "-" * 40,
            "Detects unbounded data growth (large list/dict accumulation), missing generator use, repeated object creation in loops, and allocations that may not be released.",
            f"Files Scanned: {report.memory_report.total_files_scanned}",
            f"Issues Found: {report.memory_report.issues_found}",
        ])

        if report.memory_report.findings:
            lines.append("")
            for finding in report.memory_report.findings:
                lines.append(f"  [{finding.severity.upper()}] {finding.file_path}:{finding.line_number}")
                lines.append(f"    {finding.description}")
        lines.append("")

    if report.cpu_report:
        lines.extend([
            "-" * 40,
            "CPU/COMPLEXITY ANALYSIS",
            "-" * 40,
            "Identifies functions where cyclomatic complexity exceeds the configured threshold, indicating code that is expensive to reason about and likely to have performance bottlenecks.",
            f"Files Scanned: {report.cpu_report.total_files_scanned}",
            f"Functions Analyzed: {report.cpu_report.total_functions_analyzed}",
            f"Issues Found: {report.cpu_report.issues_found}",
            f"Average Complexity: {report.cpu_report.average_complexity:.1f}",
            f"Max Complexity: {report.cpu_report.max_complexity:.1f}",
        ])

        if report.cpu_report.findings:
            lines.append("")
            for finding in report.cpu_report.findings:
                lines.append(f"  [{finding.severity.upper()}] {finding.file_path}:{finding.line_number}")
                lines.append(f"    {finding.description}")
        lines.append("")

    if report.database_report:
        lines.extend([
            "-" * 40,
            "DATABASE ANALYSIS",
            "-" * 40,
            "Looks for N+1 query patterns, queries inside loops, missing index hints, and unparameterised queries that force full table scans.",
            f"Files Scanned: {report.database_report.total_files_scanned}",
            f"Issues Found: {report.database_report.issues_found}",
        ])

        if report.database_report.orm_detected:
            lines.append(f"ORM Detected: {report.database_report.orm_detected}")

        if report.database_report.findings:
            lines.append("")
            for finding in report.database_report.findings:
                lines.append(f"  [{finding.severity.upper()}] {finding.file_path}:{finding.line_number}")
                lines.append(f"    {finding.description}")
        lines.append("")

    if report.cache_report:
        lines.extend([
            "-" * 40,
            "CACHE ANALYSIS",
            "-" * 40,
            "Detects repeated expensive operations that are candidates for caching and validates that detected cache systems are being used effectively.",
            f"Files Scanned: {report.cache_report.total_files_scanned}",
            f"Issues Found: {report.cache_report.issues_found}",
        ])

        if report.cache_report.cache_systems_detected:
            lines.append(f"Cache Systems: {', '.join(report.cache_report.cache_systems_detected)}")

        if report.cache_report.findings:
            lines.append("")
            for finding in report.cache_report.findings:
                lines.append(f"  [{finding.severity.upper()}] {finding.file_path}:{finding.line_number}")
                lines.append(f"    {finding.description}")
        lines.append("")

    lines.extend([
        "=" * 60,
        f"RESULT: {'HEALTHY' if report.is_healthy else 'NEEDS ATTENTION'}",
        "=" * 60,
    ])

    return "\n".join(lines)
