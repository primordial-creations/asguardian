"""
Tests for 2020-12 syntax-lint vocabulary, dialect-mismatch warnings, and
inference dialect/closed-schema options.
"""

from Asgard.Forseti.JSONSchema.models.jsonschema_models import JSONSchemaConfig
from Asgard.Forseti.JSONSchema.services.schema_inference_service import SchemaInferenceService
from Asgard.Forseti.JSONSchema.utilities.jsonschema_utils import validate_schema_syntax


DRAFT7 = "http://json-schema.org/draft-07/schema#"
D2020 = "https://json-schema.org/draft/2020-12/schema"


class TestSyntaxLint2020Vocabulary:
    def test_valid_2020_schema_has_no_errors(self):
        schema = {
            "$schema": D2020,
            "type": "array",
            "prefixItems": [{"type": "integer"}],
            "items": {"type": "string"},
            "minContains": 1,
        }
        assert validate_schema_syntax(schema) == []

    def test_prefix_items_must_be_array(self):
        errors = validate_schema_syntax({"$schema": D2020, "prefixItems": {"type": "integer"}})
        assert any("'prefixItems' must be an array" in e for e in errors)

    def test_dependent_required_shape(self):
        errors = validate_schema_syntax(
            {"$schema": D2020, "dependentRequired": {"a": "not-a-list"}})
        assert any("dependentRequired/a" in e for e in errors)

    def test_prefix_items_under_draft7_warns(self):
        errors = validate_schema_syntax({"$schema": DRAFT7, "prefixItems": [{"type": "integer"}]})
        assert any(e.startswith("WARNING:") and "prefixItems" in e for e in errors)

    def test_legacy_keywords_under_2020_warn(self):
        errors = validate_schema_syntax(
            {"$schema": D2020, "definitions": {"x": {"type": "string"}}, "dependencies": {"a": ["b"]}})
        warnings = [e for e in errors if e.startswith("WARNING:")]
        assert any("definitions" in w for w in warnings)
        assert any("dependencies" in w for w in warnings)

    def test_array_items_under_2020_warns(self):
        errors = validate_schema_syntax({"$schema": D2020, "items": [{"type": "string"}]})
        assert any("prefixItems" in e for e in errors if e.startswith("WARNING:"))

    def test_nested_subschemas_do_not_require_schema_declaration(self):
        schema = {"$schema": DRAFT7, "type": "object",
                  "properties": {"a": {"type": "string"}}}
        assert validate_schema_syntax(schema) == []

    def test_nested_mismatch_inherits_root_dialect(self):
        schema = {"$schema": DRAFT7, "type": "object",
                  "properties": {"a": {"type": "array", "prefixItems": [{"type": "string"}]}}}
        errors = validate_schema_syntax(schema)
        assert any("prefixItems" in e and "WARNING" in e for e in errors)


class TestInferenceOptions:
    def test_default_emits_draft7(self):
        result = SchemaInferenceService().infer([{"a": 1}])
        assert result.inferred_schema["$schema"] == DRAFT7

    def test_dialect_configurable_to_2020(self):
        config = JSONSchemaConfig(schema_version=D2020)
        result = SchemaInferenceService(config).infer([{"a": 1}])
        assert result.inferred_schema["$schema"] == D2020

    def test_closed_schemas_emit_additional_properties_false(self):
        config = JSONSchemaConfig(closed_schemas=True)
        result = SchemaInferenceService(config).infer([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
        assert result.inferred_schema["additionalProperties"] is False

    def test_open_by_default(self):
        result = SchemaInferenceService().infer([{"a": 1}])
        assert "additionalProperties" not in result.inferred_schema
