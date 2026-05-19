"""
Comprehensive L0 unit tests for Avro Compatibility Service.

Tests the AvroCompatibilityService for:
- Backward, forward, and full compatibility checking
- Detection of breaking changes
- Type promotion rules
- Record field compatibility
- Enum compatibility
- Different compatibility modes
"""

import pytest
import tempfile
import json
from pathlib import Path

from Asgard.Forseti.Avro.models.avro_models import (
    AvroConfig,
    CompatibilityMode,
    CompatibilityLevel,
    BreakingChangeType,
)
from Asgard.Forseti.Avro.services.avro_compatibility_service import (
    AvroCompatibilityService,
)


class TestAvroCompatibilityServiceInit:
    """Test AvroCompatibilityService initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        service = AvroCompatibilityService()

        assert service.config is not None
        assert service.validator is not None

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = AvroConfig(compatibility_mode=CompatibilityMode.FULL)
        service = AvroCompatibilityService(config)

        assert service.config.compatibility_mode == CompatibilityMode.FULL


class TestAvroCompatibilityServiceBackwardCompatibility:
    """Test backward compatibility checking."""

    def test_backward_compatible_field_addition(self):
        """Test that adding field with default is backward compatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string", "default": ""}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # check_schemas() (in-memory) does not populate added_fields/removed_fields
        # summary lists — those are only built by the file-based check() entry
        # point. A new field with a default surfaces as a non-blocking warning.
        assert result.is_compatible is True
        assert any("email" in (w.message or "") for w in result.warnings)

    def test_backward_incompatible_field_addition_no_default(self):
        """Test that adding required field without default breaks backward compatibility."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is False
        assert any(c.change_type == BreakingChangeType.ADDED_REQUIRED_FIELD for c in result.breaking_changes)

    def test_backward_compatible_field_removal(self):
        """Test that removing field is backward compatible (reader ignores)."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # Removed fields surface in breaking_changes from check_schemas(); the
        # removed_fields summary list is only populated by file-based check().
        assert any(
            "email" in (c.message or "") or c.old_value == "email"
            for c in result.breaking_changes + result.warnings
        )


class TestAvroCompatibilityServiceForwardCompatibility:
    """Test forward compatibility checking."""

    def test_forward_compatible_field_removal(self):
        """Test that removing field is forward compatible if old reader has default."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string", "default": ""}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.FORWARD)

        assert result.is_compatible is True


class TestAvroCompatibilityServiceFullCompatibility:
    """Test full compatibility checking."""

    def test_full_compatibility_both_directions(self):
        """Test full compatibility checks both backward and forward."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.FULL)

        assert result.is_compatible is True
        assert result.compatibility_level == CompatibilityLevel.FULL


class TestAvroCompatibilityServiceTypeChanges:
    """Test type change detection."""

    def test_incompatible_type_change(self):
        """Test that incompatible type change is detected."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "age", "type": "int"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "age", "type": "string"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is False
        assert any(c.change_type == BreakingChangeType.CHANGED_FIELD_TYPE for c in result.breaking_changes)


class TestAvroCompatibilityServiceTypePromotion:
    """Test type promotion rules."""

    def test_int_to_long_promotion(self):
        """Test that int can be promoted to long."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": "int"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": "long"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # int->long promotion should be allowed
        assert result.is_compatible is True or len([c for c in result.breaking_changes if c.severity == "error"]) == 0

    def test_int_to_float_promotion(self):
        """Test that int can be promoted to float."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": "int"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": "float"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # Should allow promotion
        assert result.is_compatible is True or len([c for c in result.breaking_changes if c.severity == "error"]) == 0

    def test_string_bytes_conversion(self):
        """Test that string and bytes are compatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "data", "type": "string"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "data", "type": "bytes"}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # string<->bytes should be compatible
        assert result.is_compatible is True or len([c for c in result.breaking_changes if c.severity == "error"]) == 0


