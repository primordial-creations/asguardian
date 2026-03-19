"""
Custom Assertion Utilities

Enhanced assertions for common testing scenarios including YAML/JSON validation,
schema validation, approximate comparisons, and file system assertions.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema
import yaml


def assert_yaml_valid(content: str) -> None:
    """
    Assert that a string contains valid YAML.

    Args:
        content: String to validate as YAML

    Raises:
        AssertionError: If the content is not valid YAML

    Example:
        >>> yaml_str = '''
        ... name: test_service
        ... version: 1.0.0
        ... ports:
        ...   - 8080
        ...   - 8443
        ... '''
        >>> assert_yaml_valid(yaml_str)  # Passes
        >>>
        >>> invalid_yaml = "name: test\\n  invalid: [unclosed"
        >>> assert_yaml_valid(invalid_yaml)  # Raises AssertionError
    """
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise AssertionError(f"Invalid YAML content: {e}")


def assert_json_valid(content: str) -> None:
    """
    Assert that a string contains valid JSON.

    Args:
        content: String to validate as JSON

    Raises:
        AssertionError: If the content is not valid JSON

    Example:
        >>> json_str = '{"name": "test", "value": 123}'
        >>> assert_json_valid(json_str)  # Passes
        >>>
        >>> invalid_json = '{"name": "test", invalid}'
        >>> assert_json_valid(invalid_json)  # Raises AssertionError
    """
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON content: {e}")


def assert_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """
    Assert that data matches a JSON schema.

    Args:
        data: Data to validate
        schema: JSON schema to validate against

    Raises:
        AssertionError: If the data doesn't match the schema

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "name": {"type": "string"},
        ...         "age": {"type": "integer", "minimum": 0}
        ...     },
        ...     "required": ["name", "age"]
        ... }
        >>> data = {"name": "Alice", "age": 30}
        >>> assert_json_schema(data, schema)  # Passes
        >>>
        >>> invalid_data = {"name": "Bob"}  # Missing required field
        >>> assert_json_schema(invalid_data, schema)  # Raises AssertionError
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        raise AssertionError(f"JSON schema validation failed: {e.message}")
    except jsonschema.SchemaError as e:
        raise AssertionError(f"Invalid JSON schema: {e.message}")


def assert_approximate(
    actual: float,
    expected: float,
    tolerance: float = 0.001,
    message: Optional[str] = None
) -> None:
    """
    Assert that two floating point numbers are approximately equal.

    Args:
        actual: Actual value
        expected: Expected value
        tolerance: Maximum allowed difference (default: 0.001)
        message: Custom error message

    Raises:
        AssertionError: If the values differ by more than tolerance

    Example:
        >>> assert_approximate(1.0001, 1.0002, tolerance=0.001)  # Passes
        >>> assert_approximate(1.0, 1.1, tolerance=0.001)  # Raises AssertionError
        >>>
        >>> # Useful for timing assertions
        >>> measured_time = 1.234567
        >>> expected_time = 1.235
        >>> assert_approximate(measured_time, expected_time, tolerance=0.01)
    """
    diff = abs(actual - expected)
    if diff > tolerance:
        if message is None:
            message = (
                f"Values not approximately equal: "
                f"actual={actual}, expected={expected}, "
                f"difference={diff}, tolerance={tolerance}"
            )
        raise AssertionError(message)


def assert_file_exists(path: Path, message: Optional[str] = None) -> None:
    """
    Assert that a file or directory exists.

    Args:
        path: Path to check
        message: Custom error message

    Raises:
        AssertionError: If the path doesn't exist

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(delete=False) as f:
        ...     temp_path = Path(f.name)
        >>> assert_file_exists(temp_path)  # Passes
        >>>
        >>> assert_file_exists(Path("/nonexistent/path"))  # Raises AssertionError
    """
    path = Path(path)
    if not path.exists():
        if message is None:
            message = f"Path does not exist: {path}"
        raise AssertionError(message)


def assert_directory_structure(path: Path, expected: Dict[str, Any]) -> None:
    """
    Assert that a directory has the expected structure.

    Args:
        path: Root directory path
        expected: Expected structure as nested dict
                 Keys are file/directory names
                 Values are:
                   - str: expected file content (partial match)
                   - dict: nested directory structure
                   - None: file should exist (content not checked)

    Raises:
        AssertionError: If the structure doesn't match

    Example:
        >>> # Create test directory
        >>> import tempfile
        >>> tmpdir = Path(tempfile.mkdtemp())
        >>> (tmpdir / "file1.txt").write_text("content1")
        >>> (tmpdir / "subdir").mkdir()
        >>> (tmpdir / "subdir" / "file2.txt").write_text("content2")
        >>>
        >>> # Assert structure
        >>> expected = {
        ...     "file1.txt": "content1",
        ...     "subdir": {
        ...         "file2.txt": "content2"
        ...     }
        ... }
        >>> assert_directory_structure(tmpdir, expected)  # Passes
    """
    path = Path(path)

    if not path.exists():
        raise AssertionError(f"Root path does not exist: {path}")

    if not path.is_dir():
        raise AssertionError(f"Path is not a directory: {path}")

    for name, content in expected.items():
        item_path = path / name

        if not item_path.exists():
            raise AssertionError(f"Expected item does not exist: {item_path}")

        if isinstance(content, dict):
            # Recursively check subdirectory
            if not item_path.is_dir():
                raise AssertionError(f"Expected directory but found file: {item_path}")
            assert_directory_structure(item_path, content)
        elif content is not None:
            # Check file content (partial match)
            if not item_path.is_file():
                raise AssertionError(f"Expected file but found directory: {item_path}")

            actual_content = item_path.read_text(encoding="utf-8")
            if str(content) not in actual_content:
                raise AssertionError(
                    f"File content mismatch in {item_path}:\n"
                    f"Expected substring: {content}\n"
                    f"Actual content: {actual_content}"
                )
        # If content is None, just check existence (already done)
