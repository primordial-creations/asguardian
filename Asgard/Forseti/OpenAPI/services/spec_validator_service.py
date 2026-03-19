"""
OpenAPI Specification Validator Service.

Validates OpenAPI specifications against the OpenAPI standard.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIConfig,
    OpenAPIValidationError,
    OpenAPIValidationResult,
    OpenAPIVersion,
    ValidationSeverity,
)
from Asgard.Forseti.OpenAPI.utilities.openapi_utils import (
    load_spec_file,
    detect_openapi_version,
)


class SpecValidatorService:
    """
    Service for validating OpenAPI specifications.

    Validates specifications against OpenAPI standards and reports
    errors, warnings, and informational messages.

    Usage:
        service = SpecValidatorService()
        result = service.validate("openapi.yaml")
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    def __init__(self, config: Optional[OpenAPIConfig] = None):
        """
        Initialize the validator service.

        Args:
            config: Optional configuration for validation behavior.
        """
        self.config = config or OpenAPIConfig()

    def validate(self, spec_path: str | Path) -> OpenAPIValidationResult:
        """
        Validate an OpenAPI specification file.

        Args:
            spec_path: Path to the OpenAPI specification file.

        Returns:
            OpenAPIValidationResult with validation details.
        """
        start_time = time.time()
        spec_path = Path(spec_path)

        errors: list[OpenAPIValidationError] = []
        warnings: list[OpenAPIValidationError] = []
        info_messages: list[OpenAPIValidationError] = []

        # Check file exists
        if not spec_path.exists():
            errors.append(OpenAPIValidationError(
                path="",
                message=f"Specification file not found: {spec_path}",
                severity=ValidationSeverity.ERROR,
                rule="file-exists",
            ))
            return OpenAPIValidationResult(
                is_valid=False,
                spec_path=str(spec_path),
                errors=errors,
                warnings=warnings,
                info_messages=info_messages,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        # Load specification
        try:
            spec_data = load_spec_file(spec_path)
        except Exception as e:
            errors.append(OpenAPIValidationError(
                path="",
                message=f"Failed to parse specification: {str(e)}",
                severity=ValidationSeverity.ERROR,
                rule="valid-syntax",
            ))
            return OpenAPIValidationResult(
                is_valid=False,
                spec_path=str(spec_path),
                errors=errors,
                warnings=warnings,
                info_messages=info_messages,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        # Detect version
        openapi_version = detect_openapi_version(spec_data)

        # Validate structure
        structure_errors = self._validate_structure(spec_data, openapi_version)
        errors.extend([e for e in structure_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in structure_errors if e.severity == ValidationSeverity.WARNING])
        info_messages.extend([e for e in structure_errors if e.severity == ValidationSeverity.INFO])

        # Validate paths
        path_errors = self._validate_paths(spec_data)
        errors.extend([e for e in path_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in path_errors if e.severity == ValidationSeverity.WARNING])

        # Validate schemas if enabled
        if self.config.validate_schemas:
            schema_errors = self._validate_schemas(spec_data)
            errors.extend([e for e in schema_errors if e.severity == ValidationSeverity.ERROR])
            warnings.extend([e for e in schema_errors if e.severity == ValidationSeverity.WARNING])

        # Validate examples if enabled
        if self.config.validate_examples:
            example_errors = self._validate_examples(spec_data)
            warnings.extend(example_errors)

        # Check for deprecated operations
        if not self.config.allow_deprecated:
            deprecated_errors = self._check_deprecated(spec_data)
            errors.extend(deprecated_errors)

        # Limit errors if configured
        if self.config.max_errors > 0:
            errors = errors[:self.config.max_errors]

        validation_time_ms = (time.time() - start_time) * 1000

        return OpenAPIValidationResult(
            is_valid=len(errors) == 0,
            spec_path=str(spec_path),
            openapi_version=openapi_version,
            errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages,
            validation_time_ms=validation_time_ms,
        )

    def validate_spec_data(self, spec_data: dict[str, Any]) -> OpenAPIValidationResult:
        """
        Validate an OpenAPI specification from parsed data.

        Args:
            spec_data: Parsed OpenAPI specification as a dictionary.

        Returns:
            OpenAPIValidationResult with validation details.
        """
        start_time = time.time()

        errors: list[OpenAPIValidationError] = []
        warnings: list[OpenAPIValidationError] = []
        info_messages: list[OpenAPIValidationError] = []

        # Detect version
        openapi_version = detect_openapi_version(spec_data)

        # Validate structure
        structure_errors = self._validate_structure(spec_data, openapi_version)
        errors.extend([e for e in structure_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in structure_errors if e.severity == ValidationSeverity.WARNING])
        info_messages.extend([e for e in structure_errors if e.severity == ValidationSeverity.INFO])

        # Validate paths
        path_errors = self._validate_paths(spec_data)
        errors.extend([e for e in path_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in path_errors if e.severity == ValidationSeverity.WARNING])

        # Validate schemas
        if self.config.validate_schemas:
            schema_errors = self._validate_schemas(spec_data)
            errors.extend([e for e in schema_errors if e.severity == ValidationSeverity.ERROR])
            warnings.extend([e for e in schema_errors if e.severity == ValidationSeverity.WARNING])

        validation_time_ms = (time.time() - start_time) * 1000

        return OpenAPIValidationResult(
            is_valid=len(errors) == 0,
            openapi_version=openapi_version,
            errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages,
            validation_time_ms=validation_time_ms,
        )

    def _validate_structure(
        self,
        spec_data: dict[str, Any],
        version: Optional[OpenAPIVersion]
    ) -> list[OpenAPIValidationError]:
        """Validate the basic structure of the specification."""
        errors: list[OpenAPIValidationError] = []

        # Check for required fields
        if version in [OpenAPIVersion.V3_0, OpenAPIVersion.V3_1]:
            if "openapi" not in spec_data:
                errors.append(OpenAPIValidationError(
                    path="/",
                    message="Missing required field: openapi",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))
            if "info" not in spec_data:
                errors.append(OpenAPIValidationError(
                    path="/",
                    message="Missing required field: info",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))
            else:
                info = spec_data.get("info", {})
                if "title" not in info:
                    errors.append(OpenAPIValidationError(
                        path="/info",
                        message="Missing required field: info.title",
                        severity=ValidationSeverity.ERROR,
                        rule="required-field",
                    ))
                if "version" not in info:
                    errors.append(OpenAPIValidationError(
                        path="/info",
                        message="Missing required field: info.version",
                        severity=ValidationSeverity.ERROR,
                        rule="required-field",
                    ))

            # paths or webhooks required in 3.1, just paths in 3.0
            if "paths" not in spec_data:
                if version == OpenAPIVersion.V3_1:
                    if "webhooks" not in spec_data and "components" not in spec_data:
                        errors.append(OpenAPIValidationError(
                            path="/",
                            message="At least one of paths, webhooks, or components is required",
                            severity=ValidationSeverity.ERROR,
                            rule="required-field",
                        ))
                else:
                    errors.append(OpenAPIValidationError(
                        path="/",
                        message="Missing required field: paths",
                        severity=ValidationSeverity.ERROR,
                        rule="required-field",
                    ))

        elif version == OpenAPIVersion.V2_0:
            if "swagger" not in spec_data:
                errors.append(OpenAPIValidationError(
                    path="/",
                    message="Missing required field: swagger",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))
            if "info" not in spec_data:
                errors.append(OpenAPIValidationError(
                    path="/",
                    message="Missing required field: info",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))
            if "paths" not in spec_data:
                errors.append(OpenAPIValidationError(
                    path="/",
                    message="Missing required field: paths",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))

        return errors

    def _validate_paths(self, spec_data: dict[str, Any]) -> list[OpenAPIValidationError]:
        """Validate path definitions."""
        errors: list[OpenAPIValidationError] = []
        paths = spec_data.get("paths", {})
        http_methods = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                errors.append(OpenAPIValidationError(
                    path=f"/paths{path}",
                    message=f"Invalid path item type for {path}",
                    severity=ValidationSeverity.ERROR,
                    rule="valid-path-item",
                ))
                continue

            # Check path starts with /
            if not path.startswith("/"):
                errors.append(OpenAPIValidationError(
                    path=f"/paths/{path}",
                    message=f"Path must start with /: {path}",
                    severity=ValidationSeverity.ERROR,
                    rule="path-format",
                ))

            # Check path parameters are defined
            path_params = self._extract_path_parameters(path)
            for method in http_methods:
                operation = path_item.get(method)
                if operation:
                    op_errors = self._validate_operation(
                        path, method, operation, path_params
                    )
                    errors.extend(op_errors)

        return errors

    def _extract_path_parameters(self, path: str) -> set[str]:
        """Extract parameter names from path template."""
        return set(re.findall(r"\{([^}]+)\}", path))

    def _validate_operation(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
        path_params: set[str]
    ) -> list[OpenAPIValidationError]:
        """Validate a single operation."""
        errors: list[OpenAPIValidationError] = []
        base_path = f"/paths{path}/{method}"

        # Check responses exist
        if "responses" not in operation:
            errors.append(OpenAPIValidationError(
                path=base_path,
                message=f"Operation {method.upper()} {path} missing required field: responses",
                severity=ValidationSeverity.ERROR,
                rule="required-field",
            ))
        else:
            responses = operation.get("responses", {})
            if not responses:
                errors.append(OpenAPIValidationError(
                    path=f"{base_path}/responses",
                    message=f"Operation {method.upper()} {path} must define at least one response",
                    severity=ValidationSeverity.ERROR,
                    rule="non-empty-responses",
                ))

            # Check each response has a description
            for status_code, response in responses.items():
                if isinstance(response, dict) and "description" not in response:
                    errors.append(OpenAPIValidationError(
                        path=f"{base_path}/responses/{status_code}",
                        message=f"Response {status_code} missing required field: description",
                        severity=ValidationSeverity.ERROR,
                        rule="required-field",
                    ))

        # Check path parameters are defined in operation
        defined_path_params = set()
        for param in operation.get("parameters", []):
            if isinstance(param, dict) and param.get("in") == "path":
                defined_path_params.add(param.get("name"))

        missing_params = path_params - defined_path_params
        for param in missing_params:
            errors.append(OpenAPIValidationError(
                path=f"{base_path}/parameters",
                message=f"Path parameter '{param}' not defined in operation parameters",
                severity=ValidationSeverity.ERROR,
                rule="path-parameter-defined",
            ))

        return errors

    def _validate_schemas(self, spec_data: dict[str, Any]) -> list[OpenAPIValidationError]:
        """Validate schema definitions."""
        errors: list[OpenAPIValidationError] = []
        components = spec_data.get("components", {})
        schemas = components.get("schemas", {})

        for schema_name, schema in schemas.items():
            if not isinstance(schema, dict):
                errors.append(OpenAPIValidationError(
                    path=f"/components/schemas/{schema_name}",
                    message=f"Invalid schema type for {schema_name}",
                    severity=ValidationSeverity.ERROR,
                    rule="valid-schema",
                ))
                continue

            # Check for recursive references without base case
            if "$ref" in schema and schema.get("$ref", "").endswith(f"/{schema_name}"):
                errors.append(OpenAPIValidationError(
                    path=f"/components/schemas/{schema_name}",
                    message=f"Schema {schema_name} has direct self-reference",
                    severity=ValidationSeverity.WARNING,
                    rule="no-direct-self-reference",
                ))

        return errors

    def _validate_examples(self, spec_data: dict[str, Any]) -> list[OpenAPIValidationError]:
        """Validate examples against schemas."""
        warnings: list[OpenAPIValidationError] = []
        # Example validation would require JSON Schema validation
        # This is a placeholder for future implementation
        return warnings

    def _check_deprecated(self, spec_data: dict[str, Any]) -> list[OpenAPIValidationError]:
        """Check for deprecated operations."""
        errors: list[OpenAPIValidationError] = []
        paths = spec_data.get("paths", {})
        http_methods = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in http_methods:
                operation = path_item.get(method)
                if operation and operation.get("deprecated", False):
                    errors.append(OpenAPIValidationError(
                        path=f"/paths{path}/{method}",
                        message=f"Operation {method.upper()} {path} is deprecated",
                        severity=ValidationSeverity.ERROR,
                        rule="no-deprecated",
                    ))

        return errors

    def generate_report(
        self,
        result: OpenAPIValidationResult,
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

    def _generate_text_report(self, result: OpenAPIValidationResult) -> str:
        """Generate a text format report."""
        lines = []
        lines.append("=" * 60)
        lines.append("OpenAPI Validation Report")
        lines.append("=" * 60)
        lines.append(f"File: {result.spec_path or 'N/A'}")
        lines.append(f"Version: {result.openapi_version or 'Unknown'}")
        lines.append(f"Valid: {'Yes' if result.is_valid else 'No'}")
        lines.append(f"Errors: {result.error_count}")
        lines.append(f"Warnings: {result.warning_count}")
        lines.append(f"Time: {result.validation_time_ms:.2f}ms")
        lines.append("-" * 60)

        if result.errors:
            lines.append("\nErrors:")
            for error in result.errors:
                lines.append(f"  [{error.rule or 'error'}] {error.path}: {error.message}")

        if result.warnings:
            lines.append("\nWarnings:")
            for warning in result.warnings:
                lines.append(f"  [{warning.rule or 'warning'}] {warning.path}: {warning.message}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _generate_markdown_report(self, result: OpenAPIValidationResult) -> str:
        """Generate a markdown format report."""
        lines = []
        lines.append("# OpenAPI Validation Report\n")
        lines.append(f"- **File**: {result.spec_path or 'N/A'}")
        lines.append(f"- **Version**: {result.openapi_version or 'Unknown'}")
        lines.append(f"- **Valid**: {'Yes' if result.is_valid else 'No'}")
        lines.append(f"- **Errors**: {result.error_count}")
        lines.append(f"- **Warnings**: {result.warning_count}")
        lines.append(f"- **Time**: {result.validation_time_ms:.2f}ms\n")

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
