"""
Avro Compatibility Report Helpers.

Report generation helpers for AvroCompatibilityService.
"""

from Asgard.Forseti.Avro.models.avro_models import AvroCompatibilityResult


def generate_text_report(result: AvroCompatibilityResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Avro Schema Compatibility Report")
    lines.append("=" * 60)
    lines.append(f"Old Schema: {result.source_file or 'N/A'}")
    lines.append(f"New Schema: {result.target_file or 'N/A'}")
    lines.append(f"Mode: {result.compatibility_mode}")
    lines.append(f"Compatible: {'Yes' if result.is_compatible else 'No'}")
    lines.append(f"Compatibility Level: {result.compatibility_level}")
    lines.append(f"Breaking Changes: {result.breaking_change_count}")
    lines.append(f"Time: {result.check_time_ms:.2f}ms")
    lines.append("-" * 60)
    if result.added_fields:
        lines.append(f"\nAdded Fields: {', '.join(result.added_fields)}")
    if result.removed_fields:
        lines.append(f"Removed Fields: {', '.join(result.removed_fields)}")
    if result.modified_fields:
        lines.append(f"Modified Fields: {', '.join(result.modified_fields)}")
    if result.breaking_changes:
        lines.append("\nBreaking Changes:")
        for change in result.breaking_changes:
            lines.append(f"  [{change.change_type}] {change.path}")
            lines.append(f"    {change.message}")
            if change.mitigation:
                lines.append(f"    Mitigation: {change.mitigation}")
    if result.warnings:
        lines.append("\nWarnings:")
        for warning in result.warnings:
            lines.append(f"  [{warning.change_type}] {warning.message}")
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(result: AvroCompatibilityResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# Avro Schema Compatibility Report\n")
    lines.append(f"- **Old Schema**: {result.source_file or 'N/A'}")
    lines.append(f"- **New Schema**: {result.target_file or 'N/A'}")
    lines.append(f"- **Mode**: {result.compatibility_mode}")
    lines.append(f"- **Compatible**: {'Yes' if result.is_compatible else 'No'}")
    lines.append(f"- **Compatibility Level**: {result.compatibility_level}")
    lines.append(f"- **Breaking Changes**: {result.breaking_change_count}\n")
    if result.breaking_changes:
        lines.append("## Breaking Changes\n")
        lines.append("| Type | Path | Message | Mitigation |")
        lines.append("|------|------|---------|------------|")
        for change in result.breaking_changes:
            mitigation = change.mitigation or "-"
            lines.append(f"| {change.change_type} | `{change.path}` | {change.message} | {mitigation} |")
    if result.added_fields:
        lines.append("\n## Added Fields\n")
        for field in result.added_fields:
            lines.append(f"- `{field}`")
    if result.removed_fields:
        lines.append("\n## Removed Fields\n")
        for field in result.removed_fields:
            lines.append(f"- `{field}`")
    if result.modified_fields:
        lines.append("\n## Modified Fields\n")
        for field in result.modified_fields:
            lines.append(f"- `{field}`")
    if result.warnings:
        lines.append("\n## Warnings\n")
        for warning in result.warnings:
            lines.append(f"- [{warning.change_type}] {warning.message}")
    return "\n".join(lines)
