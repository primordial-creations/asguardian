"""
JSONSchema Module - JSON Schema generation and validation.

This module provides tools for working with JSON Schemas including
validation, generation from types, and schema inference from samples.
"""

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaSpec,
    JSONSchemaValidationResult,
    JSONSchemaValidationError,
    JSONSchemaInferenceResult,
    SchemaType,
    SchemaFormat,
)

from Asgard.Forseti.JSONSchema.services.schema_validator_service import SchemaValidatorService
from Asgard.Forseti.JSONSchema.services.schema_generator_service import SchemaGeneratorService
from Asgard.Forseti.JSONSchema.services.schema_inference_service import SchemaInferenceService
from Asgard.Forseti.JSONSchema.services.schema_compiler_service import (
    CompiledSchema,
    SchemaCompilerService,
    SchemaDialect,
)
from Asgard.Forseti.JSONSchema.services.dialect_converter_service import DialectConverterService
from Asgard.Forseti.JSONSchema.services.llm_profile_service import LLMProfileService
from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    DialectConversionResult,
    LLMCompatibilityIssue,
    LLMCompatibilityResult,
    LossRecord,
)

from Asgard.Forseti.JSONSchema.utilities.jsonschema_utils import (
    load_schema_file,
    save_schema_file,
    merge_schemas,
    resolve_refs,
    validate_schema_syntax,
)

__all__ = [
    # Models
    "JSONSchemaConfig",
    "JSONSchemaSpec",
    "JSONSchemaValidationResult",
    "JSONSchemaValidationError",
    "JSONSchemaInferenceResult",
    "SchemaType",
    "SchemaFormat",
    "DialectConversionResult",
    "LLMCompatibilityIssue",
    "LLMCompatibilityResult",
    "LossRecord",
    # Services
    "CompiledSchema",
    "DialectConverterService",
    "LLMProfileService",
    "SchemaCompilerService",
    "SchemaDialect",
    "SchemaValidatorService",
    "SchemaGeneratorService",
    "SchemaInferenceService",
    # Utilities
    "load_schema_file",
    "save_schema_file",
    "merge_schemas",
    "resolve_refs",
    "validate_schema_syntax",
]
