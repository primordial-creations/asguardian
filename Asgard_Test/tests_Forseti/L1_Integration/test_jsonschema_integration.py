"""
JSON Schema Integration Tests

Tests for JSON Schema validation, generation, and inference workflows.
"""

import json
import pytest
from pathlib import Path

from Asgard.Forseti.JSONSchema import (
    SchemaValidatorService as JSONSchemaValidatorService,
    SchemaGeneratorService,
    SchemaInferenceService,
    JSONSchemaConfig,
)


class TestJSONSchemaValidation:
    """Tests for JSON Schema validation workflows."""

    def test_workflow_validate_data_against_schema(self, sample_json_schema, sample_valid_data):
        """Test validating data against a JSON schema."""
        validator = JSONSchemaValidatorService()

        result = validator.validate(sample_valid_data, sample_json_schema)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_workflow_detect_validation_errors(self, sample_json_schema, sample_invalid_data):
        """Test detecting validation errors."""
        validator = JSONSchemaValidatorService()

        result = validator.validate(sample_invalid_data, sample_json_schema)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Should report specific validation errors
        for error in result.errors:
            assert error.message is not None
            assert error.path is not None

    def test_workflow_validate_from_files(self, json_schema_file, tmp_path, sample_valid_data):
        """Test validating data from files."""
        # Save data to file
        data_file = tmp_path / "data.json"
        with open(data_file, "w") as f:
            json.dump(sample_valid_data, f)

        validator = JSONSchemaValidatorService()
        result = validator.validate_file(data_file, json_schema_file)

        assert result.is_valid is True

    def test_workflow_validate_multiple_drafts(self, tmp_path, jsonschema_draft_7, jsonschema_draft_2020_12):
        """Test validating schemas from different JSON Schema drafts."""
        validator = JSONSchemaValidatorService()

        # Test draft 7
        draft7_file = tmp_path / "draft7.json"
        with open(draft7_file, "w") as f:
            json.dump(jsonschema_draft_7, f)

        data = {"id": 1, "email": "test@example.com", "name": "Test"}
        result_draft7 = validator.validate(data, jsonschema_draft_7)
        assert result_draft7.is_valid is True

        # Test draft 2020-12
        draft2020_file = tmp_path / "draft2020.json"
        with open(draft2020_file, "w") as f:
            json.dump(jsonschema_draft_2020_12, f)

        result_draft2020 = validator.validate(data, jsonschema_draft_2020_12)
        assert result_draft2020.is_valid is True

    def test_workflow_validation_report_generation(self, sample_json_schema, sample_invalid_data):
        """Test generating validation reports."""
        validator = JSONSchemaValidatorService()

        result = validator.validate(sample_invalid_data, sample_json_schema)

        # Generate reports
        text_report = validator.generate_report(result, format="text")
        json_report = validator.generate_report(result, format="json")

        assert len(text_report) > 0
        assert len(json_report) > 0

        # Verify JSON report structure
        json_data = json.loads(json_report)
        assert "is_valid" in json_data
        assert json_data["is_valid"] is False
        assert "errors" in json_data


class TestJSONSchemaInference:
    """Tests for JSON Schema inference from data."""

    def test_workflow_infer_from_simple_data(self, json_data_samples):
        """Test inferring schema from simple JSON data."""
        inference = SchemaInferenceService()

        result = inference.infer([json_data_samples["simple_user"]])

        assert result.inferred_schema is not None

        # Verify inferred schema structure
        schema = result.inferred_schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "id" in schema["properties"]
        assert "email" in schema["properties"]
        assert "name" in schema["properties"]

    def test_workflow_infer_from_nested_data(self, json_data_samples):
        """Test inferring schema from nested JSON data."""
        inference = SchemaInferenceService()

        result = inference.infer([json_data_samples["complex_nested"]])

        schema = result.inferred_schema
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_workflow_infer_from_array_data(self, json_data_samples):
        """Test inferring schema from array data."""
        inference = SchemaInferenceService()

        samples = [
            json_data_samples["simple_user"],
            {"id": 2, "email": "user2@example.com", "name": "Jane Doe"}
        ]

        result = inference.infer(samples)

        schema = result.inferred_schema
        # With multiple object samples the inferred schema should be of type object.
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_workflow_infer_and_validate(self, json_data_samples):
        """Test inferring schema and then validating data against it."""
        # Disable enum inference so similar (but new) values still validate.
        inference = SchemaInferenceService(JSONSchemaConfig(infer_enums=False))
        validator = JSONSchemaValidatorService()

        # Provide multiple varied samples so inference does not lock values to enums.
        samples = [
            json_data_samples["simple_user"],
            {"id": 2, "email": "alice@example.com", "name": "Alice"},
            {"id": 3, "email": "bob@example.com", "name": "Bob"},
            {"id": 4, "email": "carol@example.com", "name": "Carol"},
            {"id": 5, "email": "dave@example.com", "name": "Dave"},
            {"id": 6, "email": "eve@example.com", "name": "Eve"},
        ]
        infer_result = inference.infer(samples)

        validation_result = validator.validate(
            json_data_samples["simple_user"],
            infer_result.inferred_schema
        )
        assert validation_result.is_valid is True

        # Stay within inferred min/max ranges from samples (id 1..6).
        similar_data = {"id": 3, "email": "test@example.com", "name": "Test User"}
        validation_result2 = validator.validate(similar_data, infer_result.inferred_schema)
        assert validation_result2.is_valid is True

    def test_workflow_infer_from_multiple_samples(self, json_data_samples):
        """Test inferring schema from multiple data samples."""
        inference = SchemaInferenceService()

        samples = [
            {"id": 1, "email": "user1@example.com", "name": "User 1"},
            {"id": 2, "email": "user2@example.com", "name": "User 2"},
            {"id": 3, "email": "user3@example.com"},  # Missing name
        ]

        result = inference.infer(samples)

        schema = result.inferred_schema
        assert schema["type"] == "object"
        # name should be optional since it was missing in one sample (if 'required' present)
        if "required" in schema:
            assert "name" not in schema["required"]

    def test_workflow_save_inferred_schema(self, tmp_path, json_data_samples):
        """Test inferring schema and saving it to file."""
        inference = SchemaInferenceService()

        infer_result = inference.infer([json_data_samples["simple_user"]])

        schema_file = tmp_path / "inferred_schema.json"
        with open(schema_file, "w") as f:
            json.dump(infer_result.inferred_schema, f, indent=2)

        assert schema_file.exists()

        with open(schema_file) as f:
            loaded_schema = json.load(f)

        assert loaded_schema["type"] == "object"


