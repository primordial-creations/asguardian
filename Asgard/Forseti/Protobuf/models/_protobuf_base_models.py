"""
Protobuf Base Models - Enums, config, and field-level models.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProtobufSyntaxVersion(str, Enum):
    """Supported Protobuf syntax versions."""
    PROTO2 = "proto2"
    PROTO3 = "proto3"


class ValidationSeverity(str, Enum):
    """Severity levels for validation errors."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class BreakingChangeType(str, Enum):
    """Types of breaking changes in Protobuf schemas."""
    REMOVED_FIELD = "removed_field"
    REMOVED_MESSAGE = "removed_message"
    REMOVED_ENUM = "removed_enum"
    REMOVED_ENUM_VALUE = "removed_enum_value"
    REMOVED_SERVICE = "removed_service"
    REMOVED_RPC = "removed_rpc"
    CHANGED_FIELD_TYPE = "changed_field_type"
    CHANGED_FIELD_NUMBER = "changed_field_number"
    CHANGED_FIELD_LABEL = "changed_field_label"
    CHANGED_ENUM_VALUE_NUMBER = "changed_enum_value_number"
    RESERVED_FIELD_REUSED = "reserved_field_reused"
    RESERVED_NUMBER_REUSED = "reserved_number_reused"


class CompatibilityLevel(str, Enum):
    """Compatibility level between schema versions."""
    FULL = "full"
    BACKWARD = "backward"
    FORWARD = "forward"
    NONE = "none"


class ProtobufConfig(BaseModel):
    """Configuration for Protobuf validation and processing."""

    strict_mode: bool = Field(
        default=False,
        description="Enable strict validation mode"
    )
    check_naming_conventions: bool = Field(
        default=True,
        description="Check naming convention best practices"
    )
    check_field_numbers: bool = Field(
        default=True,
        description="Validate field number ranges and recommendations"
    )
    check_reserved_fields: bool = Field(
        default=True,
        description="Validate reserved field declarations"
    )
    allow_proto2: bool = Field(
        default=True,
        description="Allow proto2 syntax files"
    )
    require_package: bool = Field(
        default=True,
        description="Require package declaration"
    )
    max_errors: int = Field(
        default=100,
        description="Maximum number of errors to report"
    )
    include_warnings: bool = Field(
        default=True,
        description="Include warnings in validation results"
    )

    class Config:
        use_enum_values = True


class ProtobufValidationError(BaseModel):
    """Represents a single validation error or warning."""

    path: str = Field(
        description="Path to the error location (e.g., 'Message.field_name')"
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
    line: Optional[int] = Field(
        default=None,
        description="Line number in the proto file"
    )
    context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional context about the error"
    )

    class Config:
        use_enum_values = True


class ProtobufField(BaseModel):
    """Represents a field in a Protobuf message."""

    name: str = Field(
        description="Field name"
    )
    number: int = Field(
        description="Field number"
    )
    type: str = Field(
        description="Field type (e.g., 'int32', 'string', 'MyMessage')"
    )
    label: Optional[str] = Field(
        default=None,
        description="Field label (optional, required, repeated)"
    )
    default_value: Optional[str] = Field(
        default=None,
        description="Default value for the field"
    )
    options: Optional[dict[str, Any]] = Field(
        default=None,
        description="Field options"
    )
    oneof_group: Optional[str] = Field(
        default=None,
        description="Name of the oneof group if applicable"
    )
    map_key_type: Optional[str] = Field(
        default=None,
        description="Key type for map fields"
    )
    map_value_type: Optional[str] = Field(
        default=None,
        description="Value type for map fields"
    )


class ProtobufEnum(BaseModel):
    """Represents an enum definition in Protobuf."""

    name: str = Field(
        description="Enum name"
    )
    values: dict[str, int] = Field(
        default_factory=dict,
        description="Enum values mapping name to number"
    )
    options: Optional[dict[str, Any]] = Field(
        default=None,
        description="Enum options"
    )
    allow_alias: bool = Field(
        default=False,
        description="Whether allow_alias option is set"
    )
    reserved_names: list[str] = Field(
        default_factory=list,
        description="Reserved enum value names"
    )
    reserved_numbers: list[int] = Field(
        default_factory=list,
        description="Reserved enum value numbers"
    )


class ProtobufService(BaseModel):
    """Represents a service definition in Protobuf."""

    name: str = Field(
        description="Service name"
    )
    rpcs: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="RPC definitions mapping name to input/output types"
    )
    options: Optional[dict[str, Any]] = Field(
        default=None,
        description="Service options"
    )
