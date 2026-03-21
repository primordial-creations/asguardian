import json
from typing import Dict

from Asgard.Heimdall.Quality.models.naming_models import (
    NamingReport,
    NamingViolation,
)


def generate_text_report(report: NamingReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "NAMING CONVENTION REPORT",
        "=" * 60,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        "",
        "SUMMARY",
        "-" * 40,
        f"Total Violations: {report.total_violations}",
        f"Files With Violations: {report.files_with_violations}",
        "",
    ]

    if report.violations_by_type:
        lines.append("Violations by Type:")
        for element_type, count in sorted(report.violations_by_type.items()):
            lines.append(f"  {element_type}: {count}")
        lines.append("")

    if report.has_violations:
        lines.extend(["VIOLATIONS", "-" * 40, ""])
        for file_path, violations in sorted(report.file_results.items()):
            if not violations:
                continue
            lines.append(f"  {file_path}")
            for v in sorted(violations, key=lambda x: x.line_number):
                lines.append(f"    Line {v.line_number:4d}: [{v.element_type}] {v.element_name}")
                lines.append(f"             {v.description}")
            lines.append("")
    else:
        lines.extend(["No naming violations found.", ""])

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_json_report(report: NamingReport) -> str:
    """Generate JSON report."""
    def serialize_violation(v: NamingViolation) -> Dict:
        return {
            "file_path": v.file_path,
            "line_number": v.line_number,
            "element_type": v.element_type,
            "element_name": v.element_name,
            "expected_convention": v.expected_convention,
            "description": v.description,
        }

    output = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
        },
        "summary": {
            "total_violations": report.total_violations,
            "files_with_violations": report.files_with_violations,
            "violations_by_type": report.violations_by_type,
        },
        "file_results": {
            file_path: [serialize_violation(v) for v in violations]
            for file_path, violations in sorted(report.file_results.items())
            if violations
        },
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(report: NamingReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Naming Convention Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Violations | {report.total_violations} |",
        f"| Files With Violations | {report.files_with_violations} |",
        "",
    ]

    if report.has_violations:
        lines.extend(["## Violations", ""])
        for file_path, violations in sorted(report.file_results.items()):
            if not violations:
                continue
            lines.extend([f"### `{file_path}`", ""])
            for v in sorted(violations, key=lambda x: x.line_number):
                lines.append(
                    f"- Line {v.line_number}: `{v.element_name}` "
                    f"[{v.element_type}] - {v.description}"
                )
            lines.append("")
    else:
        lines.extend(["No naming violations found.", ""])

    return "\n".join(lines)