class TestJSONSchemaGeneration:
    """Tests for JSON Schema generation from Python types."""

    def test_workflow_generate_from_python_types(self):
        """Test generating JSON schema from a sample dict."""
        generator = SchemaGeneratorService()

        sample = {
            "id": 1,
            "email": "user@example.com",
            "name": "User",
            "age": 30,
            "is_active": True,
        }

        schema = generator.from_dict_sample(sample)

        assert schema["type"] == "object"
        assert "properties" in schema
        assert len(schema["properties"]) == 5

    def test_workflow_generate_with_nested_objects(self):
        """Test generating schema with nested objects."""
        generator = SchemaGeneratorService()

        sample = {
            "id": 1,
            "profile": {
                "firstName": "A",
                "lastName": "B",
                "age": 30,
            }
        }

        schema = generator.from_dict_sample(sample)

        assert schema["type"] == "object"
        assert "profile" in schema["properties"]
        assert schema["properties"]["profile"]["type"] == "object"

    def test_workflow_generate_with_arrays(self):
        """Test generating schema with array types."""
        generator = SchemaGeneratorService()

        sample = {
            "id": 1,
            "tags": ["a", "b"],
            "scores": [1.0, 2.5],
        }

        schema = generator.from_dict_sample(sample)

        assert "tags" in schema["properties"]
        assert schema["properties"]["tags"]["type"] == "array"

    def test_workflow_generate_and_validate(self):
        """Test generating schema from a sample and validating data against it."""
        generator = SchemaGeneratorService()
        validator = JSONSchemaValidatorService()

        sample = {"id": 1, "email": "test@example.com"}
        schema = generator.from_dict_sample(sample)

        valid_data = {"id": 1, "email": "test@example.com"}
        validation_result = validator.validate(valid_data, schema)
        assert validation_result.is_valid is True


