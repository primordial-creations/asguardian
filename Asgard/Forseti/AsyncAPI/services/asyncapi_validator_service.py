"""
AsyncAPI Specification Validator Service.

Validates AsyncAPI specifications against the AsyncAPI standard.
"""

import json
import re
import time
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
from Asgard.Forseti.AsyncAPI.services._asyncapi_validator_helpers import (
    check_deprecated,
    generate_markdown_report,
    generate_text_report,
    validate_channels,
    validate_schemas,
    validate_servers,
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
        """Validate an AsyncAPI specification file."""
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

        return self._run_validation(spec_data, str(spec_path), start_time, errors, warnings, info_messages)

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

        return self._run_validation(spec_data, None, start_time, errors, warnings, info_messages)

    def _run_validation(
        self,
        spec_data: dict[str, Any],
        spec_path: Optional[str],
        start_time: float,
        errors: list[AsyncAPIValidationError],
        warnings: list[AsyncAPIValidationError],
        info_messages: list[AsyncAPIValidationError],
    ) -> AsyncAPIValidationResult:
        """Run all validation checks and return a result."""
        asyncapi_version = self._detect_asyncapi_version(spec_data)

        structure_errors = self._validate_structure(spec_data, asyncapi_version)
        errors.extend([e for e in structure_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in structure_errors if e.severity == ValidationSeverity.WARNING])
        info_messages.extend([e for e in structure_errors if e.severity == ValidationSeverity.INFO])

        channel_errors = validate_channels(spec_data)
        errors.extend([e for e in channel_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in channel_errors if e.severity == ValidationSeverity.WARNING])

        server_errors = validate_servers(spec_data)
        errors.extend([e for e in server_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in server_errors if e.severity == ValidationSeverity.WARNING])

        if self.config.validate_schemas:
            schema_errors = validate_schemas(spec_data)
            errors.extend([e for e in schema_errors if e.severity == ValidationSeverity.ERROR])
            warnings.extend([e for e in schema_errors if e.severity == ValidationSeverity.WARNING])

        if self.config.validate_examples:
            pass

        if not self.config.allow_deprecated:
            errors.extend(check_deprecated(spec_data))

        if self.config.max_errors > 0:
            errors = errors[:self.config.max_errors]

        validation_time_ms = (time.time() - start_time) * 1000

        return AsyncAPIValidationResult(
            is_valid=len(errors) == 0,
            spec_path=spec_path,
            asyncapi_version=asyncapi_version,
            errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages,
            validation_time_ms=validation_time_ms,
        )

    def _load_spec_file(self, spec_path: Path) -> dict[str, Any]:
        """Load a specification file (YAML or JSON)."""
        content = spec_path.read_text(encoding="utf-8")

        try:
            return cast(dict[str, Any], yaml.safe_load(content))
        except yaml.YAMLError:
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

        if version and version != AsyncAPIVersion.V3_0:
            if "channels" not in spec_data:
                errors.append(AsyncAPIValidationError(
                    path="/",
                    message="Missing required field: channels",
                    severity=ValidationSeverity.ERROR,
                    rule="required-field",
                ))

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
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
