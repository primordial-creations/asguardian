"""
Avro Validator Service Helpers.

Private helper methods for AvroValidatorService.
"""

import json
import re
from typing import Any, Callable, Optional

from Asgard.Forseti.Avro.models.avro_models import (
    AvroConfig,
    AvroValidationError,
    AvroValidationResult,
    ValidationSeverity,
)


def generate_text_report(result: AvroValidationResult) -> str:
    """Generate a text format report (thin wrapper over the unified renderer)."""
    from Asgard.Forseti.Reporting.services.legacy_report_service import (
        render_legacy_text_report,
    )

    extra_blocks = []
    if result.parsed_schema:
        block = [f"Name: {result.parsed_schema.full_name}"]
        if result.parsed_schema.fields:
            block.append(f"Fields: {result.parsed_schema.field_count}")
        if result.parsed_schema.symbols:
            block.append(f"Symbols: {len(result.parsed_schema.symbols)}")
        extra_blocks.append(block)
    return render_legacy_text_report(
        "Avro Schema Validation Report",
        [
            f"File: {result.file_path or 'N/A'}",
            f"Type: {result.schema_type or 'Unknown'}",
            f"Valid: {'Yes' if result.is_valid else 'No'}",
            f"Errors: {result.error_count}",
            f"Warnings: {result.warning_count}",
            f"Time: {result.validation_time_ms:.2f}ms",
        ],
        [
            ("Errors", [f"  [{e.rule or 'error'}] {e.path}: {e.message}"
                        for e in result.errors]),
            ("Warnings", [f"  [{w.rule or 'warning'}] {w.path}: {w.message}"
                          for w in result.warnings]),
        ],
        extra_blocks=extra_blocks,
    )


_MD_TABLE_HEADER = ["| Path | Rule | Message |", "|------|------|---------|"]