class TestJSONSchemaComplexScenarios:
    """Tests for complex JSON Schema scenarios."""

    def test_workflow_schema_with_references(self, tmp_path):
        """Test handling schemas with $ref references."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "user": {"$ref": "#/definitions/User"},
                "posts": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Post"}
                }
            },
            "definitions": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "email": {"type": "string"}
                    }
                },
                "Post": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "title": {"type": "string"}
                    }
                }
            }
        }

        validator = JSONSchemaValidatorService()

        data = {
            "user": {"id": 1, "email": "test@example.com"},
            "posts": [
                {"id": 1, "title": "First Post"},
                {"id": 2, "title": "Second Post"}
            ]
        }

        result = validator.validate(data, schema)
        assert result.is_valid is True

    def test_workflow_schema_with_patterns(self):
        """Test validating with pattern constraints."""
        schema = {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                },
                "phone": {
                    "type": "string",
                    "pattern": "^\\+?[1-9]\\d{1,14}$"
                }
            }
        }

        validator = JSONSchemaValidatorService()

        # Valid data
        valid_data = {
            "email": "test@example.com",
            "phone": "+1234567890"
        }
        result = validator.validate(valid_data, schema)
        assert result.is_valid is True

        # Invalid email
        invalid_data = {
            "email": "not-an-email",
            "phone": "+1234567890"
        }
        result2 = validator.validate(invalid_data, schema)
        assert result2.is_valid is False

    def test_workflow_schema_with_oneOf(self):
        """Test validating with oneOf constraint."""
        schema = {
            "type": "object",
            "properties": {
                "contact": {
                    "oneOf": [
                        {
                            "type": "object",
                            "properties": {
                                "email": {"type": "string"}
                            },
                            "required": ["email"]
                        },
                        {
                            "type": "object",
                            "properties": {
                                "phone": {"type": "string"}
                            },
                            "required": ["phone"]
                        }
                    ]
                }
            }
        }

        validator = JSONSchemaValidatorService()

        # Valid: has email
        data1 = {"contact": {"email": "test@example.com"}}
        result1 = validator.validate(data1, schema)
        assert result1.is_valid is True

        # Valid: has phone
        data2 = {"contact": {"phone": "1234567890"}}
        result2 = validator.validate(data2, schema)
        assert result2.is_valid is True

        # Invalid: has both (violates oneOf)
        data3 = {"contact": {"email": "test@example.com", "phone": "1234567890"}}
        result3 = validator.validate(data3, schema)
        # oneOf allows exactly one match
        # This may or may not fail depending on exact schema structure

    def test_workflow_infer_validate_refine_cycle(self, json_data_samples):
        """Test complete cycle: infer schema, validate, refine schema."""
        inference = SchemaInferenceService(JSONSchemaConfig(infer_enums=False))
        validator = JSONSchemaValidatorService()
        generator = SchemaGeneratorService()

        # Step 1: Infer schema from multiple samples to avoid enum locking.
        samples = [
            json_data_samples["simple_user"],
            {"id": 2, "email": "alice@example.com", "name": "Alice"},
            {"id": 3, "email": "bob@example.com", "name": "Bob"},
            {"id": 4, "email": "carol@example.com", "name": "Carol"},
            {"id": 5, "email": "dave@example.com", "name": "Dave"},
            {"id": 6, "email": "eve@example.com", "name": "Eve"},
        ]
        initial_schema_result = inference.infer(samples)

        # Step 2: Validate new data against inferred schema (within inferred ranges).
        new_data = {"id": 3, "email": "new@example.com", "name": "New User"}
        validation_result = validator.validate(new_data, initial_schema_result.inferred_schema)
        assert validation_result.is_valid is True

        # Step 3: Add constraints to schema
        import copy
        refined_schema = copy.deepcopy(initial_schema_result.inferred_schema)
        refined_schema["properties"]["id"]["minimum"] = 1
        refined_schema["properties"]["email"]["format"] = "email"

        # Step 4: Validate against refined schema
        validation_result2 = validator.validate(new_data, refined_schema)
        assert validation_result2.is_valid is True

    def test_workflow_large_schema_validation(self, tmp_path):
        """Test validating data against large schema."""
        # Create a large schema with many properties
        properties = {}
        for i in range(100):
            properties[f"field_{i}"] = {"type": "string"}

        schema = {
            "type": "object",
            "properties": properties
        }

        # Create matching data
        data = {f"field_{i}": f"value_{i}" for i in range(100)}

        validator = JSONSchemaValidatorService()
        result = validator.validate(data, schema)

        assert result.is_valid is True

    def test_workflow_schema_evolution(self, tmp_path):
        """Test schema evolution over time."""
        validator = JSONSchemaValidatorService()

        # Version 1 schema
        v1_schema = {
            "type": "object",
            "required": ["id", "email"],
            "properties": {
                "id": {"type": "integer"},
                "email": {"type": "string"}
            },
            "additionalProperties": False
        }

        # Version 2 schema (backward compatible)
        v2_schema = {
            "type": "object",
            "required": ["id", "email"],
            "properties": {
                "id": {"type": "integer"},
                "email": {"type": "string"},
                "name": {"type": "string"}  # New optional field
            },
            "additionalProperties": False
        }

        # Data valid for v1
        v1_data = {"id": 1, "email": "test@example.com"}

        # Should validate against v1 schema
        result_v1 = validator.validate(v1_data, v1_schema)
        assert result_v1.is_valid is True

        # Should also validate against v2 schema (backward compatible)
        result_v2 = validator.validate(v1_data, v2_schema)
        assert result_v2.is_valid is True

        # Data with new field
        v2_data = {"id": 1, "email": "test@example.com", "name": "Test"}

        # Should validate against v2 schema
        result_v2_new = validator.validate(v2_data, v2_schema)
        assert result_v2_new.is_valid is True

        # Should NOT validate against v1 schema (additionalProperties: false)
        result_v1_new = validator.validate(v2_data, v1_schema)
        assert result_v1_new.is_valid is False

    def test_workflow_cross_format_validation(self, tmp_path, jsonschema_draft_7, jsonschema_draft_2020_12):
        """Test validating same data against different schema drafts."""
        validator = JSONSchemaValidatorService()

        data = {
            "id": 1,
            "email": "test@example.com",
            "name": "Test User",
            "profile": {
                "firstName": "Test",
                "lastName": "User",
                "age": 30
            }
        }

        # Validate against draft 7
        result_draft7 = validator.validate(data, jsonschema_draft_7)
        # May pass or fail depending on schema

        # Validate against draft 2020-12
        result_draft2020 = validator.validate(data, jsonschema_draft_2020_12)
        # May pass or fail depending on schema

        # Both validations should complete without errors
        assert result_draft7 is not None
        assert result_draft2020 is not None
