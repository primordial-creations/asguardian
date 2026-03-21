"""
Heimdall Layer Analyzer Report Generation

Report generation helpers for LayerAnalyzer.
"""

import json

from Asgard.Heimdall.Architecture.models.architecture_models import LayerReport


def generate_text_report(result: LayerReport) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL LAYER ARCHITECTURE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:        {result.scan_path}")
    lines.append(f"  Total Violations: {result.total_violations}")
    lines.append(f"  Architecture:     {'VALID' if result.is_valid else 'INVALID'}")
    lines.append("")

    lines.append("-" * 70)
    lines.append("  LAYER DEFINITIONS")
    lines.append("-" * 70)
    lines.append("")

    for layer in result.layers:
        lines.append(f"  {layer.name}")
        lines.append(f"    Patterns: {', '.join(layer.patterns)}")
        lines.append(f"    Allowed:  {', '.join(layer.allowed_dependencies) or '(none)'}")
        lines.append("")

    if result.violations:
        lines.append("-" * 70)
        lines.append("  VIOLATIONS")
        lines.append("-" * 70)
        lines.append("")

        for v in result.violations:
            lines.append(f"  [{v.severity.value.upper()}] {v.message}")
            lines.append(f"    Source: {v.source_module} ({v.source_layer})")
            lines.append(f"    Target: {v.target_module} ({v.target_layer})")
            lines.append(f"    File:   {v.file_path}")
            lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(result: LayerReport) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "is_valid": result.is_valid,
        "total_violations": result.total_violations,
        "layers": [
            {
                "name": l.name,
                "patterns": l.patterns,
                "allowed_dependencies": l.allowed_dependencies,
                "description": l.description,
            }
            for l in result.layers
        ],
        "layer_assignments": result.layer_assignments,
        "violations": [
            {
                "source_module": v.source_module,
                "source_layer": v.source_layer,
                "target_module": v.target_module,
                "target_layer": v.target_layer,
                "file_path": v.file_path,
                "line_number": v.line_number,
                "message": v.message,
                "severity": v.severity.value,
            }
            for v in result.violations
        ],
    }
    return json.dumps(output, indent=2)


def generate_markdown_report(result: LayerReport) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Layer Architecture Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Architecture Status:** {'Valid' if result.is_valid else 'Invalid'}")
    lines.append(f"- **Total Violations:** {result.total_violations}")
    lines.append("")

    lines.append("## Layer Definitions")
    lines.append("")
    lines.append("| Layer | Patterns | Allowed Dependencies |")
    lines.append("|-------|----------|---------------------|")

    for layer in result.layers:
        lines.append(
            f"| {layer.name} | {', '.join(layer.patterns)} | "
            f"{', '.join(layer.allowed_dependencies) or '(none)'} |"
        )

    lines.append("")

    if result.violations:
        lines.append("## Violations")
        lines.append("")
        lines.append("| Source | Target | Severity | Message |")
        lines.append("|--------|--------|----------|---------|")

        for v in result.violations:
            lines.append(
                f"| {v.source_module} | {v.target_module} | "
                f"{v.severity.value.upper()} | {v.message} |"
            )

        lines.append("")

    return "\n".join(lines)
