"""
OpenAPI Base Models - Enums, config, and simple models.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenAPIVersion(str, Enum):
    """Supported OpenAPI specification versions."""
    V2_0 = "2.0"
    V3_0 = "3.0"
    V3_1 = "3.1"


class ValidationSeverity(str, Enum):
    """Severity levels for validation errors."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ParameterLocation(str, Enum):
    """Parameter location in OpenAPI specification."""
    QUERY = "query"
    HEADER = "header"
    PATH = "path"
    COOKIE = "cookie"


class SecuritySchemeType(str, Enum):
    """Security scheme types in OpenAPI specification."""
    API_KEY = "apiKey"
    HTTP = "http"
    OAUTH2 = "oauth2"
    OPENID_CONNECT = "openIdConnect"


class OpenAPIConfig(BaseModel):
    """Configuration for OpenAPI validation and processing."""

    strict_mode: bool = Field(
        default=False,
        description="Enable strict validation mode"
    )
    validate_examples: bool = Field(
        default=True,
        description="Validate examples against schemas"
    )
    validate_schemas: bool = Field(
        default=True,
        description="Validate schema definitions"
    )
    allow_deprecated: bool = Field(
        default=True,
        description="Allow deprecated operations"
    )
    target_version: Optional[OpenAPIVersion] = Field(
        default=None,
        description="Target OpenAPI version for conversion"
    )
    include_warnings: bool = Field(
        default=True,
        description="Include warnings in validation results"
    )
    max_errors: int = Field(
        default=100,
        description="Maximum number of errors to report"
    )

    class Config:
        use_enum_values = True


class OpenAPIValidationError(BaseModel):
    """Represents a single validation error or warning."""

    path: str = Field(
        description="JSON path to the error location"
    )
    message: str = Field(
        description="Human-readable error message"
    )
    severity: ValidationSeverity = Field(
        default=ValidationSeverity.ERROR,
        description="Severity level of the error"
    )
    rule: Optional[str] = Field(
        default=None,
        description="Validation rule that triggered the error"
    )
    context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional context about the error"
    )

    class Config:
        use_enum_values = True


class OpenAPIValidationResult(BaseModel):
    """Result of OpenAPI specification validation."""

    is_valid: bool = Field(
        description="Whether the specification is valid"
    )
    spec_path: Optional[str] = Field(
        default=None,
        description="Path to the validated specification file"
    )
    openapi_version: Optional[OpenAPIVersion] = Field(
        default=None,
        description="Detected OpenAPI version"
    )
    errors: list[OpenAPIValidationError] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    warnings: list[OpenAPIValidationError] = Field(
        default_factory=list,
        description="List of validation warnings"
    )
    info_messages: list[OpenAPIValidationError] = Field(
        default_factory=list,
        description="List of informational messages"
    )
    validated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of validation"
    )
    validation_time_ms: float = Field(
        default=0.0,
        description="Time taken to validate in milliseconds"
    )

    class Config:
        use_enum_values = True

    @property
    def error_count(self) -> int:
        """Return the number of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Return the number of warnings."""
        return len(self.warnings)

    @property
    def total_issues(self) -> int:
        """Return total number of issues (errors + warnings)."""
        return self.error_count + self.warning_count


class OpenAPIContact(BaseModel):
    """Contact information for the API."""

    name: Optional[str] = Field(default=None, description="Contact name")
    url: Optional[str] = Field(default=None, description="Contact URL")
    email: Optional[str] = Field(default=None, description="Contact email")


class OpenAPILicense(BaseModel):
    """License information for the API."""

    name: str = Field(description="License name")
    url: Optional[str] = Field(default=None, description="License URL")
    identifier: Optional[str] = Field(
        default=None,
        description="SPDX license identifier (OpenAPI 3.1)"
    )


class OpenAPIInfo(BaseModel):
    """API information object."""

    title: str = Field(description="API title")
    version: str = Field(description="API version")
    description: Optional[str] = Field(default=None, description="API description")
    terms_of_service: Optional[str] = Field(
        default=None,
        description="Terms of service URL"
    )
    contact: Optional[OpenAPIContact] = Field(
        default=None,
        description="Contact information"
    )
    license: Optional[OpenAPILicense] = Field(
        default=None,
        description="License information"
    )
    summary: Optional[str] = Field(
        default=None,
        description="Short summary (OpenAPI 3.1)"
    )


class OpenAPIServer(BaseModel):
    """Server object for API endpoints."""

    url: str = Field(description="Server URL")
    description: Optional[str] = Field(default=None, description="Server description")
    variables: Optional[dict[str, Any]] = Field(
        default=None,
        description="Server variables"
    )
