"""
GraphQL Schema Validator Service.

Validates GraphQL schemas against the GraphQL specification.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLConfig,
    GraphQLValidationError,
    GraphQLValidationResult,
    ValidationSeverity,
)
from Asgard.Forseti.GraphQL.utilities.graphql_utils import load_schema_file, parse_sdl


class SchemaValidatorService:
    """
    Service for validating GraphQL schemas.

    Validates schemas against the GraphQL specification and reports
    errors and warnings.

    Usage:
        service = SchemaValidatorService()
        result = service.validate("schema.graphql")
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    # Built-in scalar types
    BUILTIN_SCALARS = {"String", "Int", "Float", "Boolean", "ID"}

    # Built-in directives
    BUILTIN_DIRECTIVES = {"skip", "include", "deprecated", "specifiedBy"}

    def __init__(self, config: Optional[GraphQLConfig] = None):
        """
        Initialize the validator service.

        Args:
            config: Optional configuration for validation behavior.
        """
        self.config = config or GraphQLConfig()

    def validate(self, schema_path: str | Path) -> GraphQLValidationResult:
        """
        Validate a GraphQL schema file.

        Args:
            schema_path: Path to the GraphQL schema file.

        Returns:
            GraphQLValidationResult with validation details.
        """
        start_time = time.time()
        schema_path = Path(schema_path)

        errors: list[GraphQLValidationError] = []
        warnings: list[GraphQLValidationError] = []

        # Check file exists
        if not schema_path.exists():
            errors.append(GraphQLValidationError(
                message=f"Schema file not found: {schema_path}",
                severity=ValidationSeverity.ERROR,
                rule="file-exists",
            ))
            return GraphQLValidationResult(
                is_valid=False,
                schema_path=str(schema_path),
                errors=errors,
                warnings=warnings,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        # Load schema
        try:
            sdl = load_schema_file(schema_path)
        except Exception as e:
            errors.append(GraphQLValidationError(
                message=f"Failed to read schema file: {str(e)}",
                severity=ValidationSeverity.ERROR,
                rule="valid-file",
            ))
            return GraphQLValidationResult(
                is_valid=False,
                schema_path=str(schema_path),
                errors=errors,
                warnings=warnings,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        return self.validate_sdl(sdl, str(schema_path))

    def validate_sdl(
        self,
        sdl: str,
        source_name: Optional[str] = None
    ) -> GraphQLValidationResult:
        """
        Validate a GraphQL SDL string.

        Args:
            sdl: GraphQL SDL source code.
            source_name: Optional source name for error messages.

        Returns:
            GraphQLValidationResult with validation details.
        """
        start_time = time.time()
        errors: list[GraphQLValidationError] = []
        warnings: list[GraphQLValidationError] = []

        # Parse SDL
        try:
            schema = parse_sdl(sdl)
        except Exception as e:
            errors.append(GraphQLValidationError(
                message=f"SDL parse error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                rule="valid-syntax",
            ))
            return GraphQLValidationResult(
                is_valid=False,
                schema_path=source_name,
                errors=errors,
                warnings=warnings,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        # Validate structure
        structure_errors = self._validate_structure(sdl)
        for error in structure_errors:
            if error.severity == ValidationSeverity.ERROR:
                errors.append(error)
            else:
                warnings.append(error)

        # Validate types
        type_errors = self._validate_types(sdl)
        for error in type_errors:
            if error.severity == ValidationSeverity.ERROR:
                errors.append(error)
            else:
                warnings.append(error)

        # Validate directives
        directive_errors = self._validate_directives(sdl)
        for error in directive_errors:
            if error.severity == ValidationSeverity.ERROR:
                errors.append(error)
            else:
                warnings.append(error)

        # Count types and fields
        type_count = len(re.findall(r'\btype\s+\w+', sdl))
        field_count = len(re.findall(r'^\s+\w+\s*[:(]', sdl, re.MULTILINE))

        validation_time_ms = (time.time() - start_time) * 1000

        return GraphQLValidationResult(
            is_valid=len(errors) == 0,
            schema_path=source_name,
            errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            type_count=type_count,
            field_count=field_count,
            validation_time_ms=validation_time_ms,
        )

    def _validate_structure(self, sdl: str) -> list[GraphQLValidationError]:
        """Validate the basic structure of the schema."""
        errors: list[GraphQLValidationError] = []

        # Check for Query type
        if not re.search(r'\btype\s+Query\b', sdl):
            # Check for schema definition with custom query type
            schema_match = re.search(r'\bschema\s*\{[^}]*query\s*:\s*(\w+)', sdl)
            if not schema_match:
                errors.append(GraphQLValidationError(
                    message="Schema must define a Query type",
                    severity=ValidationSeverity.ERROR,
                    rule="query-type-required",
                ))

        # Check for balanced braces
        open_braces = sdl.count("{")
        close_braces = sdl.count("}")
        if open_braces != close_braces:
            errors.append(GraphQLValidationError(
                message=f"Unbalanced braces: {open_braces} opening, {close_braces} closing",
                severity=ValidationSeverity.ERROR,
                rule="balanced-braces",
            ))

        # Check for unclosed strings
        string_pattern = r'"([^"\\]|\\.)*"'
        stripped = re.sub(string_pattern, '""', sdl)
        if '"' in stripped:
            errors.append(GraphQLValidationError(
                message="Unclosed string literal",
                severity=ValidationSeverity.ERROR,
                rule="closed-strings",
            ))

        return errors

    def _validate_types(self, sdl: str) -> list[GraphQLValidationError]:
        """Validate type definitions."""
        errors: list[GraphQLValidationError] = []

        # Extract all type definitions
        type_defs = re.findall(
            r'(type|interface|enum|union|input|scalar)\s+(\w+)',
            sdl
        )
        defined_types = {name for _, name in type_defs}
        defined_types.update(self.BUILTIN_SCALARS)

        # Extract type references in fields
        field_types = re.findall(
            r':\s*\[?\s*(\w+)[\]!]*',
            sdl
        )

        # Check for undefined types
        for type_name in field_types:
            if type_name not in defined_types:
                errors.append(GraphQLValidationError(
                    location=type_name,
                    message=f"Reference to undefined type: {type_name}",
                    severity=ValidationSeverity.ERROR,
                    rule="defined-type",
                ))

        # Check for duplicate type definitions
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

        # Check interface implementations
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

    def _validate_directives(self, sdl: str) -> list[GraphQLValidationError]:
        """Validate directive usage."""
        errors: list[GraphQLValidationError] = []

        # Extract custom directive definitions
        directive_defs = re.findall(r'directive\s+@(\w+)', sdl)
        defined_directives = set(directive_defs) | self.BUILTIN_DIRECTIVES

        # Find directive usages
        directive_usages = re.findall(r'@(\w+)', sdl)

        # Check for undefined directives
        for directive in directive_usages:
            if directive not in defined_directives:
                errors.append(GraphQLValidationError(
                    location=f"@{directive}",
                    message=f"Unknown directive: @{directive}",
                    severity=ValidationSeverity.WARNING,
                    rule="known-directive",
                ))

        # Check deprecated usage
        if self.config.validate_deprecation:
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

    def generate_report(
        self,
        result: GraphQLValidationResult,
        format: str = "text"
    ) -> str:
        """
        Generate a validation report.

        Args:
            result: Validation result to report.
            format: Output format (text, json, markdown).

        Returns:
            Formatted report string.
        """
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: GraphQLValidationResult) -> str:
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

    def _generate_markdown_report(self, result: GraphQLValidationResult) -> str:
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
