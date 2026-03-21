import json
import os
from collections import defaultdict
from typing import Callable, Dict, List

from Asgard.Heimdall.Quality.models.smell_models import (
    CodeSmell,
    SmellCategory,
    SmellReport,
    SmellSeverity,
)
from Asgard.Heimdall.Quality.services._code_smell_report_html import generate_html_report


def generate_text_report(report: SmellReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "CODE SMELLS REPORT",
        "=" * 60,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Smells: {report.total_smells}",
        "",
        "By Severity:",
    ]

    for severity in [SmellSeverity.CRITICAL, SmellSeverity.HIGH, SmellSeverity.MEDIUM, SmellSeverity.LOW]:
        count = report.smells_by_severity.get(severity.value, 0)
        if count > 0:
            lines.append(f"  {severity.value.upper()}: {count}")

    lines.extend(["", "By Category:"])
    for category in SmellCategory:
        count = report.smells_by_category.get(category.value, 0)
        if count > 0:
            lines.append(f"  {category.value.replace('_', ' ').title()}: {count}")

    if report.most_problematic_files:
        lines.extend(["", "Most Problematic Files:", "-" * 40])
        for file_path, count in report.most_problematic_files[:5]:
            filename = os.path.basename(file_path)
            lines.append(f"  {filename}: {count} smells")

    if report.remediation_priorities:
        lines.extend(["", "Remediation Priorities:", "-" * 40])
        for priority in report.remediation_priorities:
            lines.append(f"  - {priority}")

    if report.detected_smells:
        lines.extend(["", "DETECTED SMELLS", "-" * 40])

        smells_by_sev: Dict[str, List[CodeSmell]] = defaultdict(list)
        for smell in report.detected_smells:
            sev = smell.severity if isinstance(smell.severity, str) else smell.severity.value
            smells_by_sev[sev].append(smell)

        for severity in [SmellSeverity.CRITICAL, SmellSeverity.HIGH, SmellSeverity.MEDIUM, SmellSeverity.LOW]:
            sev_smells = smells_by_sev.get(severity.value, [])
            if sev_smells:
                lines.extend(["", f"[{severity.value.upper()}]"])
                for smell in sev_smells[:10]:
                    lines.append(f"  {smell.name} - {smell.location}")
                    lines.append(f"    {smell.description}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: SmellReport) -> str:
    """Generate JSON report."""
    smells_data = []
    for smell in report.detected_smells:
        sev = smell.severity if isinstance(smell.severity, str) else smell.severity.value
        cat = smell.category if isinstance(smell.category, str) else smell.category.value
        smells_data.append(
            {
                "name": smell.name,
                "category": cat,
                "severity": sev,
                "file_path": smell.file_path,
                "line_number": smell.line_number,
                "description": smell.description,
                "evidence": smell.evidence,
                "remediation": smell.remediation,
                "confidence": smell.confidence,
            }
        )

    report_data = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
        },
        "summary": {
            "total_smells": report.total_smells,
            "smells_by_severity": report.smells_by_severity,
            "smells_by_category": report.smells_by_category,
        },
        "detected_smells": smells_data,
        "most_problematic_files": [
            {"file": file_path, "smell_count": count} for file_path, count in report.most_problematic_files
        ],
        "remediation_priorities": report.remediation_priorities,
    }

    return json.dumps(report_data, indent=2)


def generate_markdown_report(report: SmellReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Code Smells Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        "",
        "## Summary",
        "",
        f"**Total Code Smells:** {report.total_smells}",
        "",
        "### By Severity",
        "",
        "| Severity | Count |",
        "|----------|-------|",
    ]

    for severity in [SmellSeverity.CRITICAL, SmellSeverity.HIGH, SmellSeverity.MEDIUM, SmellSeverity.LOW]:
        count = report.smells_by_severity.get(severity.value, 0)
        lines.append(f"| {severity.value.title()} | {count} |")

    lines.extend(
        [
            "",
            "### By Category",
            "",
            "| Category | Count |",
            "|----------|-------|",
        ]
    )

    for category in SmellCategory:
        count = report.smells_by_category.get(category.value, 0)
        lines.append(f"| {category.value.replace('_', ' ').title()} | {count} |")

    if report.most_problematic_files:
        lines.extend(["", "## Most Problematic Files", ""])
        for file_path, count in report.most_problematic_files[:10]:
            filename = os.path.basename(file_path)
            lines.append(f"- `{filename}`: {count} smells")

    if report.remediation_priorities:
        lines.extend(["", "## Remediation Priorities", ""])
        for priority in report.remediation_priorities:
            lines.append(f"- {priority}")

    lines.extend(["", "## Detected Smells", ""])

    smells_by_sev: Dict[str, List[CodeSmell]] = defaultdict(list)
    for smell in report.detected_smells:
        sev = smell.severity if isinstance(smell.severity, str) else smell.severity.value
        smells_by_sev[sev].append(smell)

    for severity in [SmellSeverity.CRITICAL, SmellSeverity.HIGH, SmellSeverity.MEDIUM, SmellSeverity.LOW]:
        sev_smells = smells_by_sev.get(severity.value, [])
        if sev_smells:
            lines.extend([f"### {severity.value.title()} Severity", ""])

            for smell in sev_smells[:20]:
                filename = os.path.basename(smell.file_path)
                cat = smell.category if isinstance(smell.category, str) else smell.category.value
                lines.extend(
                    [
                        f"#### {smell.name} - `{filename}:{smell.line_number}`",
                        "",
                        f"**Category:** {cat.replace('_', ' ').title()}",
                        "",
                        f"**Description:** {smell.description}",
                        "",
                        f"**Evidence:** {smell.evidence}",
                        "",
                        f"**Remediation:** {smell.remediation}",
                        "",
                    ]
                )

    return "\n".join(lines)


__all__ = [
    "generate_text_report",
    "generate_json_report",
    "generate_markdown_report",
    "generate_html_report",
]
