"""
Comprehensive L0 unit tests for Avro Models.

Tests all Pydantic models in the Forseti Avro module for:
- Model instantiation and validation
- Field defaults and constraints
- Property methods
- Enum values
- Edge cases and invalid inputs
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from Asgard.Forseti.Avro.models.avro_models import (
    AvroSchemaType,
    ValidationSeverity,
    BreakingChangeType,
    CompatibilityLevel,
    CompatibilityMode,
    AvroConfig,
    AvroValidationError,
    AvroField,
    AvroSchema,
    AvroValidationResult,
    BreakingChange,
    AvroCompatibilityResult,
)


class TestAvroSchemaType:
    """Test AvroSchemaType enum."""

    def test_primitive_types(self):
        """Test all primitive type values."""
        assert AvroSchemaType.NULL == "null"
        assert AvroSchemaType.BOOLEAN == "boolean"
        assert AvroSchemaType.INT == "int"
        assert AvroSchemaType.LONG == "long"
        assert AvroSchemaType.FLOAT == "float"
        assert AvroSchemaType.DOUBLE == "double"
        assert AvroSchemaType.BYTES == "bytes"
        assert AvroSchemaType.STRING == "string"

    def test_complex_types(self):
        """Test all complex type values."""
        assert AvroSchemaType.RECORD == "record"
        assert AvroSchemaType.ENUM == "enum"
        assert AvroSchemaType.ARRAY == "array"
        assert AvroSchemaType.MAP == "map"
        assert AvroSchemaType.UNION == "union"
        assert AvroSchemaType.FIXED == "fixed"


class TestCompatibilityMode:
    """Test CompatibilityMode enum."""

    def test_all_modes(self):
        """Test all compatibility mode values."""
        assert CompatibilityMode.BACKWARD == "backward"
        assert CompatibilityMode.FORWARD == "forward"
        assert CompatibilityMode.FULL == "full"
        assert CompatibilityMode.NONE == "none"


class TestAvroConfig:
    """Test AvroConfig model."""

    def test_default_config(self):
        """Test config with all default values."""
        config = AvroConfig()

        assert config.strict_mode is False
        assert config.check_naming_conventions is True
        assert config.require_doc is False
        assert config.require_default is False
        assert config.compatibility_mode == CompatibilityMode.BACKWARD
        assert config.max_errors == 100
        assert config.include_warnings is True
        assert config.allow_unknown_logical_types is True

    def test_custom_config(self):
        """Test config with custom values."""
        config = AvroConfig(
            strict_mode=True,
            check_naming_conventions=False,
            require_doc=True,
            require_default=True,
            compatibility_mode=CompatibilityMode.FULL,
            max_errors=50,
            include_warnings=False,
            allow_unknown_logical_types=False
        )

        assert config.strict_mode is True
        assert config.check_naming_conventions is False
        assert config.require_doc is True
        assert config.require_default is True
        assert config.compatibility_mode == CompatibilityMode.FULL
        assert config.max_errors == 50
        assert config.include_warnings is False
        assert config.allow_unknown_logical_types is False


class TestAvroValidationError:
    """Test AvroValidationError model."""

    def test_minimal_error(self):
        """Test error with only required fields."""
        error = AvroValidationError(
            path="/record/field",
            message="Test error"
        )

        assert error.path == "/record/field"
        assert error.message == "Test error"
        assert error.severity == ValidationSeverity.ERROR
        assert error.rule is None
        assert error.context is None

    def test_complete_error(self):
        """Test error with all fields populated."""
        error = AvroValidationError(
            path="/record/field",
            message="Test error",
            severity=ValidationSeverity.WARNING,
            rule="test-rule",
            context={"extra": "data"}
        )

        assert error.severity == ValidationSeverity.WARNING
        assert error.rule == "test-rule"
        assert error.context == {"extra": "data"}


class TestAvroField:
    """Test AvroField model."""

    def test_basic_field(self):
        """Test basic field with minimal attributes."""
        field = AvroField(
            name="test_field",
            type="string"
        )

        assert field.name == "test_field"
        assert field.type == "string"
        assert field.default is None
        assert field.doc is None
        assert field.order is None
        assert field.aliases is None

    def test_field_with_default(self):
        """Test field with default value."""
        field = AvroField(
            name="field_with_default",
            type="int",
            default=42
        )

        assert field.default == 42
        assert field.has_default is True

    def test_field_without_default(self):
        """Test field without default value."""
        field = AvroField(
            name="field",
            type="string"
        )

        assert field.has_default is False

    def test_optional_field(self):
        """Test field that is optional (union with null)."""
        field = AvroField(
            name="optional_field",
            type=["null", "string"]
        )

        assert field.is_optional is True

    def test_required_field(self):
        """Test field that is required (not nullable)."""
        field = AvroField(
            name="required_field",
            type="string"
        )

        assert field.is_optional is False

    def test_field_with_doc(self):
        """Test field with documentation."""
        field = AvroField(
            name="documented_field",
            type="string",
            doc="Field documentation"
        )

        assert field.doc == "Field documentation"

    def test_field_with_order(self):
        """Test field with sort order."""
        field = AvroField(
            name="sorted_field",
            type="int",
            order="descending"
        )

        assert field.order == "descending"

    def test_field_with_aliases(self):
        """Test field with aliases."""
        field = AvroField(
            name="current_name",
            type="string",
            aliases=["old_name", "another_name"]
        )

        assert field.aliases == ["old_name", "another_name"]


class TestAvroSchema:
    """Test AvroSchema model."""

    def test_minimal_schema(self):
        """Test schema with minimal required fields."""
        schema = AvroSchema(type="string")

        assert schema.type == "string"
        assert schema.name is None
        assert schema.namespace is None
        assert schema.doc is None
        assert schema.fields is None
        assert schema.symbols is None
        assert schema.items is None
        assert schema.values is None
        assert schema.size is None
        assert schema.aliases is None
        assert schema.logical_type is None
        assert schema.raw_schema is None
        assert schema.file_path is None

    def test_record_schema(self):
        """Test record schema with fields."""
        fields = [
            AvroField(name="name", type="string"),
            AvroField(name="age", type="int")
        ]
        schema = AvroSchema(
            type="record",
            name="Person",
            fields=fields
        )

        assert schema.type == "record"
        assert schema.name == "Person"
        assert len(schema.fields) == 2
        assert schema.field_count == 2

    def test_schema_with_namespace(self):
        """Test schema with namespace."""
        schema = AvroSchema(
            type="record",
            name="User",
            namespace="com.example"
        )

        assert schema.namespace == "com.example"
        assert schema.full_name == "com.example.User"

    def test_schema_without_namespace(self):
        """Test full_name for schema without namespace."""
        schema = AvroSchema(
            type="record",
            name="User"
        )

        assert schema.full_name == "User"

    def test_schema_without_name(self):
        """Test full_name for schema without name (primitive type)."""
        schema = AvroSchema(type="string")

        assert schema.full_name == "string"

    def test_enum_schema(self):
        """Test enum schema with symbols."""
        schema = AvroSchema(
            type="enum",
            name="Status",
            symbols=["ACTIVE", "INACTIVE", "PENDING"]
        )

        assert schema.type == "enum"
        assert schema.name == "Status"
        assert schema.symbols == ["ACTIVE", "INACTIVE", "PENDING"]

    def test_array_schema(self):
        """Test array schema with items type."""
        schema = AvroSchema(
            type="array",
            items="string"
        )

        assert schema.type == "array"
        assert schema.items == "string"

    def test_map_schema(self):
        """Test map schema with values type."""
        schema = AvroSchema(
            type="map",
            values="int"
        )

        assert schema.type == "map"
        assert schema.values == "int"

    def test_fixed_schema(self):
        """Test fixed schema with size."""
        schema = AvroSchema(
            type="fixed",
            name="MD5",
            size=16
        )

        assert schema.type == "fixed"
        assert schema.name == "MD5"
        assert schema.size == 16

    def test_schema_with_logical_type(self):
        """Test schema with logical type annotation."""
        schema = AvroSchema(
            type="long",
            logical_type="timestamp-millis"
        )

        assert schema.type == "long"
        assert schema.logical_type == "timestamp-millis"

    def test_schema_with_aliases(self):
        """Test schema with aliases."""
        schema = AvroSchema(
            type="record",
            name="User",
            aliases=["Person", "Account"]
        )

        assert schema.aliases == ["Person", "Account"]

    def test_schema_with_doc(self):
        """Test schema with documentation."""
        schema = AvroSchema(
            type="record",
            name="User",
            doc="User record"
        )

        assert schema.doc == "User record"

    def test_schema_field_count_with_no_fields(self):
        """Test field_count property for schema without fields."""
        schema = AvroSchema(type="string")

        assert schema.field_count == 0


class TestAvroValidationResult:
    """Test AvroValidationResult model."""

    def test_valid_result(self):
        """Test validation result for valid schema."""
        result = AvroValidationResult(
            is_valid=True,
            file_path="test.avsc"
        )

        assert result.is_valid is True
        assert result.file_path == "test.avsc"
        assert result.schema_type is None
        assert result.parsed_schema is None
        assert result.errors == []
        assert result.warnings == []
        assert result.info_messages == []
        assert isinstance(result.validated_at, datetime)
        assert result.validation_time_ms == 0.0

    def test_invalid_result_with_errors(self):
        """Test validation result with errors."""
        errors = [
            AvroValidationError(path="/", message="Error 1"),
            AvroValidationError(path="/field", message="Error 2")
        ]
        result = AvroValidationResult(
            is_valid=False,
            errors=errors
        )

        assert result.is_valid is False
        assert len(result.errors) == 2
        assert result.error_count == 2

    def test_result_with_warnings(self):
        """Test validation result with warnings."""
        warnings = [
            AvroValidationError(
                path="/field",
                message="Warning",
                severity=ValidationSeverity.WARNING
            )
        ]
        result = AvroValidationResult(
            is_valid=True,
            warnings=warnings
        )

        assert result.warning_count == 1

    def test_result_total_issues(self):
        """Test total issues property."""
        errors = [
            AvroValidationError(path="/e1", message="Error 1"),
            AvroValidationError(path="/e2", message="Error 2")
        ]
        warnings = [
            AvroValidationError(
                path="/w1",
                message="Warning",
                severity=ValidationSeverity.WARNING
            )
        ]
        result = AvroValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings
        )

        assert result.total_issues == 3

    def test_result_with_parsed_schema(self):
        """Test validation result with parsed schema."""
        schema = AvroSchema(type="record", name="Test")
        result = AvroValidationResult(
            is_valid=True,
            schema_type="record",
            parsed_schema=schema
        )

        assert result.parsed_schema is not None
        assert result.schema_type == "record"


class TestBreakingChange:
    """Test BreakingChange model."""

    def test_minimal_breaking_change(self):
        """Test breaking change with minimal fields."""
        change = BreakingChange(
            change_type=BreakingChangeType.REMOVED_FIELD,
            path="/fields/name",
            message="Field removed"
        )

        assert change.change_type == BreakingChangeType.REMOVED_FIELD
        assert change.path == "/fields/name"
        assert change.message == "Field removed"
        assert change.old_value is None
        assert change.new_value is None
        assert change.severity == "error"
        assert change.mitigation is None

    def test_complete_breaking_change(self):
        """Test breaking change with all fields."""
        change = BreakingChange(
            change_type=BreakingChangeType.CHANGED_FIELD_TYPE,
            path="/fields/age",
            message="Type changed",
            old_value="int",
            new_value="long",
            severity="warning",
            mitigation="Use type promotion"
        )

        assert change.old_value == "int"
        assert change.new_value == "long"
        assert change.severity == "warning"
        assert change.mitigation == "Use type promotion"


class TestAvroCompatibilityResult:
    """Test AvroCompatibilityResult model."""

    def test_compatible_result(self):
        """Test compatibility result for compatible schemas."""
        result = AvroCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.FULL
        )

        assert result.is_compatible is True
        assert result.compatibility_level == CompatibilityLevel.FULL
        assert result.compatibility_mode == CompatibilityMode.BACKWARD
        assert result.source_file is None
        assert result.target_file is None
        assert result.breaking_changes == []
        assert result.warnings == []
        assert result.added_fields == []
        assert result.removed_fields == []
        assert result.modified_fields == []
        assert result.check_time_ms == 0.0
        assert isinstance(result.checked_at, datetime)

    def test_incompatible_result(self):
        """Test compatibility result with breaking changes."""
        breaking_changes = [
            BreakingChange(
                change_type=BreakingChangeType.REMOVED_FIELD,
                path="/fields/name",
                message="Field removed"
            )
        ]
        result = AvroCompatibilityResult(
            is_compatible=False,
            compatibility_level=CompatibilityLevel.NONE,
            breaking_changes=breaking_changes
        )

        assert result.is_compatible is False
        assert result.breaking_change_count == 1

    def test_result_with_field_lists(self):
        """Test compatibility result with field change lists."""
        result = AvroCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.BACKWARD,
            added_fields=["email"],
            removed_fields=["old_field"],
            modified_fields=["name"]
        )

        assert result.added_fields == ["email"]
        assert result.removed_fields == ["old_field"]
        assert result.modified_fields == ["name"]

    def test_result_with_compatibility_mode(self):
        """Test compatibility result with specific mode."""
        result = AvroCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.FULL,
            compatibility_mode=CompatibilityMode.FULL
        )

        assert result.compatibility_mode == CompatibilityMode.FULL

    def test_result_warning_count(self):
        """Test warning count property."""
        warnings = [
            BreakingChange(
                change_type=BreakingChangeType.CHANGED_FIELD_DEFAULT,
                path="/fields/status",
                message="Default changed",
                severity="warning"
            )
        ]
        result = AvroCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.FULL,
            warnings=warnings
        )

        assert result.warning_count == 1


class TestBreakingChangeType:
    """Test BreakingChangeType enum."""

    def test_all_change_types(self):
        """Test all breaking change type values."""
        assert BreakingChangeType.REMOVED_FIELD == "removed_field"
        assert BreakingChangeType.REMOVED_TYPE == "removed_type"
        assert BreakingChangeType.REMOVED_ENUM_SYMBOL == "removed_enum_symbol"
        assert BreakingChangeType.CHANGED_FIELD_TYPE == "changed_field_type"
        assert BreakingChangeType.CHANGED_FIELD_DEFAULT == "changed_field_default"
        assert BreakingChangeType.ADDED_REQUIRED_FIELD == "added_required_field"
        assert BreakingChangeType.CHANGED_NAMESPACE == "changed_namespace"
        assert BreakingChangeType.CHANGED_NAME == "changed_name"
        assert BreakingChangeType.CHANGED_SIZE == "changed_size"
        assert BreakingChangeType.CHANGED_ENUM_ORDER == "changed_enum_order"
        assert BreakingChangeType.INCOMPATIBLE_UNION == "incompatible_union"


class TestModelValidation:
    """Test Pydantic validation for required fields."""

    def test_avro_field_requires_name(self):
        """Test that AvroField requires name."""
        with pytest.raises(ValidationError) as exc_info:
            AvroField(type="string")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_avro_field_requires_type(self):
        """Test that AvroField requires type."""
        with pytest.raises(ValidationError) as exc_info:
            AvroField(name="field")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_avro_schema_requires_type(self):
        """Test that AvroSchema requires type."""
        with pytest.raises(ValidationError) as exc_info:
            AvroSchema()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_avro_validation_result_requires_is_valid(self):
        """Test that AvroValidationResult requires is_valid."""
        with pytest.raises(ValidationError) as exc_info:
            AvroValidationResult()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("is_valid",) for e in errors)

    def test_breaking_change_requires_fields(self):
        """Test that BreakingChange requires change_type, path, and message."""
        with pytest.raises(ValidationError) as exc_info:
            BreakingChange()

        errors = exc_info.value.errors()
        error_locs = {e["loc"] for e in errors}
        assert ("change_type",) in error_locs
        assert ("path",) in error_locs
        assert ("message",) in error_locs

    def test_compatibility_result_requires_fields(self):
        """Test that AvroCompatibilityResult requires is_compatible and compatibility_level."""
        with pytest.raises(ValidationError) as exc_info:
            AvroCompatibilityResult()

        errors = exc_info.value.errors()
        error_locs = {e["loc"] for e in errors}
        assert ("is_compatible",) in error_locs
        assert ("compatibility_level",) in error_locs


class TestAvroFieldProperties:
    """Test AvroField property methods."""

    def test_is_optional_with_null_union(self):
        """Test is_optional returns True for union with null."""
        field = AvroField(name="field", type=["null", "string"])
        assert field.is_optional is True

    def test_is_optional_with_string_union(self):
        """Test is_optional returns True when null is in string union."""
        field = AvroField(name="field", type=["string", "null"])
        assert field.is_optional is True

    def test_is_optional_without_null(self):
        """Test is_optional returns False for union without null."""
        field = AvroField(name="field", type=["string", "int"])
        assert field.is_optional is False

    def test_is_optional_non_union(self):
        """Test is_optional returns False for non-union types."""
        field = AvroField(name="field", type="string")
        assert field.is_optional is False

    def test_has_default_with_value(self):
        """Test has_default returns True when default is set."""
        field = AvroField(name="field", type="int", default=0)
        assert field.has_default is True

    def test_has_default_without_value(self):
        """Test has_default returns False when default is not set."""
        field = AvroField(name="field", type="int")
        assert field.has_default is False

    def test_has_default_with_null_value(self):
        """has_default reflects whether the underlying default attribute is set.

        AvroField models has_default as `default is not None`, so an explicit
        `default=None` (which is indistinguishable from "unset" without a
        sentinel) is reported as False.
        """
        field = AvroField(name="field", type=["null", "string"], default=None)
        assert field.has_default is False


class TestAvroSchemaProperties:
    """Test AvroSchema property methods."""

    def test_full_name_with_namespace_and_name(self):
        """Test full_name with both namespace and name."""
        schema = AvroSchema(
            type="record",
            name="User",
            namespace="com.example"
        )
        assert schema.full_name == "com.example.User"

    def test_full_name_with_name_only(self):
        """Test full_name with only name."""
        schema = AvroSchema(type="record", name="User")
        assert schema.full_name == "User"

    def test_full_name_without_name(self):
        """Test full_name for primitive type without name."""
        schema = AvroSchema(type="string")
        assert schema.full_name == "string"

    def test_field_count_with_fields(self):
        """Test field_count with fields present."""
        fields = [
            AvroField(name="f1", type="string"),
            AvroField(name="f2", type="int"),
            AvroField(name="f3", type="boolean")
        ]
        schema = AvroSchema(type="record", name="Test", fields=fields)
        assert schema.field_count == 3

    def test_field_count_without_fields(self):
        """Test field_count without fields."""
        schema = AvroSchema(type="string")
        assert schema.field_count == 0

    def test_field_count_with_empty_list(self):
        """Test field_count with empty fields list."""
        schema = AvroSchema(type="record", name="Empty", fields=[])
        assert schema.field_count == 0


class TestLogicalTypeAliasing:
    """Test logicalType field aliasing."""

    def test_logical_type_with_camel_case(self):
        """Test that logicalType can be set with camelCase."""
        schema = AvroSchema(
            type="long",
            **{"logicalType": "timestamp-millis"}
        )
        assert schema.logical_type == "timestamp-millis"

    def test_logical_type_with_snake_case(self):
        """Test that logical_type can be set with snake_case."""
        schema = AvroSchema(
            type="long",
            logical_type="timestamp-millis"
        )
        assert schema.logical_type == "timestamp-millis"
