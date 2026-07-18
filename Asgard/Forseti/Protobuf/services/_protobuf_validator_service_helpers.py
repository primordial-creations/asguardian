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
    """Generate a text format report (thin wrapper over the unified renderer)."""
    from Asgard.Forseti.Reporting.services.legacy_report_service import (
        render_legacy_text_report,
    )

    extra_blocks = []
    if result.parsed_schema:
        extra_blocks.append([
            f"Package: {result.parsed_schema.package or 'N/A'}",
            f"Messages: {result.parsed_schema.message_count}",
            f"Enums: {result.parsed_schema.enum_count}",
            f"Services: {result.parsed_schema.service_count}",
        ])
    error_items = []
    for error in result.errors:
        line_info = f" (line {error.line})" if error.line else ""
        error_items.append(
            f"  [{error.rule or 'error'}] {error.path}{line_info}: {error.message}"
        )
    return render_legacy_text_report(
        "Protobuf Validation Report",
        [
            f"File: {result.file_path or 'N/A'}",
            f"Syntax: {result.syntax_version or 'Unknown'}",
            f"Valid: {'Yes' if result.is_valid else 'No'}",
            f"Errors: {result.error_count}",
            f"Warnings: {result.warning_count}",
            f"Time: {result.validation_time_ms:.2f}ms",
        ],
        [
            ("Errors", error_items),
            ("Warnings", [f"  [{w.rule or 'warning'}] {w.path}: {w.message}"
                          for w in result.warnings]),
        ],
        extra_blocks=extra_blocks,
    )


_MD_TABLE_HEADER = ["| Path | Rule | Message |", "|------|------|---------|"]


def generate_markdown_report(result: ProtobufValidationResult) -> str:
    """Generate a markdown format report (thin wrapper over the unified renderer)."""
    from Asgard.Forseti.Reporting.services.legacy_report_service import (
        render_legacy_markdown_report,
    )

    header = [
        f"- **File**: {result.file_path or 'N/A'}",
        f"- **Syntax**: {result.syntax_version or 'Unknown'}",
        f"- **Valid**: {'Yes' if result.is_valid else 'No'}",
        f"- **Errors**: {result.error_count}",
        f"- **Warnings**: {result.warning_count}",
        f"- **Time**: {result.validation_time_ms:.2f}ms\n",
    ]
    if result.parsed_schema:
        header.extend([
            "## Schema Summary\n",
            f"- **Package**: {result.parsed_schema.package or 'N/A'}",
            f"- **Messages**: {result.parsed_schema.message_count}",
            f"- **Enums**: {result.parsed_schema.enum_count}",
            f"- **Services**: {result.parsed_schema.service_count}\n",
        ])
    return render_legacy_markdown_report(
        "Protobuf Validation Report",
        header,
        [
            ("Errors", _MD_TABLE_HEADER + [
                f"| `{e.path}` | {e.rule or 'error'} | {e.message} |"
                for e in result.errors] if result.errors else []),
            ("Warnings", _MD_TABLE_HEADER + [
                f"| `{w.path}` | {w.rule or 'warning'} | {w.message} |"
                for w in result.warnings] if result.warnings else []),
        ],
    )
