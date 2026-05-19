"""
Tests for File Utilities

Unit tests for file-based test helpers including temp file creation
and directory structure generation.
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from Asgard_Test.test_utils.file_utils import (
    create_temp_directory_structure,
    create_temp_json_file,
    create_temp_python_file,
    create_temp_yaml_file,
    load_fixture,
)


class TestCreateTempPythonFile:
    """Tests for create_temp_python_file function."""

    def test_creates_file_with_py_extension(self):
        """Test creating Python file with default extension."""
        code = "def test_function():\n    pass"
        file_path = create_temp_python_file(code)

        assert file_path.exists()
        assert file_path.suffix == ".py"
        assert file_path.read_text() == code

    def test_creates_file_with_custom_suffix(self):
        """Test creating Python file with custom suffix."""
        code = "class TestClass: pass"
        file_path = create_temp_python_file(code, suffix=".pyx")

        assert file_path.exists()
        assert file_path.suffix == ".pyx"

    def test_content_is_written_correctly(self):
        """Test that file content is written correctly."""
        code = '''
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
'''
        file_path = create_temp_python_file(code)
        content = file_path.read_text()

        assert "class Calculator:" in content
        assert "def add" in content
        assert "def subtract" in content

    def test_handles_unicode_content(self):
        """Test handling Unicode characters in content."""
        code = '# -*- coding: utf-8 -*-\nprint("Hello, 世界!")'
        file_path = create_temp_python_file(code)

        assert file_path.exists()
        assert "世界" in file_path.read_text()

    def test_handles_empty_content(self):
        """Test creating file with empty content."""
        file_path = create_temp_python_file("")

        assert file_path.exists()
        assert file_path.read_text() == ""


class TestCreateTempYamlFile:
    """Tests for create_temp_yaml_file function."""

    def test_creates_yaml_file(self):
        """Test creating YAML file with dictionary content."""
        data = {
            "name": "test_service",
            "version": "1.0.0",
            "dependencies": ["requests", "pyyaml"]
        }
        file_path = create_temp_yaml_file(data)

        assert file_path.exists()
        assert file_path.suffix == ".yaml"

    def test_yaml_content_is_valid(self):
        """Test that YAML content can be loaded back."""
        data = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "test_db"
            },
            "cache": {
                "enabled": True,
                "ttl": 3600
            }
        }
        file_path = create_temp_yaml_file(data)

        with open(file_path) as f:
            loaded = yaml.safe_load(f)

        assert loaded == data
        assert loaded["database"]["host"] == "localhost"
        assert loaded["cache"]["enabled"] is True

    def test_custom_suffix(self):
        """Test creating YAML file with custom suffix."""
        data = {"key": "value"}
        file_path = create_temp_yaml_file(data, suffix=".yml")

        assert file_path.suffix == ".yml"

    def test_nested_structures(self):
        """Test creating YAML with deeply nested structures."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        file_path = create_temp_yaml_file(data)

        with open(file_path) as f:
            loaded = yaml.safe_load(f)

        assert loaded["level1"]["level2"]["level3"]["value"] == "deep"

    def test_lists_in_yaml(self):
        """Test creating YAML with list structures."""
        data = {
            "items": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"}
            ]
        }
        file_path = create_temp_yaml_file(data)

        with open(file_path) as f:
            loaded = yaml.safe_load(f)

        assert len(loaded["items"]) == 2
        assert loaded["items"][0]["name"] == "first"


class TestCreateTempJsonFile:
    """Tests for create_temp_json_file function."""

    def test_creates_json_file(self):
        """Test creating JSON file with dictionary content."""
        data = {
            "test_id": "test_001",
            "status": "passed",
            "duration": 1.23
        }
        file_path = create_temp_json_file(data)

        assert file_path.exists()
        assert file_path.suffix == ".json"

    def test_json_content_is_valid(self):
        """Test that JSON content can be loaded back."""
        data = {
            "metrics": {
                "memory": 1024,
                "cpu": 45.5
            },
            "tags": ["test", "performance"]
        }
        file_path = create_temp_json_file(data)

        with open(file_path) as f:
            loaded = json.load(f)

        assert loaded == data
        assert loaded["metrics"]["memory"] == 1024

    def test_custom_suffix(self):
        """Test creating JSON file with custom suffix."""
        data = {"key": "value"}
        file_path = create_temp_json_file(data, suffix=".jsonl")

        assert file_path.suffix == ".jsonl"

    def test_nested_objects(self):
        """Test creating JSON with nested objects."""
        data = {
            "user": {
                "profile": {
                    "name": "Test User",
                    "settings": {
                        "theme": "dark",
                        "notifications": True
                    }
                }
            }
        }
        file_path = create_temp_json_file(data)

        with open(file_path) as f:
            loaded = json.load(f)

        assert loaded["user"]["profile"]["settings"]["theme"] == "dark"

    def test_arrays_in_json(self):
        """Test creating JSON with array structures."""
        data = {
            "results": [
                {"id": 1, "score": 95},
                {"id": 2, "score": 87}
            ]
        }
        file_path = create_temp_json_file(data)

        with open(file_path) as f:
            loaded = json.load(f)

        assert len(loaded["results"]) == 2
        assert loaded["results"][1]["score"] == 87


