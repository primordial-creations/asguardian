"""
Avro Schema Validator Service.

Validates Apache Avro schema files against the Avro specification.
Uses JSON parsing - no external avro-tools required.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Optional, cast

from Asgard.Forseti.Avro.models.avro_models import (
    AvroConfig,
    AvroField,
    AvroSchema,
    AvroSchemaType,
    AvroValidationError,
    AvroValidationResult,
    ValidationSeverity,
)
from Asgard.Forseti.Avro.services._avro_validator_service_helpers import (
    generate_markdown_report,
    generate_text_report,
    validate_enum_block,
    validate_record_block,
)


class AvroValidatorService:
    """
    Service for validating Apache Avro schemas.

    Usage:
        service = AvroValidatorService()
        result = service.validate("schema.avsc")
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    PRIMITIVE_TYPES = {"null", "boolean", "int", "long", "float", "double", "bytes", "string"}
    COMPLEX_TYPES = {"record", "enum", "array", "map", "fixed"}
    KNOWN_LOGICAL_TYPES = {
        "decimal", "uuid", "date", "time-millis", "time-micros",
        "timestamp-millis", "timestamp-micros", "duration",
        "local-timestamp-millis", "local-timestamp-micros"
    }

    def __init__(self, config: Optional[AvroConfig] = None):
        self.config = config or AvroConfig()
        self._named_types: dict[str, dict[str, Any]] = {}

    def validate(self, schema_path: str | Path) -> AvroValidationResult:
        return self.validate_file(schema_path)

    def validate_file(self, schema_path: str | Path) -> AvroValidationResult:
        start_time = time.time()
        schema_path = Path(schema_path)
        self._named_types = {}
        errors: list[AvroValidationError] = []
        if not schema_path.exists():
            errors.append(AvroValidationError(path="", message=f"Schema file not found: {schema_path}", severity=ValidationSeverity.ERROR, rule="file-exists"))
            return AvroValidationResult(is_valid=False, file_path=str(schema_path), errors=errors, validation_time_ms=(time.time() - start_time) * 1000)
        try:
            content = schema_path.read_text(encoding="utf-8")
            schema_data = json.loads(content)
        except json.JSONDecodeError as e:
            errors.append(AvroValidationError(path="", message=f"Invalid JSON: {str(e)}", severity=ValidationSeverity.ERROR, rule="valid-json"))
            return AvroValidationResult(is_valid=False, file_path=str(schema_path), errors=errors, validation_time_ms=(time.time() - start_time) * 1000)
        except Exception as e:
            errors.append(AvroValidationError(path="", message=f"Failed to read schema file: {str(e)}", severity=ValidationSeverity.ERROR, rule="readable-file"))
            return AvroValidationResult(is_valid=False, file_path=str(schema_path), errors=errors, validation_time_ms=(time.time() - start_time) * 1000)
        return self._validate_schema_data(schema_data, str(schema_path), start_time)

    def validate_schema_data(self, schema_data: Any) -> AvroValidationResult:
        self._named_types = {}
        return self._validate_schema_data(schema_data, None, time.time())

    def _validate_schema_data(self, schema_data: Any, file_path: Optional[str], start_time: float) -> AvroValidationResult:
        errors: list[AvroValidationError] = []
        warnings: list[AvroValidationError] = []
        info_messages: list[AvroValidationError] = []
        for err in self._validate_type("/", schema_data):
            if err.severity == ValidationSeverity.ERROR:
                errors.append(err)
            elif err.severity == ValidationSeverity.WARNING:
                warnings.append(err)
            else:
                info_messages.append(err)
        parsed_schema = None
        schema_type = None
        if not errors:
            try:
                parsed_schema = self._parse_schema(schema_data, file_path)
                schema_type = parsed_schema.type
            except Exception as e:
                errors.append(AvroValidationError(path="/", message=f"Failed to parse schema: {str(e)}", severity=ValidationSeverity.ERROR, rule="parseable-schema"))
        if self.config.max_errors > 0:
            errors = errors[:self.config.max_errors]
        return AvroValidationResult(
            is_valid=len(errors) == 0, file_path=file_path, schema_type=schema_type,
            parsed_schema=parsed_schema, errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages, validation_time_ms=(time.time() - start_time) * 1000,
        )

    def _validate_type(self, path: str, schema: Any, in_union: bool = False) -> list[AvroValidationError]:
        if schema is None:
            return [AvroValidationError(path=path, message="Schema cannot be null", severity=ValidationSeverity.ERROR, rule="non-null-schema")]
        if isinstance(schema, str):
            return self._validate_string_type(path, schema)
        if isinstance(schema, list):
            return self._validate_union(path, schema)
        if isinstance(schema, dict):
            return self._validate_complex_type(path, schema, in_union)
        return [AvroValidationError(path=path, message=f"Invalid schema type: {type(schema).__name__}", severity=ValidationSeverity.ERROR, rule="valid-schema-type")]

    def _validate_string_type(self, path: str, type_name: str) -> list[AvroValidationError]:
        if type_name in self.PRIMITIVE_TYPES or type_name in self._named_types:
            return []
        for full_name in self._named_types:
            if full_name.endswith("." + type_name):
                return []
        return [AvroValidationError(path=path, message=f"Unknown type: '{type_name}'", severity=ValidationSeverity.ERROR, rule="known-type")]

    def _validate_union(self, path: str, union_types: list[Any]) -> list[AvroValidationError]:
        errors: list[AvroValidationError] = []
        if not union_types:
            return [AvroValidationError(path=path, message="Union types cannot be empty", severity=ValidationSeverity.ERROR, rule="non-empty-union")]
        type_names: set[str] = set()
        for i, union_type in enumerate(union_types):
            type_path = f"{path}[{i}]"
            errors.extend(self._validate_type(type_path, union_type, in_union=True))
            type_name = self._get_type_name(union_type)
            if type_name in type_names:
                errors.append(AvroValidationError(path=type_path, message=f"Duplicate type in union: '{type_name}'", severity=ValidationSeverity.ERROR, rule="no-duplicate-union-types"))
            type_names.add(type_name)
            if isinstance(union_type, list):
                errors.append(AvroValidationError(path=type_path, message="Unions cannot directly contain other unions", severity=ValidationSeverity.ERROR, rule="no-nested-unions"))
        return errors

    def _get_type_name(self, schema: Any) -> str:
        if isinstance(schema, str):
            return schema
        if isinstance(schema, dict) and "type" in schema:
            type_val = schema["type"]
            if type_val in self.COMPLEX_TYPES and "name" in schema:
                return cast(str, schema.get("name", type_val))
            return cast(str, type_val)
        return str(schema)

    def _validate_complex_type(self, path: str, schema: dict[str, Any], in_union: bool = False) -> list[AvroValidationError]:
        errors: list[AvroValidationError] = []
        if "type" not in schema:
            return [AvroValidationError(path=path, message="Missing required field: 'type'", severity=ValidationSeverity.ERROR, rule="required-type-field")]
        type_val = schema["type"]
        if type_val == "record":
            errors.extend(validate_record_block(path, schema, self._named_types, self.config, self._is_valid_name, self._validate_type))
        elif type_val == "enum":
            errors.extend(validate_enum_block(path, schema, self._named_types, self.config, self._is_valid_name))
        elif type_val == "array":
            if "items" not in schema:
                errors.append(AvroValidationError(path=path, message="Array type requires 'items' field", severity=ValidationSeverity.ERROR, rule="array-has-items"))
            else:
                errors.extend(self._validate_type(f"{path}/items", schema["items"]))
        elif type_val == "map":
            if "values" not in schema:
                errors.append(AvroValidationError(path=path, message="Map type requires 'values' field", severity=ValidationSeverity.ERROR, rule="map-has-values"))
            else:
                errors.extend(self._validate_type(f"{path}/values", schema["values"]))
        elif type_val == "fixed":
            errors.extend(self._validate_fixed(path, schema))
        elif type_val in self.PRIMITIVE_TYPES:
            errors.extend(self._validate_annotated_primitive(path, schema))
        else:
            errors.append(AvroValidationError(path=path, message=f"Unknown type: '{type_val}'", severity=ValidationSeverity.ERROR, rule="known-type"))
        return errors

    def _validate_fixed(self, path: str, schema: dict[str, Any]) -> list[AvroValidationError]:
        errors: list[AvroValidationError] = []
        if "name" not in schema:
            return [AvroValidationError(path=path, message="Fixed type requires 'name' field", severity=ValidationSeverity.ERROR, rule="fixed-has-name")]
        name = schema["name"]
        namespace = schema.get("namespace", "")
        if not self._is_valid_name(name):
            errors.append(AvroValidationError(path=f"{path}/name", message=f"Invalid name format: '{name}'", severity=ValidationSeverity.ERROR, rule="valid-name"))
        self._named_types[f"{namespace}.{name}" if namespace else name] = schema
        if "size" not in schema:
            errors.append(AvroValidationError(path=path, message="Fixed type requires 'size' field", severity=ValidationSeverity.ERROR, rule="fixed-has-size"))
            return errors
        size = schema["size"]
        if not isinstance(size, int) or size < 1:
            errors.append(AvroValidationError(path=f"{path}/size", message=f"Size must be a positive integer, got {size}", severity=ValidationSeverity.ERROR, rule="valid-size"))
        return errors

    def _validate_annotated_primitive(self, path: str, schema: dict[str, Any]) -> list[AvroValidationError]:
        errors: list[AvroValidationError] = []
        if "logicalType" in schema:
            logical_type = schema["logicalType"]
            if logical_type not in self.KNOWN_LOGICAL_TYPES:
                severity = ValidationSeverity.INFO if self.config.allow_unknown_logical_types else ValidationSeverity.ERROR
                errors.append(AvroValidationError(path=f"{path}/logicalType", message=f"Unknown logical type: '{logical_type}'", severity=severity, rule="known-logical-type"))
            if logical_type == "decimal" and "precision" not in schema:
                errors.append(AvroValidationError(path=path, message="Decimal logical type requires 'precision'", severity=ValidationSeverity.ERROR, rule="decimal-has-precision"))
        return errors

    def _is_valid_name(self, name: str) -> bool:
        return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name))

    def _parse_schema(self, schema_data: Any, file_path: Optional[str]) -> AvroSchema:
        if isinstance(schema_data, str):
            return AvroSchema(type=schema_data, file_path=file_path)
        if isinstance(schema_data, list):
            return AvroSchema(type="union", raw_schema={"union": schema_data}, file_path=file_path)
        if isinstance(schema_data, dict):
            fields = None
            if "fields" in schema_data:
                fields = [AvroField(name=f["name"], type=f["type"], default=f.get("default"), doc=f.get("doc"), order=f.get("order"), aliases=f.get("aliases")) for f in schema_data["fields"]]
            return AvroSchema(
                type=schema_data.get("type", "unknown"), name=schema_data.get("name"),
                namespace=schema_data.get("namespace"), doc=schema_data.get("doc"),
                fields=fields, symbols=schema_data.get("symbols"), items=schema_data.get("items"),
                values=schema_data.get("values"), size=schema_data.get("size"),
                aliases=schema_data.get("aliases"), logical_type=schema_data.get("logicalType"),
                raw_schema=schema_data, file_path=file_path,
            )
        return AvroSchema(type="unknown", file_path=file_path)

    def generate_report(self, result: AvroValidationResult, format: str = "text") -> str:
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
