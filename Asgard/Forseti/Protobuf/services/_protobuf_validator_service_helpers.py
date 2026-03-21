"""
Protobuf Validator Service Helpers.

Report generation helpers for ProtobufValidatorService.
"""

from Asgard.Forseti.Protobuf.models.protobuf_models import (
    ProtobufCompatibilityResult,
    ProtobufValidationResult,
)
from Asgard.Forseti.Protobuf.services._protobuf_validator_parse_helpers import (
    MESSAGE_PATTERN,
    ENUM_PATTERN,
    SERVICE_PATTERN,
    extract_block,
    parse_enum_block,
    parse_imports,
    parse_message_block,
    parse_options,
    parse_package,
    parse_service_block,
    parse_syntax,
    remove_comments,
)


def generate_text_report(result: ProtobufValidationResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("Protobuf Validation Report")
    lines.append("=" * 60)
    lines.append(f"File: {result.file_path or 'N/A'}")
    lines.append(f"Syntax: {result.syntax_version or 'Unknown'}")
    lines.append(f"Valid: {'Yes' if result.is_valid else 'No'}")
    lines.append(f"Errors: {result.error_count}")
    lines.append(f"Warnings: {result.warning_count}")
    lines.append(f"Time: {result.validation_time_ms:.2f}ms")
    lines.append("-" * 60)
    if result.parsed_schema:
        lines.append(f"Package: {result.parsed_schema.package or 'N/A'}")
        lines.append(f"Messages: {result.parsed_schema.message_count}")
        lines.append(f"Enums: {result.parsed_schema.enum_count}")
        lines.append(f"Services: {result.parsed_schema.service_count}")
        lines.append("-" * 60)
    if result.errors:
        lines.append("\nErrors:")
        for error in result.errors:
            line_info = f" (line {error.line})" if error.line else ""
            lines.append(f"  [{error.rule or 'error'}] {error.path}{line_info}: {error.message}")
    if result.warnings:
        lines.append("\nWarnings:")
        for warning in result.warnings:
            lines.append(f"  [{warning.rule or 'warning'}] {warning.path}: {warning.message}")
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(result: ProtobufValidationResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# Protobuf Validation Report\n")
    lines.append(f"- **File**: {result.file_path or 'N/A'}")
    lines.append(f"- **Syntax**: {result.syntax_version or 'Unknown'}")
    lines.append(f"- **Valid**: {'Yes' if result.is_valid else 'No'}")
    lines.append(f"- **Errors**: {result.error_count}")
    lines.append(f"- **Warnings**: {result.warning_count}")
    lines.append(f"- **Time**: {result.validation_time_ms:.2f}ms\n")
    if result.parsed_schema:
        lines.append("## Schema Summary\n")
        lines.append(f"- **Package**: {result.parsed_schema.package or 'N/A'}")
        lines.append(f"- **Messages**: {result.parsed_schema.message_count}")
        lines.append(f"- **Enums**: {result.parsed_schema.enum_count}")
        lines.append(f"- **Services**: {result.parsed_schema.service_count}\n")
    if result.errors:
        lines.append("## Errors\n")
        lines.append("| Path | Rule | Message |")
        lines.append("|------|------|---------|")
        for error in result.errors:
            lines.append(f"| `{error.path}` | {error.rule or 'error'} | {error.message} |")
    if result.warnings:
        lines.append("\n## Warnings\n")
        lines.append("| Path | Rule | Message |")
        lines.append("|------|------|---------|")
        for warning in result.warnings:
            lines.append(f"| `{warning.path}` | {warning.rule or 'warning'} | {warning.message} |")
    return "\n".join(lines)
