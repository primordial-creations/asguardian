"""
Schema Validator Service Helpers.

Helper functions for SchemaValidatorService.
"""

import re
from typing import Any, Callable

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaValidationError,
    JSONSchemaValidationResult,
)


def generate_text_report(result: JSONSchemaValidationResult) -> str:
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


def generate_markdown_report(result: JSONSchemaValidationResult) -> str:
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


def validate_string(
    value: str,
    schema: dict[str, Any],
    path: str,
    errors: list[JSONSchemaValidationError],
    format_patterns: dict[str, re.Pattern],
    check_formats: bool,
) -> None:
    """Validate string constraints."""
    if "minLength" in schema:
        if len(value) < schema["minLength"]:
            errors.append(JSONSchemaValidationError(path=path, message=f"String length {len(value)} is less than minimum {schema['minLength']}", value=value, constraint="minLength", expected=schema["minLength"]))
    if "maxLength" in schema:
        if len(value) > schema["maxLength"]:
            errors.append(JSONSchemaValidationError(path=path, message=f"String length {len(value)} exceeds maximum {schema['maxLength']}", value=value, constraint="maxLength", expected=schema["maxLength"]))
    if "pattern" in schema:
        if not re.search(schema["pattern"], value):
            errors.append(JSONSchemaValidationError(path=path, message=f"String does not match pattern: {schema['pattern']}", value=value, constraint="pattern", expected=schema["pattern"]))
    if "format" in schema and check_formats:
        fmt = schema["format"]
        if fmt in format_patterns:
            if not format_patterns[fmt].match(value):
                errors.append(JSONSchemaValidationError(path=path, message=f"String does not match format: {fmt}", value=value, constraint="format", expected=fmt))


def validate_number(value: Any, schema: dict[str, Any], path: str, errors: list[JSONSchemaValidationError]) -> None:
    """Validate number constraints."""
    if "minimum" in schema and value < schema["minimum"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Value {value} is less than minimum {schema['minimum']}", value=value, constraint="minimum", expected=schema["minimum"]))
    if "maximum" in schema and value > schema["maximum"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Value {value} exceeds maximum {schema['maximum']}", value=value, constraint="maximum", expected=schema["maximum"]))
    if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Value {value} must be greater than {schema['exclusiveMinimum']}", value=value, constraint="exclusiveMinimum", expected=schema["exclusiveMinimum"]))
    if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Value {value} must be less than {schema['exclusiveMaximum']}", value=value, constraint="exclusiveMaximum", expected=schema["exclusiveMaximum"]))
    if "multipleOf" in schema and value % schema["multipleOf"] != 0:
        errors.append(JSONSchemaValidationError(path=path, message=f"Value {value} is not a multiple of {schema['multipleOf']}", value=value, constraint="multipleOf", expected=schema["multipleOf"]))


def validate_array(
    value: list[Any],
    schema: dict[str, Any],
    path: str,
    errors: list[JSONSchemaValidationError],
    validate_value_fn: Callable,
) -> None:
    """Validate array constraints."""
    if "minItems" in schema and len(value) < schema["minItems"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Array has {len(value)} items, minimum is {schema['minItems']}", value=value, constraint="minItems", expected=schema["minItems"]))
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Array has {len(value)} items, maximum is {schema['maxItems']}", value=value, constraint="maxItems", expected=schema["maxItems"]))
    if schema.get("uniqueItems"):
        seen: list[Any] = []
        for i, item in enumerate(value):
            if repr(item) in [repr(s) for s in seen]:
                errors.append(JSONSchemaValidationError(path=f"{path}[{i}]", message="Duplicate item in array", value=item, constraint="uniqueItems"))
            seen.append(item)
    if "items" in schema:
        items_schema = schema["items"]
        if isinstance(items_schema, dict):
            for i, item in enumerate(value):
                validate_value_fn(item, items_schema, f"{path}[{i}]", errors)
        elif isinstance(items_schema, list):
            for i, item in enumerate(value):
                if i < len(items_schema):
                    validate_value_fn(item, items_schema[i], f"{path}[{i}]", errors)
                elif "additionalItems" in schema:
                    if schema["additionalItems"] is False:
                        errors.append(JSONSchemaValidationError(path=f"{path}[{i}]", message="Additional items not allowed", value=item, constraint="additionalItems"))
                    elif isinstance(schema["additionalItems"], dict):
                        validate_value_fn(item, schema["additionalItems"], f"{path}[{i}]", errors)
    if "contains" in schema:
        contains_valid = False
        for item in value:
            sub_errors: list[JSONSchemaValidationError] = []
            validate_value_fn(item, schema["contains"], path, sub_errors)
            if not sub_errors:
                contains_valid = True
                break
        if not contains_valid:
            errors.append(JSONSchemaValidationError(path=path, message="Array does not contain required item", value=value, constraint="contains"))


def validate_object(
    value: dict[str, Any],
    schema: dict[str, Any],
    path: str,
    errors: list[JSONSchemaValidationError],
    validate_value_fn: Callable,
    strict_mode: bool,
) -> None:
    """Validate object constraints."""
    if "required" in schema:
        for prop_name in schema["required"]:
            if prop_name not in value:
                errors.append(JSONSchemaValidationError(path=f"{path}.{prop_name}", message=f"Required property '{prop_name}' is missing", constraint="required", expected=prop_name))
    validated_props: set[str] = set()
    if "properties" in schema:
        for prop_name, prop_schema in schema["properties"].items():
            if prop_name in value:
                validate_value_fn(value[prop_name], prop_schema, f"{path}.{prop_name}", errors)
                validated_props.add(prop_name)
    if "patternProperties" in schema:
        for pattern, prop_schema in schema["patternProperties"].items():
            regex = re.compile(pattern)
            for prop_name in value:
                if regex.search(prop_name):
                    validate_value_fn(value[prop_name], prop_schema, f"{path}.{prop_name}", errors)
                    validated_props.add(prop_name)
    additional_props = set(value.keys()) - validated_props
    if additional_props and "additionalProperties" in schema:
        if schema["additionalProperties"] is False:
            if strict_mode:
                for prop_name in additional_props:
                    errors.append(JSONSchemaValidationError(path=f"{path}.{prop_name}", message=f"Additional property '{prop_name}' is not allowed", constraint="additionalProperties"))
        elif isinstance(schema["additionalProperties"], dict):
            for prop_name in additional_props:
                validate_value_fn(value[prop_name], schema["additionalProperties"], f"{path}.{prop_name}", errors)
    if "minProperties" in schema and len(value) < schema["minProperties"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Object has {len(value)} properties, minimum is {schema['minProperties']}", value=value, constraint="minProperties", expected=schema["minProperties"]))
    if "maxProperties" in schema and len(value) > schema["maxProperties"]:
        errors.append(JSONSchemaValidationError(path=path, message=f"Object has {len(value)} properties, maximum is {schema['maxProperties']}", value=value, constraint="maxProperties", expected=schema["maxProperties"]))
    if "propertyNames" in schema:
        for prop_name in value:
            validate_value_fn(prop_name, schema["propertyNames"], f"{path}[propertyName:{prop_name}]", errors)
