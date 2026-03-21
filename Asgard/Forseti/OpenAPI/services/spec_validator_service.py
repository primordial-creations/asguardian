"""
OpenAPI Specification Validator Service.

Validates OpenAPI specifications against the OpenAPI standard.
"""

import json
import time
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
from Asgard.Forseti.OpenAPI.services._spec_validator_helpers import (
    check_deprecated,
    generate_markdown_report,
    generate_text_report,
    validate_paths,
    validate_schemas,
    validate_structure,
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

        openapi_version = detect_openapi_version(spec_data)

        structure_errors = validate_structure(spec_data, openapi_version)
        errors.extend([e for e in structure_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in structure_errors if e.severity == ValidationSeverity.WARNING])
        info_messages.extend([e for e in structure_errors if e.severity == ValidationSeverity.INFO])

        path_errors = validate_paths(spec_data)
        errors.extend([e for e in path_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in path_errors if e.severity == ValidationSeverity.WARNING])

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

        openapi_version = detect_openapi_version(spec_data)

        structure_errors = validate_structure(spec_data, openapi_version)
        errors.extend([e for e in structure_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in structure_errors if e.severity == ValidationSeverity.WARNING])
        info_messages.extend([e for e in structure_errors if e.severity == ValidationSeverity.INFO])

        path_errors = validate_paths(spec_data)
        errors.extend([e for e in path_errors if e.severity == ValidationSeverity.ERROR])
        warnings.extend([e for e in path_errors if e.severity == ValidationSeverity.WARNING])

        if self.config.validate_schemas:
            schema_errors = validate_schemas(spec_data)
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
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
