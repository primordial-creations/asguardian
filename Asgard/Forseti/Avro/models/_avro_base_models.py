"""
Avro Base Models - Enums, configs, and simple field/error models.
"""

from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field


class AvroSchemaType(str, Enum):
    """Avro primitive and complex types."""
    # Primitive types
    NULL = "null"
    BOOLEAN = "boolean"
    INT = "int"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    BYTES = "bytes"
    STRING = "string"
    # Complex types
    RECORD = "record"
    ENUM = "enum"
    ARRAY = "array"
    MAP = "map"
    UNION = "union"
    FIXED = "fixed"


class ValidationSeverity(str, Enum):
    """Severity levels for validation errors."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class BreakingChangeType(str, Enum):
    """Types of breaking changes in Avro schemas."""
    REMOVED_FIELD = "removed_field"
    REMOVED_TYPE = "removed_type"
    REMOVED_ENUM_SYMBOL = "removed_enum_symbol"
    CHANGED_FIELD_TYPE = "changed_field_type"
    CHANGED_FIELD_DEFAULT = "changed_field_default"
    ADDED_REQUIRED_FIELD = "added_required_field"
    CHANGED_NAMESPACE = "changed_namespace"
    CHANGED_NAME = "changed_name"
    CHANGED_SIZE = "changed_size"
    CHANGED_ENUM_ORDER = "changed_enum_order"
    INCOMPATIBLE_UNION = "incompatible_union"


class CompatibilityLevel(str, Enum):
    """Compatibility level between schema versions."""
    FULL = "full"
    BACKWARD = "backward"
    FORWARD = "forward"
    NONE = "none"


class CompatibilityMode(str, Enum):
    """Compatibility checking mode."""
    BACKWARD = "backward"  # New schema can read old data
    FORWARD = "forward"    # Old schema can read new data
    FULL = "full"          # Both directions compatible
    NONE = "none"          # No compatibility guarantee


class AvroConfig(BaseModel):
    """Configuration for Avro validation and processing."""

    strict_mode: bool = Field(
        default=False,
        description="Enable strict validation mode"
    )
    check_naming_conventions: bool = Field(
        default=True,
        description="Check naming convention best practices"
    )
    require_doc: bool = Field(
        default=False,
        description="Require documentation on all types and fields"
    )
    require_default: bool = Field(
        default=False,
        description="Require default values on optional fields"
    )
    compatibility_mode: CompatibilityMode = Field(
        default=CompatibilityMode.BACKWARD,
        description="Default compatibility checking mode"
    )
    max_errors: int = Field(
        default=100,
        description="Maximum number of errors to report"
    )
    include_warnings: bool = Field(
        default=True,
        description="Include warnings in validation results"
    )
    allow_unknown_logical_types: bool = Field(
        default=True,
        description="Allow unknown logical types (treat as base type)"
    )

    class Config:
        use_enum_values = True


class AvroValidationError(BaseModel):
    """Represents a single validation error or warning."""

    path: str = Field(
        description="Path to the error location (e.g., 'Record.field_name')"
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


class AvroField(BaseModel):
    """Represents a field in an Avro record."""

    name: str = Field(
        description="Field name"
    )
    type: Any = Field(
        description="Field type (can be string, dict, or list for unions)"
    )
    default: Optional[Any] = Field(
        default=None,
        description="Default value for the field"
    )
    doc: Optional[str] = Field(
        default=None,
        description="Documentation for the field"
    )
    order: Optional[str] = Field(
        default=None,
        description="Sort order (ascending, descending, ignore)"
    )
    aliases: Optional[list[str]] = Field(
        default=None,
        description="Aliases for this field"
    )

    @property
    def is_optional(self) -> bool:
        """Check if the field is optional (has null in union)."""
        if isinstance(self.type, list):
            return "null" in self.type
        return False

    @property
    def has_default(self) -> bool:
        """Check if the field has a default value."""
        return self.default is not None
