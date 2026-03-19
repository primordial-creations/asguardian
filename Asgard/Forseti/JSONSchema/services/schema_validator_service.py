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

    # Format validators
    FORMAT_PATTERNS = {
        SchemaFormat.EMAIL.value: re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        ),
        SchemaFormat.URI.value: re.compile(
            r"^https?://[^\s/$.?#].[^\s]*$"
        ),
        SchemaFormat.UUID.value: re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE
        ),
        SchemaFormat.DATE.value: re.compile(
            r"^\d{4}-\d{2}-\d{2}$"
        ),
        SchemaFormat.DATE_TIME.value: re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
        ),
        SchemaFormat.TIME.value: re.compile(
            r"^\d{2}:\d{2}:\d{2}(\.\d+)?$"
        ),
        SchemaFormat.IPV4.value: re.compile(
            r"^(\d{1,3}\.){3}\d{1,3}$"
        ),
        SchemaFormat.IPV6.value: re.compile(
            r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$"
        ),
        SchemaFormat.HOSTNAME.value: re.compile(
            r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
        ),
    }

    def __init__(self, config: Optional[JSONSchemaConfig] = None):
        """
        Initialize the validator service.

        Args:
            config: Optional configuration for validation behavior.
        """
        self.config = config or JSONSchemaConfig()

    def validate(
        self,
        data: Any,
        schema: dict[str, Any] | str | Path,
    ) -> JSONSchemaValidationResult:
        """
        Validate data against a JSON Schema.

        Args:
            data: Data to validate.
            schema: JSON Schema as dict, or path to schema file.

        Returns:
            JSONSchemaValidationResult with validation details.
        """
        start_time = time.time()
        errors: list[JSONSchemaValidationError] = []

        # Load schema if path provided
        schema_path = None
        if isinstance(schema, (str, Path)):
            schema_path = str(schema)
            try:
                schema = load_schema_file(Path(schema))
            except Exception as e:
                errors.append(JSONSchemaValidationError(
                    path="$",
                    message=f"Failed to load schema: {str(e)}",
                    constraint="schema_load",
                ))
                return JSONSchemaValidationResult(
                    is_valid=False,
                    errors=errors,
                    schema_path=schema_path,
                    validation_time_ms=(time.time() - start_time) * 1000,
                )

        # Resolve references if configured
        if self.config.resolve_references:
            schema = resolve_refs(schema)

        # Validate
        self._validate_value(data, cast(dict[str, Any], schema), "$", errors)

        validation_time_ms = (time.time() - start_time) * 1000

        return JSONSchemaValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            schema_path=schema_path,
            validation_time_ms=validation_time_ms,
        )

    def validate_file(
        self,
        data_path: str | Path,
        schema_path: str | Path
    ) -> JSONSchemaValidationResult:
        """
        Validate data file against a schema file.

        Args:
            data_path: Path to data file (JSON or YAML).
            schema_path: Path to schema file.

        Returns:
            JSONSchemaValidationResult with validation details.
        """
        start_time = time.time()

        # Load data
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
                errors=[JSONSchemaValidationError(
                    path="$",
                    message=f"Failed to load data file: {str(e)}",
                    constraint="data_load",
                )],
                data_path=str(data_path),
                schema_path=str(schema_path),
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        result = self.validate(data, schema_path)
        result.data_path = str(data_path)
        return result

    def _validate_value(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        errors: list[JSONSchemaValidationError]
    ) -> None:
        """Validate a value against a schema."""
        # Handle boolean schemas
        if isinstance(schema, bool):
            if not schema:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message="Schema is false, no value is valid",
                    constraint="false_schema",
                ))
            return

        # Handle const
        if "const" in schema:
            if value != schema["const"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value must be {schema['const']}",
                    value=value,
                    constraint="const",
                    expected=schema["const"],
                ))
            return

        # Handle enum
        if "enum" in schema:
            if value not in schema["enum"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value must be one of: {schema['enum']}",
                    value=value,
                    constraint="enum",
                    expected=schema["enum"],
                ))
            return

        # Handle type validation
        if "type" in schema:
            self._validate_type(value, schema, path, errors)

        # Handle allOf
        if "allOf" in schema:
            for i, subschema in enumerate(schema["allOf"]):
                self._validate_value(value, subschema, path, errors)

        # Handle anyOf
        if "anyOf" in schema:
            any_valid = False
            for subschema in schema["anyOf"]:
                sub_errors: list[JSONSchemaValidationError] = []
                self._validate_value(value, subschema, path, sub_errors)
                if not sub_errors:
                    any_valid = True
                    break
            if not any_valid:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message="Value does not match any of the allowed schemas",
                    value=value,
                    constraint="anyOf",
                ))

        # Handle oneOf
        if "oneOf" in schema:
            matches = 0
            for subschema in schema["oneOf"]:
                sub_errors = []
                self._validate_value(value, subschema, path, sub_errors)
                if not sub_errors:
                    matches += 1
            if matches != 1:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value must match exactly one schema, but matched {matches}",
                    value=value,
                    constraint="oneOf",
                ))

        # Handle not
        if "not" in schema:
            sub_errors = []
            self._validate_value(value, schema["not"], path, sub_errors)
            if not sub_errors:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message="Value must not match the schema",
                    value=value,
                    constraint="not",
                ))

    def _validate_type(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        errors: list[JSONSchemaValidationError]
    ) -> None:
        """Validate value type."""
        schema_type = schema["type"]

        # Handle multiple types
        if isinstance(schema_type, list):
            type_valid = any(
                self._check_type(value, t) for t in schema_type
            )
            if not type_valid:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value type must be one of: {schema_type}",
                    value=value,
                    constraint="type",
                    expected=schema_type,
                ))
            return

        # Handle single type
        if not self._check_type(value, schema_type):
            errors.append(JSONSchemaValidationError(
                path=path,
                message=f"Expected type '{schema_type}', got '{type(value).__name__}'",
                value=value,
                constraint="type",
                expected=schema_type,
            ))
            return

        # Type-specific validation
        if schema_type == "string":
            self._validate_string(value, schema, path, errors)
        elif schema_type == "number" or schema_type == "integer":
            self._validate_number(value, schema, path, errors)
        elif schema_type == "array":
            self._validate_array(value, schema, path, errors)
        elif schema_type == "object":
            self._validate_object(value, schema, path, errors)

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON type."""
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

    def _validate_string(
        self,
        value: str,
        schema: dict[str, Any],
        path: str,
        errors: list[JSONSchemaValidationError]
    ) -> None:
        """Validate string constraints."""
        # minLength
        if "minLength" in schema:
            if len(value) < schema["minLength"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"String length {len(value)} is less than minimum {schema['minLength']}",
                    value=value,
                    constraint="minLength",
                    expected=schema["minLength"],
                ))

        # maxLength
        if "maxLength" in schema:
            if len(value) > schema["maxLength"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"String length {len(value)} exceeds maximum {schema['maxLength']}",
                    value=value,
                    constraint="maxLength",
                    expected=schema["maxLength"],
                ))

        # pattern
        if "pattern" in schema:
            if not re.search(schema["pattern"], value):
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"String does not match pattern: {schema['pattern']}",
                    value=value,
                    constraint="pattern",
                    expected=schema["pattern"],
                ))

        # format
        if "format" in schema and self.config.check_formats:
            fmt = schema["format"]
            if fmt in self.FORMAT_PATTERNS:
                if not self.FORMAT_PATTERNS[fmt].match(value):
                    errors.append(JSONSchemaValidationError(
                        path=path,
                        message=f"String does not match format: {fmt}",
                        value=value,
                        constraint="format",
                        expected=fmt,
                    ))

    def _validate_number(
        self,
        value: int | float,
        schema: dict[str, Any],
        path: str,
        errors: list[JSONSchemaValidationError]
    ) -> None:
        """Validate number constraints."""
        # minimum
        if "minimum" in schema:
            if value < schema["minimum"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value {value} is less than minimum {schema['minimum']}",
                    value=value,
                    constraint="minimum",
                    expected=schema["minimum"],
                ))

        # maximum
        if "maximum" in schema:
            if value > schema["maximum"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value {value} exceeds maximum {schema['maximum']}",
                    value=value,
                    constraint="maximum",
                    expected=schema["maximum"],
                ))

        # exclusiveMinimum
        if "exclusiveMinimum" in schema:
            if value <= schema["exclusiveMinimum"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value {value} must be greater than {schema['exclusiveMinimum']}",
                    value=value,
                    constraint="exclusiveMinimum",
                    expected=schema["exclusiveMinimum"],
                ))

        # exclusiveMaximum
        if "exclusiveMaximum" in schema:
            if value >= schema["exclusiveMaximum"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value {value} must be less than {schema['exclusiveMaximum']}",
                    value=value,
                    constraint="exclusiveMaximum",
                    expected=schema["exclusiveMaximum"],
                ))

        # multipleOf
        if "multipleOf" in schema:
            if value % schema["multipleOf"] != 0:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Value {value} is not a multiple of {schema['multipleOf']}",
                    value=value,
                    constraint="multipleOf",
                    expected=schema["multipleOf"],
                ))

    def _validate_array(
        self,
        value: list[Any],
        schema: dict[str, Any],
        path: str,
        errors: list[JSONSchemaValidationError]
    ) -> None:
        """Validate array constraints."""
        # minItems
        if "minItems" in schema:
            if len(value) < schema["minItems"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Array has {len(value)} items, minimum is {schema['minItems']}",
                    value=value,
                    constraint="minItems",
                    expected=schema["minItems"],
                ))

        # maxItems
        if "maxItems" in schema:
            if len(value) > schema["maxItems"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Array has {len(value)} items, maximum is {schema['maxItems']}",
                    value=value,
                    constraint="maxItems",
                    expected=schema["maxItems"],
                ))

        # uniqueItems
        if schema.get("uniqueItems"):
            seen: list[Any] = []
            for i, item in enumerate(value):
                # Use repr for hashability check
                item_repr = repr(item)
                if item_repr in [repr(s) for s in seen]:
                    errors.append(JSONSchemaValidationError(
                        path=f"{path}[{i}]",
                        message="Duplicate item in array",
                        value=item,
                        constraint="uniqueItems",
                    ))
                seen.append(item)

        # items
        if "items" in schema:
            items_schema = schema["items"]
            if isinstance(items_schema, dict):
                # All items must match same schema
                for i, item in enumerate(value):
                    self._validate_value(item, items_schema, f"{path}[{i}]", errors)
            elif isinstance(items_schema, list):
                # Tuple validation
                for i, item in enumerate(value):
                    if i < len(items_schema):
                        self._validate_value(item, items_schema[i], f"{path}[{i}]", errors)
                    elif "additionalItems" in schema:
                        if schema["additionalItems"] is False:
                            errors.append(JSONSchemaValidationError(
                                path=f"{path}[{i}]",
                                message="Additional items not allowed",
                                value=item,
                                constraint="additionalItems",
                            ))
                        elif isinstance(schema["additionalItems"], dict):
                            self._validate_value(
                                item, schema["additionalItems"], f"{path}[{i}]", errors
                            )

        # contains
        if "contains" in schema:
            contains_valid = False
            for item in value:
                sub_errors: list[JSONSchemaValidationError] = []
                self._validate_value(item, schema["contains"], path, sub_errors)
                if not sub_errors:
                    contains_valid = True
                    break
            if not contains_valid:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message="Array does not contain required item",
                    value=value,
                    constraint="contains",
                ))

    def _validate_object(
        self,
        value: dict[str, Any],
        schema: dict[str, Any],
        path: str,
        errors: list[JSONSchemaValidationError]
    ) -> None:
        """Validate object constraints."""
        # required
        if "required" in schema:
            for prop_name in schema["required"]:
                if prop_name not in value:
                    errors.append(JSONSchemaValidationError(
                        path=f"{path}.{prop_name}",
                        message=f"Required property '{prop_name}' is missing",
                        constraint="required",
                        expected=prop_name,
                    ))

        # properties
        validated_props: set[str] = set()
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                if prop_name in value:
                    self._validate_value(
                        value[prop_name],
                        prop_schema,
                        f"{path}.{prop_name}",
                        errors
                    )
                    validated_props.add(prop_name)

        # patternProperties
        if "patternProperties" in schema:
            for pattern, prop_schema in schema["patternProperties"].items():
                regex = re.compile(pattern)
                for prop_name in value:
                    if regex.search(prop_name):
                        self._validate_value(
                            value[prop_name],
                            prop_schema,
                            f"{path}.{prop_name}",
                            errors
                        )
                        validated_props.add(prop_name)

        # additionalProperties
        additional_props = set(value.keys()) - validated_props
        if additional_props:
            if "additionalProperties" in schema:
                if schema["additionalProperties"] is False:
                    if self.config.strict_mode:
                        for prop_name in additional_props:
                            errors.append(JSONSchemaValidationError(
                                path=f"{path}.{prop_name}",
                                message=f"Additional property '{prop_name}' is not allowed",
                                constraint="additionalProperties",
                            ))
                elif isinstance(schema["additionalProperties"], dict):
                    for prop_name in additional_props:
                        self._validate_value(
                            value[prop_name],
                            schema["additionalProperties"],
                            f"{path}.{prop_name}",
                            errors
                        )

        # minProperties
        if "minProperties" in schema:
            if len(value) < schema["minProperties"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Object has {len(value)} properties, minimum is {schema['minProperties']}",
                    value=value,
                    constraint="minProperties",
                    expected=schema["minProperties"],
                ))

        # maxProperties
        if "maxProperties" in schema:
            if len(value) > schema["maxProperties"]:
                errors.append(JSONSchemaValidationError(
                    path=path,
                    message=f"Object has {len(value)} properties, maximum is {schema['maxProperties']}",
                    value=value,
                    constraint="maxProperties",
                    expected=schema["maxProperties"],
                ))

        # propertyNames
        if "propertyNames" in schema:
            for prop_name in value:
                self._validate_value(
                    prop_name,
                    schema["propertyNames"],
                    f"{path}[propertyName:{prop_name}]",
                    errors
                )

    def generate_report(
        self,
        result: JSONSchemaValidationResult,
        format: str = "text"
    ) -> str:
        """Generate a validation report."""
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: JSONSchemaValidationResult) -> str:
        """Generate a text format report."""
        lines = []
        lines.append("=" * 60)
        lines.append("JSON Schema Validation Report")
        lines.append("=" * 60)
        if result.schema_path:
            lines.append(f"Schema: {result.schema_path}")
        if result.data_path:
            lines.append(f"Data: {result.data_path}")
        lines.append(f"Valid: {'Yes' if result.is_valid else 'No'}")
        lines.append(f"Errors: {result.error_count}")
        lines.append(f"Time: {result.validation_time_ms:.2f}ms")
        lines.append("-" * 60)

        if result.errors:
            lines.append("\nValidation Errors:")
            for error in result.errors:
                lines.append(f"  [{error.path}] {error.message}")
                if error.constraint:
                    lines.append(f"    Constraint: {error.constraint}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _generate_markdown_report(self, result: JSONSchemaValidationResult) -> str:
        """Generate a markdown format report."""
        lines = []
        lines.append("# JSON Schema Validation Report\n")
        if result.schema_path:
            lines.append(f"- **Schema**: {result.schema_path}")
        if result.data_path:
            lines.append(f"- **Data**: {result.data_path}")
        lines.append(f"- **Valid**: {'Yes' if result.is_valid else 'No'}")
        lines.append(f"- **Errors**: {result.error_count}\n")

        if result.errors:
            lines.append("## Validation Errors\n")
            lines.append("| Path | Message | Constraint |")
            lines.append("|------|---------|------------|")
            for error in result.errors:
                constraint = error.constraint or "-"
                lines.append(f"| `{error.path}` | {error.message} | {constraint} |")

        return "\n".join(lines)
