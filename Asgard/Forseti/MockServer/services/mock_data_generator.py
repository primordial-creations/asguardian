"""
Mock Data Generator Service.

Generates realistic mock data based on JSON schemas and specifications.
"""

import random
import uuid
from typing import Any, Optional

from Asgard.Forseti.MockServer.models.mock_models import (
    DataType,
    MockDataConfig,
    MockDataResult,
)
from Asgard.Forseti.MockServer.services._mock_data_generator_helpers import (
    CITIES,
    COUNTRIES,
    DOMAINS,
    FIRST_NAMES,
    LAST_NAMES,
    STREET_TYPES,
    generate_address,
    generate_date,
    generate_datetime,
    generate_email,
    generate_formatted_string,
    generate_from_pattern,
    generate_ipv4,
    generate_lorem,
    generate_name,
    generate_password,
    generate_phone,
    generate_string,
    generate_time,
    generate_token,
    generate_url,
    generate_username,
    infer_from_property_name,
    merge_all_of,
)


class MockDataGeneratorService:
    """
    Service for generating realistic mock data from JSON schemas.

    Generates data that matches schema constraints while providing
    realistic values based on field names and formats.

    Usage:
        generator = MockDataGeneratorService()
        data = generator.generate_from_schema(schema)
        print(data)
    """

    def __init__(self, config: Optional[MockDataConfig] = None):
        self.config = config or MockDataConfig()
        self._random = random.Random()
        if config and config.locale:
            self._random.seed(hash(config.locale))

    def set_seed(self, seed: int) -> None:
        self._random.seed(seed)

    def generate_from_schema(
        self,
        schema: dict[str, Any],
        property_name: Optional[str] = None,
    ) -> MockDataResult:
        warnings: list[str] = []
        if self.config.use_examples and "example" in schema:
            return MockDataResult(data=schema["example"], schema_used=schema, generation_strategy="example")
        if self.config.use_examples and "examples" in schema:
            examples = schema["examples"]
            if examples:
                return MockDataResult(data=self._random.choice(examples), schema_used=schema, generation_strategy="examples")
        if self.config.use_defaults and "default" in schema:
            return MockDataResult(data=schema["default"], schema_used=schema, generation_strategy="default")
        if "enum" in schema:
            return MockDataResult(data=self._random.choice(schema["enum"]), schema_used=schema, generation_strategy="enum")
        if "const" in schema:
            return MockDataResult(data=schema["const"], schema_used=schema, generation_strategy="const")
        if "oneOf" in schema:
            return self.generate_from_schema(self._random.choice(schema["oneOf"]), property_name)
        if "anyOf" in schema:
            return self.generate_from_schema(self._random.choice(schema["anyOf"]), property_name)
        if "allOf" in schema:
            return self.generate_from_schema(merge_all_of(schema["allOf"]), property_name)
        schema_type = schema.get("type", "object")
        schema_format = schema.get("format")
        if isinstance(schema_type, list):
            for t in schema_type:
                if t != "null":
                    schema_type = t
                    break
            else:
                schema_type = "null"
        data = self._generate_by_type(schema_type, schema, schema_format, property_name, warnings)
        return MockDataResult(data=data, schema_used=schema, generation_strategy=f"generated_{schema_type}", warnings=warnings)

    def generate_value(self, data_type: DataType, constraints: Optional[dict[str, Any]] = None) -> Any:
        constraints = constraints or {}
        if data_type == DataType.STRING:
            return generate_string(constraints, self._random, self.config.string_min_length, self.config.string_max_length)
        elif data_type == DataType.INTEGER:
            return self._generate_integer(constraints)
        elif data_type == DataType.NUMBER:
            return self._generate_number(constraints)
        elif data_type == DataType.BOOLEAN:
            return self._random.choice([True, False])
        elif data_type == DataType.DATE:
            return generate_date(self._random)
        elif data_type == DataType.DATETIME:
            return generate_datetime(self._random)
        elif data_type == DataType.EMAIL:
            return generate_email(self._random)
        elif data_type == DataType.UUID:
            return str(uuid.uuid4())
        elif data_type == DataType.URL:
            return generate_url(self._random)
        elif data_type == DataType.PHONE:
            return generate_phone(self._random)
        elif data_type == DataType.NAME:
            return generate_name(self._random)
        elif data_type == DataType.ADDRESS:
            return generate_address(self._random)
        elif data_type == DataType.ARRAY:
            return []
        elif data_type == DataType.OBJECT:
            return {}
        else:
            return None

    def _generate_by_type(
        self,
        schema_type: str,
        schema: dict[str, Any],
        schema_format: Optional[str],
        property_name: Optional[str],
        warnings: list[str],
    ) -> Any:
        if schema_type == "string":
            return self._generate_string_from_schema(schema, schema_format, property_name)
        elif schema_type == "integer":
            return self._generate_integer(schema)
        elif schema_type == "number":
            return self._generate_number(schema)
        elif schema_type == "boolean":
            return self._random.choice([True, False])
        elif schema_type == "array":
            return self._generate_array(schema, warnings)
        elif schema_type == "object":
            return self._generate_object(schema, warnings)
        elif schema_type == "null":
            return None
        else:
            warnings.append(f"Unknown type: {schema_type}, defaulting to null")
            return None

    def _generate_string_from_schema(
        self,
        schema: dict[str, Any],
        schema_format: Optional[str],
        property_name: Optional[str],
    ) -> str:
        if schema_format:
            return generate_formatted_string(schema_format, self._random)
        if "pattern" in schema:
            return generate_from_pattern(schema["pattern"], self._random, self.config.string_min_length, self.config.string_max_length)
        if property_name:
            inferred = infer_from_property_name(property_name, self._random)
            if inferred is not None:
                return inferred
        return generate_string(schema, self._random, self.config.string_min_length, self.config.string_max_length)

    def _generate_integer(self, constraints: dict[str, Any]) -> int:
        minimum = constraints.get("minimum", int(self.config.number_min))
        maximum = constraints.get("maximum", int(self.config.number_max))
        if constraints.get("exclusiveMinimum"):
            minimum = constraints["exclusiveMinimum"] + 1
        if constraints.get("exclusiveMaximum"):
            maximum = constraints["exclusiveMaximum"] - 1
        return self._random.randint(minimum, maximum)

    def _generate_number(self, constraints: dict[str, Any]) -> float:
        minimum = constraints.get("minimum", self.config.number_min)
        maximum = constraints.get("maximum", self.config.number_max)
        if constraints.get("exclusiveMinimum"):
            minimum = constraints["exclusiveMinimum"] + 0.001
        if constraints.get("exclusiveMaximum"):
            maximum = constraints["exclusiveMaximum"] - 0.001
        return round(self._random.uniform(minimum, maximum), 2)

    def _generate_array(self, schema: dict[str, Any], warnings: list[str]) -> list:
        min_items = schema.get("minItems", self.config.array_min_items)
        max_items = schema.get("maxItems", self.config.array_max_items)
        count = self._random.randint(min_items, max_items)
        items_schema = schema.get("items", {})
        if not items_schema:
            warnings.append("Array schema has no items definition")
            return []
        result = []
        for _ in range(count):
            item_result = self.generate_from_schema(items_schema)
            result.append(item_result.data)
            warnings.extend(item_result.warnings)
        return result

    def _generate_object(self, schema: dict[str, Any], warnings: list[str]) -> dict:
        result = {}
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        for prop_name, prop_schema in properties.items():
            if prop_name in required or self.config.generate_optional:
                prop_result = self.generate_from_schema(prop_schema, prop_name)
                result[prop_name] = prop_result.data
                warnings.extend(prop_result.warnings)
        return result
