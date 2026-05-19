"""
L0 Unit Tests for Avro Validator Service.

Tests the AvroValidatorService for parsing and validating
Apache Avro schema files and content.
"""

import json
import tempfile
from pathlib import Path

import pytest

from Asgard.Forseti.Avro.models.avro_models import (
    AvroConfig,
    AvroSchemaType,
    ValidationSeverity,
)
from Asgard.Forseti.Avro.services.avro_validator_service import (
    AvroValidatorService,
)


class TestAvroValidatorServiceInit:
    """Tests for AvroValidatorService initialization."""

    def test_init_default_config(self):
        """Test initialization with default configuration."""
        service = AvroValidatorService()
        assert service.config is not None
        assert service.config.strict_mode is False
        assert service.config.check_naming_conventions is True

    def test_init_custom_config(self):
        """Test initialization with custom configuration."""
        config = AvroConfig(
            strict_mode=True,
            require_doc=True,
        )
        service = AvroValidatorService(config)
        assert service.config.strict_mode is True
        assert service.config.require_doc is True


class TestAvroValidatorServiceValidateFile:
    """Tests for file validation functionality."""

    def test_validate_nonexistent_file(self):
        """Test validation of a file that doesn't exist."""
        service = AvroValidatorService()
        result = service.validate("/nonexistent/path.avsc")
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message.lower()

    def test_validate_valid_record_schema(self, tmp_path):
        """Test validation of a valid record schema."""
        schema = {
            "type": "record",
            "name": "User",
            "namespace": "com.example",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "age", "type": "int"},
                {"name": "email", "type": ["null", "string"], "default": None},
            ]
        }
        schema_file = tmp_path / "user.avsc"
        schema_file.write_text(json.dumps(schema, indent=2))

        service = AvroValidatorService()
        result = service.validate(schema_file)

        assert result.is_valid is True
        assert result.parsed_schema is not None
        assert result.parsed_schema.name == "User"
        assert result.parsed_schema.namespace == "com.example"

    def test_validate_invalid_json(self, tmp_path):
        """Test validation of invalid JSON."""
        schema_file = tmp_path / "invalid.avsc"
        schema_file.write_text("{ not valid json }")

        service = AvroValidatorService()
        result = service.validate(schema_file)

        assert result.is_valid is False
        assert len(result.errors) > 0


