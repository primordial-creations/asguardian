"""
Comprehensive L0 unit tests for Avro Validator Service.

Tests the AvroValidatorService for:
- Valid and invalid avro schema validation
- Type validation (primitives, records, enums, arrays, maps, unions)
- Field validation
- Logical type validation
- Naming convention checking
"""

import pytest
import tempfile
import json
from pathlib import Path

from Asgard.Forseti.Avro.models.avro_models import (
    AvroConfig,
    AvroSchemaType,
    ValidationSeverity,
    CompatibilityMode,
)
from Asgard.Forseti.Avro.services.avro_validator_service import (
    AvroValidatorService,
)


class TestAvroValidatorServiceInit:
    """Test AvroValidatorService initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        service = AvroValidatorService()

        assert service.config is not None
        assert isinstance(service.config, AvroConfig)
        assert service.config.strict_mode is False

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = AvroConfig(strict_mode=True, max_errors=25)
        service = AvroValidatorService(config)

        assert service.config.strict_mode is True
        assert service.config.max_errors == 25


class TestAvroValidatorServiceValidateFile:
    """Test file validation functionality."""

    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file."""
        service = AvroValidatorService()
        result = service.validate_file("/nonexistent/schema.avsc")

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message.lower()

    def test_validate_valid_record_schema_file(self):
        """Test validation of valid record schema file."""
        service = AvroValidatorService()

        schema = {
            "type": "record",
            "name": "User",
            "namespace": "com.example",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "age", "type": "int"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.avsc', delete=False) as f:
            json.dump(schema, f)
            temp_path = f.name

        try:
            result = service.validate_file(temp_path)

            assert result.is_valid is True
            assert result.schema_type == "record"
            assert result.parsed_schema is not None
            assert result.parsed_schema.name == "User"
        finally:
            Path(temp_path).unlink()

    def test_validate_invalid_json_file(self):
        """Test validation of file with invalid JSON."""
        service = AvroValidatorService()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.avsc', delete=False) as f:
            f.write("{ invalid json")
            temp_path = f.name

        try:
            result = service.validate_file(temp_path)

            assert result.is_valid is False
            assert any("JSON" in e.message for e in result.errors)
        finally:
            Path(temp_path).unlink()


class TestAvroValidatorServiceValidatePrimitiveTypes:
    """Test primitive type validation."""

    def test_validate_string_type(self):
        """Test validation of string primitive type."""
        service = AvroValidatorService()
        result = service.validate_schema_data("string")

        assert result.is_valid is True
        assert result.schema_type == "string"

    def test_validate_int_type(self):
        """Test validation of int primitive type."""
        service = AvroValidatorService()
        result = service.validate_schema_data("int")

        assert result.is_valid is True

    def test_validate_all_primitive_types(self):
        """Test validation of all primitive types."""
        service = AvroValidatorService()
        primitives = ["null", "boolean", "int", "long", "float", "double", "bytes", "string"]

        for prim_type in primitives:
            result = service.validate_schema_data(prim_type)
            assert result.is_valid is True

    def test_validate_unknown_primitive_type(self):
        """Test validation of unknown primitive type."""
        service = AvroValidatorService()
        result = service.validate_schema_data("unknown_type")

        assert result.is_valid is False
        assert any("Unknown type" in e.message for e in result.errors)


class TestAvroValidatorServiceValidateRecord:
    """Test record type validation."""

    def test_validate_valid_record(self):
        """Test validation of valid record schema."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Person",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "age", "type": "int"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True
        assert result.parsed_schema.name == "Person"
        assert len(result.parsed_schema.fields) == 2

    def test_validate_record_without_name(self):
        """Test validation detects record without name."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "fields": []
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("name" in e.message.lower() for e in result.errors)

    def test_validate_record_without_fields(self):
        """Test validation detects record without fields."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Empty"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("fields" in e.message.lower() for e in result.errors)

    def test_validate_record_with_invalid_field_name(self):
        """Test validation detects invalid field name."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "123invalid", "type": "string"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("name format" in e.message.lower() for e in result.errors)

    def test_validate_record_with_duplicate_field_names(self):
        """Test validation detects duplicate field names."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "field1", "type": "string"},
                {"name": "field1", "type": "int"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("duplicate" in e.message.lower() for e in result.errors)

    def test_validate_record_with_namespace(self):
        """Test validation of record with namespace."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "User",
            "namespace": "com.example",
            "fields": []
        }

        result = service.validate_schema_data(schema)

        assert result.parsed_schema.namespace == "com.example"
        assert result.parsed_schema.full_name == "com.example.User"


