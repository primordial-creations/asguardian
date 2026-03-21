"""
Heimdall Architecture Analyzer - Markdown report generation.
"""

from Asgard.Heimdall.Architecture.models.architecture_models import ArchitectureReport
from Asgard.Heimdall.Architecture.services._arch_reporter_text import generate_recommendations


def generate_markdown_report(result: ArchitectureReport) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Architecture Analysis Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Violations:** {result.total_violations}")
    lines.append(f"- **Patterns Found:** {result.total_patterns}")
    lines.append(f"- **Health Status:** {'Healthy' if result.is_healthy else 'Needs Attention'}")
    lines.append("")

    if result.solid_report:
        lines.append("## SOLID Principles")
        lines.append("")
        lines.append(f"- **Classes Analyzed:** {result.solid_report.total_classes}")
        lines.append(f"- **Violations Found:** {result.solid_report.total_violations}")
        lines.append("")
        if result.solid_report.violations:
            lines.append("### Violations")
            lines.append("")
            lines.append("| Principle | Class | Message | Severity |")
            lines.append("|-----------|-------|---------|----------|")
            for v in result.solid_report.violations:
                lines.append(
                    f"| {v.principle_name[:20]} | {v.class_name} | "
                    f"{v.message[:40]} | {v.severity.value.upper()} |"
                )
            lines.append("")

    if result.layer_report:
        lines.append("## Layer Architecture")
        lines.append("")
        lines.append(f"- **Status:** {'Valid' if result.layer_report.is_valid else 'Invalid'}")
        lines.append(f"- **Violations:** {result.layer_report.total_violations}")
        lines.append("")
        if result.layer_report.violations:
            lines.append("### Layer Violations")
            lines.append("")
            lines.append("| Source | Target | Message |")
            lines.append("|--------|--------|---------|")
            for v in result.layer_report.violations:
                lines.append(
                    f"| {v.source_module} ({v.source_layer}) | "
                    f"{v.target_module} ({v.target_layer}) | {v.message} |"
                )
            lines.append("")

    if result.pattern_report and result.pattern_report.patterns:
        lines.append("## Design Patterns")
        lines.append("")
        lines.append("| Pattern | Class | Confidence |")
        lines.append("|---------|-------|------------|")
        for p in result.pattern_report.patterns:
            lines.append(
                f"| {p.pattern_type.value.replace('_', ' ').title()} | "
                f"{p.class_name} | {p.confidence:.0%} |"
            )
        lines.append("")

    if result.hexagonal_report:
        lines.append("## Hexagonal Architecture")
        lines.append("")
        lines.append(f"- **Status:** {'Valid' if result.hexagonal_report.is_valid else 'Invalid'}")
        lines.append(f"- **Ports:** {len(result.hexagonal_report.ports)}")
        lines.append(f"- **Adapters:** {len(result.hexagonal_report.adapters)}")
        lines.append(f"- **Violations:** {result.hexagonal_report.total_violations}")
        lines.append("")
        if result.hexagonal_report.violations:
            lines.append("### Hexagonal Violations")
            lines.append("")
            lines.append("| Severity | Source Zone | Target Zone | Message |")
            lines.append("|----------|------------|-------------|---------|")
            for v in result.hexagonal_report.violations:
                lines.append(
                    f"| {v.severity.value.upper()} | "
                    f"{v.source_zone.value} | {v.target_zone.value} | "
                    f"{v.message[:60]} |"
                )
            lines.append("")

    if result.suggestion_report and result.suggestion_report.suggestions:
        lines.append("## Pattern Candidate Suggestions")
        lines.append("")
        lines.append(f"- **Total Suggestions:** {result.suggestion_report.total_suggestions}")
        lines.append("")
        lines.append("| Pattern | Class | Confidence | Signals |")
        lines.append("|---------|-------|------------|---------|")
        for s in result.suggestion_report.suggestions:
            signal_str = "; ".join(s.signals[:2]) if s.signals else ""
            lines.append(
                f"| {s.pattern_type.value.replace('_', ' ').title()} | "
                f"{s.class_name} | {s.confidence:.0%} | {signal_str[:60]} |"
            )
        lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    for rec in generate_recommendations(result):
        lines.append(f"- {rec}")
    lines.append("")

    return "\n".join(lines)
