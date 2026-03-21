import json
import os
from typing import List

from Asgard.Heimdall.Quality.models.debt_models import (
    DebtReport,
    DebtSeverity,
    DebtType,
)


def generate_text_report(report: DebtReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "TECHNICAL DEBT REPORT",
        "=" * 60,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        f"Lines of Code: {report.total_lines_of_code:,}",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Debt: {report.total_debt_hours:.1f} hours",
        f"Debt Ratio: {report.debt_ratio:.2f} hours per 1K LOC",
        "",
        "By Type:",
    ]

    for debt_type in DebtType:
        hours = report.debt_by_type.get(debt_type.value, 0)
        if hours > 0:
            lines.append(f"  {debt_type.value.title()}: {hours:.1f} hours")

    lines.extend(["", "By Severity:"])
    for severity in [DebtSeverity.CRITICAL, DebtSeverity.HIGH, DebtSeverity.MEDIUM, DebtSeverity.LOW]:
        count = report.debt_by_severity.get(severity.value, 0)
        if count > 0:
            lines.append(f"  {severity.value.upper()}: {count} items")

    if report.most_indebted_files:
        lines.extend(["", "Most Indebted Files:", "-" * 40])
        for file_path, hours in report.most_indebted_files[:5]:
            filename = os.path.basename(file_path)
            lines.append(f"  {filename}: {hours:.1f} hours")

    if report.remediation_priorities:
        lines.extend(["", "Remediation Priorities:", "-" * 40])
        for priority in report.remediation_priorities:
            lines.append(f"  - {priority}")

    if report.prioritized_items:
        lines.extend(["", "TOP PRIORITY ITEMS", "-" * 40])
        for i, item in enumerate(report.prioritized_items[:10], 1):
            lines.extend([
                f"{i}. {item.description}",
                f"   Location: {item.location}",
                f"   Effort: {item.effort_hours:.1f}h | Impact: {item.business_impact:.2f}",
                f"   Strategy: {item.remediation_strategy}",
                "",
            ])

    lines.extend([
        "ROI ANALYSIS",
        "-" * 40,
        f"Overall ROI: {report.roi_analysis.overall_roi:.2f}",
        f"Payback Period: {report.roi_analysis.payback_period_months:.1f} months",
        "",
        "TIME PROJECTION",
        "-" * 40,
        f"Current Debt: {report.time_projection.current_debt_hours:.1f} hours",
        f"Projected ({report.time_projection.time_horizon}): {report.time_projection.projected_debt_hours:.1f} hours",
        f"Growth: {report.time_projection.growth_percentage:.1f}%",
        "",
        "=" * 60,
    ])

    return "\n".join(lines)


def generate_json_report(report: DebtReport) -> str:
    """Generate JSON report."""
    output = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
            "lines_of_code": report.total_lines_of_code,
        },
        "summary": {
            "total_debt_hours": report.total_debt_hours,
            "debt_ratio": report.debt_ratio,
            "debt_by_type": report.debt_by_type,
            "debt_by_severity": report.debt_by_severity,
        },
        "roi_analysis": {
            "overall_roi": report.roi_analysis.overall_roi,
            "roi_by_type": report.roi_analysis.roi_by_type,
            "payback_period_months": report.roi_analysis.payback_period_months,
            "total_effort_hours": report.roi_analysis.total_effort_hours,
        },
        "time_projection": {
            "current_debt_hours": report.time_projection.current_debt_hours,
            "projected_debt_hours": report.time_projection.projected_debt_hours,
            "growth_percentage": report.time_projection.growth_percentage,
            "time_horizon": report.time_projection.time_horizon,
        },
        "debt_items": [
            {
                "debt_type": item.debt_type,
                "file_path": item.file_path,
                "line_number": item.line_number,
                "description": item.description,
                "severity": item.severity,
                "effort_hours": item.effort_hours,
                "business_impact": item.business_impact,
                "interest_rate": item.interest_rate,
                "remediation_strategy": item.remediation_strategy,
            }
            for item in report.prioritized_items[:50]
        ],
        "most_indebted_files": [
            {"file": path, "debt_hours": hours}
            for path, hours in report.most_indebted_files
        ],
        "remediation_priorities": report.remediation_priorities,
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(report: DebtReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Technical Debt Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        f"**Lines of Code:** {report.total_lines_of_code:,}",
        "",
        "## Summary",
        "",
        f"**Total Debt:** {report.total_debt_hours:.1f} hours",
        f"**Debt Ratio:** {report.debt_ratio:.2f} hours per 1K LOC",
        "",
        "### By Type",
        "",
        "| Type | Hours |",
        "|------|-------|",
    ]

    for debt_type in DebtType:
        hours = report.debt_by_type.get(debt_type.value, 0)
        lines.append(f"| {debt_type.value.title()} | {hours:.1f} |")

    lines.extend([
        "",
        "### By Severity",
        "",
        "| Severity | Count |",
        "|----------|-------|",
    ])

    for severity in [DebtSeverity.CRITICAL, DebtSeverity.HIGH, DebtSeverity.MEDIUM, DebtSeverity.LOW]:
        count = report.debt_by_severity.get(severity.value, 0)
        lines.append(f"| {severity.value.title()} | {count} |")

    if report.most_indebted_files:
        lines.extend(["", "## Most Indebted Files", ""])
        for file_path, hours in report.most_indebted_files[:10]:
            filename = os.path.basename(file_path)
            lines.append(f"- `{filename}`: {hours:.1f} hours")

    if report.remediation_priorities:
        lines.extend(["", "## Remediation Priorities", ""])
        for priority in report.remediation_priorities:
            lines.append(f"- {priority}")

    lines.extend([
        "",
        "## ROI Analysis",
        "",
        f"- **Overall ROI:** {report.roi_analysis.overall_roi:.2f}",
        f"- **Payback Period:** {report.roi_analysis.payback_period_months:.1f} months",
        f"- **Total Effort:** {report.roi_analysis.total_effort_hours:.1f} hours",
        "",
        "## Time Projection",
        "",
        f"- **Current Debt:** {report.time_projection.current_debt_hours:.1f} hours",
        f"- **Projected ({report.time_projection.time_horizon}):** {report.time_projection.projected_debt_hours:.1f} hours",
        f"- **Growth:** {report.time_projection.growth_percentage:.1f}%",
        "",
    ])

    if report.prioritized_items:
        lines.extend(["## Top Priority Items", ""])
        for i, item in enumerate(report.prioritized_items[:10], 1):
            lines.extend([
                f"### {i}. {item.description}",
                "",
                f"- **Location:** `{item.location}`",
                f"- **Type:** {item.debt_type}",
                f"- **Severity:** {item.severity}",
                f"- **Effort:** {item.effort_hours:.1f} hours",
                f"- **Strategy:** {item.remediation_strategy}",
                "",
            ])

    return "\n".join(lines)
