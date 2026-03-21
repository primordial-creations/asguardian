import json
import os
from typing import Dict

from Asgard.Heimdall.Quality.models.maintainability_models import (
    FileMaintainability,
    FunctionMaintainability,
    MaintainabilityLevel,
    MaintainabilityReport,
)


def generate_text_report(report: MaintainabilityReport) -> str:
    """Generate plain text report."""
    lines = [
        "=" * 60,
        "MAINTAINABILITY INDEX REPORT",
        "=" * 60,
        "",
        f"Scan Path: {report.scan_path}",
        f"Scan Time: {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.scan_duration_seconds:.2f} seconds",
        "",
        "SUMMARY",
        "-" * 40,
        f"Overall MI: {report.overall_index:.2f} ({report.overall_level})",
        f"Total Files: {report.total_files}",
        f"Total Functions: {report.total_functions}",
        f"Lines of Code: {report.total_lines_of_code:,}",
        "",
        "Files by Level:",
    ]

    for level in MaintainabilityLevel:
        count = report.files_by_level.get(level.value, 0)
        if count > 0:
            lines.append(f"  {level.value.title()}: {count}")

    if report.improvement_priorities:
        lines.extend(["", "Improvement Priorities:", "-" * 40])
        for priority in report.improvement_priorities:
            lines.append(f"  - {priority}")

    if report.worst_functions:
        lines.extend(["", "LOWEST MAINTAINABILITY FUNCTIONS", "-" * 40])
        for i, func in enumerate(report.worst_functions[:10], 1):
            level = func.maintainability_level
            lines.extend([
                f"{i}. {func.name} - MI: {func.maintainability_index:.2f} ({level})",
                f"   Location: {func.location}",
                f"   Complexity: {func.cyclomatic_complexity} | LOC: {func.lines_of_code}",
            ])
            if func.recommendations:
                lines.append(f"   Recommendation: {func.recommendations[0]}")
            lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


def generate_json_report(report: MaintainabilityReport) -> str:
    """Generate JSON report."""
    def serialize_function(func: FunctionMaintainability) -> Dict:
        return {
            "name": func.name,
            "file_path": func.file_path,
            "line_number": func.line_number,
            "maintainability_index": func.maintainability_index,
            "maintainability_level": func.maintainability_level,
            "cyclomatic_complexity": func.cyclomatic_complexity,
            "lines_of_code": func.lines_of_code,
            "halstead_volume": func.halstead_volume,
            "comment_percentage": func.comment_percentage,
            "recommendations": func.recommendations,
        }

    def serialize_file(file_result: FileMaintainability) -> Dict:
        return {
            "file_path": file_result.file_path,
            "maintainability_index": file_result.maintainability_index,
            "maintainability_level": file_result.maintainability_level,
            "total_lines": file_result.total_lines,
            "code_lines": file_result.code_lines,
            "comment_lines": file_result.comment_lines,
            "function_count": file_result.function_count,
            "functions": [serialize_function(f) for f in file_result.functions],
        }

    output = {
        "scan_info": {
            "scan_path": report.scan_path,
            "scanned_at": report.scanned_at.isoformat(),
            "duration_seconds": report.scan_duration_seconds,
        },
        "summary": {
            "overall_index": report.overall_index,
            "overall_level": report.overall_level,
            "total_files": report.total_files,
            "total_functions": report.total_functions,
            "total_lines_of_code": report.total_lines_of_code,
            "files_by_level": report.files_by_level,
            "functions_by_level": report.functions_by_level,
        },
        "file_results": [serialize_file(f) for f in report.file_results],
        "worst_functions": [serialize_function(f) for f in report.worst_functions[:20]],
        "improvement_priorities": report.improvement_priorities,
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(report: MaintainabilityReport) -> str:
    """Generate Markdown report."""
    lines = [
        "# Maintainability Index Report",
        "",
        f"**Scan Path:** `{report.scan_path}`",
        f"**Generated:** {report.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {report.scan_duration_seconds:.2f} seconds",
        "",
        "## Summary",
        "",
        f"**Overall Maintainability Index:** {report.overall_index:.2f} ({report.overall_level})",
        f"**Total Files:** {report.total_files}",
        f"**Total Functions:** {report.total_functions}",
        f"**Lines of Code:** {report.total_lines_of_code:,}",
        "",
        "### Files by Maintainability Level",
        "",
        "| Level | Count |",
        "|-------|-------|",
    ]

    for level in MaintainabilityLevel:
        count = report.files_by_level.get(level.value, 0)
        lines.append(f"| {level.value.title()} | {count} |")

    if report.improvement_priorities:
        lines.extend(["", "## Improvement Priorities", ""])
        for priority in report.improvement_priorities:
            lines.append(f"- {priority}")

    if report.worst_functions:
        lines.extend(["", "## Lowest Maintainability Functions", ""])

        for func in report.worst_functions[:15]:
            level = func.maintainability_level
            lines.extend([
                f"### {func.name}",
                f"- **Location:** `{func.location}`",
                f"- **MI:** {func.maintainability_index:.2f} ({level})",
                f"- **Complexity:** {func.cyclomatic_complexity}",
                f"- **Lines:** {func.lines_of_code}",
                f"- **Comment %:** {func.comment_percentage:.1f}%",
                "",
            ])

            if func.recommendations:
                lines.append("**Recommendations:**")
                for rec in func.recommendations[:3]:
                    lines.append(f"- {rec}")
                lines.append("")

    return "\n".join(lines)
