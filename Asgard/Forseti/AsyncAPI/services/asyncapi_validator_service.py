"""
AsyncAPI Specification Validator Service.

Validates AsyncAPI specifications against the AsyncAPI standard.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.AsyncAPI.models.asyncapi_models import (
    AsyncAPIConfig,
    AsyncAPIValidationError,
    AsyncAPIValidationResult,
    AsyncAPIVersion,
    ValidationSeverity,
)


class AsyncAPIValidatorService:
    """
    Service for validating AsyncAPI specifications.

    Validates specifications against AsyncAPI standards and reports
    errors, warnings, and informational messages.

    Usage:
        service = AsyncAPIValidatorService()
        result = service.validate("asyncapi.yaml")
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    def __init__(self, config: Optional[AsyncAPIConfig] = None):
        """
        Initialize the validator service.

        Args:
            config: Optional configuration for validation behavior.
        """
        self.config = config or AsyncAPIConfig()

    def validate(self, spec_path: str | Path) -> AsyncAPIValidationResult:
        """
        Validate an AsyncAPI specification file.

        Args:
            spec_path: Path to the AsyncAPI specification file.

        Returns:
            AsyncAPIValidationResult with validation details.
        """
        return self.validate_file(spec_path)

    def validate_file(self, spec_path: str | Path) -> AsyncAPIValidationResult:
        """
        Validate an AsyncAPI specification file.

        Args:
            spec_path: Path to the AsyncAPI specification file.

        Returns:
            AsyncAPIValidationResult with validation details.
        """
        start_time = time.time()
        spec_path = Path(spec_path)

        errors: list[AsyncAPIValidationError] = []
        warnings: list[AsyncAPIValidationError] = []
        info_messages: list[AsyncAPIValidationError] = []

        # Check file exists
        if not spec_path.exists():
            errors.append(AsyncAPIValidationError(
                path="",
                message=f"Specification file not found: {spec_path}",
                severity=ValidationSeverity.ERROR,
                rule="file-exists",
            ))
            return AsyncAPIValidationResult(
                is_valid=False,
                spec_path=str(spec_path),
                errors=errors,
                warnings=warnings,
                info_messages=info_messages,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        # Load specification
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(AsyncAPIValidationError(
                path="",
                message=f"Failed to parse specification: {str(e)}",
                severity=ValidationSeverity.ERROR,
                rule="valid-syntax",
            ))
            return AsyncAPIValidationResult(
                is_valid=False,
                spec_path=str(spec_path),
                errors=errors,
                warnings=warnings,
                info_messages=info_messages,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        # Detect version
        asyncapi_version = self._detect_asyncapi_version(spec_data)

        # Validate structure
        structure_errors = self._validate_structure(spec_data, asyncapi_version)
        errors.extend([e for e in structure_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in structure_errors if e.severity == ValidationSeverity.WARNING])
        info_messages.extend([e for e in structure_errors if e.severity == ValidationSeverity.INFO])

        # Validate channels
        channel_errors = self._validate_channels(spec_data)
        errors.extend([e for e in channel_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in channel_errors if e.severity == ValidationSeverity.WARNING])

        # Validate servers
        server_errors = self._validate_servers(spec_data)
        errors.extend([e for e in server_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in server_errors if e.severity == ValidationSeverity.WARNING])

        # Validate schemas if enabled
        if self.config.validate_schemas:
            schema_errors = self._validate_schemas(spec_data)
            errors.extend([e for e in schema_errors if e.severity == ValidationSeverity.ERROR])
            warnings.extend([e for e in schema_errors if e.severity == ValidationSeverity.WARNING])

        # Validate examples if enabled
        if self.config.validate_examples:
            example_errors = self._validate_examples(spec_data)
            warnings.extend(example_errors)

        # Check for deprecated channels
        if not self.config.allow_deprecated:
            deprecated_errors = self._check_deprecated(spec_data)
            errors.extend(deprecated_errors)

        # Limit errors if configured
        if self.config.max_errors > 0:
            errors = errors[:self.config.max_errors]

        validation_time_ms = (time.time() - start_time) * 1000

        return AsyncAPIValidationResult(
            is_valid=len(errors) == 0,
            spec_path=str(spec_path),
            asyncapi_version=asyncapi_version,
            errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages,
            validation_time_ms=validation_time_ms,
        )

    def validate_spec_data(self, spec_data: dict[str, Any]) -> AsyncAPIValidationResult:
        """
        Validate an AsyncAPI specification from parsed data.

        Args:
            spec_data: Parsed AsyncAPI specification as a dictionary.

        Returns:
            AsyncAPIValidationResult with validation details.
        """
        start_time = time.time()

        errors: list[AsyncAPIValidationError] = []
        warnings: list[AsyncAPIValidationError] = []
        info_messages: list[AsyncAPIValidationError] = []

        # Detect version
        asyncapi_version = self._detect_asyncapi_version(spec_data)

        # Validate structure
        structure_errors = self._validate_structure(spec_data, asyncapi_version)
        errors.extend([e for e in structure_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in structure_errors if e.severity == ValidationSeverity.WARNING])
        info_messages.extend([e for e in structure_errors if e.severity == ValidationSeverity.INFO])

        # Validate channels
        channel_errors = self._validate_channels(spec_data)
        errors.extend([e for e in channel_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in channel_errors if e.severity == ValidationSeverity.WARNING])

        # Validate servers
        server_errors = self._validate_servers(spec_data)
        errors.extend([e for e in server_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in server_errors if e.severity == ValidationSeverity.WARNING])

        # Validate schemas
        if self.config.validate_schemas:
            schema_errors = self._validate_schemas(spec_data)
            errors.extend([e for e in schema_errors if e.severity == ValidationSeverity.ERROR])
            warnings.extend([e for e in schema_errors if e.severity == ValidationSeverity.WARNING])

        validation_time_ms = (time.time() - start_time) * 1000

        return AsyncAPIValidationResult(
            is_valid=len(errors) == 0,
            asyncapi_version=asyncapi_version,
            errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages,
            validation_time_ms=validation_time_ms,
        )

    def _load_spec_file(self, spec_path: Path) -> dict[str, Any]:
        """Load a specification file (YAML or JSON)."""
        content = spec_path.read_text(encoding="utf-8")

        # Try YAML first (handles JSON too)
        try:
            return cast(dict[str, Any], yaml.safe_load(content))
        except yaml.YAMLError:
            # Try JSON
            return cast(dict[str, Any], json.loads(content))

    def _detect_asyncapi_version(self, spec_data: dict[str, Any]) -> Optional[AsyncAPIVersion]:
        """Detect the AsyncAPI version from the specification."""
        version_str = spec_data.get("asyncapi", "")

        if version_str.startswith("3."):
            return AsyncAPIVersion.V3_0
        elif version_str.startswith("2.6"):
            return AsyncAPIVersion.V2_6
        elif version_str.startswith("2.5"):
            return AsyncAPIVersion.V2_5
        elif version_str.startswith("2.4"):
            return AsyncAPIVersion.V2_4
        elif version_str.startswith("2.3"):
            return AsyncAPIVersion.V2_3
        elif version_str.startswith("2.2"):
            return AsyncAPIVersion.V2_2
        elif version_str.startswith("2.1"):
            return AsyncAPIVersion.V2_1
        elif version_str.startswith("2.0"):
            return AsyncAPIVersion.V2_0

        return None

    def _validate_structure(
        self,
        spec_data: dict[str, Any],
        version: Optional[AsyncAPIVersion]
    ) -> list[AsyncAPIValidationError]:
        """Validate the basic structure of the specification."""
        errors: list[AsyncAPIValidationError] = []

        # Check for required fields
        if "asyncapi" not in spec_data:
            errors.append(AsyncAPIValidationError(
                path="/",
                message="Missing required field: asyncapi",
                severity=ValidationSeverity.ERROR,
                rule="required-field",
            ))

        if "info" not in spec_data:
            errors.append(AsyncAPIValidationError(
                path="/",
                message="Missing required field: info",
                severity=ValidationSeverity.ERROR,
                rule="required-field",
            ))
        else:
            info = spec_data.get("info", {})
            if "title" not in info:
                errors.append(AsyncAPIValidationError(
                    path="/info",
                    message="Missing required field: info.title",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))
            if "version" not in info:
                errors.append(AsyncAPIValidationError(
                    path="/info",
                    message="Missing required field: info.version",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))

        # channels required in 2.x, optional in 3.x
        if version and version != AsyncAPIVersion.V3_0:
            if "channels" not in spec_data:
                errors.append(AsyncAPIValidationError(
                    path="/",
                    message="Missing required field: channels",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))

        # Validate AsyncAPI version string format
        asyncapi_version = spec_data.get("asyncapi", "")
        version_pattern = r"^\d+\.\d+\.\d+$"
        if asyncapi_version and not re.match(version_pattern, asyncapi_version):
            errors.append(AsyncAPIValidationError(
                path="/asyncapi",
                message=f"Invalid AsyncAPI version format: {asyncapi_version}. Expected semver format (e.g., 2.6.0)",
                severity=ValidationSeverity.WARNING,
                rule="version-format",
            ))

        return errors

    def _validate_channels(self, spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
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

            # Check for at least one operation
            has_subscribe = "subscribe" in channel_data
            has_publish = "publish" in channel_data

            if not has_subscribe and not has_publish:
                errors.append(AsyncAPIValidationError(
                    path=f"/channels/{channel_name}",
                    message=f"Channel {channel_name} must have at least one operation (subscribe or publish)",
                    severity=ValidationSeverity.WARNING,
                    rule="channel-has-operation",
                ))

            # Validate operations
            for op_type in ["subscribe", "publish"]:
                if op_type in channel_data:
                    op_errors = self._validate_operation(
                        channel_name, op_type, channel_data[op_type]
                    )
                    errors.extend(op_errors)

            # Validate channel parameters
            channel_params = self._extract_channel_parameters(channel_name)
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

    def _extract_channel_parameters(self, channel_name: str) -> set[str]:
        """Extract parameter names from channel name."""
        return set(re.findall(r"\{([^}]+)\}", channel_name))

    def _validate_operation(
        self,
        channel_name: str,
        op_type: str,
        operation: dict[str, Any]
    ) -> list[AsyncAPIValidationError]:
        """Validate a single operation."""
        errors: list[AsyncAPIValidationError] = []
        base_path = f"/channels/{channel_name}/{op_type}"

        # Validate operation structure
        if not isinstance(operation, dict):
            errors.append(AsyncAPIValidationError(
                path=base_path,
                message=f"Invalid operation type for {op_type}",
                severity=ValidationSeverity.ERROR,
                rule="valid-operation",
            ))
            return errors

        # Check for message
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
                msg_errors = self._validate_message(base_path, message)
                errors.extend(msg_errors)
            elif isinstance(message, list):
                for i, msg in enumerate(message):
                    msg_errors = self._validate_message(f"{base_path}/message/{i}", msg)
                    errors.extend(msg_errors)

        # Check operationId uniqueness recommendation
        if "operationId" not in operation:
            errors.append(AsyncAPIValidationError(
                path=base_path,
                message=f"Operation on channel {channel_name} should have an operationId",
                severity=ValidationSeverity.INFO,
                rule="operation-id-recommended",
            ))

        return errors

    def _validate_message(
        self,
        base_path: str,
        message: dict[str, Any]
    ) -> list[AsyncAPIValidationError]:
        """Validate a message definition."""
        errors: list[AsyncAPIValidationError] = []

        if not isinstance(message, dict):
            return errors

        # Check if it's a reference
        if "$ref" in message:
            return errors  # References are validated elsewhere

        # Validate payload if present
        if "payload" in message:
            payload = message["payload"]
            if isinstance(payload, dict) and "$ref" not in payload:
                # Basic JSON Schema validation
                if "type" not in payload and "oneOf" not in payload and "anyOf" not in payload:
                    errors.append(AsyncAPIValidationError(
                        path=f"{base_path}/message/payload",
                        message="Payload schema should have a type",
                        severity=ValidationSeverity.INFO,
                        rule="payload-has-type",
                    ))

        return errors

    def _validate_servers(self, spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
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

            # Check required fields
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

            # Validate URL format
            url = server_data.get("url", "")
            if url and "{" not in url:
                # Check for valid URL structure (basic check)
                if not re.match(r"^[\w\-\.]+(:[\d]+)?(/.*)?$", url.replace("://", "")):
                    errors.append(AsyncAPIValidationError(
                        path=f"/servers/{server_name}/url",
                        message=f"Server URL may be malformed: {url}",
                        severity=ValidationSeverity.WARNING,
                        rule="valid-url",
                    ))

        return errors

    def _validate_schemas(self, spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
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

            # Check for recursive references without base case
            if "$ref" in schema and schema.get("$ref", "").endswith(f"/{schema_name}"):
                errors.append(AsyncAPIValidationError(
                    path=f"/components/schemas/{schema_name}",
                    message=f"Schema {schema_name} has direct self-reference",
                    severity=ValidationSeverity.WARNING,
                    rule="no-direct-self-reference",
                ))

        return errors

    def _validate_examples(self, spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
        """Validate examples against schemas."""
        warnings: list[AsyncAPIValidationError] = []
        # Example validation would require JSON Schema validation
        # This is a placeholder for future implementation
        return warnings

    def _check_deprecated(self, spec_data: dict[str, Any]) -> list[AsyncAPIValidationError]:
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

    def generate_report(
        self,
        result: AsyncAPIValidationResult,
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

    def _generate_text_report(self, result: AsyncAPIValidationResult) -> str:
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

    def _generate_markdown_report(self, result: AsyncAPIValidationResult) -> str:
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
