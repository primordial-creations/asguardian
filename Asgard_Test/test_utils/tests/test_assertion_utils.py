"""
Tests for Assertion Utilities

Unit tests for custom assertions including YAML/JSON validation,
schema validation, and file system assertions.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard_Test.test_utils.assertion_utils import (
    assert_approximate,
    assert_directory_structure,
    assert_file_exists,
    assert_json_schema,
    assert_json_valid,
    assert_yaml_valid,
)


class TestAssertYamlValid:
    """Tests for assert_yaml_valid function."""

    def test_valid_yaml_passes(self):
        """Test that valid YAML passes assertion."""
        yaml_str = """
name: test_service
version: 1.0.0
ports:
  - 8080
  - 8443
"""
        assert_yaml_valid(yaml_str)

    def test_empty_yaml_passes(self):
        """Test that empty YAML passes assertion."""
        assert_yaml_valid("")

    def test_simple_yaml_passes(self):
        """Test that simple YAML passes assertion."""
        assert_yaml_valid("key: value")

    def test_complex_yaml_passes(self):
        """Test that complex YAML structure passes."""
        yaml_str = """
database:
  host: localhost
  port: 5432
  credentials:
    username: admin
    password: secret
cache:
  enabled: true
  ttl: 3600
"""
        assert_yaml_valid(yaml_str)

    def test_invalid_yaml_raises_assertion_error(self):
        """Test that invalid YAML raises AssertionError."""
        invalid_yaml = "name: test\n  invalid: [unclosed"
        with pytest.raises(AssertionError) as exc_info:
            assert_yaml_valid(invalid_yaml)
        assert "Invalid YAML" in str(exc_info.value)

    def test_malformed_indentation_raises_error(self):
        """Test that malformed indentation raises error."""
        invalid_yaml = """
key1: value1
  key2: value2
"""
        with pytest.raises(AssertionError):
            assert_yaml_valid(invalid_yaml)


class TestAssertJsonValid:
    """Tests for assert_json_valid function."""

    def test_valid_json_passes(self):
        """Test that valid JSON passes assertion."""
        json_str = '{"name": "test", "value": 123}'
        assert_json_valid(json_str)

    def test_empty_object_passes(self):
        """Test that empty object passes assertion."""
        assert_json_valid("{}")

    def test_empty_array_passes(self):
        """Test that empty array passes assertion."""
        assert_json_valid("[]")

    def test_complex_json_passes(self):
        """Test that complex JSON structure passes."""
        json_str = '''
{
    "user": {
        "id": 1,
        "name": "Test User",
        "tags": ["admin", "developer"],
        "settings": {
            "theme": "dark",
            "notifications": true
        }
    }
}
'''
        assert_json_valid(json_str)

    def test_invalid_json_raises_assertion_error(self):
        """Test that invalid JSON raises AssertionError."""
        invalid_json = '{"name": "test", invalid}'
        with pytest.raises(AssertionError) as exc_info:
            assert_json_valid(invalid_json)
        assert "Invalid JSON" in str(exc_info.value)

    def test_unclosed_bracket_raises_error(self):
        """Test that unclosed bracket raises error."""
        invalid_json = '{"key": "value"'
        with pytest.raises(AssertionError):
            assert_json_valid(invalid_json)

    def test_trailing_comma_raises_error(self):
        """Test that trailing comma raises error."""
        invalid_json = '{"key": "value",}'
        with pytest.raises(AssertionError):
            assert_json_valid(invalid_json)


class TestAssertJsonSchema:
    """Tests for assert_json_schema function."""

    def test_valid_data_passes(self):
        """Test that data matching schema passes."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        data = {"name": "Alice", "age": 30}
        assert_json_schema(data, schema)

    def test_minimal_valid_data_passes(self):
        """Test that minimal valid data passes."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        data = {"name": "Bob"}
        assert_json_schema(data, schema)

    def test_missing_required_field_raises_error(self):
        """Test that missing required field raises error."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        }
        data = {"name": "Charlie"}
        with pytest.raises(AssertionError) as exc_info:
            assert_json_schema(data, schema)
        assert "validation failed" in str(exc_info.value).lower()

    def test_wrong_type_raises_error(self):
        """Test that wrong type raises error."""
        schema = {
            "type": "object",
            "properties": {
                "age": {"type": "integer"}
            }
        }
        data = {"age": "not an integer"}
        with pytest.raises(AssertionError):
            assert_json_schema(data, schema)

    def test_array_schema(self):
        """Test validation with array schema."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"}
                }
            }
        }
        data = [
            {"id": 1, "name": "first"},
            {"id": 2, "name": "second"}
        ]
        assert_json_schema(data, schema)

    def test_nested_schema(self):
        """Test validation with nested schema."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "profile": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"}
                            },
                            "required": ["name"]
                        }
                    }
                }
            }
        }
        data = {
            "user": {
                "profile": {
                    "name": "Test User"
                }
            }
        }
        assert_json_schema(data, schema)

    def test_minimum_constraint(self):
        """Test validation with minimum constraint."""
        schema = {
            "type": "object",
            "properties": {
                "age": {"type": "integer", "minimum": 0}
            }
        }
        valid_data = {"age": 25}
        assert_json_schema(valid_data, schema)

        invalid_data = {"age": -5}
        with pytest.raises(AssertionError):
            assert_json_schema(invalid_data, schema)

    def test_invalid_schema_raises_error(self):
        """Test that invalid schema raises error."""
        invalid_schema = {
            "type": "invalid_type"
        }
        data = {"key": "value"}
        with pytest.raises(AssertionError) as exc_info:
            assert_json_schema(data, invalid_schema)
        assert "Invalid JSON schema" in str(exc_info.value)


