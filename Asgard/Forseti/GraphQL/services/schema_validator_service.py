"""
GraphQL Schema Validator Service.

Validates GraphQL schemas against the GraphQL specification.
"""

import json
import re
import time
from pathlib import Path
from typing import Optional

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLConfig,
    GraphQLValidationError,
    GraphQLValidationResult,
    ValidationSeverity,
)
from Asgard.Forseti.GraphQL.utilities.graphql_utils import load_schema_file, parse_sdl
from Asgard.Forseti.GraphQL.services._schema_validator_helpers import (
    generate_markdown_report,
    generate_text_report,
    validate_directives,
    validate_structure,
    validate_types,
)


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

    BUILTIN_SCALARS = {"String", "Int", "Float", "Boolean", "ID"}
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

        try:
            parse_sdl(sdl)
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

        for error in validate_structure(sdl):
            if error.severity == ValidationSeverity.ERROR:
                errors.append(error)
            else:
                warnings.append(error)

        for error in validate_types(sdl, self.BUILTIN_SCALARS):
            if error.severity == ValidationSeverity.ERROR:
                errors.append(error)
            else:
                warnings.append(error)

        for error in validate_directives(sdl, self.BUILTIN_DIRECTIVES, self.config.validate_deprecation):
            if error.severity == ValidationSeverity.ERROR:
                errors.append(error)
            else:
                warnings.append(error)

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
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
