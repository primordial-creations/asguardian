"""
Heimdall Coverage Analyzer - report generation helpers.

Standalone functions for generating text, JSON, and Markdown reports
from a CoverageReport. Accepts the report as an explicit parameter.
"""

import json

from Asgard.Heimdall.Coverage.models.coverage_models import CoverageReport


def generate_text_report(result: CoverageReport) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL COVERAGE ANALYSIS REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:        {result.scan_path}")
    lines.append(f"  Scanned At:       {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Duration:         {result.scan_duration_seconds:.2f}s")
    lines.append("")

    lines.append("-" * 70)
    lines.append("  COVERAGE METRICS")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Total Methods:      {result.metrics.total_methods}")
    lines.append(f"  Covered Methods:    {result.metrics.covered_methods}")
    lines.append(f"  Method Coverage:    {result.metrics.method_coverage_percent:.1f}%")
    if result.metrics.total_branches > 0:
        lines.append(f"  Total Branches:     {result.metrics.total_branches}")
        lines.append(f"  Branch Coverage:    {result.metrics.branch_coverage_percent:.1f}%")
    lines.append("")

    if result.gaps:
        lines.append("-" * 70)
        lines.append("  COVERAGE GAPS")
        lines.append("-" * 70)
        lines.append("")

        for severity, gaps in result.gaps_by_severity.items():
            if gaps:
                lines.append(f"  {severity.value.upper()}: {len(gaps)} gaps")

        lines.append("")
        lines.append("  Top Gaps:")
        for gap in result.gaps[:5]:
            lines.append(f"    [{gap.severity.value.upper()}] {gap.method.full_name}")
            lines.append(f"      File: {gap.file_path}:{gap.line_number}")

        lines.append("")

    if result.suggestions:
        lines.append("-" * 70)
        lines.append("  TEST SUGGESTIONS")
        lines.append("-" * 70)
        lines.append("")

        for priority, suggestions in result.suggestions_by_priority.items():
            if suggestions:
                lines.append(f"  {priority.value.upper()}: {len(suggestions)} suggestions")

        lines.append("")
        lines.append("  Top Suggestions:")
        for sug in result.suggestions[:5]:
            lines.append(f"    [{sug.priority.value.upper()}] {sug.test_name}")
            lines.append(f"      {sug.description}")

        lines.append("")

    if result.class_coverage:
        poor = [c for c in result.class_coverage if c.coverage_percent < 50]
        if poor:
            lines.append("-" * 70)
            lines.append("  CLASSES NEEDING ATTENTION")
            lines.append("-" * 70)
            lines.append("")

            for cls in sorted(poor, key=lambda c: c.coverage_percent)[:5]:
                lines.append(f"  {cls.class_name}: {cls.coverage_percent:.1f}% coverage")
                lines.append(f"    Uncovered: {', '.join(cls.uncovered_methods[:3])}")

            lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(result: CoverageReport) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "scan_duration_seconds": result.scan_duration_seconds,
        "metrics": {
            "total_methods": result.metrics.total_methods,
            "covered_methods": result.metrics.covered_methods,
            "method_coverage_percent": round(result.metrics.method_coverage_percent, 2),
            "total_branches": result.metrics.total_branches,
            "branch_coverage_percent": round(result.metrics.branch_coverage_percent, 2),
        },
        "summary": {
            "total_gaps": result.total_gaps,
            "total_suggestions": result.total_suggestions,
        },
        "gaps": [
            {
                "method": gap.method.full_name,
                "file_path": gap.file_path,
                "line_number": gap.line_number,
                "severity": gap.severity.value,
                "message": gap.message,
                "details": gap.details,
            }
            for gap in result.gaps
        ],
        "suggestions": [
            {
                "test_name": sug.test_name,
                "method": sug.method.full_name,
                "priority": sug.priority.value,
                "test_type": sug.test_type,
                "description": sug.description,
                "test_cases": sug.test_cases,
            }
            for sug in result.suggestions
        ],
        "class_coverage": [
            {
                "class_name": cls.class_name,
                "file_path": cls.file_path,
                "total_methods": cls.total_methods,
                "covered_methods": cls.covered_methods,
                "coverage_percent": round(cls.coverage_percent, 2),
                "uncovered_methods": cls.uncovered_methods,
            }
            for cls in result.class_coverage
        ],
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(result: CoverageReport) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Coverage Analysis Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
    lines.append("")

    lines.append("## Coverage Metrics")
    lines.append("")
    lines.append(f"- **Method Coverage:** {result.metrics.method_coverage_percent:.1f}%")
    lines.append(f"  - Total Methods: {result.metrics.total_methods}")
    lines.append(f"  - Covered: {result.metrics.covered_methods}")
    if result.metrics.total_branches > 0:
        lines.append(f"- **Branch Coverage:** {result.metrics.branch_coverage_percent:.1f}%")
    lines.append("")

    if result.gaps:
        lines.append("## Coverage Gaps")
        lines.append("")
        lines.append("| Method | File | Severity | Message |")
        lines.append("|--------|------|----------|---------|")

        for gap in result.gaps[:20]:
            lines.append(
                f"| {gap.method.full_name} | {gap.file_path}:{gap.line_number} | "
                f"{gap.severity.value.upper()} | {gap.message} |"
            )

        if len(result.gaps) > 20:
            lines.append(f"| ... | ... | ... | +{len(result.gaps) - 20} more gaps |")

        lines.append("")

    if result.suggestions:
        lines.append("## Test Suggestions")
        lines.append("")
        lines.append("| Test | Priority | Type | Description |")
        lines.append("|------|----------|------|-------------|")

        for sug in result.suggestions[:15]:
            lines.append(
                f"| {sug.test_name} | {sug.priority.value.upper()} | "
                f"{sug.test_type} | {sug.description} |"
            )

        lines.append("")

    if result.class_coverage:
        lines.append("## Class Coverage")
        lines.append("")
        lines.append("| Class | Coverage | Covered/Total | Uncovered Methods |")
        lines.append("|-------|----------|---------------|-------------------|")

        for cls in sorted(result.class_coverage, key=lambda c: c.coverage_percent)[:20]:
            uncovered = ", ".join(cls.uncovered_methods[:3])
            if len(cls.uncovered_methods) > 3:
                uncovered += f" +{len(cls.uncovered_methods) - 3} more"

            lines.append(
                f"| {cls.class_name} | {cls.coverage_percent:.1f}% | "
                f"{cls.covered_methods}/{cls.total_methods} | {uncovered} |"
            )

        lines.append("")

    return "\n".join(lines)