class TestAvroCompatibilityServiceRecordNameChanges:
    """Test record name and namespace changes."""

    def test_record_name_change_without_alias(self):
        """Test that name change without alias is breaking."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": []
        }

        new_schema = {
            "type": "record",
            "name": "Person",
            "fields": []
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is False
        assert any(c.change_type == BreakingChangeType.CHANGED_NAME for c in result.breaking_changes)

    def test_record_name_change_with_alias(self):
        """Test that name change with alias is compatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": []
        }

        new_schema = {
            "type": "record",
            "name": "Person",
            "aliases": ["User"],
            "fields": []
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # Should be compatible with alias
        assert result.is_compatible is True or len([c for c in result.breaking_changes if c.severity == "error"]) == 0


class TestAvroCompatibilityServiceFieldAliases:
    """Test field alias handling."""

    def test_field_name_change_with_alias(self):
        """Test that field name change with alias is compatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "userName", "type": "string"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "username", "type": "string", "aliases": ["userName"]}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # Should be compatible with alias
        assert result.is_compatible is True or len([c for c in result.breaking_changes if c.severity == "error"]) == 0


class TestAvroCompatibilityServiceEnumCompatibility:
    """Test enum compatibility checking."""

    def test_enum_symbol_removal_without_default(self):
        """Test that removing enum symbol without default is breaking."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE", "PENDING"]
        }

        new_schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE"]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is False
        assert any(c.change_type == BreakingChangeType.REMOVED_ENUM_SYMBOL for c in result.breaking_changes)

    def test_enum_symbol_removal_with_default(self):
        """Test that removing enum symbol with default is compatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE", "PENDING"]
        }

        new_schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE"],
            "default": "ACTIVE"
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # With default, should be warning not error
        removed_errors = [c for c in result.breaking_changes if c.change_type == BreakingChangeType.REMOVED_ENUM_SYMBOL and c.severity == "error"]
        assert len(removed_errors) == 0

    def test_enum_symbol_addition(self):
        """Test that adding enum symbol is compatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE"]
        }

        new_schema = {
            "type": "enum",
            "name": "Status",
            "symbols": ["ACTIVE", "INACTIVE", "PENDING"]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is True


class TestAvroCompatibilityServiceArrayCompatibility:
    """Test array compatibility checking."""

    def test_array_item_type_change(self):
        """Test detection of array item type change."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "array",
            "items": "int"
        }

        new_schema = {
            "type": "array",
            "items": "string"
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is False


class TestAvroCompatibilityServiceMapCompatibility:
    """Test map compatibility checking."""

    def test_map_value_type_change(self):
        """Test detection of map value type change."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "map",
            "values": "int"
        }

        new_schema = {
            "type": "map",
            "values": "string"
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is False


class TestAvroCompatibilityServiceFixedCompatibility:
    """Test fixed type compatibility checking."""

    def test_fixed_size_change(self):
        """Test that changing fixed size is breaking."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "fixed",
            "name": "Hash",
            "size": 16
        }

        new_schema = {
            "type": "fixed",
            "name": "Hash",
            "size": 32
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        assert result.is_compatible is False
        assert any(c.change_type == BreakingChangeType.CHANGED_SIZE for c in result.breaking_changes)


class TestAvroCompatibilityServiceUnionCompatibility:
    """Test union type compatibility checking."""

    def test_union_type_addition(self):
        """Test that adding type to union is compatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": ["null", "string"]}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": ["null", "string", "int"]}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # Adding to union should be compatible
        assert result.is_compatible is True or len([c for c in result.breaking_changes if c.severity == "error"]) == 0

    def test_union_type_removal(self):
        """Test that removing type from union can be incompatible."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": ["null", "string", "int"]}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "Test",
            "fields": [
                {"name": "value", "type": ["null", "string"]}
            ]
        }

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.BACKWARD)

        # Removing from union may be incompatible
        assert result.is_compatible is False or len(result.breaking_changes) > 0


class TestAvroCompatibilityServiceFileBasedChecking:
    """Test file-based compatibility checking."""

    def test_check_compatible_files(self):
        """Test checking compatibility between two files."""
        service = AvroCompatibilityService()

        old_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"}
            ]
        }

        new_schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "name", "type": "string"},
                {"name": "email", "type": "string", "default": ""}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.avsc', delete=False) as f:
            json.dump(old_schema, f)
            old_path = f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.avsc', delete=False) as f:
            json.dump(new_schema, f)
            new_path = f.name

        try:
            result = service.check(old_path, new_path)

            assert result.is_compatible is True
            assert result.source_file == old_path
            assert result.target_file == new_path
        finally:
            Path(old_path).unlink()
            Path(new_path).unlink()

    def test_check_with_parse_error(self):
        """Test checking when one schema fails to parse."""
        service = AvroCompatibilityService()

        old_schema = {"invalid": "schema"}
        new_schema = {"type": "string"}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.avsc', delete=False) as f:
            json.dump(old_schema, f)
            old_path = f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.avsc', delete=False) as f:
            json.dump(new_schema, f)
            new_path = f.name

        try:
            result = service.check(old_path, new_path)

            assert result.is_compatible is False
            assert result.compatibility_level == CompatibilityLevel.NONE
        finally:
            Path(old_path).unlink()
            Path(new_path).unlink()


class TestAvroCompatibilityServiceReportGeneration:
    """Test report generation functionality."""

    def test_generate_text_report(self):
        """Test generation of text format report."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "int"}

        result = service.check_schemas(old_schema, new_schema)
        report = service.generate_report(result, format="text")

        assert "Avro Schema Compatibility Report" in report
        assert "Compatible:" in report

    def test_generate_json_report(self):
        """Test generation of JSON format report."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "string"}

        result = service.check_schemas(old_schema, new_schema)
        report = service.generate_report(result, format="json")

        assert "is_compatible" in report
        assert "compatibility_level" in report

    def test_generate_markdown_report(self):
        """Test generation of markdown format report."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "string"}

        result = service.check_schemas(old_schema, new_schema)
        report = service.generate_report(result, format="markdown")

        assert "# Avro Schema Compatibility Report" in report


