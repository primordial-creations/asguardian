"""
JSONSchema Models - Data models for JSON Schema handling.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from Asgard.Forseti.JSONSchema.models._jsonschema_base_models import (
    JSONSchemaConfig,
    JSONSchemaValidationError,
    JSONSchemaValidationResult,
    SchemaFormat,
    SchemaType,
)


class JSONSchemaSpec(BaseModel):
    """Represents a JSON Schema specification."""

    schema_uri: str = Field(
        default="http://json-schema.org/draft-07/schema#",
        alias="$schema",
        description="JSON Schema version URI"
    )
    schema_id: Optional[str] = Field(
        default=None,
        alias="$id",
        description="Schema identifier URI"
    )
    title: Optional[str] = Field(
        default=None,
        description="Schema title"
    )
    description: Optional[str] = Field(
        default=None,
        description="Schema description"
    )
    type: Optional[str | list[str]] = Field(
        default=None,
        description="Data type(s)"
    )
    properties: Optional[dict[str, Any]] = Field(
        default=None,
        description="Object properties"
    )
    required: Optional[list[str]] = Field(
        default=None,
        description="Required property names"
    )
    items: Optional[dict[str, Any] | list[dict[str, Any]]] = Field(
        default=None,
        description="Array item schema(s)"
    )
    definitions: Optional[dict[str, Any]] = Field(
        default=None,
        description="Schema definitions for $ref"
    )
    defs: Optional[dict[str, Any]] = Field(
        default=None,
        alias="$defs",
        description="Schema definitions (draft 2019-09+)"
    )
    additional_properties: Optional[bool | dict[str, Any]] = Field(
        default=None,
        alias="additionalProperties",
        description="Additional properties schema"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="String pattern regex"
    )
    format: Optional[str] = Field(
        default=None,
        description="String format"
    )
    enum: Optional[list[Any]] = Field(
        default=None,
        description="Allowed values"
    )
    const: Optional[Any] = Field(
        default=None,
        description="Constant value"
    )
    minimum: Optional[float] = Field(
        default=None,
        description="Minimum number value"
    )
    maximum: Optional[float] = Field(
        default=None,
        description="Maximum number value"
    )
    min_length: Optional[int] = Field(
        default=None,
        alias="minLength",
        description="Minimum string length"
    )
    max_length: Optional[int] = Field(
        default=None,
        alias="maxLength",
        description="Maximum string length"
    )
    min_items: Optional[int] = Field(
        default=None,
        alias="minItems",
        description="Minimum array items"
    )
    max_items: Optional[int] = Field(
        default=None,
        alias="maxItems",
        description="Maximum array items"
    )
    unique_items: Optional[bool] = Field(
        default=None,
        alias="uniqueItems",
        description="Array items must be unique"
    )
    all_of: Optional[list[dict[str, Any]]] = Field(
        default=None,
        alias="allOf",
        description="All schemas must match"
    )
    any_of: Optional[list[dict[str, Any]]] = Field(
        default=None,
        alias="anyOf",
        description="Any schema must match"
    )
    one_of: Optional[list[dict[str, Any]]] = Field(
        default=None,
        alias="oneOf",
        description="Exactly one schema must match"
    )
    not_schema: Optional[dict[str, Any]] = Field(
        default=None,
        alias="not",
        description="Schema must not match"
    )
    default: Optional[Any] = Field(
        default=None,
        description="Default value"
    )
    examples: Optional[list[Any]] = Field(
        default=None,
        description="Example values"
    )

    model_config = {"populate_by_name": True}

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard JSON Schema dictionary."""
        result: dict[str, Any] = {}

        if self.schema_uri:
            result["$schema"] = self.schema_uri
        if self.schema_id:
            result["$id"] = self.schema_id
        if self.title:
            result["title"] = self.title
        if self.description:
            result["description"] = self.description
        if self.type:
            result["type"] = self.type
        if self.properties:
            result["properties"] = self.properties
        if self.required:
            result["required"] = self.required
        if self.items:
            result["items"] = self.items
        if self.definitions:
            result["definitions"] = self.definitions
        if self.defs:
            result["$defs"] = self.defs
        if self.additional_properties is not None:
            result["additionalProperties"] = self.additional_properties
        if self.pattern:
            result["pattern"] = self.pattern
        if self.format:
            result["format"] = self.format
        if self.enum:
            result["enum"] = self.enum
        if self.const is not None:
            result["const"] = self.const
        if self.minimum is not None:
            result["minimum"] = self.minimum
        if self.maximum is not None:
            result["maximum"] = self.maximum
        if self.min_length is not None:
            result["minLength"] = self.min_length
        if self.max_length is not None:
            result["maxLength"] = self.max_length
        if self.min_items is not None:
            result["minItems"] = self.min_items
        if self.max_items is not None:
            result["maxItems"] = self.max_items
        if self.unique_items is not None:
            result["uniqueItems"] = self.unique_items
        if self.all_of:
            result["allOf"] = self.all_of
        if self.any_of:
            result["anyOf"] = self.any_of
        if self.one_of:
            result["oneOf"] = self.one_of
        if self.not_schema:
            result["not"] = self.not_schema
        if self.default is not None:
            result["default"] = self.default
        if self.examples:
            result["examples"] = self.examples

        return result


class JSONSchemaInferenceResult(BaseModel):
    """Result of schema inference from sample data."""

    model_config = {"populate_by_name": True}

    inferred_schema: dict[str, Any] = Field(
        alias="schema",
        description="Inferred JSON Schema"
    )
    sample_count: int = Field(
        description="Number of samples analyzed"
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence score (0.0 to 1.0)"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about inference quality"
    )
    statistics: dict[str, Any] = Field(
        default_factory=dict,
        description="Statistics about the analyzed data"
    )


__all__ = [
    "JSONSchemaConfig",
    "JSONSchemaInferenceResult",
    "JSONSchemaSpec",
    "JSONSchemaValidationError",
    "JSONSchemaValidationResult",
    "SchemaFormat",
    "SchemaType",
]
