"""
Protobuf Compatibility Report Helpers.

Report generation helpers for ProtobufCompatibilityService.
"""

from Asgard.Forseti.Protobuf.models.protobuf_models import ProtobufCompatibilityResult


def generate_text_report(result: ProtobufCompatibilityResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Protobuf Compatibility Report")
    lines.append("=" * 60)
    lines.append(f"Old Schema: {result.source_file or 'N/A'}")
    lines.append(f"New Schema: {result.target_file or 'N/A'}")
    lines.append(f"Compatible: {'Yes' if result.is_compatible else 'No'}")
    lines.append(f"Compatibility Level: {result.compatibility_level}")
    lines.append(f"Breaking Changes: {result.breaking_change_count}")
    lines.append(f"Time: {result.check_time_ms:.2f}ms")
    lines.append("-" * 60)
    if result.added_messages:
        lines.append(f"\nAdded Messages: {', '.join(result.added_messages)}")
    if result.removed_messages:
        lines.append(f"Removed Messages: {', '.join(result.removed_messages)}")
    if result.modified_messages:
        lines.append(f"Modified Messages: {', '.join(result.modified_messages)}")
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


def generate_markdown_report(result: ProtobufCompatibilityResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# Protobuf Compatibility Report\n")
    lines.append(f"- **Old Schema**: {result.source_file or 'N/A'}")
    lines.append(f"- **New Schema**: {result.target_file or 'N/A'}")
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
    if result.added_messages:
        lines.append("\n## Added Messages\n")
        for msg in result.added_messages:
            lines.append(f"- `{msg}`")
    if result.removed_messages:
        lines.append("\n## Removed Messages\n")
        for msg in result.removed_messages:
            lines.append(f"- `{msg}`")
    if result.modified_messages:
        lines.append("\n## Modified Messages\n")
        for msg in result.modified_messages:
            lines.append(f"- `{msg}`")
    if result.warnings:
        lines.append("\n## Warnings\n")
        for warning in result.warnings:
            lines.append(f"- [{warning.change_type}] {warning.message}")
    return "\n".join(lines)