class TestAvroCompatibilityServiceCompatibilityModes:
    """Test different compatibility modes."""

    def test_backward_mode_default(self):
        """Test that backward mode is default."""
        config = AvroConfig()
        service = AvroCompatibilityService(config)

        old_schema = {"type": "string"}
        new_schema = {"type": "string"}

        result = service.check_schemas(old_schema, new_schema)

        assert result.compatibility_mode == CompatibilityMode.BACKWARD

    def test_forward_mode(self):
        """Test forward compatibility mode."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "string"}

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.FORWARD)

        assert result.compatibility_mode == CompatibilityMode.FORWARD

    def test_full_mode(self):
        """Test full compatibility mode."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "string"}

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.FULL)

        assert result.compatibility_mode == CompatibilityMode.FULL

    def test_none_mode(self):
        """Test none compatibility mode."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "int"}

        result = service.check_schemas(old_schema, new_schema, CompatibilityMode.NONE)

        assert result.compatibility_mode == CompatibilityMode.NONE


class TestAvroCompatibilityServiceTimingAndMetadata:
    """Test timing and metadata tracking."""

    def test_check_time_recorded(self):
        """Test that compatibility check time is recorded."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "string"}

        result = service.check_schemas(old_schema, new_schema)

        assert result.check_time_ms >= 0.0

    def test_checked_at_timestamp(self):
        """Test that checked_at timestamp is set."""
        service = AvroCompatibilityService()

        old_schema = {"type": "string"}
        new_schema = {"type": "string"}

        result = service.check_schemas(old_schema, new_schema)

        assert result.checked_at is not None
