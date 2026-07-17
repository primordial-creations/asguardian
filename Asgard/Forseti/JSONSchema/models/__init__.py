"""
JSONSchema Models - Data models for JSON Schema handling.
"""

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaSpec,
    JSONSchemaValidationResult,
    JSONSchemaValidationError,
    JSONSchemaInferenceResult,
    DialectConversionResult,
    LLMCompatibilityIssue,
    LLMCompatibilityResult,
    LossRecord,
    SchemaType,
    SchemaFormat,
)

__all__ = [
    "JSONSchemaConfig",
    "JSONSchemaSpec",
    "JSONSchemaValidationResult",
    "JSONSchemaValidationError",
    "JSONSchemaInferenceResult",
    "DialectConversionResult",
    "LLMCompatibilityIssue",
    "LLMCompatibilityResult",
    "LossRecord",
    "SchemaType",
    "SchemaFormat",
]
