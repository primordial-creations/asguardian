"""
Heimdall Hexagonal Architecture Report Generation

Report generation helpers for HexagonalAnalyzer.
"""

import json

from Asgard.Heimdall.Architecture.models.architecture_models import HexagonalReport


def generate_text_report(result: HexagonalReport) -> str:
    """Generate text format report."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  HEIMDALL HEXAGONAL ARCHITECTURE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"  Scan Path:        {result.scan_path}")
    lines.append(f"  Total Violations: {result.total_violations}")
    lines.append(f"  Architecture:     {'VALID' if result.is_valid else 'INVALID'}")
    lines.append(f"  Ports Found:      {len(result.ports)}")
    lines.append(f"  Adapters Found:   {len(result.adapters)}")
    lines.append("")

    zone_counts = {}
    for zone in result.zone_assignments.values():
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    lines.append("-" * 70)
    lines.append("  ZONE ASSIGNMENTS")
    lines.append("-" * 70)
    lines.append("")
    for zone, count in sorted(zone_counts.items()):
        lines.append(f"  {zone:20s} {count} modules")
    lines.append("")

    if result.ports:
        lines.append("-" * 70)
        lines.append("  PORTS (Interfaces)")
        lines.append("-" * 70)
        lines.append("")
        for port in result.ports:
            lines.append(f"  {port.name} [{port.direction.value}]")
            lines.append(f"    File:    {port.file_path}")
            if port.abstract_methods:
                lines.append(f"    Methods: {', '.join(port.abstract_methods)}")
            lines.append("")

    if result.adapters:
        lines.append("-" * 70)
        lines.append("  ADAPTERS")
        lines.append("-" * 70)
        lines.append("")
        for adapter in result.adapters:
            lines.append(f"  {adapter.name} -> {adapter.implements_port}")
            lines.append(f"    File: {adapter.file_path}")
            if adapter.framework_imports:
                lines.append(f"    Frameworks: {', '.join(adapter.framework_imports)}")
            lines.append("")

    if result.violations:
        lines.append("-" * 70)
        lines.append("  VIOLATIONS")
        lines.append("-" * 70)
        lines.append("")
        for v in result.violations:
            lines.append(f"  [{v.severity.value.upper()}] {v.message}")
            lines.append(f"    File:  {v.file_path}")
            lines.append(f"    Zones: {v.source_zone.value} -> {v.target_zone.value}")
            lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def generate_json_report(result: HexagonalReport) -> str:
    """Generate JSON format report."""
    output = {
        "scan_path": result.scan_path,
        "scanned_at": result.scanned_at.isoformat(),
        "is_valid": result.is_valid,
        "total_violations": result.total_violations,
        "ports": [
            {
                "name": p.name,
                "file_path": p.file_path,
                "direction": p.direction.value,
                "abstract_methods": p.abstract_methods,
            }
            for p in result.ports
        ],
        "adapters": [
            {
                "name": a.name,
                "file_path": a.file_path,
                "implements_port": a.implements_port,
                "zone": a.zone.value,
                "framework_imports": a.framework_imports,
            }
            for a in result.adapters
        ],
        "zone_assignments": result.zone_assignments,
        "violations": [
            {
                "file_path": v.file_path,
                "source_zone": v.source_zone.value,
                "target_zone": v.target_zone.value,
                "class_name": v.class_name,
                "message": v.message,
                "severity": v.severity.value,
            }
            for v in result.violations
        ],
    }

    return json.dumps(output, indent=2)


def generate_markdown_report(result: HexagonalReport) -> str:
    """Generate Markdown format report."""
    lines = []
    lines.append("# Heimdall Hexagonal Architecture Report")
    lines.append("")
    lines.append(f"- **Scan Path:** `{result.scan_path}`")
    lines.append(f"- **Status:** {'Valid' if result.is_valid else 'Invalid'}")
    lines.append(f"- **Total Violations:** {result.total_violations}")
    lines.append(f"- **Ports:** {len(result.ports)}")
    lines.append(f"- **Adapters:** {len(result.adapters)}")
    lines.append("")

    if result.ports:
        lines.append("## Ports")
        lines.append("")
        lines.append("| Name | Direction | Methods | File |")
        lines.append("|------|-----------|---------|------|")
        for p in result.ports:
            methods = ", ".join(p.abstract_methods[:3])
            if len(p.abstract_methods) > 3:
                methods += f" (+{len(p.abstract_methods) - 3})"
            lines.append(
                f"| {p.name} | {p.direction.value} | "
                f"{methods} | {p.file_path} |"
            )
        lines.append("")

    if result.adapters:
        lines.append("## Adapters")
        lines.append("")
        lines.append("| Name | Implements | Zone | Frameworks |")
        lines.append("|------|-----------|------|------------|")
        for a in result.adapters:
            lines.append(
                f"| {a.name} | {a.implements_port} | "
                f"{a.zone.value} | "
                f"{', '.join(a.framework_imports) or '(none)'} |"
            )
        lines.append("")

    if result.violations:
        lines.append("## Violations")
        lines.append("")
        lines.append("| Severity | Source Zone | Target Zone | Message |")
        lines.append("|----------|------------|-------------|---------|")
        for v in result.violations:
            lines.append(
                f"| {v.severity.value.upper()} | "
                f"{v.source_zone.value} | {v.target_zone.value} | "
                f"{v.message} |"
            )
        lines.append("")

    return "\n".join(lines)
