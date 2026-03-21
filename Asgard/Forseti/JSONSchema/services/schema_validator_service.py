"""
Schema Validator Service.

Validates data against JSON Schemas.
"""

import json
import re
import time
import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Any, Optional, cast

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaValidationResult,
    JSONSchemaValidationError,
    SchemaFormat,
)
from Asgard.Forseti.JSONSchema.utilities.jsonschema_utils import load_schema_file, resolve_refs
from Asgard.Forseti.JSONSchema.services._schema_validator_service_helpers import (
    generate_markdown_report,
    generate_text_report,
    validate_array,
    validate_number,
    validate_object,
    validate_string,
)


class SchemaValidatorService:
    """
    Service for validating data against JSON Schemas.

    Provides comprehensive validation with detailed error reporting.

    Usage:
        service = SchemaValidatorService()
        result = service.validate(data, schema)
        if not result.is_valid:
            for error in result.errors:
                print(f"Error at {error.path}: {error.message}")
    """

    FORMAT_PATTERNS = {
        SchemaFormat.EMAIL.value: re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        SchemaFormat.URI.value: re.compile(r"^https?://[^\s/$.?#].[^\s]*$"),
        SchemaFormat.UUID.value: re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE),
        SchemaFormat.DATE.value: re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        SchemaFormat.DATE_TIME.value: re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"),
        SchemaFormat.TIME.value: re.compile(r"^\d{2}:\d{2}:\d{2}(\.\d+)?$"),
        SchemaFormat.IPV4.value: re.compile(r"^(\d{1,3}\.){3}\d{1,3}$"),
        SchemaFormat.IPV6.value: re.compile(r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"),
        SchemaFormat.HOSTNAME.value: re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"),
    }

    def __init__(self, config: Optional[JSONSchemaConfig] = None):
        self.config = config or JSONSchemaConfig()

    def validate(self, data: Any, schema: dict[str, Any] | str | Path) -> JSONSchemaValidationResult:
        start_time = time.time()
        errors: list[JSONSchemaValidationError] = []
        schema_path = None
        if isinstance(schema, (str, Path)):
            schema_path = str(schema)
            try:
                schema = load_schema_file(Path(schema))
            except Exception as e:
                errors.append(JSONSchemaValidationError(path="$", message=f"Failed to load schema: {str(e)}", constraint="schema_load"))
                return JSONSchemaValidationResult(is_valid=False, errors=errors, schema_path=schema_path, validation_time_ms=(time.time() - start_time) * 1000)
        if self.config.resolve_references:
            schema = resolve_refs(schema)
        self._validate_value(data, cast(dict[str, Any], schema), "$", errors)
        return JSONSchemaValidationResult(is_valid=len(errors) == 0, errors=errors, schema_path=schema_path, validation_time_ms=(time.time() - start_time) * 1000)

    def validate_file(self, data_path: str | Path, schema_path: str | Path) -> JSONSchemaValidationResult:
        start_time = time.time()
        try:
            data_file = Path(data_path)
            content = data_file.read_text(encoding="utf-8")
            if data_file.suffix.lower() in [".yaml", ".yml"]:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
        except Exception as e:
            return JSONSchemaValidationResult(
                is_valid=False,
                errors=[JSONSchemaValidationError(path="$", message=f"Failed to load data file: {str(e)}", constraint="data_load")],
                data_path=str(data_path),
                schema_path=str(schema_path),
                validation_time_ms=(time.time() - start_time) * 1000,
            )
        result = self.validate(data, schema_path)
        result.data_path = str(data_path)
        return result

    def _validate_value(self, value: Any, schema: dict[str, Any], path: str, errors: list[JSONSchemaValidationError]) -> None:
        if isinstance(schema, bool):
            if not schema:
                errors.append(JSONSchemaValidationError(path=path, message="Schema is false, no value is valid", constraint="false_schema"))
            return
        if "const" in schema:
            if value != schema["const"]:
                errors.append(JSONSchemaValidationError(path=path, message=f"Value must be {schema['const']}", value=value, constraint="const", expected=schema["const"]))
            return
        if "enum" in schema:
            if value not in schema["enum"]:
                errors.append(JSONSchemaValidationError(path=path, message=f"Value must be one of: {schema['enum']}", value=value, constraint="enum", expected=schema["enum"]))
            return
        if "type" in schema:
            self._validate_type(value, schema, path, errors)
        if "allOf" in schema:
            for subschema in schema["allOf"]:
                self._validate_value(value, subschema, path, errors)
        if "anyOf" in schema:
            any_valid = False
            for subschema in schema["anyOf"]:
                sub_errors: list[JSONSchemaValidationError] = []
                self._validate_value(value, subschema, path, sub_errors)
                if not sub_errors:
                    any_valid = True
                    break
            if not any_valid:
                errors.append(JSONSchemaValidationError(path=path, message="Value does not match any of the allowed schemas", value=value, constraint="anyOf"))
        if "oneOf" in schema:
            matches = 0
            for subschema in schema["oneOf"]:
                sub_errors = []
                self._validate_value(value, subschema, path, sub_errors)
                if not sub_errors:
                    matches += 1
            if matches != 1:
                errors.append(JSONSchemaValidationError(path=path, message=f"Value must match exactly one schema, but matched {matches}", value=value, constraint="oneOf"))
        if "not" in schema:
            sub_errors = []
            self._validate_value(value, schema["not"], path, sub_errors)
            if not sub_errors:
                errors.append(JSONSchemaValidationError(path=path, message="Value must not match the schema", value=value, constraint="not"))

    def _validate_type(self, value: Any, schema: dict[str, Any], path: str, errors: list[JSONSchemaValidationError]) -> None:
        schema_type = schema["type"]
        if isinstance(schema_type, list):
            if not any(self._check_type(value, t) for t in schema_type):
                errors.append(JSONSchemaValidationError(path=path, message=f"Value type must be one of: {schema_type}", value=value, constraint="type", expected=schema_type))
            return
        if not self._check_type(value, schema_type):
            errors.append(JSONSchemaValidationError(path=path, message=f"Expected type '{schema_type}', got '{type(value).__name__}'", value=value, constraint="type", expected=schema_type))
            return
        if schema_type == "string":
            validate_string(value, schema, path, errors, self.FORMAT_PATTERNS, self.config.check_formats)
        elif schema_type in ("number", "integer"):
            validate_number(value, schema, path, errors)
        elif schema_type == "array":
            validate_array(value, schema, path, errors, self._validate_value)
        elif schema_type == "object":
            validate_object(value, schema, path, errors, self._validate_value, self.config.strict_mode)

    def _check_type(self, value: Any, expected_type: str) -> bool:
        if expected_type == "null":
            return value is None
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "object":
            return isinstance(value, dict)
        return False

    def generate_report(self, result: JSONSchemaValidationResult, format: str = "text") -> str:
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
