"""
Tests for the Schema Compiler Service (compile-then-run engine).

Covers dialect detection, $ref/$defs/anchor resolution, cycle safety,
file references, compilation caching, and validator-service integration.
"""

import json

import pytest

from Asgard.Forseti.JSONSchema.models.jsonschema_models import JSONSchemaConfig
from Asgard.Forseti.JSONSchema.services.schema_compiler_service import (
    SchemaCompilerService,
    SchemaDialect,
)
from Asgard.Forseti.JSONSchema.services.schema_validator_service import SchemaValidatorService
from Asgard.Forseti.JSONSchema.services._ref_resolver_helpers import (
    RefResolutionError,
    SchemaRegistry,
    resolve_json_pointer,
)


class TestDialectDetection:
    def test_detects_draft7_from_schema_uri(self):
        compiled = SchemaCompilerService().compile(
            {"$schema": "http://json-schema.org/draft-07/schema#", "type": "string"})
        assert compiled.dialect == SchemaDialect.DRAFT7

    def test_detects_2020_12_from_schema_uri(self):
        compiled = SchemaCompilerService().compile(
            {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "string"})
        assert compiled.dialect == SchemaDialect.DRAFT2020

    def test_detects_2019_09_from_schema_uri(self):
        compiled = SchemaCompilerService().compile(
            {"$schema": "https://json-schema.org/draft/2019-09/schema", "type": "string"})
        assert compiled.dialect == SchemaDialect.DRAFT2019

    def test_defaults_to_configured_version_when_absent(self):
        compiled = SchemaCompilerService().compile({"type": "string"})
        assert compiled.dialect == SchemaDialect.DRAFT7  # config default is draft-07

    def test_explicit_dialect_override_wins(self):
        compiled = SchemaCompilerService().compile(
            {"$schema": "http://json-schema.org/draft-07/schema#"}, dialect="2020-12")
        assert compiled.dialect == SchemaDialect.DRAFT2020

    def test_validation_result_carries_dialect(self):
        result = SchemaValidatorService().validate(
            "x", {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "string"})
        assert result.dialect == "2020-12"
        assert result.is_valid


class TestRefResolution:
    def test_defs_ref(self):
        schema = {"$defs": {"name": {"type": "string"}}, "properties": {"n": {"$ref": "#/$defs/name"}}}
        compiled = SchemaCompilerService().compile(schema, dialect="2020-12")
        assert compiled.is_valid({"n": "ok"})
        assert not compiled.is_valid({"n": 1})

    def test_definitions_ref_draft7(self):
        schema = {"definitions": {"name": {"type": "string"}}, "properties": {"n": {"$ref": "#/definitions/name"}}}
        compiled = SchemaCompilerService().compile(schema, dialect="draft-07")
        assert compiled.is_valid({"n": "ok"})
        assert not compiled.is_valid({"n": 1})

    def test_self_referencing_linked_list_cycle_safe(self):
        schema = {
            "$defs": {"node": {
                "type": "object",
                "properties": {"value": {"type": "integer"}, "next": {"$ref": "#/$defs/node"}},
                "required": ["value"],
            }},
            "$ref": "#/$defs/node",
        }
        compiled = SchemaCompilerService().compile(schema, dialect="2020-12")
        chain = {"value": 1}
        for i in range(2, 60):
            chain = {"value": i, "next": chain}
        assert compiled.is_valid(chain)
        assert not compiled.is_valid({"value": 1, "next": {"no_value": True}})

    def test_mutually_recursive_refs(self):
        schema = {
            "$defs": {
                "a": {"type": "object", "properties": {"b": {"$ref": "#/$defs/b"}}},
                "b": {"type": "object", "properties": {"a": {"$ref": "#/$defs/a"}}},
            },
            "$ref": "#/$defs/a",
        }
        compiled = SchemaCompilerService().compile(schema, dialect="2020-12")
        assert compiled.is_valid({"b": {"a": {"b": {}}}})
        assert not compiled.is_valid({"b": "not-an-object"})

    def test_anchor_ref(self):
        schema = {"$defs": {"x": {"$anchor": "target", "type": "integer"}},
                  "properties": {"v": {"$ref": "#target"}}}
        compiled = SchemaCompilerService().compile(schema, dialect="2020-12")
        assert compiled.is_valid({"v": 1})
        assert not compiled.is_valid({"v": "s"})

    def test_unresolvable_ref_reports_error(self):
        compiled = SchemaCompilerService().compile({"$ref": "#/$defs/missing"}, dialect="2020-12")
        errors = compiled.validate(1)
        assert errors and errors[0].constraint == "ref"

    def test_file_ref_relative_to_schema_file(self, tmp_path):
        (tmp_path / "name.json").write_text(json.dumps({"type": "string", "minLength": 2}))
        main = tmp_path / "main.json"
        main.write_text(json.dumps({"properties": {"name": {"$ref": "name.json"}}}))
        service = SchemaValidatorService()
        assert service.validate({"name": "ok"}, main).is_valid
        assert not service.validate({"name": "x"}, main).is_valid

    def test_json_pointer_escapes(self):
        doc = {"a/b": {"c~d": 42}}
        assert resolve_json_pointer(doc, "/a~1b/c~0d") == 42
        with pytest.raises(RefResolutionError):
            resolve_json_pointer(doc, "/missing")

    def test_registry_indexes_ids_and_anchors(self):
        schema = {"$id": "https://ex.com/root", "$defs": {
            "a": {"$id": "https://ex.com/a", "$anchor": "anch", "type": "integer"}}}
        registry = SchemaRegistry(schema, base_uri="https://ex.com/root")
        sub, base = registry.resolve("https://ex.com/a", "https://ex.com/root")
        assert sub["type"] == "integer"
        sub2, _ = registry.resolve("https://ex.com/a#anch", "https://ex.com/root")
        assert sub2 is sub