class TestAssertApproximate:
    """Tests for assert_approximate function."""

    def test_equal_values_pass(self):
        """Test that equal values pass."""
        assert_approximate(1.0, 1.0)

    def test_values_within_tolerance_pass(self):
        """Test that values within tolerance pass."""
        assert_approximate(1.0001, 1.0002, tolerance=0.001)

    def test_default_tolerance(self):
        """Test that default tolerance is 0.001."""
        assert_approximate(1.0, 1.0009)

    def test_values_outside_tolerance_raise_error(self):
        """Test that values outside tolerance raise error."""
        with pytest.raises(AssertionError) as exc_info:
            assert_approximate(1.0, 1.1, tolerance=0.001)
        error_msg = str(exc_info.value)
        assert "not approximately equal" in error_msg.lower()

    def test_custom_tolerance(self):
        """Test assertion with custom tolerance."""
        assert_approximate(100.0, 105.0, tolerance=10.0)

    def test_negative_values(self):
        """Test assertion with negative values."""
        assert_approximate(-1.0, -1.0005, tolerance=0.001)

    def test_custom_error_message(self):
        """Test custom error message."""
        custom_msg = "Custom error message"
        with pytest.raises(AssertionError) as exc_info:
            assert_approximate(1.0, 2.0, tolerance=0.001, message=custom_msg)
        assert custom_msg in str(exc_info.value)

    def test_timing_comparison(self):
        """Test comparing timing measurements."""
        measured = 1.234567
        expected = 1.235
        assert_approximate(measured, expected, tolerance=0.01)

    def test_zero_values(self):
        """Test with zero values."""
        assert_approximate(0.0, 0.0)
        assert_approximate(0.0, 0.0001, tolerance=0.001)


