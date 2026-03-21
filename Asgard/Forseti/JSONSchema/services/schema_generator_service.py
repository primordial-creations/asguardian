"""
Schema Generator Service.

Generates JSON Schemas from Python types and Pydantic models.
"""

import dataclasses
import json
import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Any, Optional, Union, get_args, get_origin

from pydantic import BaseModel

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
)
from Asgard.Forseti.JSONSchema.services._schema_generator_helpers import (
    generate_object_schema,
    infer_schema_from_value,
    remove_descriptions,
    remove_examples,
    type_to_schema,
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

        if issubclass(model, BaseModel):
            schema = model.model_json_schema()

            if not self.config.include_descriptions:
                remove_descriptions(schema)
            if not self.config.include_examples:
                remove_examples(schema)

            if title:
                schema["title"] = title
            if description:
                schema["description"] = description

            return schema

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

        schema["$schema"] = self.config.schema_version

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

            if field.default is not dataclasses.MISSING:
                if self.config.include_defaults:
                    field_schema["default"] = field.default
            elif field.default_factory is not dataclasses.MISSING:
                pass
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
        if hasattr(type_hint, "__annotations__") and not get_origin(type_hint):
            return self._generate_object_schema(type_hint)
        return type_to_schema(type_hint, self._type_to_schema)

    def _generate_object_schema(
        self,
        cls: type,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate schema for a class with type annotations."""
        return generate_object_schema(
            cls,
            self.config.schema_version,
            self.config.include_descriptions,
            self.config.include_defaults,
            self._type_to_schema,
            self._definitions,
            title,
            description,
        )

    def _infer_schema_from_value(self, value: Any) -> dict[str, Any]:
        """Infer schema from a sample value."""
        return infer_schema_from_value(value, self.config.infer_formats, self._infer_schema_from_value)

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
