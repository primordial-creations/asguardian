"""
Heimdall Dependency Analyzer - Report Generation Helpers

Standalone functions for generating text, JSON, and Markdown
dependency analysis reports from a DependencyReport instance.
"""

import json

from Asgard.Heimdall.Dependencies.models.dependency_models import DependencyReport


def generate_text_report(result: DependencyReport) -> str:
    """Generate text format dependency report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL DEPENDENCY ANALYSIS REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:    {result.scan_path}")
    lines.append(f"  Scanned At:   {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Duration:     {result.scan_duration_seconds:.2f}s")
    lines.append("")
    lines.append(f"  Total Modules:      {result.total_modules}")
    lines.append(f"  Total Dependencies: {result.total_dependencies}")
    lines.append("")

    if result.has_cycles:
        lines.append("-" * 70)
        lines.append("  CIRCULAR DEPENDENCIES")
        lines.append("-" * 70)
        lines.append("")

        for cycle in result.circular_dependencies:
            lines.append(f"  [{cycle.severity.value.upper()}] {cycle.as_string}")
            lines.append("")

    if result.high_coupling_modules:
        lines.append("-" * 70)
        lines.append("  HIGH COUPLING MODULES")
        lines.append("-" * 70)
        lines.append("")

        for module in result.high_coupling_modules:
            lines.append(f"  {module.module_name}")
            lines.append(f"    Afferent (Ca): {module.afferent_coupling}")
            lines.append(f"    Efferent (Ce): {module.efferent_coupling}")
            lines.append(f"    Instability:   {module.instability:.2f}")
            lines.append("")

    lines.append("-" * 70)
    lines.append("  MODULARITY METRICS")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Modularity Score:   {result.modularity.modularity_score:.2f}")
    lines.append(f"  Clusters Found:     {len(result.modularity.clusters)}")
    lines.append(f"  Average Afferent:   {result.modularity.average_afferent:.2f}")
    lines.append(f"  Average Efferent:   {result.modularity.average_efferent:.2f}")
    lines.append(f"  Stable Modules:     {len(result.modularity.stable_modules)}")
    lines.append(f"  Unstable Modules:   {len(result.modularity.unstable_modules)}")
    lines.append("")

    lines.append("-" * 70)
    lines.append("  SUMMARY")
    lines.append("-" * 70)
    lines.append("")

    if result.has_cycles:
        lines.append(f"  [!] Found {result.total_cycles} circular dependencies")
    else:
        lines.append("  [OK] No circular dependencies found")

    if result.high_coupling_modules:
        lines.append(f"  [!] Found {len(result.high_coupling_modules)} high coupling modules")
    else:
        lines.append("  [OK] No high coupling modules found")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def generate_json_report(result: DependencyReport) -> str:
    """Generate JSON format dependency report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "scan_duration_seconds": result.scan_duration_seconds,
        "summary": {
            "total_modules": result.total_modules,
            "total_dependencies": result.total_dependencies,
            "total_cycles": result.total_cycles,
            "has_cycles": result.has_cycles,
        },
        "circular_dependencies": [
            {
                "cycle": cycle.cycle,
                "length": cycle.cycle_length,
                "severity": cycle.severity.value,
            }
            for cycle in result.circular_dependencies
        ],
        "modularity": {
            "score": result.modularity.modularity_score,
            "clusters": len(result.modularity.clusters),
            "average_afferent": result.modularity.average_afferent,
            "average_efferent": result.modularity.average_efferent,
            "stable_modules": result.modularity.stable_modules,
            "unstable_modules": result.modularity.unstable_modules,
        },
        "modules": [
            {
                "name": m.module_name,
                "file": m.relative_path,
                "dependencies": list(m.all_dependencies),
                "afferent_coupling": m.afferent_coupling,
                "efferent_coupling": m.efferent_coupling,
                "instability": round(m.instability, 2),
            }
            for m in result.modules
        ],
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(result: DependencyReport) -> str:
    """Generate Markdown format dependency report."""
    lines = []
    lines.append("# Heimdall Dependency Analysis Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Scanned At:** {result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Duration:** {result.scan_duration_seconds:.2f}s")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Modules:** {result.total_modules}")
    lines.append(f"- **Total Dependencies:** {result.total_dependencies}")
    lines.append(f"- **Circular Dependencies:** {result.total_cycles}")
    lines.append("")

    if result.has_cycles:
        lines.append("## Circular Dependencies")
        lines.append("")
        lines.append("| Cycle | Length | Severity |")
        lines.append("|-------|--------|----------|")

        for cycle in result.circular_dependencies:
            lines.append(
                f"| {cycle.as_string} | {cycle.cycle_length} | "
                f"{cycle.severity.value.upper()} |"
            )

        lines.append("")

    lines.append("## Modularity Metrics")
    lines.append("")
    lines.append(f"- **Modularity Score:** {result.modularity.modularity_score:.2f}")
    lines.append(f"- **Clusters:** {len(result.modularity.clusters)}")
    lines.append(f"- **Average Afferent:** {result.modularity.average_afferent:.2f}")
    lines.append(f"- **Average Efferent:** {result.modularity.average_efferent:.2f}")
    lines.append("")

    return "\n".join(lines)