class TestCompilationCache:
    def test_cache_returns_same_compiled_object(self):
        SchemaCompilerService.clear_cache()
        service = SchemaCompilerService()
        schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
        first = service.compile(schema)
        second = service.compile(json.loads(json.dumps(schema)))  # equal content, new dict
        assert first is second

    def test_cache_distinguishes_config(self):
        SchemaCompilerService.clear_cache()
        schema = {"type": "string", "format": "email"}
        a = SchemaCompilerService(JSONSchemaConfig(check_formats=True)).compile(schema)
        b = SchemaCompilerService(JSONSchemaConfig(check_formats=False)).compile(schema)
        assert a is not b
        assert not a.is_valid("nope")
        assert b.is_valid("nope")  # annotation-only

    def test_cache_distinguishes_dialect(self):
        SchemaCompilerService.clear_cache()
        service = SchemaCompilerService()
        schema = {"items": [{"type": "integer"}], "additionalItems": False}
        d7 = service.compile(schema, dialect="draft-07")
        d20 = service.compile(schema, dialect="2020-12")
        assert d7 is not d20
        assert not d7.is_valid([1, "extra"])  # additionalItems enforced in draft-07


class TestEngineBehaviors:
    def test_draft7_ref_ignores_siblings(self):
        schema = {"definitions": {"arr": {"type": "array"}},
                  "properties": {"x": {"$ref": "#/definitions/arr", "maxItems": 1}}}
        d7 = SchemaCompilerService().compile(schema, dialect="draft-07")
        assert d7.is_valid({"x": [1, 2, 3]})
        d20 = SchemaCompilerService().compile(schema, dialect="2020-12")
        assert not d20.is_valid({"x": [1, 2, 3]})

    def test_resolve_references_false_disables_refs(self):
        config = JSONSchemaConfig(resolve_references=False)
        compiled = SchemaCompilerService(config).compile(
            {"$defs": {"s": {"type": "string"}}, "$ref": "#/$defs/s"}, dialect="2020-12")
        assert compiled.is_valid(123)  # $ref inert

    def test_legacy_strict_mode_false_allows_additional_properties(self):
        config = JSONSchemaConfig(strict_mode=False)
        compiled = SchemaCompilerService(config).compile(
            {"type": "object", "properties": {"a": {}}, "additionalProperties": False})
        assert compiled.is_valid({"a": 1, "extra": 2})

    def test_draft4_boolean_exclusive_minimum_tolerated(self):
        compiled = SchemaCompilerService().compile(
            {"minimum": 5, "exclusiveMinimum": True}, dialect="draft-04")
        assert not compiled.is_valid(5)
        assert compiled.is_valid(6)

    def test_deeply_nested_data_guard(self):
        schema = {"$defs": {"n": {"properties": {"next": {"$ref": "#/$defs/n"}}}}, "$ref": "#/$defs/n"}
        compiled = SchemaCompilerService().compile(schema, dialect="2020-12")
        data: dict = {}
        cursor = data
        for _ in range(600):
            cursor["next"] = {}
            cursor = cursor["next"]
        errors = compiled.validate(data)
        assert errors and errors[0].constraint == "max_depth"
