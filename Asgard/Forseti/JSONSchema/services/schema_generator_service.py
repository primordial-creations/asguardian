"""
Schema Generator Service.

Generates JSON Schemas from Python types and Pydantic models.
"""

import dataclasses
import inspect
import json
import re
import yaml  # type: ignore[import-untyped]
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaSpec,
)


class SchemaGeneratorService:
    """
    Service for generating JSON Schemas from Python types.

    Supports Pydantic models, dataclasses, and type hints.

    Usage:
        service = SchemaGeneratorService()
        schema = service.from_pydantic(UserModel)
        # or
        schema = service.from_type(dict[str, list[int]])
    """

    # Type mappings
    TYPE_MAP = {
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

    def __init__(self, config: Optional[JSONSchemaConfig] = None):
        """
        Initialize the generator service.

        Args:
            config: Optional configuration for generation behavior.
        """
        self.config = config or JSONSchemaConfig()
        self._definitions: dict[str, dict[str, Any]] = {}

    def from_pydantic(
        self,
        model: type,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Generate JSON Schema from a Pydantic model.

        Args:
            model: Pydantic model class.
            title: Optional schema title.
            description: Optional schema description.

        Returns:
            JSON Schema dictionary.
        """
        self._definitions = {}

        # Try to use Pydantic's built-in schema generation
        if issubclass(model, BaseModel):
            schema = model.model_json_schema()

            # Apply config options
            if not self.config.include_descriptions:
                self._remove_descriptions(schema)
            if not self.config.include_examples:
                self._remove_examples(schema)

            # Override title/description if provided
            if title:
                schema["title"] = title
            if description:
                schema["description"] = description

            return schema

        # Fallback to manual generation
        return self._generate_object_schema(model, title, description)

    def from_type(
        self,
        type_hint: type,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Generate JSON Schema from a Python type hint.

        Args:
            type_hint: Python type or type hint.
            title: Optional schema title.
            description: Optional schema description.

        Returns:
            JSON Schema dictionary.
        """
        self._definitions = {}

        schema = self._type_to_schema(type_hint)

        if title:
            schema["title"] = title
        if description and self.config.include_descriptions:
            schema["description"] = description

        # Add schema version
        schema["$schema"] = self.config.schema_version

        # Add definitions if any
        if self._definitions:
            schema["definitions"] = self._definitions

        return schema

    def from_dataclass(
        self,
        dataclass_type: type,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Generate JSON Schema from a dataclass.

        Args:
            dataclass_type: Dataclass type.
            title: Optional schema title.
            description: Optional schema description.

        Returns:
            JSON Schema dictionary.
        """
        if not dataclasses.is_dataclass(dataclass_type):
            raise ValueError(f"{dataclass_type} is not a dataclass")

        self._definitions = {}
        properties: dict[str, Any] = {}
        required: list[str] = []

        for field in dataclasses.fields(dataclass_type):
            field_schema = self._type_to_schema(field.type)

            # Handle default values
            if field.default is not dataclasses.MISSING:
                if self.config.include_defaults:
                    field_schema["default"] = field.default
            elif field.default_factory is not dataclasses.MISSING:
                pass  # Can't serialize default_factory
            else:
                required.append(field.name)

            properties[field.name] = field_schema

        schema: dict[str, Any] = {
            "$schema": self.config.schema_version,
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        if title:
            schema["title"] = title
        elif hasattr(dataclass_type, "__name__"):
            schema["title"] = dataclass_type.__name__

        if description and self.config.include_descriptions:
            schema["description"] = description
        elif dataclass_type.__doc__ and self.config.include_descriptions:
            schema["description"] = dataclass_type.__doc__.strip()

        if self._definitions:
            schema["definitions"] = self._definitions

        return schema

    def from_dict_sample(
        self,
        sample: dict[str, Any],
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Generate JSON Schema from a sample dictionary.

        Args:
            sample: Sample dictionary.
            title: Optional schema title.
            description: Optional schema description.

        Returns:
            JSON Schema dictionary.
        """
        schema = self._infer_schema_from_value(sample)

        schema["$schema"] = self.config.schema_version

        if title:
            schema["title"] = title
        if description and self.config.include_descriptions:
            schema["description"] = description

        return schema

    def _type_to_schema(self, type_hint: Any) -> dict[str, Any]:
        """Convert a type hint to JSON Schema."""
        # Handle None
        if type_hint is type(None):
            return {"type": "null"}

        # Handle basic types
        if type_hint in self.TYPE_MAP:
            return dict(self.TYPE_MAP[type_hint])

        # Get origin for generic types
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        # Handle Optional (Union with None)
        if origin is Union:
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1 and type(None) in args:
                # Optional type
                schema = self._type_to_schema(non_none_args[0])
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
                # Union type
                return {
                    "anyOf": [self._type_to_schema(arg) for arg in args]
                }

        # Handle list/List
        if origin is list:
            schema = {"type": "array"}
            if args:
                schema["items"] = self._type_to_schema(args[0])
            return schema

        # Handle set/Set
        if origin is set:
            schema = {"type": "array", "uniqueItems": True}
            if args:
                schema["items"] = self._type_to_schema(args[0])
            return schema

        # Handle tuple/Tuple
        if origin is tuple:
            if args:
                if len(args) == 2 and args[1] is Ellipsis:
                    # Variable length tuple
                    return {
                        "type": "array",
                        "items": self._type_to_schema(args[0])
                    }
                else:
                    # Fixed length tuple
                    return {
                        "type": "array",
                        "items": [self._type_to_schema(arg) for arg in args],
                        "minItems": len(args),
                        "maxItems": len(args),
                    }
            return {"type": "array"}

        # Handle dict/Dict
        if origin is dict:
            schema = {"type": "object"}
            if args and len(args) == 2:
                # dict[str, ValueType]
                if args[0] is str:
                    schema["additionalProperties"] = self._type_to_schema(args[1])
            return schema

        # Handle Enum
        if isinstance(type_hint, type) and issubclass(type_hint, Enum):
            values = [e.value for e in type_hint]
            # Determine type from first value
            if values:
                first_type = type(values[0])
                if first_type is str:
                    return {"type": "string", "enum": values}
                elif first_type is int:
                    return {"type": "integer", "enum": values}
            return {"enum": values}

        # Handle Literal
        if get_origin(type_hint) is Literal:
            values = list(get_args(type_hint))
            return {"enum": values}

        # Handle classes with annotations (dataclass-like)
        if hasattr(type_hint, "__annotations__"):
            return self._generate_object_schema(type_hint)

        # Fallback
        return {}

    def _generate_object_schema(
        self,
        cls: type,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate schema for a class with type annotations."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        annotations = getattr(cls, "__annotations__", {})

        for name, type_hint in annotations.items():
            field_schema = self._type_to_schema(type_hint)

            # Check for default value
            if hasattr(cls, name):
                default = getattr(cls, name)
                if self.config.include_defaults and not callable(default):
                    field_schema["default"] = default
            else:
                # No default, so required
                origin = get_origin(type_hint)
                args = get_args(type_hint)
                # Check if Optional
                if not (origin is Union and type(None) in args):
                    required.append(name)

            properties[name] = field_schema

        schema: dict[str, Any] = {
            "$schema": self.config.schema_version,
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        if title:
            schema["title"] = title
        elif hasattr(cls, "__name__"):
            schema["title"] = cls.__name__

        if description and self.config.include_descriptions:
            schema["description"] = description
        elif cls.__doc__ and self.config.include_descriptions:
            schema["description"] = cls.__doc__.strip()

        if self._definitions:
            schema["definitions"] = self._definitions

        return schema

    def _infer_schema_from_value(self, value: Any) -> dict[str, Any]:
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
            # Try to infer format
            if self.config.infer_formats:
                fmt = self._infer_string_format(value)
                if fmt:
                    schema["format"] = fmt
            return schema
        if isinstance(value, list):
            schema = {"type": "array"}
            if value:
                # Infer items schema from first element
                schema["items"] = self._infer_schema_from_value(value[0])
            return schema
        if isinstance(value, dict):
            properties = {}
            for key, val in value.items():
                properties[key] = self._infer_schema_from_value(val)
            return {
                "type": "object",
                "properties": properties,
            }
        return {}

    def _infer_string_format(self, value: str) -> Optional[str]:
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

    def _remove_descriptions(self, schema: dict[str, Any]) -> None:
        """Remove descriptions from schema."""
        schema.pop("description", None)
        for key in ["properties", "definitions", "$defs"]:
            if key in schema:
                for prop_schema in schema[key].values():
                    if isinstance(prop_schema, dict):
                        self._remove_descriptions(prop_schema)
        if "items" in schema and isinstance(schema["items"], dict):
            self._remove_descriptions(schema["items"])

    def _remove_examples(self, schema: dict[str, Any]) -> None:
        """Remove examples from schema."""
        schema.pop("examples", None)
        for key in ["properties", "definitions", "$defs"]:
            if key in schema:
                for prop_schema in schema[key].values():
                    if isinstance(prop_schema, dict):
                        self._remove_examples(prop_schema)
        if "items" in schema and isinstance(schema["items"], dict):
            self._remove_examples(schema["items"])

    def save_schema(
        self,
        schema: dict[str, Any],
        output_path: str | Path
    ) -> None:
        """
        Save schema to file.

        Args:
            schema: Schema dictionary.
            output_path: Output file path.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.suffix.lower() in [".yaml", ".yml"]:
            content = yaml.dump(schema, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(schema, indent=2)

        path.write_text(content, encoding="utf-8")