def generate_markdown_report(result: AvroValidationResult) -> str:
    """Generate a markdown format report (thin wrapper over the unified renderer)."""
    from Asgard.Forseti.Reporting.services.legacy_report_service import (
        render_legacy_markdown_report,
    )

    header = [
        f"- **File**: {result.file_path or 'N/A'}",
        f"- **Type**: {result.schema_type or 'Unknown'}",
        f"- **Valid**: {'Yes' if result.is_valid else 'No'}",
        f"- **Errors**: {result.error_count}",
        f"- **Warnings**: {result.warning_count}",
        f"- **Time**: {result.validation_time_ms:.2f}ms\n",
    ]
    if result.parsed_schema:
        header.append("## Schema Summary\n")
        header.append(f"- **Name**: {result.parsed_schema.full_name}")
        if result.parsed_schema.fields:
            header.append(f"- **Fields**: {result.parsed_schema.field_count}")
        if result.parsed_schema.symbols:
            header.append(f"- **Symbols**: {len(result.parsed_schema.symbols)}\n")
    return render_legacy_markdown_report(
        "Avro Schema Validation Report",
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


def validate_enum_block(
    path: str,
    schema: dict[str, Any],
    named_types: dict[str, dict[str, Any]],
    config: AvroConfig,
    is_valid_name_fn: Callable[[str], bool]
) -> list[AvroValidationError]:
    """Validate an enum type."""
    errors: list[AvroValidationError] = []
    if "name" not in schema:
        errors.append(AvroValidationError(path=path, message="Enum type requires 'name' field", severity=ValidationSeverity.ERROR, rule="enum-has-name"))
        return errors
    name = schema["name"]
    namespace = schema.get("namespace", "")
    if not is_valid_name_fn(name):
        errors.append(AvroValidationError(path=f"{path}/name", message=f"Invalid name format: '{name}'", severity=ValidationSeverity.ERROR, rule="valid-name"))
    named_types[f"{namespace}.{name}" if namespace else name] = schema
    if "symbols" not in schema:
        errors.append(AvroValidationError(path=path, message="Enum type requires 'symbols' field", severity=ValidationSeverity.ERROR, rule="enum-has-symbols"))
        return errors
    symbols = schema["symbols"]
    if not isinstance(symbols, list):
        errors.append(AvroValidationError(path=f"{path}/symbols", message="Symbols must be an array", severity=ValidationSeverity.ERROR, rule="symbols-is-array"))
        return errors
    if not symbols:
        errors.append(AvroValidationError(path=f"{path}/symbols", message="Enum must have at least one symbol", severity=ValidationSeverity.ERROR, rule="non-empty-symbols"))
    seen_symbols: set[str] = set()
    for i, symbol in enumerate(symbols):
        if not isinstance(symbol, str):
            errors.append(AvroValidationError(path=f"{path}/symbols[{i}]", message=f"Symbol must be a string, got {type(symbol).__name__}", severity=ValidationSeverity.ERROR, rule="symbol-is-string"))
            continue
        if not is_valid_name_fn(symbol):
            errors.append(AvroValidationError(path=f"{path}/symbols[{i}]", message=f"Invalid symbol format: '{symbol}'", severity=ValidationSeverity.ERROR, rule="valid-symbol"))
        if symbol in seen_symbols:
            errors.append(AvroValidationError(path=f"{path}/symbols[{i}]", message=f"Duplicate symbol: '{symbol}'", severity=ValidationSeverity.ERROR, rule="unique-symbols"))
        seen_symbols.add(symbol)
        if config.check_naming_conventions and not re.match(r'^[A-Z][A-Z0-9_]*$', symbol):
            errors.append(AvroValidationError(path=f"{path}/symbols[{i}]", message=f"Symbol '{symbol}' should be SCREAMING_SNAKE_CASE", severity=ValidationSeverity.WARNING, rule="naming-convention"))
    if "default" in schema and schema["default"] not in symbols:
        errors.append(AvroValidationError(path=f"{path}/default", message=f"Default value '{schema['default']}' is not in symbols", severity=ValidationSeverity.ERROR, rule="valid-default"))
    return errors


def validate_field_block(
    path: str,
    field: Any,
    existing_names: set[str],
    config: AvroConfig,
    is_valid_name_fn: Callable[[str], bool],
    validate_type_fn: Callable[[str, Any], list[AvroValidationError]]
) -> list[AvroValidationError]:
    """Validate a record field."""
    errors: list[AvroValidationError] = []
    if not isinstance(field, dict):
        errors.append(AvroValidationError(path=path, message="Field must be an object", severity=ValidationSeverity.ERROR, rule="field-is-object"))
        return errors
    if "name" not in field:
        errors.append(AvroValidationError(path=path, message="Field requires 'name'", severity=ValidationSeverity.ERROR, rule="field-has-name"))
        return errors
    name = field["name"]
    if not is_valid_name_fn(name):
        errors.append(AvroValidationError(path=f"{path}/name", message=f"Invalid field name format: '{name}'", severity=ValidationSeverity.ERROR, rule="valid-field-name"))
    if name in existing_names:
        errors.append(AvroValidationError(path=f"{path}/name", message=f"Duplicate field name: '{name}'", severity=ValidationSeverity.ERROR, rule="unique-field-names"))
    existing_names.add(name)
    if "type" not in field:
        errors.append(AvroValidationError(path=path, message=f"Field '{name}' requires 'type'", severity=ValidationSeverity.ERROR, rule="field-has-type"))
        return errors
    errors.extend(validate_type_fn(f"{path}/type", field["type"]))
    if "order" in field:
        order = field["order"]
        if order not in {"ascending", "descending", "ignore"}:
            errors.append(AvroValidationError(path=f"{path}/order", message=f"Invalid order value: '{order}'. Must be one of {{'ascending', 'descending', 'ignore'}}", severity=ValidationSeverity.ERROR, rule="valid-order"))
    if config.require_doc and "doc" not in field:
        errors.append(AvroValidationError(path=path, message=f"Field '{name}' should have documentation", severity=ValidationSeverity.WARNING, rule="doc-recommended"))
    if config.require_default:
        type_def = field["type"]
        if isinstance(type_def, list) and "null" in type_def and "default" not in field:
            errors.append(AvroValidationError(path=path, message=f"Optional field '{name}' should have a default value", severity=ValidationSeverity.WARNING, rule="default-recommended"))
    if config.check_naming_conventions and not re.match(r'^[a-z][a-zA-Z0-9_]*$', name):
        errors.append(AvroValidationError(path=f"{path}/name", message=f"Field name '{name}' should be camelCase or snake_case", severity=ValidationSeverity.WARNING, rule="naming-convention"))
    return errors


def validate_record_block(
    path: str,
    schema: dict[str, Any],
    named_types: dict[str, dict[str, Any]],
    config: AvroConfig,
    is_valid_name_fn: Callable[[str], bool],
    validate_type_fn: Callable[[str, Any], list[AvroValidationError]]
) -> list[AvroValidationError]:
    """Validate a record type."""
    errors: list[AvroValidationError] = []
    if "name" not in schema:
        errors.append(AvroValidationError(path=path, message="Record type requires 'name' field", severity=ValidationSeverity.ERROR, rule="record-has-name"))
        return errors
    name = schema["name"]
    namespace = schema.get("namespace", "")
    if not is_valid_name_fn(name):
        errors.append(AvroValidationError(path=f"{path}/name", message=f"Invalid name format: '{name}'", severity=ValidationSeverity.ERROR, rule="valid-name"))
    named_types[f"{namespace}.{name}" if namespace else name] = schema
    if "fields" not in schema:
        errors.append(AvroValidationError(path=path, message="Record type requires 'fields' field", severity=ValidationSeverity.ERROR, rule="record-has-fields"))
        return errors
    fields = schema["fields"]
    if not isinstance(fields, list):
        errors.append(AvroValidationError(path=f"{path}/fields", message="Fields must be an array", severity=ValidationSeverity.ERROR, rule="fields-is-array"))
        return errors
    field_names: set[str] = set()
    for i, field in enumerate(fields):
        errors.extend(validate_field_block(f"{path}/fields[{i}]", field, field_names, config, is_valid_name_fn, validate_type_fn))
    if config.require_doc and "doc" not in schema:
        errors.append(AvroValidationError(path=path, message=f"Record '{name}' should have documentation", severity=ValidationSeverity.WARNING, rule="doc-recommended"))
    if config.check_naming_conventions and not re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
        errors.append(AvroValidationError(path=f"{path}/name", message=f"Record name '{name}' should be PascalCase", severity=ValidationSeverity.WARNING, rule="naming-convention"))
    return errors