class TestAvroValidatorServiceValidateEnum:
    """Test enum type validation."""

    def test_validate_valid_enum(self):
        """Test validation of valid enum schema."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE", "PENDING"]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True
        assert result.parsed_schema.name == "Status"
        assert result.parsed_schema.symbols == ["ACTIVE", "INACTIVE", "PENDING"]

    def test_validate_enum_without_name(self):
        """Test validation detects enum without name."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "symbols": ["A", "B"]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("name" in e.message.lower() for e in result.errors)

    def test_validate_enum_without_symbols(self):
        """Test validation detects enum without symbols."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "name": "Status"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("symbols" in e.message.lower() for e in result.errors)

    def test_validate_enum_with_empty_symbols(self):
        """Test validation detects enum with empty symbols array."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": []
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("at least one" in e.message.lower() for e in result.errors)

    def test_validate_enum_with_duplicate_symbols(self):
        """Test validation detects duplicate enum symbols."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE", "ACTIVE"]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("duplicate" in e.message.lower() for e in result.errors)

    def test_validate_enum_with_invalid_symbol_name(self):
        """Test validation detects invalid symbol names."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["123INVALID"]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("symbol format" in e.message.lower() for e in result.errors)

    def test_validate_enum_with_default(self):
        """Test validation of enum with default value."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE"],
            "default": "ACTIVE"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_enum_with_invalid_default(self):
        """Test validation detects default not in symbols."""
        service = AvroValidatorService()
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE"],
            "default": "INACTIVE"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("not in symbols" in e.message.lower() for e in result.errors)


class TestAvroValidatorServiceValidateArray:
    """Test array type validation."""

    def test_validate_valid_array(self):
        """Test validation of valid array schema."""
        service = AvroValidatorService()
        schema = {
            "type": "array",
            "items": "string"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_array_without_items(self):
        """Test validation detects array without items."""
        service = AvroValidatorService()
        schema = {
            "type": "array"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("items" in e.message.lower() for e in result.errors)

    def test_validate_array_with_complex_items(self):
        """Test validation of array with complex item type."""
        service = AvroValidatorService()
        schema = {
            "type": "array",
            "items": {
                "type": "record",
                "name": "Item",
                "fields": [{"name": "value", "type": "int"}]
            }
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True


class TestAvroValidatorServiceValidateMap:
    """Test map type validation."""

    def test_validate_valid_map(self):
        """Test validation of valid map schema."""
        service = AvroValidatorService()
        schema = {
            "type": "map",
            "values": "int"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_map_without_values(self):
        """Test validation detects map without values."""
        service = AvroValidatorService()
        schema = {
            "type": "map"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("values" in e.message.lower() for e in result.errors)


class TestAvroValidatorServiceValidateFixed:
    """Test fixed type validation."""

    def test_validate_valid_fixed(self):
        """Test validation of valid fixed schema."""
        service = AvroValidatorService()
        schema = {
            "type": "fixed",
            "name": "MD5",
            "size": 16
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_fixed_without_name(self):
        """Test validation detects fixed without name."""
        service = AvroValidatorService()
        schema = {
            "type": "fixed",
            "size": 16
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_validate_fixed_without_size(self):
        """Test validation detects fixed without size."""
        service = AvroValidatorService()
        schema = {
            "type": "fixed",
            "name": "Test"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_validate_fixed_with_invalid_size(self):
        """Test validation detects invalid size."""
        service = AvroValidatorService()
        schema = {
            "type": "fixed",
            "name": "Test",
            "size": -1
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("positive integer" in e.message.lower() for e in result.errors)


class TestAvroValidatorServiceValidateUnion:
    """Test union type validation."""

    def test_validate_valid_union(self):
        """Test validation of valid union."""
        service = AvroValidatorService()
        schema = ["null", "string"]

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_empty_union(self):
        """Test validation detects empty union."""
        service = AvroValidatorService()
        schema = []

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("empty" in e.message.lower() for e in result.errors)

    def test_validate_union_with_duplicate_types(self):
        """Test validation detects duplicate types in union."""
        service = AvroValidatorService()
        schema = ["string", "string"]

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("duplicate" in e.message.lower() for e in result.errors)

    def test_validate_union_with_nested_union(self):
        """Test validation detects nested union."""
        service = AvroValidatorService()
        schema = ["string", ["int", "long"]]

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("nested" in e.message.lower() or "union" in e.message.lower() for e in result.errors)


class TestAvroValidatorServiceValidateLogicalTypes:
    """Test logical type validation."""

    def test_validate_timestamp_millis(self):
        """Test validation of timestamp-millis logical type."""
        service = AvroValidatorService()
        schema = {
            "type": "long",
            "logicalType": "timestamp-millis"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_decimal_with_precision(self):
        """Test validation of decimal logical type with precision."""
        service = AvroValidatorService()
        schema = {
            "type": "bytes",
            "logicalType": "decimal",
            "precision": 10,
            "scale": 2
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_decimal_without_precision(self):
        """Test validation detects decimal without precision."""
        service = AvroValidatorService()
        schema = {
            "type": "bytes",
            "logicalType": "decimal"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("precision" in e.message.lower() for e in result.errors)

    def test_validate_unknown_logical_type_allowed(self):
        """Test unknown logical type allowed with config."""
        config = AvroConfig(allow_unknown_logical_types=True)
        service = AvroValidatorService(config)
        schema = {
            "type": "string",
            "logicalType": "custom-type"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True
        assert any(
            "Unknown logical type" in msg.message and msg.severity == ValidationSeverity.INFO
            for msg in result.info_messages
        )

    def test_validate_unknown_logical_type_not_allowed(self):
        """Test unknown logical type not allowed with config."""
        config = AvroConfig(allow_unknown_logical_types=False)
        service = AvroValidatorService(config)
        schema = {
            "type": "string",
            "logicalType": "custom-type"
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("Unknown logical type" in e.message for e in result.errors)


class TestAvroValidatorServiceNamingConventions:
    """Test naming convention checks."""

    def test_check_record_pascal_case(self):
        """Test naming convention check for record names."""
        config = AvroConfig(check_naming_conventions=True)
        service = AvroValidatorService(config)
        schema = {
            "type": "record",
            "name": "bad_record_name",
            "fields": []
        }

        result = service.validate_schema_data(schema)

        assert any("PascalCase" in w.message for w in result.warnings)

    def test_check_field_naming(self):
        """Test naming convention check for field names."""
        config = AvroConfig(check_naming_conventions=True)
        service = AvroValidatorService(config)
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "BadFieldName", "type": "string"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert any("camelCase" in w.message or "snake_case" in w.message for w in result.warnings)

    def test_check_enum_symbol_screaming_snake_case(self):
        """Test naming convention check for enum symbols."""
        config = AvroConfig(check_naming_conventions=True)
        service = AvroValidatorService(config)
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["bad_symbol"]
        }

        result = service.validate_schema_data(schema)

        assert any("SCREAMING_SNAKE_CASE" in w.message for w in result.warnings)


class TestAvroValidatorServiceFieldValidation:
    """Test field-specific validation."""

    def test_validate_field_with_doc(self):
        """Test validation of field with documentation."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "field", "type": "string", "doc": "Field documentation"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_field_with_order(self):
        """Test validation of field with sort order."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "field", "type": "int", "order": "descending"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_field_with_invalid_order(self):
        """Test validation detects invalid sort order."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "field", "type": "int", "order": "invalid"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("order value" in e.message.lower() for e in result.errors)

    def test_validate_field_with_aliases(self):
        """Test validation of field with aliases."""
        service = AvroValidatorService()
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "current_name", "type": "string", "aliases": ["old_name"]}
            ]
        }

        result = service.validate_schema_data(schema)

        assert result.is_valid is True


