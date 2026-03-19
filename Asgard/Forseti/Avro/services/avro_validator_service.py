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


class AvroValidatorService:
    """
    Service for validating Apache Avro schemas.

    Validates schema files against Avro specification and reports
    errors, warnings, and informational messages.

    Usage:
        service = AvroValidatorService()
        result = service.validate("schema.avsc")
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    # Avro primitive types
    PRIMITIVE_TYPES = {"null", "boolean", "int", "long", "float", "double", "bytes", "string"}

    # Avro complex types
    COMPLEX_TYPES = {"record", "enum", "array", "map", "fixed"}

    # Known logical types
    KNOWN_LOGICAL_TYPES = {
        "decimal", "uuid", "date", "time-millis", "time-micros",
        "timestamp-millis", "timestamp-micros", "duration",
        "local-timestamp-millis", "local-timestamp-micros"
    }

    # Valid sort orders
    VALID_ORDERS = {"ascending", "descending", "ignore"}

    def __init__(self, config: Optional[AvroConfig] = None):
        """
        Initialize the validator service.

        Args:
            config: Optional configuration for validation behavior.
        """
        self.config = config or AvroConfig()
        self._named_types: dict[str, dict[str, Any]] = {}

    def validate(self, schema_path: str | Path) -> AvroValidationResult:
        """
        Validate an Avro schema file.

        Args:
            schema_path: Path to the Avro schema file (.avsc).

        Returns:
            AvroValidationResult with validation details.
        """
        return self.validate_file(schema_path)

    def validate_file(self, schema_path: str | Path) -> AvroValidationResult:
        """
        Validate an Avro schema file.

        Args:
            schema_path: Path to the Avro schema file.

        Returns:
            AvroValidationResult with validation details.
        """
        start_time = time.time()
        schema_path = Path(schema_path)
        self._named_types = {}

        errors: list[AvroValidationError] = []
        warnings: list[AvroValidationError] = []
        info_messages: list[AvroValidationError] = []

        # Check file exists
        if not schema_path.exists():
            errors.append(AvroValidationError(
                path="",
                message=f"Schema file not found: {schema_path}",
                severity=ValidationSeverity.ERROR,
                rule="file-exists",
            ))
            return AvroValidationResult(
                is_valid=False,
                file_path=str(schema_path),
                errors=errors,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        # Read and parse JSON
        try:
            content = schema_path.read_text(encoding="utf-8")
            schema_data = json.loads(content)
        except json.JSONDecodeError as e:
            errors.append(AvroValidationError(
                path="",
                message=f"Invalid JSON: {str(e)}",
                severity=ValidationSeverity.ERROR,
                rule="valid-json",
            ))
            return AvroValidationResult(
                is_valid=False,
                file_path=str(schema_path),
                errors=errors,
                validation_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            errors.append(AvroValidationError(
                path="",
                message=f"Failed to read schema file: {str(e)}",
                severity=ValidationSeverity.ERROR,
                rule="readable-file",
            ))
            return AvroValidationResult(
                is_valid=False,
                file_path=str(schema_path),
                errors=errors,
                validation_time_ms=(time.time() - start_time) * 1000,
            )

        return self._validate_schema_data(schema_data, str(schema_path), start_time)

    def validate_schema_data(self, schema_data: Any) -> AvroValidationResult:
        """
        Validate Avro schema from parsed data.

        Args:
            schema_data: Parsed Avro schema (dict, list, or string).

        Returns:
            AvroValidationResult with validation details.
        """
        self._named_types = {}
        return self._validate_schema_data(schema_data, None, time.time())

    def _validate_schema_data(
        self,
        schema_data: Any,
        file_path: Optional[str],
        start_time: float
    ) -> AvroValidationResult:
        """Internal method to validate schema data."""
        errors: list[AvroValidationError] = []
        warnings: list[AvroValidationError] = []
        info_messages: list[AvroValidationError] = []

        # Validate the schema structure
        validation_errors = self._validate_type("/", schema_data)
        for err in validation_errors:
            if err.severity == ValidationSeverity.ERROR:
                errors.append(err)
            elif err.severity == ValidationSeverity.WARNING:
                warnings.append(err)
            else:
                info_messages.append(err)

        # Parse schema if valid
        parsed_schema = None
        schema_type = None
        if not errors:
            try:
                parsed_schema = self._parse_schema(schema_data, file_path)
                schema_type = parsed_schema.type
            except Exception as e:
                errors.append(AvroValidationError(
                    path="/",
                    message=f"Failed to parse schema: {str(e)}",
                    severity=ValidationSeverity.ERROR,
                    rule="parseable-schema",
                ))

        # Limit errors if configured
        if self.config.max_errors > 0:
            errors = errors[:self.config.max_errors]

        validation_time_ms = (time.time() - start_time) * 1000

        return AvroValidationResult(
            is_valid=len(errors) == 0,
            file_path=file_path,
            schema_type=schema_type,
            parsed_schema=parsed_schema,
            errors=errors,
            warnings=warnings if self.config.include_warnings else [],
            info_messages=info_messages,
            validation_time_ms=validation_time_ms,
        )

    def _validate_type(
        self,
        path: str,
        schema: Any,
        in_union: bool = False
    ) -> list[AvroValidationError]:
        """Validate a type definition."""
        errors: list[AvroValidationError] = []

        if schema is None:
            errors.append(AvroValidationError(
                path=path,
                message="Schema cannot be null",
                severity=ValidationSeverity.ERROR,
                rule="non-null-schema",
            ))
            return errors

        # String type (primitive or named type reference)
        if isinstance(schema, str):
            return self._validate_string_type(path, schema)

        # Array (union type)
        if isinstance(schema, list):
            return self._validate_union(path, schema)

        # Object (complex type)
        if isinstance(schema, dict):
            return self._validate_complex_type(path, schema, in_union)

        errors.append(AvroValidationError(
            path=path,
            message=f"Invalid schema type: {type(schema).__name__}",
            severity=ValidationSeverity.ERROR,
            rule="valid-schema-type",
        ))
        return errors

    def _validate_string_type(
        self,
        path: str,
        type_name: str
    ) -> list[AvroValidationError]:
        """Validate a string type reference."""
        errors: list[AvroValidationError] = []

        if type_name in self.PRIMITIVE_TYPES:
            return errors

        # Check if it's a previously defined named type
        if type_name in self._named_types:
            return errors

        # Check with namespace
        for full_name in self._named_types:
            if full_name.endswith("." + type_name):
                return errors

        errors.append(AvroValidationError(
            path=path,
            message=f"Unknown type: '{type_name}'",
            severity=ValidationSeverity.ERROR,
            rule="known-type",
        ))
        return errors

    def _validate_union(
        self,
        path: str,
        union_types: list[Any]
    ) -> list[AvroValidationError]:
        """Validate a union type."""
        errors: list[AvroValidationError] = []

        if not union_types:
            errors.append(AvroValidationError(
                path=path,
                message="Union types cannot be empty",
                severity=ValidationSeverity.ERROR,
                rule="non-empty-union",
            ))
            return errors

        # Check for duplicate types
        type_names: set[str] = set()
        for i, union_type in enumerate(union_types):
            type_path = f"{path}[{i}]"

            # Validate each type in the union
            type_errors = self._validate_type(type_path, union_type, in_union=True)
            errors.extend(type_errors)

            # Get type name for duplicate check
            type_name = self._get_type_name(union_type)
            if type_name in type_names:
                errors.append(AvroValidationError(
                    path=type_path,
                    message=f"Duplicate type in union: '{type_name}'",
                    severity=ValidationSeverity.ERROR,
                    rule="no-duplicate-union-types",
                ))
            type_names.add(type_name)

        # Unions cannot directly contain other unions
        for i, union_type in enumerate(union_types):
            if isinstance(union_type, list):
                errors.append(AvroValidationError(
                    path=f"{path}[{i}]",
                    message="Unions cannot directly contain other unions",
                    severity=ValidationSeverity.ERROR,
                    rule="no-nested-unions",
                ))

        return errors

    def _get_type_name(self, schema: Any) -> str:
        """Get the type name from a schema for duplicate checking."""
        if isinstance(schema, str):
            return schema
        if isinstance(schema, dict):
            if "type" in schema:
                type_val = schema["type"]
                if type_val in self.COMPLEX_TYPES and "name" in schema:
                    return cast(str, schema.get("name", type_val))
                return cast(str, type_val)
        return str(schema)

    def _validate_complex_type(
        self,
        path: str,
        schema: dict[str, Any],
        in_union: bool = False
    ) -> list[AvroValidationError]:
        """Validate a complex type definition."""
        errors: list[AvroValidationError] = []

        if "type" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Missing required field: 'type'",
                severity=ValidationSeverity.ERROR,
                rule="required-type-field",
            ))
            return errors

        type_val = schema["type"]

        if type_val == "record":
            errors.extend(self._validate_record(path, schema))
        elif type_val == "enum":
            errors.extend(self._validate_enum(path, schema))
        elif type_val == "array":
            errors.extend(self._validate_array(path, schema))
        elif type_val == "map":
            errors.extend(self._validate_map(path, schema))
        elif type_val == "fixed":
            errors.extend(self._validate_fixed(path, schema))
        elif type_val in self.PRIMITIVE_TYPES:
            # Primitive type with annotations (e.g., logical type)
            errors.extend(self._validate_annotated_primitive(path, schema))
        else:
            errors.append(AvroValidationError(
                path=path,
                message=f"Unknown type: '{type_val}'",
                severity=ValidationSeverity.ERROR,
                rule="known-type",
            ))

        return errors

    def _validate_record(
        self,
        path: str,
        schema: dict[str, Any]
    ) -> list[AvroValidationError]:
        """Validate a record type."""
        errors: list[AvroValidationError] = []

        # Check required name field
        if "name" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Record type requires 'name' field",
                severity=ValidationSeverity.ERROR,
                rule="record-has-name",
            ))
            return errors

        name = schema["name"]
        namespace = schema.get("namespace", "")

        # Validate name format
        if not self._is_valid_name(name):
            errors.append(AvroValidationError(
                path=f"{path}/name",
                message=f"Invalid name format: '{name}'",
                severity=ValidationSeverity.ERROR,
                rule="valid-name",
            ))

        # Register the named type
        full_name = f"{namespace}.{name}" if namespace else name
        self._named_types[full_name] = schema

        # Check for fields
        if "fields" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Record type requires 'fields' field",
                severity=ValidationSeverity.ERROR,
                rule="record-has-fields",
            ))
            return errors

        fields = schema["fields"]
        if not isinstance(fields, list):
            errors.append(AvroValidationError(
                path=f"{path}/fields",
                message="Fields must be an array",
                severity=ValidationSeverity.ERROR,
                rule="fields-is-array",
            ))
            return errors

        # Validate each field
        field_names: set[str] = set()
        for i, field in enumerate(fields):
            field_path = f"{path}/fields[{i}]"
            field_errors = self._validate_field(field_path, field, field_names)
            errors.extend(field_errors)

        # Check documentation if required
        if self.config.require_doc and "doc" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message=f"Record '{name}' should have documentation",
                severity=ValidationSeverity.WARNING,
                rule="doc-recommended",
            ))

        # Check naming convention
        if self.config.check_naming_conventions:
            if not re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
                errors.append(AvroValidationError(
                    path=f"{path}/name",
                    message=f"Record name '{name}' should be PascalCase",
                    severity=ValidationSeverity.WARNING,
                    rule="naming-convention",
                ))

        return errors

    def _validate_field(
        self,
        path: str,
        field: Any,
        existing_names: set[str]
    ) -> list[AvroValidationError]:
        """Validate a record field."""
        errors: list[AvroValidationError] = []

        if not isinstance(field, dict):
            errors.append(AvroValidationError(
                path=path,
                message="Field must be an object",
                severity=ValidationSeverity.ERROR,
                rule="field-is-object",
            ))
            return errors

        # Check required name
        if "name" not in field:
            errors.append(AvroValidationError(
                path=path,
                message="Field requires 'name'",
                severity=ValidationSeverity.ERROR,
                rule="field-has-name",
            ))
            return errors

        name = field["name"]

        # Validate name format
        if not self._is_valid_name(name):
            errors.append(AvroValidationError(
                path=f"{path}/name",
                message=f"Invalid field name format: '{name}'",
                severity=ValidationSeverity.ERROR,
                rule="valid-field-name",
            ))

        # Check for duplicate names
        if name in existing_names:
            errors.append(AvroValidationError(
                path=f"{path}/name",
                message=f"Duplicate field name: '{name}'",
                severity=ValidationSeverity.ERROR,
                rule="unique-field-names",
            ))
        existing_names.add(name)

        # Check required type
        if "type" not in field:
            errors.append(AvroValidationError(
                path=path,
                message=f"Field '{name}' requires 'type'",
                severity=ValidationSeverity.ERROR,
                rule="field-has-type",
            ))
            return errors

        # Validate field type
        type_errors = self._validate_type(f"{path}/type", field["type"])
        errors.extend(type_errors)

        # Validate order if present
        if "order" in field:
            order = field["order"]
            if order not in self.VALID_ORDERS:
                errors.append(AvroValidationError(
                    path=f"{path}/order",
                    message=f"Invalid order value: '{order}'. Must be one of {self.VALID_ORDERS}",
                    severity=ValidationSeverity.ERROR,
                    rule="valid-order",
                ))

        # Check documentation if required
        if self.config.require_doc and "doc" not in field:
            errors.append(AvroValidationError(
                path=path,
                message=f"Field '{name}' should have documentation",
                severity=ValidationSeverity.WARNING,
                rule="doc-recommended",
            ))

        # Check default for optional fields
        if self.config.require_default:
            if self._is_optional_type(field["type"]) and "default" not in field:
                errors.append(AvroValidationError(
                    path=path,
                    message=f"Optional field '{name}' should have a default value",
                    severity=ValidationSeverity.WARNING,
                    rule="default-recommended",
                ))

        # Check naming convention
        if self.config.check_naming_conventions:
            if not re.match(r'^[a-z][a-zA-Z0-9_]*$', name):
                errors.append(AvroValidationError(
                    path=f"{path}/name",
                    message=f"Field name '{name}' should be camelCase or snake_case",
                    severity=ValidationSeverity.WARNING,
                    rule="naming-convention",
                ))

        return errors

    def _is_optional_type(self, type_def: Any) -> bool:
        """Check if a type definition is optional (contains null)."""
        if isinstance(type_def, list):
            return "null" in type_def
        return False

    def _validate_enum(
        self,
        path: str,
        schema: dict[str, Any]
    ) -> list[AvroValidationError]:
        """Validate an enum type."""
        errors: list[AvroValidationError] = []

        # Check required name
        if "name" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Enum type requires 'name' field",
                severity=ValidationSeverity.ERROR,
                rule="enum-has-name",
            ))
            return errors

        name = schema["name"]
        namespace = schema.get("namespace", "")

        # Validate name format
        if not self._is_valid_name(name):
            errors.append(AvroValidationError(
                path=f"{path}/name",
                message=f"Invalid name format: '{name}'",
                severity=ValidationSeverity.ERROR,
                rule="valid-name",
            ))

        # Register the named type
        full_name = f"{namespace}.{name}" if namespace else name
        self._named_types[full_name] = schema

        # Check required symbols
        if "symbols" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Enum type requires 'symbols' field",
                severity=ValidationSeverity.ERROR,
                rule="enum-has-symbols",
            ))
            return errors

        symbols = schema["symbols"]
        if not isinstance(symbols, list):
            errors.append(AvroValidationError(
                path=f"{path}/symbols",
                message="Symbols must be an array",
                severity=ValidationSeverity.ERROR,
                rule="symbols-is-array",
            ))
            return errors

        if not symbols:
            errors.append(AvroValidationError(
                path=f"{path}/symbols",
                message="Enum must have at least one symbol",
                severity=ValidationSeverity.ERROR,
                rule="non-empty-symbols",
            ))

        # Validate symbols
        seen_symbols: set[str] = set()
        for i, symbol in enumerate(symbols):
            if not isinstance(symbol, str):
                errors.append(AvroValidationError(
                    path=f"{path}/symbols[{i}]",
                    message=f"Symbol must be a string, got {type(symbol).__name__}",
                    severity=ValidationSeverity.ERROR,
                    rule="symbol-is-string",
                ))
                continue

            if not self._is_valid_name(symbol):
                errors.append(AvroValidationError(
                    path=f"{path}/symbols[{i}]",
                    message=f"Invalid symbol format: '{symbol}'",
                    severity=ValidationSeverity.ERROR,
                    rule="valid-symbol",
                ))

            if symbol in seen_symbols:
                errors.append(AvroValidationError(
                    path=f"{path}/symbols[{i}]",
                    message=f"Duplicate symbol: '{symbol}'",
                    severity=ValidationSeverity.ERROR,
                    rule="unique-symbols",
                ))
            seen_symbols.add(symbol)

            # Check naming convention
            if self.config.check_naming_conventions:
                if not re.match(r'^[A-Z][A-Z0-9_]*$', symbol):
                    errors.append(AvroValidationError(
                        path=f"{path}/symbols[{i}]",
                        message=f"Symbol '{symbol}' should be SCREAMING_SNAKE_CASE",
                        severity=ValidationSeverity.WARNING,
                        rule="naming-convention",
                    ))

        # Validate default if present
        if "default" in schema:
            default = schema["default"]
            if default not in symbols:
                errors.append(AvroValidationError(
                    path=f"{path}/default",
                    message=f"Default value '{default}' is not in symbols",
                    severity=ValidationSeverity.ERROR,
                    rule="valid-default",
                ))

        return errors

    def _validate_array(
        self,
        path: str,
        schema: dict[str, Any]
    ) -> list[AvroValidationError]:
        """Validate an array type."""
        errors: list[AvroValidationError] = []

        if "items" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Array type requires 'items' field",
                severity=ValidationSeverity.ERROR,
                rule="array-has-items",
            ))
            return errors

        # Validate items type
        items_errors = self._validate_type(f"{path}/items", schema["items"])
        errors.extend(items_errors)

        return errors

    def _validate_map(
        self,
        path: str,
        schema: dict[str, Any]
    ) -> list[AvroValidationError]:
        """Validate a map type."""
        errors: list[AvroValidationError] = []

        if "values" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Map type requires 'values' field",
                severity=ValidationSeverity.ERROR,
                rule="map-has-values",
            ))
            return errors

        # Validate values type
        values_errors = self._validate_type(f"{path}/values", schema["values"])
        errors.extend(values_errors)

        return errors

    def _validate_fixed(
        self,
        path: str,
        schema: dict[str, Any]
    ) -> list[AvroValidationError]:
        """Validate a fixed type."""
        errors: list[AvroValidationError] = []

        # Check required name
        if "name" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Fixed type requires 'name' field",
                severity=ValidationSeverity.ERROR,
                rule="fixed-has-name",
            ))
            return errors

        name = schema["name"]
        namespace = schema.get("namespace", "")

        # Validate name format
        if not self._is_valid_name(name):
            errors.append(AvroValidationError(
                path=f"{path}/name",
                message=f"Invalid name format: '{name}'",
                severity=ValidationSeverity.ERROR,
                rule="valid-name",
            ))

        # Register the named type
        full_name = f"{namespace}.{name}" if namespace else name
        self._named_types[full_name] = schema

        # Check required size
        if "size" not in schema:
            errors.append(AvroValidationError(
                path=path,
                message="Fixed type requires 'size' field",
                severity=ValidationSeverity.ERROR,
                rule="fixed-has-size",
            ))
            return errors

        size = schema["size"]
        if not isinstance(size, int) or size < 1:
            errors.append(AvroValidationError(
                path=f"{path}/size",
                message=f"Size must be a positive integer, got {size}",
                severity=ValidationSeverity.ERROR,
                rule="valid-size",
            ))

        return errors

    def _validate_annotated_primitive(
        self,
        path: str,
        schema: dict[str, Any]
    ) -> list[AvroValidationError]:
        """Validate an annotated primitive type (e.g., with logical type)."""
        errors: list[AvroValidationError] = []

        if "logicalType" in schema:
            logical_type = schema["logicalType"]
            if logical_type not in self.KNOWN_LOGICAL_TYPES:
                if self.config.allow_unknown_logical_types:
                    errors.append(AvroValidationError(
                        path=f"{path}/logicalType",
                        message=f"Unknown logical type: '{logical_type}'",
                        severity=ValidationSeverity.INFO,
                        rule="known-logical-type",
                    ))
                else:
                    errors.append(AvroValidationError(
                        path=f"{path}/logicalType",
                        message=f"Unknown logical type: '{logical_type}'",
                        severity=ValidationSeverity.ERROR,
                        rule="known-logical-type",
                    ))

            # Validate logical type constraints
            base_type = schema["type"]
            if logical_type == "decimal":
                if "precision" not in schema:
                    errors.append(AvroValidationError(
                        path=path,
                        message="Decimal logical type requires 'precision'",
                        severity=ValidationSeverity.ERROR,
                        rule="decimal-has-precision",
                    ))

        return errors

    def _is_valid_name(self, name: str) -> bool:
        """Check if a name is valid according to Avro spec."""
        # Must start with [A-Za-z_] and contain only [A-Za-z0-9_]
        return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name))

    def _parse_schema(
        self,
        schema_data: Any,
        file_path: Optional[str]
    ) -> AvroSchema:
        """Parse schema data into AvroSchema model."""
        if isinstance(schema_data, str):
            return AvroSchema(type=schema_data, file_path=file_path)

        if isinstance(schema_data, list):
            return AvroSchema(type="union", raw_schema={"union": schema_data}, file_path=file_path)

        if isinstance(schema_data, dict):
            fields = None
            if "fields" in schema_data:
                fields = [
                    AvroField(
                        name=f["name"],
                        type=f["type"],
                        default=f.get("default"),
                        doc=f.get("doc"),
                        order=f.get("order"),
                        aliases=f.get("aliases"),
                    )
                    for f in schema_data["fields"]
                ]

            return AvroSchema(
                type=schema_data.get("type", "unknown"),
                name=schema_data.get("name"),
                namespace=schema_data.get("namespace"),
                doc=schema_data.get("doc"),
                fields=fields,
                symbols=schema_data.get("symbols"),
                items=schema_data.get("items"),
                values=schema_data.get("values"),
                size=schema_data.get("size"),
                aliases=schema_data.get("aliases"),
                logical_type=schema_data.get("logicalType"),
                raw_schema=schema_data,
                file_path=file_path,
            )

        return AvroSchema(type="unknown", file_path=file_path)

    def generate_report(
        self,
        result: AvroValidationResult,
        format: str = "text"
    ) -> str:
        """
        Generate a validation report.

        Args:
            result: Validation result to report.
            format: Output format (text, json, markdown).

        Returns:
            Formatted report string.
        """
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: AvroValidationResult) -> str:
        """Generate a text format report."""
        lines = []
        lines.append("=" * 60)
        lines.append("Avro Schema Validation Report")
        lines.append("=" * 60)
        lines.append(f"File: {result.file_path or 'N/A'}")
        lines.append(f"Type: {result.schema_type or 'Unknown'}")
        lines.append(f"Valid: {'Yes' if result.is_valid else 'No'}")
        lines.append(f"Errors: {result.error_count}")
        lines.append(f"Warnings: {result.warning_count}")
        lines.append(f"Time: {result.validation_time_ms:.2f}ms")
        lines.append("-" * 60)

        if result.parsed_schema:
            lines.append(f"Name: {result.parsed_schema.full_name}")
            if result.parsed_schema.fields:
                lines.append(f"Fields: {result.parsed_schema.field_count}")
            if result.parsed_schema.symbols:
                lines.append(f"Symbols: {len(result.parsed_schema.symbols)}")
            lines.append("-" * 60)

        if result.errors:
            lines.append("\nErrors:")
            for error in result.errors:
                lines.append(f"  [{error.rule or 'error'}] {error.path}: {error.message}")

        if result.warnings:
            lines.append("\nWarnings:")
            for warning in result.warnings:
                lines.append(f"  [{warning.rule or 'warning'}] {warning.path}: {warning.message}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def _generate_markdown_report(self, result: AvroValidationResult) -> str:
        """Generate a markdown format report."""
        lines = []
        lines.append("# Avro Schema Validation Report\n")
        lines.append(f"- **File**: {result.file_path or 'N/A'}")
        lines.append(f"- **Type**: {result.schema_type or 'Unknown'}")
        lines.append(f"- **Valid**: {'Yes' if result.is_valid else 'No'}")
        lines.append(f"- **Errors**: {result.error_count}")
        lines.append(f"- **Warnings**: {result.warning_count}")
        lines.append(f"- **Time**: {result.validation_time_ms:.2f}ms\n")

        if result.parsed_schema:
            lines.append("## Schema Summary\n")
            lines.append(f"- **Name**: {result.schema.full_name}")
            if result.schema.fields:
                lines.append(f"- **Fields**: {result.schema.field_count}")
            if result.schema.symbols:
                lines.append(f"- **Symbols**: {len(result.schema.symbols)}\n")

        if result.errors:
            lines.append("## Errors\n")
            lines.append("| Path | Rule | Message |")
            lines.append("|------|------|---------|")
            for error in result.errors:
                lines.append(f"| `{error.path}` | {error.rule or 'error'} | {error.message} |")

        if result.warnings:
            lines.append("\n## Warnings\n")
            lines.append("| Path | Rule | Message |")
            lines.append("|------|------|---------|")
            for warning in result.warnings:
                lines.append(f"| `{warning.path}` | {warning.rule or 'warning'} | {warning.message} |")

        return "\n".join(lines)
