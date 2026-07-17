"""
Tests for the Dialect Converter Service (OAS 3.0 <-> 3.1 schema dialects).
"""

from Asgard.Forseti.JSONSchema.services.dialect_converter_service import DialectConverterService


class TestConvert30To31:
    def setup_method(self):
        self.service = DialectConverterService()

    def test_nullable_true_becomes_type_array(self):
        result = self.service.convert_30_to_31({"type": "string", "nullable": True})
        assert result.converted == {"type": ["string", "null"]}
        assert result.is_lossless
        assert result.changed

    def test_nullable_false_is_dropped(self):
        result = self.service.convert_30_to_31({"type": "string", "nullable": False})
        assert result.converted == {"type": "string"}
        assert result.is_lossless

    def test_boolean_exclusive_minimum_becomes_numeric(self):
        result = self.service.convert_30_to_31({"type": "number", "minimum": 5, "exclusiveMinimum": True})
        assert result.converted == {"type": "number", "exclusiveMinimum": 5}
        assert result.is_lossless

    def test_boolean_exclusive_maximum_becomes_numeric(self):
        result = self.service.convert_30_to_31({"type": "number", "maximum": 9, "exclusiveMaximum": True})
        assert result.converted == {"type": "number", "exclusiveMaximum": 9}

    def test_exclusive_false_is_dropped(self):
        result = self.service.convert_30_to_31({"type": "number", "minimum": 5, "exclusiveMinimum": False})
        assert result.converted == {"type": "number", "minimum": 5}

    def test_example_becomes_examples(self):
        result = self.service.convert_30_to_31({"type": "string", "example": "hi"})
        assert result.converted == {"type": "string", "examples": ["hi"]}
        assert result.is_lossless

    def test_array_form_items_becomes_prefix_items(self):
        result = self.service.convert_30_to_31(
            {"type": "array", "items": [{"type": "integer"}], "additionalItems": {"type": "string"}})
        assert result.converted == {
            "type": "array", "prefixItems": [{"type": "integer"}], "items": {"type": "string"}}

    def test_nested_schemas_are_converted(self):
        result = self.service.convert_30_to_31({
            "type": "object",
            "properties": {"name": {"type": "string", "nullable": True}},
            "items": {"type": "integer", "nullable": True},
        })
        assert result.converted["properties"]["name"] == {"type": ["string", "null"]}
        assert result.converted["items"] == {"type": ["integer", "null"]}

    def test_no_change_reports_unchanged(self):
        result = self.service.convert_30_to_31({"type": "string"})
        assert not result.changed
        assert result.is_lossless


class TestConvert31To30:
    def setup_method(self):
        self.service = DialectConverterService()

    def test_type_array_with_null_becomes_nullable(self):
        result = self.service.convert_31_to_30({"type": ["string", "null"]})
        assert result.converted == {"type": "string", "nullable": True}
        assert result.is_lossless

    def test_multi_type_array_is_lossy(self):
        result = self.service.convert_31_to_30({"type": ["string", "integer", "null"]})
        assert result.converted["nullable"] is True
        assert len(result.lossy_changes) == 1
        assert result.lossy_changes[0].keyword == "type"

    def test_numeric_exclusive_minimum_becomes_boolean_form(self):
        result = self.service.convert_31_to_30({"type": "number", "exclusiveMinimum": 5})
        assert result.converted == {"type": "number", "minimum": 5, "exclusiveMinimum": True}
        assert result.is_lossless

    def test_prefix_items_becomes_array_items(self):
        result = self.service.convert_31_to_30(
            {"type": "array", "prefixItems": [{"type": "integer"}], "items": {"type": "string"}})
        assert result.converted == {
            "type": "array", "items": [{"type": "integer"}], "additionalItems": {"type": "string"}}

    def test_unevaluated_properties_dropped_with_exactly_one_loss_record(self):
        result = self.service.convert_31_to_30(
            {"type": "object", "unevaluatedProperties": False})
        assert "unevaluatedProperties" not in result.converted
        assert len(result.lossy_changes) == 1
        loss = result.lossy_changes[0]
        assert loss.keyword == "unevaluatedProperties"
        assert loss.severity == "warning"

    def test_const_becomes_single_value_enum(self):
        result = self.service.convert_31_to_30({"const": "fixed"})
        assert result.converted == {"enum": ["fixed"]}

    def test_examples_becomes_example(self):
        result = self.service.convert_31_to_30({"type": "string", "examples": ["a", "b"]})
        assert result.converted == {"type": "string", "example": "a"}
        assert len(result.lossy_changes) == 1
        assert result.lossy_changes[0].keyword == "examples"
        assert result.lossy_changes[0].severity == "info"

    def test_every_lossy_transform_yields_exactly_one_record(self):
        result = self.service.convert_31_to_30({
            "type": "object",
            "unevaluatedProperties": False,
            "properties": {"x": {"type": ["string", "integer", "boolean"]}},
        })
        assert len(result.lossy_changes) == 2
        assert {loss.keyword for loss in result.lossy_changes} == {"unevaluatedProperties", "type"}


class TestRoundTrip:
    def setup_method(self):
        self.service = DialectConverterService()

    def test_lossless_subset_round_trip_is_idempotent(self):
        original_30 = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "nullable": True, "example": "bob"},
                "age": {"type": "integer", "minimum": 0, "exclusiveMinimum": True},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        }
        up = self.service.convert_30_to_31(original_30)
        assert up.is_lossless
        down = self.service.convert_31_to_30(up.converted)
        assert down.is_lossless
        assert down.converted == original_30

    def test_up_then_down_then_up_is_stable(self):
        schema_30 = {"type": "string", "nullable": True}
        first_up = self.service.convert_30_to_31(schema_30).converted
        second_up = self.service.convert_30_to_31(
            self.service.convert_31_to_30(first_up).converted).converted
        assert first_up == second_up
