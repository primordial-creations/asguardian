"""
JSONSchema Base Models - Enums, config, and simple validation models.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SchemaType(str, Enum):
    """JSON Schema types."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


class SchemaFormat(str, Enum):
    """Common JSON Schema formats."""
    DATE_TIME = "date-time"
    DATE = "date"
    TIME = "time"
    EMAIL = "email"
    URI = "uri"
    UUID = "uuid"
    HOSTNAME = "hostname"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    REGEX = "regex"


class JSONSchemaConfig(BaseModel):
    """Configuration for JSON Schema operations."""

    strict_mode: bool = Field(
        default=True,
        description="Fail on additional properties when not explicitly allowed"
    )
    check_formats: bool = Field(
        default=True,
        description="Validate format constraints (email, uri, etc.)"
    )
    resolve_references: bool = Field(
        default=True,
        description="Resolve $ref references before validation"
    )
    include_descriptions: bool = Field(
        default=True,
        description="Include descriptions in generated schemas"
    )
    include_examples: bool = Field(
        default=False,
        description="Include examples in generated schemas"
    )
    include_defaults: bool = Field(
        default=True,
        description="Include default values in generated schemas"
    )
    infer_formats: bool = Field(
        default=True,
        description="Attempt to infer string formats (email, date, etc.)"
    )
    infer_enums: bool = Field(
        default=True,
        description="Infer enum values from repeated values"
    )
    enum_threshold: int = Field(
        default=10,
        description="Maximum unique values to consider as enum"
    )
    schema_version: str = Field(
        default="http://json-schema.org/draft-07/schema#",
        description="JSON Schema version to use"
    )


class JSONSchemaValidationError(BaseModel):
    """Represents a validation error."""

    path: str = Field(
        description="JSON path to the error location"
    )
    message: str = Field(
        description="Error message"
    )
    value: Optional[Any] = Field(
        default=None,
        description="Invalid value"
    )
    schema_path: Optional[str] = Field(
        default=None,
        description="Path in schema that failed"
    )
    constraint: Optional[str] = Field(
        default=None,
        description="Constraint that failed (e.g., 'type', 'required', 'pattern')"
    )
    expected: Optional[Any] = Field(
        default=None,
        description="Expected value or type"
    )


class JSONSchemaValidationResult(BaseModel):
    """Result of JSON Schema validation."""

    is_valid: bool = Field(
        description="Whether the data is valid"
    )
    errors: list[JSONSchemaValidationError] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    schema_path: Optional[str] = Field(
        default=None,
        description="Path to schema file if applicable"
    )
    data_path: Optional[str] = Field(
        default=None,
        description="Path to data file if applicable"
    )
    validation_time_ms: float = Field(
        default=0.0,
        description="Time taken for validation in milliseconds"
    )

    @property
    def error_count(self) -> int:
        """Get the number of errors."""
        return len(self.errors)