class TestAvroValidatorServiceConfigOptions:
    """Test configuration options."""

    def test_require_doc_for_record(self):
        """Test require_doc configuration for records."""
        config = AvroConfig(require_doc=True)
        service = AvroValidatorService(config)
        schema = {
            "type": "record",
            "name": "Test",
            "fields": []
        }

        result = service.validate_schema_data(schema)

        assert any("documentation" in w.message.lower() for w in result.warnings)

    def test_require_doc_for_field(self):
        """Test require_doc configuration for fields."""
        config = AvroConfig(require_doc=True)
        service = AvroValidatorService(config)
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "field", "type": "string"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert any("documentation" in w.message.lower() for w in result.warnings)

    def test_max_errors_limit(self):
        """Test that max_errors limits reported errors."""
        config = AvroConfig(max_errors=1)
        service = AvroValidatorService(config)
        schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "f1", "type": "unknown1"},
                {"name": "f2", "type": "unknown2"}
            ]
        }

        result = service.validate_schema_data(schema)

        assert len(result.errors) <= 1


class TestAvroValidatorServiceReportGeneration:
    """Test report generation functionality."""

    def test_generate_text_report(self):
        """Test generation of text format report."""
        service = AvroValidatorService()
        schema = {"type": "record", "name": "Test", "fields": []}

        result = service.validate_schema_data(schema)
        report = service.generate_report(result, format="text")

        assert "Avro Schema Validation Report" in report
        assert "record" in report.lower()

    def test_generate_json_report(self):
        """Test generation of JSON format report."""
        service = AvroValidatorService()
        schema = {"type": "string"}

        result = service.validate_schema_data(schema)
        report = service.generate_report(result, format="json")

        assert "is_valid" in report
        assert "schema_type" in report

    def test_generate_markdown_report(self):
        """Test generation of markdown format report."""
        service = AvroValidatorService()
        schema = {"type": "string"}

        result = service.validate_schema_data(schema)
        report = service.generate_report(result, format="markdown")

        assert "# Avro Schema Validation Report" in report


class TestAvroValidatorServiceEdgeCases:
    """Test edge cases and error conditions."""

    def test_validate_null_schema(self):
        """Test validation of null schema."""
        service = AvroValidatorService()
        result = service.validate_schema_data(None)

        assert result.is_valid is False
        assert any("cannot be null" in e.message.lower() for e in result.errors)

    def test_validate_empty_object(self):
        """Test validation of empty object."""
        service = AvroValidatorService()
        result = service.validate_schema_data({})

        assert result.is_valid is False

    def test_validation_timing(self):
        """Test that validation time is recorded."""
        service = AvroValidatorService()
        schema = {"type": "string"}

        result = service.validate_schema_data(schema)

        assert result.validation_time_ms >= 0.0