class TestLoadFixture:
    """Tests for load_fixture function."""

    def test_raises_error_for_nonexistent_fixture(self):
        """Test that loading nonexistent fixture raises error."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_fixture("heimdall", "nonexistent_fixture")

        assert "not found" in str(exc_info.value).lower()

    def test_fixture_name_and_package_in_error(self):
        """Test that error message includes fixture name and package."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_fixture("test_package", "test_fixture")

        error_msg = str(exc_info.value)
        assert "test_fixture" in error_msg
        assert "test_package" in error_msg


class TestCreateTempDirectoryStructure:
    """Tests for create_temp_directory_structure function."""

    def test_creates_basic_directory_structure(self):
        """Test creating basic directory structure."""
        structure = {
            "file1.txt": "content1",
            "file2.txt": "content2"
        }
        root = create_temp_directory_structure(structure)

        assert root.exists()
        assert (root / "file1.txt").exists()
        assert (root / "file2.txt").exists()
        assert (root / "file1.txt").read_text() == "content1"

    def test_creates_nested_directories(self):
        """Test creating nested directory structure."""
        structure = {
            "src": {
                "__init__.py": "",
                "main.py": "def main(): pass"
            },
            "tests": {
                "test_main.py": "def test_main(): pass"
            }
        }
        root = create_temp_directory_structure(structure)

        assert (root / "src").is_dir()
        assert (root / "tests").is_dir()
        assert (root / "src" / "__init__.py").exists()
        assert (root / "src" / "main.py").exists()
        assert (root / "tests" / "test_main.py").exists()

    def test_creates_deeply_nested_structure(self):
        """Test creating deeply nested directory structure."""
        structure = {
            "level1": {
                "level2": {
                    "level3": {
                        "file.txt": "deep content"
                    }
                }
            }
        }
        root = create_temp_directory_structure(structure)

        deep_file = root / "level1" / "level2" / "level3" / "file.txt"
        assert deep_file.exists()
        assert deep_file.read_text() == "deep content"

    def test_creates_empty_files(self):
        """Test creating empty files with None content."""
        structure = {
            "empty1.txt": None,
            "empty2.txt": None,
            "with_content.txt": "content"
        }
        root = create_temp_directory_structure(structure)

        assert (root / "empty1.txt").exists()
        assert (root / "empty2.txt").exists()
        assert (root / "empty1.txt").read_text() == ""
        assert (root / "with_content.txt").read_text() == "content"

    def test_uses_provided_base_path(self):
        """Test creating structure at provided base path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "custom_base"
            structure = {
                "file.txt": "content"
            }
            root = create_temp_directory_structure(structure, base_path=base)

            assert root == base
            assert (base / "file.txt").exists()

    def test_complex_project_structure(self):
        """Test creating realistic project structure."""
        structure = {
            "src": {
                "__init__.py": "",
                "main.py": "def main(): pass",
                "utils": {
                    "__init__.py": "",
                    "helpers.py": "def helper(): pass"
                }
            },
            "tests": {
                "__init__.py": "",
                "test_main.py": "def test_main(): pass",
                "fixtures": {
                    "data.json": '{"key": "value"}'
                }
            },
            "README.md": "# Test Project",
            "setup.py": "from setuptools import setup"
        }
        root = create_temp_directory_structure(structure)

        assert (root / "src" / "utils" / "helpers.py").exists()
        assert (root / "tests" / "fixtures" / "data.json").exists()
        assert (root / "README.md").exists()
        assert "Test Project" in (root / "README.md").read_text()

    def test_handles_mixed_content_types(self):
        """Test handling different content types in structure."""
        structure = {
            "string_content.txt": "string",
            "numeric_content.txt": 123,
            "empty_content.txt": None,
            "subdir": {
                "nested.txt": "nested"
            }
        }
        root = create_temp_directory_structure(structure)

        assert (root / "string_content.txt").read_text() == "string"
        assert (root / "numeric_content.txt").read_text() == "123"
        assert (root / "empty_content.txt").read_text() == ""
        assert (root / "subdir" / "nested.txt").read_text() == "nested"
