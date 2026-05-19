"""
Comprehensive L0 unit tests for Protobuf Models.

Tests all Pydantic models in the Forseti Protobuf module for:
- Model instantiation and validation
- Field defaults and constraints
- Property methods
- Enum values
- Edge cases and invalid inputs
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from Asgard.Forseti.Protobuf.models.protobuf_models import (
    ProtobufSyntaxVersion,
    ValidationSeverity,
    BreakingChangeType,
    CompatibilityLevel,
    ProtobufConfig,
    ProtobufValidationError,
    ProtobufField,
    ProtobufEnum,
    ProtobufMessage,
    ProtobufService,
    ProtobufSchema,
    ProtobufValidationResult,
    BreakingChange,
    ProtobufCompatibilityResult,
)


class TestProtobufSyntaxVersion:
    """Test ProtobufSyntaxVersion enum."""

    def test_enum_values(self):
        """Test all enum values are correctly defined."""
        assert ProtobufSyntaxVersion.PROTO2 == "proto2"
        assert ProtobufSyntaxVersion.PROTO3 == "proto3"

    def test_enum_membership(self):
        """Test enum membership checks."""
        assert "proto2" in [e.value for e in ProtobufSyntaxVersion]
        assert "proto3" in [e.value for e in ProtobufSyntaxVersion]


class TestValidationSeverity:
    """Test ValidationSeverity enum."""

    def test_enum_values(self):
        """Test all severity levels are defined."""
        assert ValidationSeverity.ERROR == "error"
        assert ValidationSeverity.WARNING == "warning"
        assert ValidationSeverity.INFO == "info"


class TestBreakingChangeType:
    """Test BreakingChangeType enum."""

    def test_all_change_types_defined(self):
        """Test all breaking change types are properly defined."""
        expected_types = [
            "removed_field", "removed_message", "removed_enum", "removed_enum_value",
            "removed_service", "removed_rpc", "changed_field_type", "changed_field_number",
            "changed_field_label", "changed_enum_value_number", "reserved_field_reused",
            "reserved_number_reused"
        ]
        actual_types = [e.value for e in BreakingChangeType]
        for expected in expected_types:
            assert expected in actual_types


class TestCompatibilityLevel:
    """Test CompatibilityLevel enum."""

    def test_compatibility_levels(self):
        """Test all compatibility levels are defined."""
        assert CompatibilityLevel.FULL == "full"
        assert CompatibilityLevel.BACKWARD == "backward"
        assert CompatibilityLevel.FORWARD == "forward"
        assert CompatibilityLevel.NONE == "none"


class TestProtobufConfig:
    """Test ProtobufConfig model."""

    def test_default_config(self):
        """Test config with all default values."""
        config = ProtobufConfig()

        assert config.strict_mode is False
        assert config.check_naming_conventions is True
        assert config.check_field_numbers is True
        assert config.check_reserved_fields is True
        assert config.allow_proto2 is True
        assert config.require_package is True
        assert config.max_errors == 100
        assert config.include_warnings is True

    def test_custom_config(self):
        """Test config with custom values."""
        config = ProtobufConfig(
            strict_mode=True,
            check_naming_conventions=False,
            check_field_numbers=False,
            check_reserved_fields=False,
            allow_proto2=False,
            require_package=False,
            max_errors=50,
            include_warnings=False
        )

        assert config.strict_mode is True
        assert config.check_naming_conventions is False
        assert config.check_field_numbers is False
        assert config.check_reserved_fields is False
        assert config.allow_proto2 is False
        assert config.require_package is False
        assert config.max_errors == 50
        assert config.include_warnings is False

    def test_partial_config(self):
        """Test config with partial custom values."""
        config = ProtobufConfig(strict_mode=True, max_errors=10)

        assert config.strict_mode is True
        assert config.max_errors == 10
        assert config.check_naming_conventions is True


class TestProtobufValidationError:
    """Test ProtobufValidationError model."""

    def test_minimal_error(self):
        """Test error with only required fields."""
        error = ProtobufValidationError(
            path="message.field",
            message="Test error message"
        )

        assert error.path == "message.field"
        assert error.message == "Test error message"
        assert error.severity == ValidationSeverity.ERROR
        assert error.rule is None
        assert error.line is None
        assert error.context is None

    def test_complete_error(self):
        """Test error with all fields populated."""
        error = ProtobufValidationError(
            path="message.field",
            message="Test error",
            severity=ValidationSeverity.WARNING,
            rule="test-rule",
            line=42,
            context={"field": "value", "number": 123}
        )

        assert error.path == "message.field"
        assert error.message == "Test error"
        assert error.severity == ValidationSeverity.WARNING
        assert error.rule == "test-rule"
        assert error.line == 42
        assert error.context == {"field": "value", "number": 123}

    def test_severity_levels(self):
        """Test creating errors with different severity levels."""
        error_sev = ProtobufValidationError(
            path="test",
            message="error",
            severity=ValidationSeverity.ERROR
        )
        warn_sev = ProtobufValidationError(
            path="test",
            message="warning",
            severity=ValidationSeverity.WARNING
        )
        info_sev = ProtobufValidationError(
            path="test",
            message="info",
            severity=ValidationSeverity.INFO
        )

        assert error_sev.severity == ValidationSeverity.ERROR
        assert warn_sev.severity == ValidationSeverity.WARNING
        assert info_sev.severity == ValidationSeverity.INFO


class TestProtobufField:
    """Test ProtobufField model."""

    def test_basic_field(self):
        """Test basic field with minimal attributes."""
        field = ProtobufField(
            name="test_field",
            number=1,
            type="string"
        )

        assert field.name == "test_field"
        assert field.number == 1
        assert field.type == "string"
        assert field.label is None
        assert field.default_value is None
        assert field.options is None
        assert field.oneof_group is None
        assert field.map_key_type is None
        assert field.map_value_type is None

    def test_field_with_label(self):
        """Test field with label (proto2 style)."""
        field = ProtobufField(
            name="repeated_field",
            number=2,
            type="int32",
            label="repeated"
        )

        assert field.label == "repeated"

    def test_field_with_default(self):
        """Test field with default value."""
        field = ProtobufField(
            name="field_with_default",
            number=3,
            type="int32",
            default_value="42"
        )

        assert field.default_value == "42"

    def test_field_with_options(self):
        """Test field with custom options."""
        field = ProtobufField(
            name="field_with_options",
            number=4,
            type="string",
            options={"deprecated": "true", "json_name": "fieldName"}
        )

        assert field.options == {"deprecated": "true", "json_name": "fieldName"}

    def test_oneof_field(self):
        """Test field that belongs to a oneof group."""
        field = ProtobufField(
            name="oneof_field",
            number=5,
            type="string",
            oneof_group="test_oneof"
        )

        assert field.oneof_group == "test_oneof"

    def test_map_field(self):
        """Test map field with key and value types."""
        field = ProtobufField(
            name="map_field",
            number=6,
            type="map",
            label="repeated",
            map_key_type="string",
            map_value_type="int32"
        )

        assert field.type == "map"
        assert field.map_key_type == "string"
        assert field.map_value_type == "int32"


class TestProtobufEnum:
    """Test ProtobufEnum model."""

    def test_basic_enum(self):
        """Test basic enum with minimal attributes."""
        enum = ProtobufEnum(
            name="TestEnum",
            values={"UNKNOWN": 0, "FIRST": 1, "SECOND": 2}
        )

        assert enum.name == "TestEnum"
        assert enum.values == {"UNKNOWN": 0, "FIRST": 1, "SECOND": 2}
        assert enum.options is None
        assert enum.allow_alias is False
        assert enum.reserved_names == []
        assert enum.reserved_numbers == []

    def test_enum_with_alias(self):
        """Test enum with allow_alias enabled."""
        enum = ProtobufEnum(
            name="AliasEnum",
            values={"FIRST": 0, "ALIAS": 0},
            allow_alias=True
        )

        assert enum.allow_alias is True

    def test_enum_with_reserved(self):
        """Test enum with reserved fields."""
        enum = ProtobufEnum(
            name="ReservedEnum",
            values={"VALID": 1},
            reserved_names=["OLD_NAME"],
            reserved_numbers=[0, 5, 10]
        )

        assert enum.reserved_names == ["OLD_NAME"]
        assert enum.reserved_numbers == [0, 5, 10]

    def test_enum_with_options(self):
        """Test enum with custom options."""
        enum = ProtobufEnum(
            name="OptionsEnum",
            values={"VALUE": 0},
            options={"deprecated": "true"}
        )

        assert enum.options == {"deprecated": "true"}


class TestProtobufMessage:
    """Test ProtobufMessage model."""

    def test_empty_message(self):
        """Test empty message with only name."""
        message = ProtobufMessage(name="EmptyMessage")

        assert message.name == "EmptyMessage"
        assert message.fields == []
        assert message.nested_messages == []
        assert message.nested_enums == []
        assert message.oneofs == {}
        assert message.reserved_names == []
        assert message.reserved_numbers == []
        assert message.reserved_ranges == []
        assert message.options is None

    def test_message_with_fields(self):
        """Test message with fields."""
        fields = [
            ProtobufField(name="field1", number=1, type="string"),
            ProtobufField(name="field2", number=2, type="int32")
        ]
        message = ProtobufMessage(name="TestMessage", fields=fields)

        assert len(message.fields) == 2
        assert message.fields[0].name == "field1"
        assert message.fields[1].name == "field2"

    def test_message_with_nested_messages(self):
        """Test message with nested messages."""
        nested = ProtobufMessage(name="NestedMessage")
        message = ProtobufMessage(
            name="ParentMessage",
            nested_messages=[nested]
        )

        assert len(message.nested_messages) == 1
        assert message.nested_messages[0].name == "NestedMessage"

    def test_message_with_nested_enums(self):
        """Test message with nested enums."""
        nested_enum = ProtobufEnum(name="NestedEnum", values={"VALUE": 0})
        message = ProtobufMessage(
            name="MessageWithEnum",
            nested_enums=[nested_enum]
        )

        assert len(message.nested_enums) == 1
        assert message.nested_enums[0].name == "NestedEnum"

    def test_message_with_oneofs(self):
        """Test message with oneof groups."""
        message = ProtobufMessage(
            name="OneofMessage",
            oneofs={"test_oneof": ["field1", "field2"]}
        )

        assert "test_oneof" in message.oneofs
        assert message.oneofs["test_oneof"] == ["field1", "field2"]

    def test_message_with_reserved_fields(self):
        """Test message with reserved fields."""
        message = ProtobufMessage(
            name="ReservedMessage",
            reserved_names=["old_field"],
            reserved_numbers=[5, 10],
            reserved_ranges=[(100, 200), (500, 1000)]
        )

        assert message.reserved_names == ["old_field"]
        assert message.reserved_numbers == [5, 10]
        assert message.reserved_ranges == [(100, 200), (500, 1000)]

    def test_message_with_options(self):
        """Test message with custom options."""
        message = ProtobufMessage(
            name="OptionsMessage",
            options={"deprecated": "true", "map_entry": "true"}
        )

        assert message.options == {"deprecated": "true", "map_entry": "true"}


class TestProtobufService:
    """Test ProtobufService model."""

    def test_empty_service(self):
        """Test service with no RPCs."""
        service = ProtobufService(name="EmptyService")

        assert service.name == "EmptyService"
        assert service.rpcs == {}
        assert service.options is None

    def test_service_with_rpcs(self):
        """Test service with RPC methods."""
        service = ProtobufService(
            name="TestService",
            rpcs={
                "GetUser": {
                    "input": "GetUserRequest",
                    "output": "User",
                    "input_stream": "false",
                    "output_stream": "false"
                }
            }
        )

        assert "GetUser" in service.rpcs
        assert service.rpcs["GetUser"]["input"] == "GetUserRequest"
        assert service.rpcs["GetUser"]["output"] == "User"

    def test_service_with_streaming_rpcs(self):
        """Test service with streaming RPC methods."""
        service = ProtobufService(
            name="StreamService",
            rpcs={
                "StreamData": {
                    "input": "Request",
                    "output": "Response",
                    "input_stream": "true",
                    "output_stream": "true"
                }
            }
        )

        assert service.rpcs["StreamData"]["input_stream"] == "true"
        assert service.rpcs["StreamData"]["output_stream"] == "true"

    def test_service_with_options(self):
        """Test service with custom options."""
        service = ProtobufService(
            name="OptionsService",
            options={"deprecated": "true"}
        )

        assert service.options == {"deprecated": "true"}


class TestProtobufSchema:
    """Test ProtobufSchema model."""

    def test_minimal_schema(self):
        """Test schema with minimal configuration."""
        schema = ProtobufSchema()

        assert schema.syntax == ProtobufSyntaxVersion.PROTO3
        assert schema.package is None
        assert schema.imports == []
        assert schema.public_imports == []
        assert schema.messages == []
        assert schema.enums == []
        assert schema.services == []
        assert schema.options is None
        assert schema.file_path is None

    def test_proto2_schema(self):
        """Test proto2 schema."""
        schema = ProtobufSchema(syntax=ProtobufSyntaxVersion.PROTO2)

        assert schema.syntax == ProtobufSyntaxVersion.PROTO2

    def test_schema_with_package(self):
        """Test schema with package name."""
        schema = ProtobufSchema(package="com.example.test")

        assert schema.package == "com.example.test"

    def test_schema_with_imports(self):
        """Test schema with imports."""
        schema = ProtobufSchema(
            imports=["google/protobuf/timestamp.proto"],
            public_imports=["common/types.proto"]
        )

        assert schema.imports == ["google/protobuf/timestamp.proto"]
        assert schema.public_imports == ["common/types.proto"]

    def test_schema_with_messages(self):
        """Test schema with message definitions."""
        messages = [
            ProtobufMessage(name="Message1"),
            ProtobufMessage(name="Message2")
        ]
        schema = ProtobufSchema(messages=messages)

        assert len(schema.messages) == 2

    def test_schema_with_enums(self):
        """Test schema with enum definitions."""
        enums = [
            ProtobufEnum(name="Enum1", values={"VALUE": 0}),
            ProtobufEnum(name="Enum2", values={"OPTION": 0})
        ]
        schema = ProtobufSchema(enums=enums)

        assert len(schema.enums) == 2

    def test_schema_with_services(self):
        """Test schema with service definitions."""
        services = [
            ProtobufService(name="Service1"),
            ProtobufService(name="Service2")
        ]
        schema = ProtobufSchema(services=services)

        assert len(schema.services) == 2

    def test_schema_message_count_simple(self):
        """Test message count property for simple messages."""
        messages = [
            ProtobufMessage(name="Message1"),
            ProtobufMessage(name="Message2")
        ]
        schema = ProtobufSchema(messages=messages)

        assert schema.message_count == 2

    def test_schema_message_count_with_nested(self):
        """Test message count property includes nested messages."""
        nested_message = ProtobufMessage(name="NestedMessage")
        parent_message = ProtobufMessage(
            name="ParentMessage",
            nested_messages=[nested_message]
        )
        schema = ProtobufSchema(messages=[parent_message])

        assert schema.message_count == 2

    def test_schema_message_count_deeply_nested(self):
        """Test message count with deeply nested structure."""
        deeply_nested = ProtobufMessage(name="Level3")
        level2 = ProtobufMessage(name="Level2", nested_messages=[deeply_nested])
        level1 = ProtobufMessage(name="Level1", nested_messages=[level2])
        schema = ProtobufSchema(messages=[level1])

        assert schema.message_count == 3

    def test_schema_enum_count(self):
        """Test enum count property."""
        enums = [
            ProtobufEnum(name="Enum1", values={"VALUE": 0}),
            ProtobufEnum(name="Enum2", values={"OPTION": 0}),
            ProtobufEnum(name="Enum3", values={"STATE": 0})
        ]
        schema = ProtobufSchema(enums=enums)

        assert schema.enum_count == 3

    def test_schema_service_count(self):
        """Test service count property."""
        services = [
            ProtobufService(name="Service1"),
            ProtobufService(name="Service2")
        ]
        schema = ProtobufSchema(services=services)

        assert schema.service_count == 2

    def test_schema_with_file_path(self):
        """Test schema with file path."""
        schema = ProtobufSchema(file_path="/path/to/schema.proto")

        assert schema.file_path == "/path/to/schema.proto"


class TestProtobufValidationResult:
    """Test ProtobufValidationResult model."""

    def test_valid_result(self):
        """Test validation result for valid schema."""
        result = ProtobufValidationResult(
            is_valid=True,
            file_path="test.proto"
        )

        assert result.is_valid is True
        assert result.file_path == "test.proto"
        assert result.syntax_version is None
        assert result.parsed_schema is None
        assert result.errors == []
        assert result.warnings == []
        assert result.info_messages == []
        assert isinstance(result.validated_at, datetime)
        assert result.validation_time_ms == 0.0

    def test_invalid_result_with_errors(self):
        """Test validation result with errors."""
        errors = [
            ProtobufValidationError(path="test", message="Error 1"),
            ProtobufValidationError(path="test2", message="Error 2")
        ]
        result = ProtobufValidationResult(
            is_valid=False,
            errors=errors
        )

        assert result.is_valid is False
        assert len(result.errors) == 2

    def test_result_with_warnings(self):
        """Test validation result with warnings."""
        warnings = [
            ProtobufValidationError(
                path="test",
                message="Warning 1",
                severity=ValidationSeverity.WARNING
            )
        ]
        result = ProtobufValidationResult(
            is_valid=True,
            warnings=warnings
        )

        assert result.is_valid is True
        assert len(result.warnings) == 1

    def test_result_with_parsed_schema(self):
        """Test validation result with parsed schema."""
        schema = ProtobufSchema(package="com.example")
        result = ProtobufValidationResult(
            is_valid=True,
            parsed_schema=schema,
            syntax_version=ProtobufSyntaxVersion.PROTO3
        )

        assert result.parsed_schema is not None
        assert result.parsed_schema.package == "com.example"
        assert result.syntax_version == ProtobufSyntaxVersion.PROTO3

    def test_result_error_count(self):
        """Test error count property."""
        errors = [
            ProtobufValidationError(path="e1", message="Error 1"),
            ProtobufValidationError(path="e2", message="Error 2"),
            ProtobufValidationError(path="e3", message="Error 3")
        ]
        result = ProtobufValidationResult(is_valid=False, errors=errors)

        assert result.error_count == 3

    def test_result_warning_count(self):
        """Test warning count property."""
        warnings = [
            ProtobufValidationError(path="w1", message="Warning 1", severity=ValidationSeverity.WARNING),
            ProtobufValidationError(path="w2", message="Warning 2", severity=ValidationSeverity.WARNING)
        ]
        result = ProtobufValidationResult(is_valid=True, warnings=warnings)

        assert result.warning_count == 2

    def test_result_total_issues(self):
        """Test total issues property."""
        errors = [
            ProtobufValidationError(path="e1", message="Error 1"),
            ProtobufValidationError(path="e2", message="Error 2")
        ]
        warnings = [
            ProtobufValidationError(path="w1", message="Warning 1", severity=ValidationSeverity.WARNING),
            ProtobufValidationError(path="w2", message="Warning 2", severity=ValidationSeverity.WARNING),
            ProtobufValidationError(path="w3", message="Warning 3", severity=ValidationSeverity.WARNING)
        ]
        result = ProtobufValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings
        )

        assert result.total_issues == 5

    def test_result_with_timing(self):
        """Test validation result with timing information."""
        result = ProtobufValidationResult(
            is_valid=True,
            validation_time_ms=123.45
        )

        assert result.validation_time_ms == 123.45


class TestBreakingChange:
    """Test BreakingChange model."""

    def test_minimal_breaking_change(self):
        """Test breaking change with minimal fields."""
        change = BreakingChange(
            change_type=BreakingChangeType.REMOVED_FIELD,
            path="message.field",
            message="Field was removed"
        )

        assert change.change_type == BreakingChangeType.REMOVED_FIELD
        assert change.path == "message.field"
        assert change.message == "Field was removed"
        assert change.old_value is None
        assert change.new_value is None
        assert change.severity == "error"
        assert change.mitigation is None

    def test_complete_breaking_change(self):
        """Test breaking change with all fields."""
        change = BreakingChange(
            change_type=BreakingChangeType.CHANGED_FIELD_TYPE,
            path="message.field",
            message="Type changed",
            old_value="string",
            new_value="int32",
            severity="error",
            mitigation="Use a new field instead"
        )

        assert change.change_type == BreakingChangeType.CHANGED_FIELD_TYPE
        assert change.old_value == "string"
        assert change.new_value == "int32"
        assert change.severity == "error"
        assert change.mitigation == "Use a new field instead"

    def test_warning_severity_change(self):
        """Test breaking change with warning severity."""
        change = BreakingChange(
            change_type=BreakingChangeType.REMOVED_FIELD,
            path="message.field",
            message="Field removed but reserved",
            severity="warning"
        )

        assert change.severity == "warning"


class TestProtobufCompatibilityResult:
    """Test ProtobufCompatibilityResult model."""

    def test_compatible_result(self):
        """Test compatibility result for compatible schemas."""
        result = ProtobufCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.FULL
        )

        assert result.is_compatible is True
        assert result.compatibility_level == CompatibilityLevel.FULL
        assert result.source_file is None
        assert result.target_file is None
        assert result.breaking_changes == []
        assert result.warnings == []
        assert result.added_messages == []
        assert result.removed_messages == []
        assert result.modified_messages == []
        assert result.check_time_ms == 0.0
        assert isinstance(result.checked_at, datetime)

    def test_incompatible_result_with_breaking_changes(self):
        """Test compatibility result with breaking changes."""
        breaking_changes = [
            BreakingChange(
                change_type=BreakingChangeType.REMOVED_FIELD,
                path="Message.field",
                message="Field removed"
            )
        ]
        result = ProtobufCompatibilityResult(
            is_compatible=False,
            compatibility_level=CompatibilityLevel.NONE,
            breaking_changes=breaking_changes
        )

        assert result.is_compatible is False
        assert result.compatibility_level == CompatibilityLevel.NONE
        assert len(result.breaking_changes) == 1

    def test_result_with_file_paths(self):
        """Test compatibility result with file paths."""
        result = ProtobufCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.BACKWARD,
            source_file="old.proto",
            target_file="new.proto"
        )

        assert result.source_file == "old.proto"
        assert result.target_file == "new.proto"

    def test_result_with_message_lists(self):
        """Test compatibility result with message change lists."""
        result = ProtobufCompatibilityResult(
            is_compatible=False,
            compatibility_level=CompatibilityLevel.NONE,
            added_messages=["NewMessage"],
            removed_messages=["OldMessage"],
            modified_messages=["ModifiedMessage"]
        )

        assert result.added_messages == ["NewMessage"]
        assert result.removed_messages == ["OldMessage"]
        assert result.modified_messages == ["ModifiedMessage"]

    def test_result_breaking_change_count(self):
        """Test breaking change count property."""
        breaking_changes = [
            BreakingChange(
                change_type=BreakingChangeType.REMOVED_FIELD,
                path="M1.f1",
                message="Removed"
            ),
            BreakingChange(
                change_type=BreakingChangeType.CHANGED_FIELD_TYPE,
                path="M2.f2",
                message="Changed"
            )
        ]
        result = ProtobufCompatibilityResult(
            is_compatible=False,
            compatibility_level=CompatibilityLevel.NONE,
            breaking_changes=breaking_changes
        )

        assert result.breaking_change_count == 2

    def test_result_warning_count(self):
        """Test warning count property."""
        warnings = [
            BreakingChange(
                change_type=BreakingChangeType.REMOVED_FIELD,
                path="M.f",
                message="Removed with reserve",
                severity="warning"
            )
        ]
        result = ProtobufCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.FULL,
            warnings=warnings
        )

        assert result.warning_count == 1

    def test_result_with_timing(self):
        """Test compatibility result with timing information."""
        result = ProtobufCompatibilityResult(
            is_compatible=True,
            compatibility_level=CompatibilityLevel.FULL,
            check_time_ms=456.78
        )

        assert result.check_time_ms == 456.78


class TestModelValidation:
    """Test Pydantic validation for required fields."""

    def test_protobuf_field_requires_name(self):
        """Test that ProtobufField requires name."""
        with pytest.raises(ValidationError) as exc_info:
            ProtobufField(number=1, type="string")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_protobuf_field_requires_number(self):
        """Test that ProtobufField requires number."""
        with pytest.raises(ValidationError) as exc_info:
            ProtobufField(name="field", type="string")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("number",) for e in errors)

    def test_protobuf_field_requires_type(self):
        """Test that ProtobufField requires type."""
        with pytest.raises(ValidationError) as exc_info:
            ProtobufField(name="field", number=1)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_protobuf_message_requires_name(self):
        """Test that ProtobufMessage requires name."""
        with pytest.raises(ValidationError) as exc_info:
            ProtobufMessage()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_protobuf_validation_result_requires_is_valid(self):
        """Test that ProtobufValidationResult requires is_valid."""
        with pytest.raises(ValidationError) as exc_info:
            ProtobufValidationResult()

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
        """Test that ProtobufCompatibilityResult requires is_compatible and compatibility_level."""
        with pytest.raises(ValidationError) as exc_info:
            ProtobufCompatibilityResult()

        errors = exc_info.value.errors()
        error_locs = {e["loc"] for e in errors}
        assert ("is_compatible",) in error_locs
        assert ("compatibility_level",) in error_locs
