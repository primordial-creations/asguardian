"""
Tests for the LLM Profile Service (structured-output subset linting).
"""

import pytest

from Asgard.Forseti.JSONSchema.services.llm_profile_service import LLMProfileService


def _strict_openai_schema():
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
        "additionalProperties": False,
    }


class TestOpenAIProfile:
    def setup_method(self):
        self.service = LLMProfileService()

    def test_compliant_schema_is_compatible(self):
        result = self.service.check(_strict_openai_schema(), provider="openai")
        assert result.is_compatible
        assert result.error_count == 0

    def test_non_object_root_is_error(self):
        result = self.service.check({"type": "string"}, provider="openai")
        assert not result.is_compatible
        assert any(i.rule_id == "llm.openai.root-object" for i in result.issues)

    def test_optional_properties_are_error(self):
        schema = _strict_openai_schema()
        schema["required"] = ["name"]
        result = self.service.check(schema, provider="openai")
        assert not result.is_compatible
        issue = next(i for i in result.issues if i.rule_id == "llm.openai.all-required")
        assert "age" in issue.message

    def test_open_object_is_error(self):
        schema = _strict_openai_schema()
        del schema["additionalProperties"]
        result = self.service.check(schema, provider="openai")
        assert any(i.rule_id == "llm.openai.additional-properties" for i in result.issues)
        assert not result.is_compatible

    def test_nested_objects_are_checked(self):
        schema = _strict_openai_schema()
        schema["properties"]["address"] = {
            "type": "object",
            "properties": {"street": {"type": "string"}},
            "required": ["street"],
            # missing additionalProperties: false
        }
        schema["required"].append("address")
        result = self.service.check(schema, provider="openai")
        assert any(i.rule_id == "llm.openai.additional-properties" and "address" in i.path
                   for i in result.issues)

    def test_unsupported_keywords_flagged(self):
        schema = _strict_openai_schema()
        schema["not"] = {"type": "null"}
        schema["patternProperties"] = {"^x": {"type": "string"}}
        result = self.service.check(schema, provider="openai")
        rule_ids = {i.rule_id for i in result.issues}
        assert "llm.openai.not" in rule_ids
        assert "llm.openai.patternproperties" in rule_ids
        assert not result.is_compatible

    def test_excessive_nesting_is_error(self):
        schema: dict = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
        cursor = schema
        for i in range(7):
            child = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
            cursor["properties"] = {f"level{i}": child}
            cursor["required"] = [f"level{i}"]
            cursor = child
        result = self.service.check(schema, provider="openai")
        assert any(i.rule_id == "llm.openai.max-nesting" for i in result.issues)

    def test_enum_value_budget(self):
        schema = _strict_openai_schema()
        schema["properties"]["code"] = {"type": "string", "enum": [f"v{i}" for i in range(600)]}
        schema["required"].append("code")
        result = self.service.check(schema, provider="openai")
        assert any(i.rule_id == "llm.openai.max-enum-values" for i in result.issues)


class TestAnthropicProfile:
    def setup_method(self):
        self.service = LLMProfileService()

    def test_optional_properties_allowed(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        result = self.service.check(schema, provider="anthropic")
        assert result.is_compatible

    def test_conditional_keywords_warn_not_error(self):
        schema = {"type": "object", "if": {"required": ["a"]}, "then": {"required": ["b"]},
                  "properties": {"a": {}, "b": {}}}
        result = self.service.check(schema, provider="anthropic")
        assert result.is_compatible  # warnings only
        assert result.warning_count >= 2

    def test_non_object_root_is_error(self):
        result = self.service.check({"type": "array"}, provider="anthropic")
        assert not result.is_compatible


class TestGeminiProfile:
    def setup_method(self):
        self.service = LLMProfileService()

    def test_ref_is_error(self):
        schema = {"type": "object", "properties": {"a": {"$ref": "#/$defs/x"}},
                  "$defs": {"x": {"type": "string"}}}
        result = self.service.check(schema, provider="gemini")
        assert not result.is_compatible
        assert any(i.rule_id == "llm.gemini.ref" for i in result.issues)
        assert any(i.rule_id == "llm.gemini.defs" for i in result.issues)

    def test_plain_subset_is_compatible(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}, "n": {"type": "number"}}}
        result = self.service.check(schema, provider="gemini")
        assert result.is_compatible


class TestProviderHandling:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMProfileService().check({}, provider="mistral")

    def test_provider_list_exposed(self):
        assert set(LLMProfileService.PROVIDERS) == {"openai", "anthropic", "gemini"}
