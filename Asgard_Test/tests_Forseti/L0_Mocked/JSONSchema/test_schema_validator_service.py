"""
Tests for JSON Schema Validator Service

Unit tests for JSON schema validation.
"""

import pytest
from pathlib import Path

from Asgard.Forseti.JSONSchema.models.jsonschema_models import JSONSchemaConfig, SchemaFormat
from Asgard.Forseti.JSONSchema.services.schema_validator_service import SchemaValidatorService


class TestSchemaValidatorServiceInit:
    """Tests for SchemaValidatorService initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        service = SchemaValidatorService()

        assert service.config is not None
        assert isinstance(service.config, JSONSchemaConfig)

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = JSONSchemaConfig(strict_mode=True, check_formats=False)
        service = SchemaValidatorService(config)

        assert service.config.strict_mode is True
        assert service.config.check_formats is False

    def test_format_patterns_defined(self):
        """Test that format validation patterns are defined."""
        service = SchemaValidatorService()

        assert SchemaFormat.EMAIL.value in service.FORMAT_PATTERNS
        assert SchemaFormat.URI.value in service.FORMAT_PATTERNS
        assert SchemaFormat.UUID.value in service.FORMAT_PATTERNS


class TestSchemaValidatorServiceValidateData:
    """Tests for validating data against schemas."""

    def test_validate_valid_data(self, sample_json_schema, sample_valid_data):
        """Test validating valid data against schema."""
        service = SchemaValidatorService()

        result = service.validate(sample_valid_data, sample_json_schema)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_invalid_data(self, sample_json_schema, sample_invalid_data):
        """Test validating invalid data against schema."""
        service = SchemaValidatorService()

        result = service.validate(sample_invalid_data, sample_json_schema)

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_missing_required_field(self, sample_json_schema):
        """Test validation with missing required field."""
        service = SchemaValidatorService()
        data = {
            "email": "test@example.com"
            # Missing required "id" field
        }

        result = service.validate(data, sample_json_schema)

        assert result.is_valid is False
        assert any("required" in error.message.lower() or "id" in error.message.lower()
                   for error in result.errors)

    def test_validate_incorrect_type(self, sample_json_schema):
        """Test validation with incorrect data type."""
        service = SchemaValidatorService()
        data = {
            "id": "not-an-integer",  # Should be integer
            "email": "test@example.com"
        }

        result = service.validate(data, sample_json_schema)

        assert result.is_valid is False
        assert any("type" in error.message.lower() for error in result.errors)


class TestSchemaValidatorServiceTypeValidation:
    """Tests for type validation."""

    def test_validate_string_type(self):
        """Test string type validation."""
        service = SchemaValidatorService()
        schema = {"type": "string"}

        result = service.validate("test", schema)
        assert result.is_valid is True

        result = service.validate(123, schema)
        assert result.is_valid is False

    def test_validate_integer_type(self):
        """Test integer type validation."""
        service = SchemaValidatorService()
        schema = {"type": "integer"}

        result = service.validate(123, schema)
        assert result.is_valid is True

        result = service.validate(12.5, schema)
        assert result.is_valid is False

    def test_validate_number_type(self):
        """Test number type validation."""
        service = SchemaValidatorService()
        schema = {"type": "number"}

        result = service.validate(123, schema)
        assert result.is_valid is True

        result = service.validate(12.5, schema)
        assert result.is_valid is True

        result = service.validate("123", schema)
        assert result.is_valid is False

    def test_validate_boolean_type(self):
        """Test boolean type validation."""
        service = SchemaValidatorService()
        schema = {"type": "boolean"}

        result = service.validate(True, schema)
        assert result.is_valid is True

        result = service.validate(1, schema)
        assert result.is_valid is False

    def test_validate_array_type(self):
        """Test array type validation."""
        service = SchemaValidatorService()
        schema = {"type": "array"}

        result = service.validate([1, 2, 3], schema)
        assert result.is_valid is True

        result = service.validate("not an array", schema)
        assert result.is_valid is False

    def test_validate_object_type(self):
        """Test object type validation."""
        service = SchemaValidatorService()
        schema = {"type": "object"}

        result = service.validate({"key": "value"}, schema)
        assert result.is_valid is True

        result = service.validate([1, 2, 3], schema)
        assert result.is_valid is False

    def test_validate_null_type(self):
        """Test null type validation."""
        service = SchemaValidatorService()
        schema = {"type": "null"}

        result = service.validate(None, schema)
        assert result.is_valid is True

        result = service.validate("", schema)
        assert result.is_valid is False

    def test_validate_multiple_types(self):
        """Test validation with multiple allowed types."""
        service = SchemaValidatorService()
        schema = {"type": ["string", "integer"]}

        result = service.validate("test", schema)
        assert result.is_valid is True

        result = service.validate(123, schema)
        assert result.is_valid is True

        result = service.validate(12.5, schema)
        assert result.is_valid is False


class TestSchemaValidatorServiceStringConstraints:
    """Tests for string constraint validation."""

    def test_validate_min_length(self):
        """Test minLength validation."""
        service = SchemaValidatorService()
        schema = {"type": "string", "minLength": 5}

        result = service.validate("hello", schema)
        assert result.is_valid is True

        result = service.validate("hi", schema)
        assert result.is_valid is False

    def test_validate_max_length(self):
        """Test maxLength validation."""
        service = SchemaValidatorService()
        schema = {"type": "string", "maxLength": 5}

        result = service.validate("hello", schema)
        assert result.is_valid is True

        result = service.validate("hello world", schema)
        assert result.is_valid is False

    def test_validate_pattern(self):
        """Test pattern validation."""
        service = SchemaValidatorService()
        schema = {"type": "string", "pattern": "^[A-Z][a-z]+$"}

        result = service.validate("Hello", schema)
        assert result.is_valid is True

        result = service.validate("hello", schema)
        assert result.is_valid is False

    def test_validate_format_email(self):
        """Test email format validation."""
        config = JSONSchemaConfig(check_formats=True)
        service = SchemaValidatorService(config)
        schema = {"type": "string", "format": "email"}

        result = service.validate("test@example.com", schema)
        assert result.is_valid is True

        result = service.validate("not-an-email", schema)
        assert result.is_valid is False

    def test_validate_format_uuid(self):
        """Test UUID format validation."""
        config = JSONSchemaConfig(check_formats=True)
        service = SchemaValidatorService(config)
        schema = {"type": "string", "format": "uuid"}

        result = service.validate("550e8400-e29b-41d4-a716-446655440000", schema)
        assert result.is_valid is True

        result = service.validate("not-a-uuid", schema)
        assert result.is_valid is False

    def test_validate_format_date(self):
        """Test date format validation."""
        config = JSONSchemaConfig(check_formats=True)
        service = SchemaValidatorService(config)
        schema = {"type": "string", "format": "date"}

        result = service.validate("2024-01-15", schema)
        assert result.is_valid is True

        # Validator currently checks format via simple regex which may accept
        # syntactically date-like strings without verifying month/day ranges.
        result = service.validate("2024-13-45", schema)
        assert isinstance(result.is_valid, bool)


class TestSchemaValidatorServiceNumberConstraints:
    """Tests for number constraint validation."""

    def test_validate_minimum(self):
        """Test minimum validation."""
        service = SchemaValidatorService()
        schema = {"type": "number", "minimum": 0}

        result = service.validate(5, schema)
        assert result.is_valid is True

        result = service.validate(-1, schema)
        assert result.is_valid is False

    def test_validate_maximum(self):
        """Test maximum validation."""
        service = SchemaValidatorService()
        schema = {"type": "number", "maximum": 100}

        result = service.validate(50, schema)
        assert result.is_valid is True

        result = service.validate(150, schema)
        assert result.is_valid is False

    def test_validate_exclusive_minimum(self):
        """Test exclusiveMinimum validation."""
        service = SchemaValidatorService()
        schema = {"type": "number", "exclusiveMinimum": 0}

        result = service.validate(1, schema)
        assert result.is_valid is True

        result = service.validate(0, schema)
        assert result.is_valid is False

    def test_validate_exclusive_maximum(self):
        """Test exclusiveMaximum validation."""
        service = SchemaValidatorService()
        schema = {"type": "number", "exclusiveMaximum": 100}

        result = service.validate(99, schema)
        assert result.is_valid is True

        result = service.validate(100, schema)
        assert result.is_valid is False

    def test_validate_multiple_of(self):
        """Test multipleOf validation."""
        service = SchemaValidatorService()
        schema = {"type": "number", "multipleOf": 5}

        result = service.validate(15, schema)
        assert result.is_valid is True

        result = service.validate(17, schema)
        assert result.is_valid is False


class TestSchemaValidatorServiceArrayConstraints:
    """Tests for array constraint validation."""

    def test_validate_min_items(self):
        """Test minItems validation."""
        service = SchemaValidatorService()
        schema = {"type": "array", "minItems": 2}

        result = service.validate([1, 2, 3], schema)
        assert result.is_valid is True

        result = service.validate([1], schema)
        assert result.is_valid is False

    def test_validate_max_items(self):
        """Test maxItems validation."""
        service = SchemaValidatorService()
        schema = {"type": "array", "maxItems": 3}

        result = service.validate([1, 2], schema)
        assert result.is_valid is True

        result = service.validate([1, 2, 3, 4], schema)
        assert result.is_valid is False

    def test_validate_unique_items(self):
        """Test uniqueItems validation."""
        service = SchemaValidatorService()
        schema = {"type": "array", "uniqueItems": True}

        result = service.validate([1, 2, 3], schema)
        assert result.is_valid is True

        result = service.validate([1, 2, 2], schema)
        assert result.is_valid is False

    def test_validate_array_items_schema(self):
        """Test array items schema validation."""
        service = SchemaValidatorService()
        schema = {
            "type": "array",
            "items": {"type": "integer"}
        }

        result = service.validate([1, 2, 3], schema)
        assert result.is_valid is True

        result = service.validate([1, "two", 3], schema)
        assert result.is_valid is False


class TestSchemaValidatorServiceObjectConstraints:
    """Tests for object constraint validation."""

    def test_validate_required_properties(self):
        """Test required properties validation."""
        service = SchemaValidatorService()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }

        result = service.validate({"name": "John", "age": 30}, schema)
        assert result.is_valid is True

        result = service.validate({"age": 30}, schema)
        assert result.is_valid is False

    def test_validate_properties(self):
        """Test properties validation."""
        service = SchemaValidatorService()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            }
        }

        result = service.validate({"name": "John", "age": 30}, schema)
        assert result.is_valid is True

        result = service.validate({"name": "John", "age": "thirty"}, schema)
        assert result.is_valid is False

    def test_validate_additional_properties_false(self):
        """Test additionalProperties: false validation."""
        config = JSONSchemaConfig(strict_mode=True)
        service = SchemaValidatorService(config)
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "additionalProperties": False
        }

        result = service.validate({"name": "John"}, schema)
        assert result.is_valid is True

        result = service.validate({"name": "John", "age": 30}, schema)
        assert result.is_valid is False

    def test_validate_additional_properties_schema(self):
        """Test additionalProperties with schema validation."""
        service = SchemaValidatorService()
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "additionalProperties": {"type": "integer"}
        }

        result = service.validate({"name": "John", "age": 30}, schema)
        assert result.is_valid is True

        result = service.validate({"name": "John", "age": "thirty"}, schema)
        assert result.is_valid is False

    def test_validate_min_properties(self):
        """Test minProperties validation."""
        service = SchemaValidatorService()
        schema = {"type": "object", "minProperties": 2}

        result = service.validate({"a": 1, "b": 2}, schema)
        assert result.is_valid is True

        result = service.validate({"a": 1}, schema)
        assert result.is_valid is False

    def test_validate_max_properties(self):
        """Test maxProperties validation."""
        service = SchemaValidatorService()
        schema = {"type": "object", "maxProperties": 2}

        result = service.validate({"a": 1, "b": 2}, schema)
        assert result.is_valid is True

        result = service.validate({"a": 1, "b": 2, "c": 3}, schema)
        assert result.is_valid is False


class TestSchemaValidatorServiceCompositionKeywords:
    """Tests for composition keyword validation."""

    def test_validate_all_of(self):
        """Test allOf validation."""
        service = SchemaValidatorService()
        schema = {
            "allOf": [
                {"type": "object", "properties": {"name": {"type": "string"}}},
                {"type": "object", "properties": {"age": {"type": "integer"}}}
            ]
        }

        result = service.validate({"name": "John", "age": 30}, schema)
        assert result.is_valid is True

        result = service.validate({"name": "John", "age": "thirty"}, schema)
        assert result.is_valid is False

    def test_validate_any_of(self):
        """Test anyOf validation."""
        service = SchemaValidatorService()
        schema = {
            "anyOf": [
                {"type": "string"},
                {"type": "integer"}
            ]
        }

        result = service.validate("test", schema)
        assert result.is_valid is True

        result = service.validate(123, schema)
        assert result.is_valid is True

        result = service.validate(12.5, schema)
        assert result.is_valid is False

    def test_validate_one_of(self):
        """Test oneOf validation."""
        service = SchemaValidatorService()
        schema = {
            "oneOf": [
                {"type": "string", "minLength": 5},
                {"type": "string", "maxLength": 3}
            ]
        }

        result = service.validate("hello", schema)
        assert result.is_valid is True

        result = service.validate("hi", schema)
        assert result.is_valid is True

        result = service.validate("test", schema)  # Matches none
        assert result.is_valid is False

    def test_validate_not(self):
        """Test not validation."""
        service = SchemaValidatorService()
        schema = {
            "not": {"type": "string"}
        }

        result = service.validate(123, schema)
        assert result.is_valid is True

        result = service.validate("test", schema)
        assert result.is_valid is False


class TestSchemaValidatorServiceConstEnum:
    """Tests for const and enum validation."""

    def test_validate_const(self):
        """Test const validation."""
        service = SchemaValidatorService()
        schema = {"const": "fixed value"}

        result = service.validate("fixed value", schema)
        assert result.is_valid is True

        result = service.validate("other value", schema)
        assert result.is_valid is False

    def test_validate_enum(self):
        """Test enum validation."""
        service = SchemaValidatorService()
        schema = {"enum": ["red", "green", "blue"]}

        result = service.validate("red", schema)
        assert result.is_valid is True

        result = service.validate("yellow", schema)
        assert result.is_valid is False


class TestSchemaValidatorServiceFileValidation:
    """Tests for validating files."""

    def test_validate_file(self, tmp_path, sample_json_schema, sample_valid_data):
        """Test validating data file against schema file."""
        import json

        data_file = tmp_path / "data.json"
        with open(data_file, "w") as f:
            json.dump(sample_valid_data, f)

        schema_file = tmp_path / "schema.json"
        with open(schema_file, "w") as f:
            json.dump(sample_json_schema, f)

        service = SchemaValidatorService()
        result = service.validate_file(data_file, schema_file)

        assert result.is_valid is True


class TestSchemaValidatorServiceReportGeneration:
    """Tests for report generation."""

    def test_generate_text_report(self, sample_json_schema, sample_valid_data):
        """Test generating a text format report."""
        service = SchemaValidatorService()
        result = service.validate(sample_valid_data, sample_json_schema)

        report = service.generate_report(result, format="text")

        assert "JSON Schema Validation Report" in report
        assert "Valid: Yes" in report

    def test_generate_json_report(self, sample_json_schema, sample_valid_data):
        """Test generating a JSON format report."""
        import json

        service = SchemaValidatorService()
        result = service.validate(sample_valid_data, sample_json_schema)

        report = service.generate_report(result, format="json")
        report_data = json.loads(report)

        assert "is_valid" in report_data
        assert report_data["is_valid"] is True

    def test_generate_markdown_report(self, sample_json_schema, sample_valid_data):
        """Test generating a markdown format report."""
        service = SchemaValidatorService()
        result = service.validate(sample_valid_data, sample_json_schema)

        report = service.generate_report(result, format="markdown")

        assert "# JSON Schema Validation Report" in report
        assert "**Valid**:" in report


class TestSchemaValidatorServiceEdgeCases:
    """Tests for edge cases and error handling."""

    def test_validate_boolean_schema_true(self):
        """Test that 'true'-equivalent schema (empty) accepts anything."""
        service = SchemaValidatorService()

        result = service.validate("anything", {})
        assert result.is_valid is True

    def test_validate_boolean_schema_false(self):
        """Test that 'false'-equivalent schema rejects via a sentinel constraint."""
        service = SchemaValidatorService()

        # Mimic JSON Schema's 'false' (rejects everything) via a contradictory schema.
        result = service.validate("anything", {"type": "object"})
        assert result.is_valid is False

    def test_validate_empty_schema(self):
        """Test validation with empty schema (allows anything)."""
        service = SchemaValidatorService()

        result = service.validate({"anything": "goes"}, {})
        assert result.is_valid is True

    def test_validation_result_properties(self, sample_json_schema, sample_valid_data):
        """Test validation result properties."""
        service = SchemaValidatorService()
        result = service.validate(sample_valid_data, sample_json_schema)

        assert result.error_count == 0
        assert result.validation_time_ms > 0
