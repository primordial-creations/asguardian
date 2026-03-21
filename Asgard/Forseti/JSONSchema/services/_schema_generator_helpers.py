"""
Schema Generator Helpers.

Helper functions for SchemaGeneratorService.
"""

import re
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Callable, Literal, Optional, Union, get_args, get_origin
from uuid import UUID


TYPE_MAP: dict[type, dict[str, Any]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    type(None): {"type": "null"},
    bytes: {"type": "string", "contentEncoding": "base64"},
    datetime: {"type": "string", "format": "date-time"},
    date: {"type": "string", "format": "date"},
    time: {"type": "string", "format": "time"},
    UUID: {"type": "string", "format": "uuid"},
}


def infer_string_format(value: str) -> Optional[str]:
    """Infer string format from value."""
    patterns = [
        (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "date-time"),
        (r"^\d{4}-\d{2}-\d{2}$", "date"),
        (r"^\d{2}:\d{2}:\d{2}$", "time"),
        (r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", "email"),
        (r"^https?://", "uri"),
        (r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", "uuid"),
    ]

    for pattern, fmt in patterns:
        if re.match(pattern, value, re.IGNORECASE):
            return fmt

    return None


def remove_descriptions(schema: dict[str, Any]) -> None:
    """Remove descriptions from schema."""
    schema.pop("description", None)
    for key in ["properties", "definitions", "$defs"]:
        if key in schema:
            for prop_schema in schema[key].values():
                if isinstance(prop_schema, dict):
                    remove_descriptions(prop_schema)
    if "items" in schema and isinstance(schema["items"], dict):
        remove_descriptions(schema["items"])


def remove_examples(schema: dict[str, Any]) -> None:
    """Remove examples from schema."""
    schema.pop("examples", None)
    for key in ["properties", "definitions", "$defs"]:
        if key in schema:
            for prop_schema in schema[key].values():
                if isinstance(prop_schema, dict):
                    remove_examples(prop_schema)
    if "items" in schema and isinstance(schema["items"], dict):
        remove_examples(schema["items"])


def infer_schema_from_value(
    value: Any,
    infer_formats: bool,
    recurse_fn: Callable,
) -> dict[str, Any]:
    """Infer schema from a sample value."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        schema: dict[str, Any] = {"type": "string"}
        if infer_formats:
            fmt = infer_string_format(value)
            if fmt:
                schema["format"] = fmt
        return schema
    if isinstance(value, list):
        schema = {"type": "array"}
        if value:
            schema["items"] = recurse_fn(value[0])
        return schema
    if isinstance(value, dict):
        properties = {}
        for key, val in value.items():
            properties[key] = recurse_fn(val)
        return {
            "type": "object",
            "properties": properties,
        }
    return {}


def type_to_schema(type_hint: Any, recurse_fn: Callable) -> dict[str, Any]:
    """Convert a type hint to JSON Schema."""
    if type_hint is type(None):
        return {"type": "null"}

    if type_hint in TYPE_MAP:
        return dict(TYPE_MAP[type_hint])

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin is Union:
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1 and type(None) in args:
            schema = recurse_fn(non_none_args[0])
            if "type" in schema:
                if isinstance(schema["type"], list):
                    if "null" not in schema["type"]:
                        schema["type"].append("null")
                else:
                    schema["type"] = [schema["type"], "null"]
            else:
                schema = {"anyOf": [schema, {"type": "null"}]}
            return schema
        else:
            return {
                "anyOf": [recurse_fn(arg) for arg in args]
            }

    if origin is list:
        schema = {"type": "array"}
        if args:
            schema["items"] = recurse_fn(args[0])
        return schema

    if origin is set:
        schema = {"type": "array", "uniqueItems": True}
        if args:
            schema["items"] = recurse_fn(args[0])
        return schema

    if origin is tuple:
        if args:
            if len(args) == 2 and args[1] is Ellipsis:
                return {
                    "type": "array",
                    "items": recurse_fn(args[0])
                }
            else:
                return {
                    "type": "array",
                    "items": [recurse_fn(arg) for arg in args],
                    "minItems": len(args),
                    "maxItems": len(args),
                }
        return {"type": "array"}

    if origin is dict:
        schema = {"type": "object"}
        if args and len(args) == 2:
            if args[0] is str:
                schema["additionalProperties"] = recurse_fn(args[1])
        return schema

    if isinstance(type_hint, type) and issubclass(type_hint, Enum):
        values = [e.value for e in type_hint]
        if values:
            first_type = type(values[0])
            if first_type is str:
                return {"type": "string", "enum": values}
            elif first_type is int:
                return {"type": "integer", "enum": values}
        return {"enum": values}

    if get_origin(type_hint) is Literal:
        values = list(get_args(type_hint))
        return {"enum": values}

    if hasattr(type_hint, "__annotations__"):
        return recurse_fn(type_hint)

    return {}


def generate_object_schema(
    cls: type,
    schema_version: str,
    include_descriptions: bool,
    include_defaults: bool,
    type_to_schema_fn: Callable,
    definitions: dict[str, Any],
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> dict[str, Any]:
    """Generate schema for a class with type annotations."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    annotations = getattr(cls, "__annotations__", {})

    for name, type_hint in annotations.items():
        field_schema = type_to_schema_fn(type_hint)

        if hasattr(cls, name):
            default = getattr(cls, name)
            if include_defaults and not callable(default):
                field_schema["default"] = default
        else:
            origin = get_origin(type_hint)
            args = get_args(type_hint)
            if not (origin is Union and type(None) in args):
                required.append(name)

        properties[name] = field_schema

    schema: dict[str, Any] = {
        "$schema": schema_version,
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    if title:
        schema["title"] = title
    elif hasattr(cls, "__name__"):
        schema["title"] = cls.__name__

    if description and include_descriptions:
        schema["description"] = description
    elif cls.__doc__ and include_descriptions:
        schema["description"] = cls.__doc__.strip()

    if definitions:
        schema["definitions"] = definitions

    return schema