class TestAvroValidatorServiceValidateSchemaData:
    """Tests for schema data validation functionality."""

    def test_validate_primitive_schema(self):
        """Test validation of primitive type schemas."""
        for ptype in ["null", "boolean", "int", "long", "float", "double", "bytes", "string"]:
            service = AvroValidatorService()
            result = service.validate_schema_data(ptype)
            assert result.is_valid is True

    def test_validate_record_schema(self):
        """Test validation of a record schema."""
        schema = {
            "type": "record",
            "name": "SimpleRecord",
            "fields": [
                {"name": "field1", "type": "string"},
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True
        assert result.parsed_schema is not None

    def test_validate_enum_schema(self):
        """Test validation of an enum schema."""
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["UNKNOWN", "ACTIVE", "INACTIVE"]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_array_schema(self):
        """Test validation of an array schema."""
        schema = {
            "type": "array",
            "items": "string"
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_map_schema(self):
        """Test validation of a map schema."""
        schema = {
            "type": "map",
            "values": "int"
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_union_schema(self):
        """Test validation of a union schema."""
        schema = ["null", "string", "int"]
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_validate_fixed_schema(self):
        """Test validation of a fixed schema."""
        schema = {
            "type": "fixed",
            "name": "MD5",
            "size": 16
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True


class TestAvroValidatorServiceRecordValidation:
    """Tests for record schema validation."""

    def test_record_missing_name(self):
        """Test that record without name is invalid."""
        schema = {
            "type": "record",
            "fields": [
                {"name": "field1", "type": "string"},
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("name" in err.message.lower() for err in result.errors)

    def test_record_missing_fields(self):
        """Test that record without fields is invalid."""
        schema = {
            "type": "record",
            "name": "EmptyRecord",
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False
        assert any("fields" in err.message.lower() for err in result.errors)

    def test_record_with_optional_fields(self):
        """Test record with optional namespace and doc."""
        schema = {
            "type": "record",
            "name": "DocumentedRecord",
            "namespace": "com.example.docs",
            "doc": "A well-documented record",
            "fields": [
                {"name": "value", "type": "string", "doc": "The value field"}
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True
        assert result.parsed_schema.doc == "A well-documented record"

    def test_record_nested_records(self):
        """Test record containing nested records."""
        schema = {
            "type": "record",
            "name": "Outer",
            "fields": [
                {
                    "name": "inner",
                    "type": {
                        "type": "record",
                        "name": "Inner",
                        "fields": [
                            {"name": "value", "type": "string"}
                        ]
                    }
                }
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True


class TestAvroValidatorServiceFieldValidation:
    """Tests for field validation."""

    def test_field_missing_name(self):
        """Test that field without name is invalid."""
        schema = {
            "type": "record",
            "name": "TestRecord",
            "fields": [
                {"type": "string"}
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_field_missing_type(self):
        """Test that field without type is invalid."""
        schema = {
            "type": "record",
            "name": "TestRecord",
            "fields": [
                {"name": "field1"}
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_field_with_default(self):
        """Test field with default value."""
        schema = {
            "type": "record",
            "name": "TestRecord",
            "fields": [
                {"name": "value", "type": "string", "default": "default_value"}
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_field_with_sort_order(self):
        """Test field with sort order."""
        for order in ["ascending", "descending", "ignore"]:
            schema = {
                "type": "record",
                "name": "TestRecord",
                "fields": [
                    {"name": "value", "type": "string", "order": order}
                ]
            }
            service = AvroValidatorService()
            result = service.validate_schema_data(schema)
            assert result.is_valid is True


class TestAvroValidatorServiceEnumValidation:
    """Tests for enum schema validation."""

    def test_enum_missing_name(self):
        """Test that enum without name is invalid."""
        schema = {
            "type": "enum",
            "symbols": ["A", "B"]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_enum_missing_symbols(self):
        """Test that enum without symbols is invalid."""
        schema = {
            "type": "enum",
            "name": "TestEnum"
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_enum_empty_symbols(self):
        """Test that enum with empty symbols is invalid."""
        schema = {
            "type": "enum",
            "name": "TestEnum",
            "symbols": []
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_enum_with_default(self):
        """Test enum with default value."""
        schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["UNKNOWN", "ACTIVE", "INACTIVE"],
            "default": "UNKNOWN"
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True


class TestAvroValidatorServiceFixedValidation:
    """Tests for fixed schema validation."""

    def test_fixed_missing_name(self):
        """Test that fixed without name is invalid."""
        schema = {
            "type": "fixed",
            "size": 16
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_fixed_missing_size(self):
        """Test that fixed without size is invalid."""
        schema = {
            "type": "fixed",
            "name": "TestFixed"
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False

    def test_fixed_invalid_size(self):
        """Test that fixed with invalid size is invalid."""
        schema = {
            "type": "fixed",
            "name": "TestFixed",
            "size": -1
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False


class TestAvroValidatorServiceUnionValidation:
    """Tests for union schema validation."""

    def test_union_empty(self):
        """Test that empty union is invalid."""
        schema = []
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is False


class TestAvroValidatorServiceLogicalTypes:
    """Tests for logical type validation."""

    def test_decimal_logical_type(self):
        """Test decimal logical type."""
        schema = {
            "type": "bytes",
            "logicalType": "decimal",
            "precision": 10,
            "scale": 2
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_date_logical_type(self):
        """Test date logical type."""
        schema = {
            "type": "int",
            "logicalType": "date"
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_uuid_logical_type(self):
        """Test uuid logical type."""
        schema = {
            "type": "string",
            "logicalType": "uuid"
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_timestamp_logical_types(self):
        """Test timestamp logical types."""
        for logical_type in ["timestamp-millis", "timestamp-micros"]:
            schema = {
                "type": "long",
                "logicalType": logical_type
            }
            service = AvroValidatorService()
            result = service.validate_schema_data(schema)
            assert result.is_valid is True


class TestAvroValidatorServiceValidationTime:
    """Tests for validation timing."""

    def test_validation_time_reported(self):
        """Test that validation time is reported."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.validation_time_ms > 0
        assert result.validation_time_ms < 1000  # Should be fast


class TestAvroValidatorServiceEdgeCases:
    """Tests for edge cases and error handling."""

    def test_complex_nested_schema(self):
        """Test handling of complex nested schema."""
        schema = {
            "type": "record",
            "name": "ComplexRecord",
            "namespace": "com.example",
            "fields": [
                {
                    "name": "users",
                    "type": {
                        "type": "array",
                        "items": {
                            "type": "record",
                            "name": "User",
                            "fields": [
                                {"name": "name", "type": "string"},
                                {
                                    "name": "address",
                                    "type": ["null", {
                                        "type": "record",
                                        "name": "Address",
                                        "fields": [
                                            {"name": "street", "type": "string"},
                                            {"name": "city", "type": "string"}
                                        ]
                                    }]
                                }
                            ]
                        }
                    }
                }
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_recursive_schema(self):
        """Test handling of recursive schema definitions."""
        schema = {
            "type": "record",
            "name": "Node",
            "fields": [
                {"name": "value", "type": "string"},
                {"name": "children", "type": {"type": "array", "items": "Node"}}
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True

    def test_aliases(self):
        """Test handling of aliases."""
        schema = {
            "type": "record",
            "name": "User",
            "aliases": ["Person", "Member"],
            "fields": [
                {
                    "name": "fullName",
                    "type": "string",
                    "aliases": ["name", "displayName"]
                }
            ]
        }
        service = AvroValidatorService()
        result = service.validate_schema_data(schema)

        assert result.is_valid is True
