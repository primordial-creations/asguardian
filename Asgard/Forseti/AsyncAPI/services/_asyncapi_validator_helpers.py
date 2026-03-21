"""
AsyncAPI Validator Helpers.

Validation helper functions for AsyncAPIValidatorService.
"""

import re
from typing import Any

from Asgard.Forseti.AsyncAPI.models.asyncapi_models import (
    AsyncAPIValidationError,
    AsyncAPIValidationResult,
    ValidationSeverity,
)


def generate_text_report(result: AsyncAPIValidationResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("AsyncAPI Validation Report")
    lines.append("=" * 60)
    lines.append(f"File: {result.spec_path or 'N/A'}")
    lines.append(f"Version: {result.asyncapi_version or 'Unknown'}")
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


def generate_markdown_report(result: AsyncAPIValidationResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# AsyncAPI Validation Report\n")
    lines.append(f"- **File**: {result.spec_path or 'N/A'}")
    lines.append(f"- **Version**: {result.asyncapi_version or 'Unknown'}")
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


def validate_message(base_path: str, message: dict[str, Any]) -> list[AsyncAPIValidationError]:
    """Validate a message definition."""
    errors: list[AsyncAPIValidationError] = []

    if not isinstance(message, dict):
        return errors

    if "$ref" in message:
        return errors

    if "payload" in message:
        payload = message["payload"]
        if isinstance(payload, dict) and "$ref" not in payload:
            if "type" not in payload and "oneOf" not in payload and "anyOf" not in payload:
                errors.append(AsyncAPIValidationError(
                    path=f"{base_path}/message/payload",
                    message="Payload schema should have a type",
                    severity=ValidationSeverity.INFO,
                    rule="payload-has-type",
                ))

    return errors


def validate_operation(
    channel_name: str,
    op_type: str,
    operation: dict[str, Any],
) -> list[AsyncAPIValidationError]:
    """Validate a single operation."""
    errors: list[AsyncAPIValidationError] = []
    base_path = f"/channels/{channel_name}/{op_type}"

    if not isinstance(operation, dict):
        errors.append(AsyncAPIValidationError(
            path=base_path,
            message=f"Invalid operation type for {op_type}",
            severity=ValidationSeverity.ERROR,
            rule="valid-operation",
        ))
        return errors

    if "message" not in operation:
        errors.append(AsyncAPIValidationError(
            path=base_path,
            message=f"Operation {op_type} on channel {channel_name} should have a message",
            severity=ValidationSeverity.WARNING,
            rule="operation-has-message",
        ))
    else:
        message = operation["message"]
        if isinstance(message, dict):
            errors.extend(validate_message(base_path, message))
        elif isinstance(message, list):
            for i, msg in enumerate(message):
                errors.extend(validate_message(f"{base_path}/message/{i}", msg))

    if "operationId" not in operation:
        errors.append(AsyncAPIValidationError(
            path=base_path,
            message=f"Operation on channel {channel_name} should have an operationId",
            severity=ValidationSeverity.INFO,
            rule="operation-id-recommended",
        ))

    return errors


def validate_channels(spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
    """Validate channel definitions."""
    errors: list[AsyncAPIValidationError] = []
    channels = spec_data.get("channels", {})

    for channel_name, channel_data in channels.items():
        if not isinstance(channel_data, dict):
            errors.append(AsyncAPIValidationError(
                path=f"/channels/{channel_name}",
                message=f"Invalid channel type for {channel_name}",
                severity=ValidationSeverity.ERROR,
                rule="valid-channel",
            ))
            continue

        has_subscribe = "subscribe" in channel_data
        has_publish = "publish" in channel_data

        if not has_subscribe and not has_publish:
            errors.append(AsyncAPIValidationError(
                path=f"/channels/{channel_name}",
                message=f"Channel {channel_name} must have at least one operation (subscribe or publish)",
                severity=ValidationSeverity.WARNING,
                rule="channel-has-operation",
            ))

        for op_type in ["subscribe", "publish"]:
            if op_type in channel_data:
                errors.extend(validate_operation(channel_name, op_type, channel_data[op_type]))

        channel_params = set(re.findall(r"\{([^}]+)\}", channel_name))
        defined_params = set(channel_data.get("parameters", {}).keys())
        missing_params = channel_params - defined_params

        for param in missing_params:
            errors.append(AsyncAPIValidationError(
                path=f"/channels/{channel_name}/parameters",
                message=f"Channel parameter '{param}' not defined",
                severity=ValidationSeverity.ERROR,
                rule="parameter-defined",
            ))

    return errors


def validate_servers(spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
    """Validate server definitions."""
    errors: list[AsyncAPIValidationError] = []
    servers = spec_data.get("servers", {})

    for server_name, server_data in servers.items():
        if not isinstance(server_data, dict):
            errors.append(AsyncAPIValidationError(
                path=f"/servers/{server_name}",
                message=f"Invalid server type for {server_name}",
                severity=ValidationSeverity.ERROR,
                rule="valid-server",
            ))
            continue

        if "url" not in server_data:
            errors.append(AsyncAPIValidationError(
                path=f"/servers/{server_name}",
                message=f"Server {server_name} missing required field: url",
                severity=ValidationSeverity.ERROR,
                rule="required-field",
            ))

        if "protocol" not in server_data:
            errors.append(AsyncAPIValidationError(
                path=f"/servers/{server_name}",
                message=f"Server {server_name} missing required field: protocol",
                severity=ValidationSeverity.ERROR,
                rule="required-field",
            ))

        url = server_data.get("url", "")
        if url and "{" not in url:
            if not re.match(r"^[\w\-\.]+(:[\d]+)?(/.*)?$", url.replace("://", "")):
                errors.append(AsyncAPIValidationError(
                    path=f"/servers/{server_name}/url",
                    message=f"Server URL may be malformed: {url}",
                    severity=ValidationSeverity.WARNING,
                    rule="valid-url",
                ))

    return errors


def validate_schemas(spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
    """Validate schema definitions."""
    errors: list[AsyncAPIValidationError] = []
    components = spec_data.get("components", {})
    schemas = components.get("schemas", {})

    for schema_name, schema in schemas.items():
        if not isinstance(schema, dict):
            errors.append(AsyncAPIValidationError(
                path=f"/components/schemas/{schema_name}",
                message=f"Invalid schema type for {schema_name}",
                severity=ValidationSeverity.ERROR,
                rule="valid-schema",
            ))
            continue

        if "$ref" in schema and schema.get("$ref", "").endswith(f"/{schema_name}"):
            errors.append(AsyncAPIValidationError(
                path=f"/components/schemas/{schema_name}",
                message=f"Schema {schema_name} has direct self-reference",
                severity=ValidationSeverity.WARNING,
                rule="no-direct-self-reference",
            ))

    return errors


def check_deprecated(spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
    """Check for deprecated channels and operations."""
    errors: list[AsyncAPIValidationError] = []
    channels = spec_data.get("channels", {})

    for channel_name, channel_data in channels.items():
        if not isinstance(channel_data, dict):
            continue

        if channel_data.get("deprecated", False):
            errors.append(AsyncAPIValidationError(
                path=f"/channels/{channel_name}",
                message=f"Channel {channel_name} is deprecated",
                severity=ValidationSeverity.ERROR,
                rule="no-deprecated",
            ))

        for op_type in ["subscribe", "publish"]:
            operation = channel_data.get(op_type)
            if operation and isinstance(operation, dict) and operation.get("deprecated", False):
                errors.append(AsyncAPIValidationError(
                    path=f"/channels/{channel_name}/{op_type}",
                    message=f"Operation {op_type} on channel {channel_name} is deprecated",
                    severity=ValidationSeverity.ERROR,
                    rule="no-deprecated",
                ))

    return errors
