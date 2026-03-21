"""
Avro Models - Pydantic models for Apache Avro schema handling.

These models represent Avro schema structures and
validation results for .avsc files.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.Avro.models._avro_base_models import (
    AvroConfig,
    AvroField,
    AvroSchemaType,
    AvroValidationError,
    BreakingChangeType,
    CompatibilityLevel,
    CompatibilityMode,
    ValidationSeverity,
)


class AvroSchema(BaseModel):
    """Complete parsed Avro schema."""

    type: str = Field(
        description="Schema type"
    )
    name: Optional[str] = Field(
        default=None,
        description="Schema name (for named types)"
    )
    namespace: Optional[str] = Field(
        default=None,
        description="Namespace"
    )
    doc: Optional[str] = Field(
        default=None,
        description="Documentation"
    )
    fields: Optional[list[AvroField]] = Field(
        default=None,
        description="Fields (for record types)"
    )
    symbols: Optional[list[str]] = Field(
        default=None,
        description="Enum symbols"
    )
    items: Optional[Any] = Field(
        default=None,
        description="Array item type"
    )
    values: Optional[Any] = Field(
        default=None,
        description="Map value type"
    )
    size: Optional[int] = Field(
        default=None,
        description="Fixed type size"
    )
    aliases: Optional[list[str]] = Field(
        default=None,
        description="Aliases for this type"
    )
    logical_type: Optional[str] = Field(
        default=None,
        alias="logicalType",
        description="Logical type annotation"
    )
    raw_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="Original raw schema"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to the schema file"
    )

    class Config:
        populate_by_name = True

    @property
    def full_name(self) -> str:
        """Return the fully qualified name."""
        if self.namespace and self.name:
            return f"{self.namespace}.{self.name}"
        return self.name or self.type

    @property
    def field_count(self) -> int:
        """Return the number of fields."""
        return len(self.fields) if self.fields else 0


class AvroValidationResult(BaseModel):
    """Result of Avro schema validation."""

    is_valid: bool = Field(
        description="Whether the schema is valid"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to the validated schema file"
    )
    schema_type: Optional[str] = Field(
        default=None,
        description="Detected schema type"
    )
    parsed_schema: Optional[AvroSchema] = Field(
        default=None,
        description="Parsed schema if validation succeeded"
    )
    errors: list[AvroValidationError] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    warnings: list[AvroValidationError] = Field(
        default_factory=list,
        description="List of validation warnings"
    )
    info_messages: list[AvroValidationError] = Field(
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


class BreakingChange(BaseModel):
    """Represents a breaking change between schema versions."""

    change_type: BreakingChangeType = Field(
        description="Type of breaking change"
    )
    path: str = Field(
        description="Path to the changed element"
    )
    message: str = Field(
        description="Human-readable description of the change"
    )
    old_value: Optional[str] = Field(
        default=None,
        description="Old value before the change"
    )
    new_value: Optional[str] = Field(
        default=None,
        description="New value after the change"
    )
    severity: str = Field(
        default="error",
        description="Severity of the breaking change"
    )
    mitigation: Optional[str] = Field(
        default=None,
        description="Suggested mitigation for the breaking change"
    )

    class Config:
        use_enum_values = True


class AvroCompatibilityResult(BaseModel):
    """Result of Avro schema compatibility check."""

    is_compatible: bool = Field(
        description="Whether the schemas are compatible"
    )
    compatibility_level: CompatibilityLevel = Field(
        description="Level of compatibility"
    )
    compatibility_mode: CompatibilityMode = Field(
        default=CompatibilityMode.BACKWARD,
        description="Mode of compatibility check performed"
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Path to the old schema file"
    )
    target_file: Optional[str] = Field(
        default=None,
        description="Path to the new schema file"
    )
    breaking_changes: list[BreakingChange] = Field(
        default_factory=list,
        description="List of breaking changes"
    )
    warnings: list[BreakingChange] = Field(
        default_factory=list,
        description="List of compatibility warnings"
    )
    added_fields: list[str] = Field(
        default_factory=list,
        description="List of added fields"
    )
    removed_fields: list[str] = Field(
        default_factory=list,
        description="List of removed fields"
    )
    modified_fields: list[str] = Field(
        default_factory=list,
        description="List of modified fields"
    )
    check_time_ms: float = Field(
        default=0.0,
        description="Time taken for compatibility check in milliseconds"
    )
    checked_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of compatibility check"
    )

    class Config:
        use_enum_values = True

    @property
    def breaking_change_count(self) -> int:
        """Return the number of breaking changes."""
        return len(self.breaking_changes)

    @property
    def warning_count(self) -> int:
        """Return the number of warnings."""
        return len(self.warnings)


__all__ = [
    "AvroCompatibilityResult",
    "AvroConfig",
    "AvroField",
    "AvroSchema",
    "AvroSchemaType",
    "AvroValidationError",
    "AvroValidationResult",
    "BreakingChange",
    "BreakingChangeType",
    "CompatibilityLevel",
    "CompatibilityMode",
    "ValidationSeverity",
]
