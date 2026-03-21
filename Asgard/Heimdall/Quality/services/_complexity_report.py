import json

from Asgard.Heimdall.Quality.models.complexity_models import (
    ComplexityResult,
    ComplexitySeverity,
)


def generate_text_report(result: ComplexityResult) -> str:
    """Generate plain text complexity report."""
    lines = [
        "=" * 70,
        "  HEIMDALL COMPLEXITY ANALYSIS REPORT",
        "=" * 70,
        "",
        f"  Scan Path:    {result.scan_path}",
        f"  Scanned At:   {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Duration:     {result.scan_duration_seconds:.2f}s",
        "",
        "-" * 70,
        "  SUMMARY",
        "-" * 70,
        "",
        f"  Files Scanned:         {result.total_files_scanned}",
        f"  Functions Analyzed:    {result.total_functions_analyzed}",
        f"  Files With Violations: {result.files_with_violations}",
        f"  Total Violations:      {result.total_violations}",
        f"  Compliance Rate:       {result.compliance_rate:.1f}%",
        f"  Thresholds:            Cyclomatic={result.cyclomatic_threshold}, Cognitive={result.cognitive_threshold}",
        f"  Averages:              CC={result.average_cyclomatic:.1f}, COG={result.average_cognitive:.1f}",
        f"  Maximums:              CC={result.max_cyclomatic}, COG={result.max_cognitive}",
        "",
        "-" * 70,
        "  METRIC DEFINITIONS",
        "-" * 70,
        "",
        "  Cyclomatic Complexity (CC): Counts the number of independent paths through",
        "    a function. Each branch (if/for/while/except/and/or) adds 1. A function",
        "    with CC=1 is perfectly linear. Higher values mean harder to test and maintain.",
        "",
        "  Cognitive Complexity (COG): Measures how hard the code is for a human to",
        "    read. Penalises nesting depth and non-linear control flow more than CC does.",
        "",
        "  SEVERITY THRESHOLDS",
        f"    (thresholds configured: CC={result.cyclomatic_threshold}, COG={result.cognitive_threshold})",
        f"    MODERATE  -- CC or COG exceeds threshold",
        f"    HIGH      -- CC or COG exceeds threshold x 1.5",
        f"    VERY_HIGH -- CC or COG exceeds threshold x 2",
        f"    CRITICAL  -- CC or COG exceeds threshold x 3",
        "",
    ]

    if result.has_violations:
        lines.extend(["-" * 70, "  VIOLATIONS (worst first)", "-" * 70, ""])
        by_severity = result.get_violations_by_severity()
        for severity in [
            ComplexitySeverity.CRITICAL.value,
            ComplexitySeverity.VERY_HIGH.value,
            ComplexitySeverity.HIGH.value,
            ComplexitySeverity.MODERATE.value,
        ]:
            violations = by_severity[severity]
            if violations:
                lines.append(f"  [{severity.upper()}]")
                for v in violations:
                    name = v.qualified_name if hasattr(v, 'qualified_name') else v.name
                    lines.append(f"    {name:<50} Line {v.line_number:>5}  CC={v.cyclomatic_complexity:>3} COG={v.cognitive_complexity:>3}")
                lines.append("")
    else:
        lines.extend(["  All functions are within the complexity thresholds.", ""])

    lines.extend(["=" * 70, ""])
    return "\n".join(lines)


def generate_json_report(result: ComplexityResult) -> str:
    """Generate JSON complexity report."""
    violations_data = []
    for v in result.violations:
        violations_data.append({
            "name": v.name,
            "qualified_name": v.qualified_name if hasattr(v, 'qualified_name') else v.name,
            "class_name": v.class_name,
            "line_number": v.line_number,
            "end_line": v.end_line,
            "cyclomatic_complexity": v.cyclomatic_complexity,
            "cognitive_complexity": v.cognitive_complexity,
            "severity": v.severity if isinstance(v.severity, str) else v.severity.value,
        })

    report_data = {
        "scan_info": {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "duration_seconds": result.scan_duration_seconds,
        },
        "summary": {
            "total_files_scanned": result.total_files_scanned,
            "total_functions_analyzed": result.total_functions_analyzed,
            "files_with_violations": result.files_with_violations,
            "total_violations": result.total_violations,
            "compliance_rate": round(result.compliance_rate, 2),
            "cyclomatic_threshold": result.cyclomatic_threshold,
            "cognitive_threshold": result.cognitive_threshold,
            "average_cyclomatic": round(result.average_cyclomatic, 2),
            "average_cognitive": round(result.average_cognitive, 2),
            "max_cyclomatic": result.max_cyclomatic,
            "max_cognitive": result.max_cognitive,
        },
        "violations": violations_data,
    }
    return json.dumps(report_data, indent=2)


def generate_markdown_report(result: ComplexityResult) -> str:
    """Generate Markdown complexity report."""
    lines = [
        "# Heimdall Complexity Analysis Report",
        "",
        f"**Scan Path:** `{result.scan_path}`",
        f"**Generated:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration:** {result.scan_duration_seconds:.2f} seconds",
        "",
        "## Summary",
        "",
        f"**Files Scanned:** {result.total_files_scanned}",
        f"**Functions Analyzed:** {result.total_functions_analyzed}",
        f"**Total Violations:** {result.total_violations}",
        f"**Compliance Rate:** {result.compliance_rate:.1f}%",
        f"**Thresholds:** Cyclomatic={result.cyclomatic_threshold}, Cognitive={result.cognitive_threshold}",
        "",
    ]

    if result.has_violations:
        lines.extend([
            "## Violations",
            "",
            "| Function | Line | Cyclomatic | Cognitive | Severity |",
            "|----------|------|-----------|-----------|----------|",
        ])
        for v in result.violations:
            name = v.qualified_name if hasattr(v, 'qualified_name') else v.name
            sev = v.severity if isinstance(v.severity, str) else v.severity.value
            lines.append(f"| `{name}` | {v.line_number} | {v.cyclomatic_complexity} | {v.cognitive_complexity} | {sev} |")
        lines.append("")
    else:
        lines.extend(["All functions are within the complexity thresholds.", ""])

    return "\n".join(lines)
