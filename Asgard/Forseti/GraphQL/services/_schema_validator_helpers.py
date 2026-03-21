"""
GraphQL Schema Validator Helpers.

Helper functions for SchemaValidatorService.
"""

import re
from typing import Any

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLValidationError,
    GraphQLValidationResult,
    ValidationSeverity,
)


def validate_structure(sdl: str) -> list[GraphQLValidationError]:
    """Validate the basic structure of the schema."""
    errors: list[GraphQLValidationError] = []

    if not re.search(r'\btype\s+Query\b', sdl):
        schema_match = re.search(r'\bschema\s*\{[^}]*query\s*:\s*(\w+)', sdl)
        if not schema_match:
            errors.append(GraphQLValidationError(
                message="Schema must define a Query type",
                severity=ValidationSeverity.ERROR,
                rule="query-type-required",
            ))

    open_braces = sdl.count("{")
    close_braces = sdl.count("}")
    if open_braces != close_braces:
        errors.append(GraphQLValidationError(
            message=f"Unbalanced braces: {open_braces} opening, {close_braces} closing",
            severity=ValidationSeverity.ERROR,
            rule="balanced-braces",
        ))

    string_pattern = r'"([^"\\]|\\.)*"'
    stripped = re.sub(string_pattern, '""', sdl)
    if '"' in stripped:
        errors.append(GraphQLValidationError(
            message="Unclosed string literal",
            severity=ValidationSeverity.ERROR,
            rule="closed-strings",
        ))

    return errors


def validate_types(
    sdl: str,
    builtin_scalars: set[str],
) -> list[GraphQLValidationError]:
    """Validate type definitions."""
    errors: list[GraphQLValidationError] = []

    type_defs = re.findall(
        r'(type|interface|enum|union|input|scalar)\s+(\w+)',
        sdl
    )
    defined_types = {name for _, name in type_defs}
    defined_types.update(builtin_scalars)

    field_types = re.findall(
        r':\s*\[?\s*(\w+)[\]!]*',
        sdl
    )

    for type_name in field_types:
        if type_name not in defined_types:
            errors.append(GraphQLValidationError(
                location=type_name,
                message=f"Reference to undefined type: {type_name}",
                severity=ValidationSeverity.ERROR,
                rule="defined-type",
            ))

    seen_types: set[str] = set()
    for _, type_name in type_defs:
        if type_name in seen_types:
            errors.append(GraphQLValidationError(
                location=type_name,
                message=f"Duplicate type definition: {type_name}",
                severity=ValidationSeverity.ERROR,
                rule="unique-type-names",
            ))
        seen_types.add(type_name)

    implements_pattern = r'type\s+(\w+)\s+implements\s+([^{]+)'
    for match in re.finditer(implements_pattern, sdl):
        type_name = match.group(1)
        interfaces = [i.strip() for i in match.group(2).split("&")]
        for interface in interfaces:
            interface = interface.strip()
            if interface and interface not in defined_types:
                errors.append(GraphQLValidationError(
                    location=type_name,
                    message=f"Type {type_name} implements undefined interface: {interface}",
                    severity=ValidationSeverity.ERROR,
                    rule="interface-exists",
                ))

    return errors


def validate_directives(
    sdl: str,
    builtin_directives: set[str],
    validate_deprecation: bool,
) -> list[GraphQLValidationError]:
    """Validate directive usage."""
    errors: list[GraphQLValidationError] = []

    directive_defs = re.findall(r'directive\s+@(\w+)', sdl)
    defined_directives = set(directive_defs) | builtin_directives

    directive_usages = re.findall(r'@(\w+)', sdl)

    for directive in directive_usages:
        if directive not in defined_directives:
            errors.append(GraphQLValidationError(
                location=f"@{directive}",
                message=f"Unknown directive: @{directive}",
                severity=ValidationSeverity.WARNING,
                rule="known-directive",
            ))

    if validate_deprecation:
        deprecated_usages = re.findall(
            r'(\w+).*@deprecated',
            sdl
        )
        for field_name in deprecated_usages:
            errors.append(GraphQLValidationError(
                location=field_name,
                message=f"Field '{field_name}' is marked as deprecated",
                severity=ValidationSeverity.INFO,
                rule="deprecated-field",
            ))

    return errors


def generate_text_report(result: GraphQLValidationResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("GraphQL Schema Validation Report")
    lines.append("=" * 60)
    lines.append(f"File: {result.schema_path or 'N/A'}")
    lines.append(f"Valid: {'Yes' if result.is_valid else 'No'}")
    lines.append(f"Types: {result.type_count}")
    lines.append(f"Fields: {result.field_count}")
    lines.append(f"Errors: {result.error_count}")
    lines.append(f"Warnings: {result.warning_count}")
    lines.append(f"Time: {result.validation_time_ms:.2f}ms")
    lines.append("-" * 60)

    if result.errors:
        lines.append("\nErrors:")
        for error in result.errors:
            loc = f"[{error.location}] " if error.location else ""
            lines.append(f"  {loc}{error.message}")

    if result.warnings:
        lines.append("\nWarnings:")
        for warning in result.warnings:
            loc = f"[{warning.location}] " if warning.location else ""
            lines.append(f"  {loc}{warning.message}")

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(result: GraphQLValidationResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# GraphQL Schema Validation Report\n")
    lines.append(f"- **File**: {result.schema_path or 'N/A'}")
    lines.append(f"- **Valid**: {'Yes' if result.is_valid else 'No'}")
    lines.append(f"- **Types**: {result.type_count}")
    lines.append(f"- **Fields**: {result.field_count}")
    lines.append(f"- **Errors**: {result.error_count}")
    lines.append(f"- **Warnings**: {result.warning_count}")
    lines.append(f"- **Time**: {result.validation_time_ms:.2f}ms\n")

    if result.errors:
        lines.append("## Errors\n")
        for error in result.errors:
            loc = f"**{error.location}**: " if error.location else ""
            lines.append(f"- {loc}{error.message}")

    if result.warnings:
        lines.append("\n## Warnings\n")
        for warning in result.warnings:
            loc = f"**{warning.location}**: " if warning.location else ""
            lines.append(f"- {loc}{warning.message}")

    return "\n".join(lines)
