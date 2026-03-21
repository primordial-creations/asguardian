"""
OpenAPI Spec Validator Helpers.

Helper functions for SpecValidatorService.
"""

import re
from typing import Any

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIValidationError,
    OpenAPIValidationResult,
    OpenAPIVersion,
    ValidationSeverity,
)


def validate_structure(
    spec_data: dict[str, Any],
    version: OpenAPIVersion | None,
) -> list[OpenAPIValidationError]:
    """Validate the basic structure of the specification."""
    errors: list[OpenAPIValidationError] = []

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


def extract_path_parameters(path: str) -> set[str]:
    """Extract parameter names from path template."""
    return set(re.findall(r"\{([^}]+)\}", path))


def validate_operation(
    path: str,
    method: str,
    operation: dict[str, Any],
    path_params: set[str],
) -> list[OpenAPIValidationError]:
    """Validate a single operation."""
    errors: list[OpenAPIValidationError] = []
    base_path = f"/paths{path}/{method}"

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

        for status_code, response in responses.items():
            if isinstance(response, dict) and "description" not in response:
                errors.append(OpenAPIValidationError(
                    path=f"{base_path}/responses/{status_code}",
                    message=f"Response {status_code} missing required field: description",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))

    defined_path_params: set[str] = set()
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


def validate_paths(spec_data: dict[str, Any]) -> list[OpenAPIValidationError]:
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

        if not path.startswith("/"):
            errors.append(OpenAPIValidationError(
                path=f"/paths/{path}",
                message=f"Path must start with /: {path}",
                severity=ValidationSeverity.ERROR,
                rule="path-format",
            ))

        path_params = extract_path_parameters(path)
        for method in http_methods:
            operation = path_item.get(method)
            if operation:
                errors.extend(validate_operation(path, method, operation, path_params))

    return errors


def validate_schemas(spec_data: dict[str, Any]) -> list[OpenAPIValidationError]:
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

        if "$ref" in schema and schema.get("$ref", "").endswith(f"/{schema_name}"):
            errors.append(OpenAPIValidationError(
                path=f"/components/schemas/{schema_name}",
                message=f"Schema {schema_name} has direct self-reference",
                severity=ValidationSeverity.WARNING,
                rule="no-direct-self-reference",
            ))

    return errors


def check_deprecated(spec_data: dict[str, Any]) -> list[OpenAPIValidationError]:
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


def generate_text_report(result: OpenAPIValidationResult) -> str:
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


def generate_markdown_report(result: OpenAPIValidationResult) -> str:
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
