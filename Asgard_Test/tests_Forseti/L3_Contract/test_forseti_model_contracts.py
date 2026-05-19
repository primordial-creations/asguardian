"""L3 Contract tests for Forseti (API contract / schema validation) models.

Public models exported from Asgard.Forseti:
  OpenAPIConfig, OpenAPIValidationResult,
  JSONSchemaConfig, JSONSchemaValidationResult,
  GraphQLConfig, GraphQLValidationResult,
  ContractConfig, CompatibilityResult,
  AsyncAPIConfig, AvroConfig, ProtobufConfig,
  CodeGenConfig, MockServerConfig
"""

import pytest
from pydantic import ValidationError

from Asgard.Forseti import (
    OpenAPIConfig,
    OpenAPIValidationResult,
    JSONSchemaConfig,
    JSONSchemaValidationResult,
    GraphQLConfig,
    GraphQLValidationResult,
    ContractConfig,
    CompatibilityResult,
    AsyncAPIConfig,
    AvroConfig,
    ProtobufConfig,
    CodeGenConfig,
    MockServerConfig,
)


# ---------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------
class TestOpenAPIConfigContract:
    def test_instantiates_with_defaults(self):
        config = OpenAPIConfig()
        assert hasattr(config, "strict_mode")

    def test_has_validate_examples_field(self):
        config = OpenAPIConfig()
        assert hasattr(config, "validate_examples")

    def test_has_validate_schemas_field(self):
        config = OpenAPIConfig()
        assert hasattr(config, "validate_schemas")

    def test_has_target_version_field(self):
        config = OpenAPIConfig()
        assert hasattr(config, "target_version")


class TestOpenAPIValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            OpenAPIValidationResult()

    def test_instantiates_with_required_fields(self):
        result = OpenAPIValidationResult(is_valid=True)
        assert result.is_valid is True

    def test_has_errors_field(self):
        result = OpenAPIValidationResult(is_valid=True)
        assert hasattr(result, "errors")
        assert isinstance(result.errors, list)

    def test_has_validated_at_field(self):
        result = OpenAPIValidationResult(is_valid=False)
        assert hasattr(result, "validated_at")


# ---------------------------------------------------------------------------
# JSONSchema
# ---------------------------------------------------------------------------
class TestJSONSchemaConfigContract:
    def test_instantiates_with_defaults(self):
        config = JSONSchemaConfig()
        assert hasattr(config, "strict_mode")

    def test_has_check_formats_field(self):
        config = JSONSchemaConfig()
        assert hasattr(config, "check_formats")

    def test_has_resolve_references_field(self):
        config = JSONSchemaConfig()
        assert hasattr(config, "resolve_references")


class TestJSONSchemaValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            JSONSchemaValidationResult()

    def test_instantiates_with_required_fields(self):
        result = JSONSchemaValidationResult(is_valid=True)
        assert result.is_valid is True

    def test_has_errors_field(self):
        result = JSONSchemaValidationResult(is_valid=True)
        assert isinstance(result.errors, list)


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------
class TestGraphQLConfigContract:
    def test_instantiates_with_defaults(self):
        config = GraphQLConfig()
        assert hasattr(config, "strict_mode")

    def test_has_max_depth_field(self):
        config = GraphQLConfig()
        assert hasattr(config, "max_depth")

    def test_has_max_complexity_field(self):
        config = GraphQLConfig()
        assert hasattr(config, "max_complexity")


class TestGraphQLValidationResultContract:
    def test_requires_is_valid(self):
        with pytest.raises((ValidationError, TypeError)):
            GraphQLValidationResult()

    def test_instantiates_with_required_fields(self):
        result = GraphQLValidationResult(is_valid=True)
        assert result.is_valid is True

    def test_has_errors_field(self):
        result = GraphQLValidationResult(is_valid=True)
        assert hasattr(result, "errors")

    def test_has_type_count_field(self):
        result = GraphQLValidationResult(is_valid=True)
        assert hasattr(result, "type_count")


# ---------------------------------------------------------------------------
# Contract / Compatibility
# ---------------------------------------------------------------------------
class TestContractConfigContract:
    def test_instantiates_with_defaults(self):
        config = ContractConfig()
        assert hasattr(config, "strict_mode")

    def test_has_check_request_body_field(self):
        config = ContractConfig()
        assert hasattr(config, "check_request_body")

    def test_has_check_response_body_field(self):
        config = ContractConfig()
        assert hasattr(config, "check_response_body")


class TestCompatibilityResultContract:
    def test_requires_is_compatible(self):
        with pytest.raises((ValidationError, TypeError)):
            CompatibilityResult()

    def test_instantiates_with_required_fields(self):
        result = CompatibilityResult(
            is_compatible=True,
            compatibility_level="backward",
        )
        assert result.is_compatible is True

    def test_has_breaking_changes_field(self):
        result = CompatibilityResult(
            is_compatible=True,
            compatibility_level="full",
        )
        assert hasattr(result, "breaking_changes")

    def test_has_checked_at_field(self):
        result = CompatibilityResult(
            is_compatible=False,
            compatibility_level="none",
        )
        assert hasattr(result, "checked_at")


# ---------------------------------------------------------------------------
# AsyncAPI / Avro / Protobuf (config shape only)
# ---------------------------------------------------------------------------
class TestAsyncAPIConfigContract:
    def test_instantiates(self):
        config = AsyncAPIConfig()
        assert config is not None

    def test_has_strict_mode_field(self):
        assert hasattr(AsyncAPIConfig(), "strict_mode")


class TestAvroConfigContract:
    def test_instantiates(self):
        config = AvroConfig()
        assert config is not None

    def test_has_strict_mode_field(self):
        assert hasattr(AvroConfig(), "strict_mode")


class TestProtobufConfigContract:
    def test_instantiates(self):
        config = ProtobufConfig()
        assert config is not None

    def test_has_strict_mode_field(self):
        assert hasattr(ProtobufConfig(), "strict_mode")


# ---------------------------------------------------------------------------
# CodeGen / MockServer (config shape only)
# ---------------------------------------------------------------------------
class TestCodeGenConfigContract:
    def test_instantiates(self):
        config = CodeGenConfig()
        assert config is not None


class TestMockServerConfigContract:
    def test_instantiates(self):
        config = MockServerConfig()
        assert config is not None