class TestAssertFileExists:
    """Tests for assert_file_exists function."""

    def test_existing_file_passes(self):
        """Test that existing file passes assertion."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
        try:
            assert_file_exists(temp_path)
        finally:
            temp_path.unlink()

    def test_existing_directory_passes(self):
        """Test that existing directory passes assertion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert_file_exists(Path(tmpdir))

    def test_nonexistent_file_raises_error(self):
        """Test that nonexistent file raises error."""
        with pytest.raises(AssertionError) as exc_info:
            assert_file_exists(Path("/nonexistent/path/file.txt"))
        assert "does not exist" in str(exc_info.value).lower()

    def test_custom_error_message(self):
        """Test custom error message."""
        custom_msg = "File should exist but doesn't"
        with pytest.raises(AssertionError) as exc_info:
            assert_file_exists(Path("/nonexistent"), message=custom_msg)
        assert custom_msg in str(exc_info.value)

    def test_path_in_error_message(self):
        """Test that path is included in error message."""
        path = Path("/test/path/file.txt")
        with pytest.raises(AssertionError) as exc_info:
            assert_file_exists(path)
        assert str(path) in str(exc_info.value)


class TestAssertDirectoryStructure:
    """Tests for assert_directory_structure function."""

    def test_simple_structure_passes(self):
        """Test that simple matching structure passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file1.txt").write_text("content1")
            (root / "file2.txt").write_text("content2")

            expected = {
                "file1.txt": "content1",
                "file2.txt": "content2"
            }
            assert_directory_structure(root, expected)

    def test_nested_structure_passes(self):
        """Test that nested matching structure passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subdir = root / "subdir"
            subdir.mkdir()
            (root / "file1.txt").write_text("content1")
            (subdir / "file2.txt").write_text("content2")

            expected = {
                "file1.txt": "content1",
                "subdir": {
                    "file2.txt": "content2"
                }
            }
            assert_directory_structure(root, expected)

    def test_partial_content_match(self):
        """Test that partial content match works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("This is a long file with lots of content")

            expected = {
                "file.txt": "long file"
            }
            assert_directory_structure(root, expected)

    def test_none_content_checks_existence_only(self):
        """Test that None content checks existence only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("any content")

            expected = {
                "file.txt": None
            }
            assert_directory_structure(root, expected)

    def test_missing_file_raises_error(self):
        """Test that missing file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            expected = {
                "nonexistent.txt": "content"
            }
            with pytest.raises(AssertionError) as exc_info:
                assert_directory_structure(root, expected)
            assert "does not exist" in str(exc_info.value).lower()

    def test_content_mismatch_raises_error(self):
        """Test that content mismatch raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("actual content")

            expected = {
                "file.txt": "expected content"
            }
            with pytest.raises(AssertionError) as exc_info:
                assert_directory_structure(root, expected)
            assert "content mismatch" in str(exc_info.value).lower()

    def test_file_instead_of_directory_raises_error(self):
        """Test that file instead of directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("content")

            expected = {
                "file.txt": {}  # Expect directory
            }
            with pytest.raises(AssertionError) as exc_info:
                assert_directory_structure(root, expected)
            assert "Expected directory but found file" in str(exc_info.value)

    def test_directory_instead_of_file_raises_error(self):
        """Test that directory instead of file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "dir").mkdir()

            expected = {
                "dir": "content"  # Expect file
            }
            with pytest.raises(AssertionError) as exc_info:
                assert_directory_structure(root, expected)
            assert "Expected file but found directory" in str(exc_info.value)

    def test_nonexistent_root_raises_error(self):
        """Test that nonexistent root raises error."""
        expected = {"file.txt": "content"}
        with pytest.raises(AssertionError) as exc_info:
            assert_directory_structure(Path("/nonexistent"), expected)
        assert "does not exist" in str(exc_info.value).lower()

    def test_file_as_root_raises_error(self):
        """Test that file as root raises error."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
        try:
            expected = {"file.txt": "content"}
            with pytest.raises(AssertionError) as exc_info:
                assert_directory_structure(temp_path, expected)
            assert "not a directory" in str(exc_info.value).lower()
        finally:
            temp_path.unlink()

    def test_deeply_nested_structure(self):
        """Test deeply nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            deep_path = root / "level1" / "level2" / "level3"
            deep_path.mkdir(parents=True)
            (deep_path / "file.txt").write_text("deep content")

            expected = {
                "level1": {
                    "level2": {
                        "level3": {
                            "file.txt": "deep content"
                        }
                    }
                }
            }
            assert_directory_structure(root, expected)
