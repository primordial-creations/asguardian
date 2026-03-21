#!/usr/bin/env python3
"""
Test Utils Package Validation Script

Quick validation that all modules can be imported and basic functionality works.
Run this script to verify the package is properly set up.
"""

import importlib
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_utils import (
    assert_approximate,
    assert_json_valid,
    create_temp_json_file,
    create_temp_python_file,
    generate_metrics_data,
    generate_python_class,
    mock_http_response,
    mock_playwright_page,
)
from test_utils import file_utils, mock_utils, assertion_utils, generators


def validate_imports():
    """Validate that all modules can be imported."""
    print("Validating imports...")

    try:
        importlib.import_module("test_utils")
        print("  ✓ test_utils package imported")
    except ImportError as e:
        print(f"  ✗ Failed to import test_utils: {e}")
        return False

    try:
        for submodule in ("test_utils.file_utils", "test_utils.mock_utils", "test_utils.assertion_utils", "test_utils.generators"):
            importlib.import_module(submodule)
        print("  ✓ All submodules imported")
    except ImportError as e:
        print(f"  ✗ Failed to import submodules: {e}")
        return False

    try:
        for name in ("create_temp_python_file", "mock_playwright_page", "assert_json_valid", "generate_python_class"):
            importlib.import_module("test_utils")
            if not hasattr(importlib.import_module("test_utils"), name):
                raise ImportError(f"{name} not found in test_utils")
        print("  ✓ All utility functions imported from root")
    except ImportError as e:
        print(f"  ✗ Failed to import functions: {e}")
        return False

    return True


def validate_file_utils():
    """Validate file_utils functionality."""
    print("\nValidating file_utils...")

    try:
        # Create a Python file
        code = "def test(): pass"
        file_path = create_temp_python_file(code)
        assert file_path.exists()
        assert file_path.read_text() == code
        print("  ✓ create_temp_python_file works")

        # Create a JSON file
        data = {"key": "value"}
        json_path = create_temp_json_file(data)
        assert json_path.exists()
        print("  ✓ create_temp_json_file works")

        return True
    except Exception as e:
        print(f"  ✗ file_utils validation failed: {e}")
        return False


def validate_mock_utils():
    """Validate mock_utils functionality."""
    print("\nValidating mock_utils...")

    try:
        # Create a mock page
        page = mock_playwright_page()
        assert page is not None
        assert hasattr(page, "goto")
        assert hasattr(page, "screenshot")
        print("  ✓ mock_playwright_page works")

        # Create a mock response
        response = mock_http_response(200, {"test": "data"})
        assert response.status_code == 200
        assert response.json() == {"test": "data"}
        print("  ✓ mock_http_response works")

        return True
    except Exception as e:
        print(f"  ✗ mock_utils validation failed: {e}")
        return False


def validate_assertion_utils():
    """Validate assertion_utils functionality."""
    print("\nValidating assertion_utils...")

    try:
        # Test JSON validation
        assert_json_valid('{"key": "value"}')
        print("  ✓ assert_json_valid works")

        # Test approximate comparison
        assert_approximate(1.0, 1.001, tolerance=0.01)
        print("  ✓ assert_approximate works")

        # Test that invalid JSON raises error
        try:
            assert_json_valid('invalid json')
            print("  ✗ assert_json_valid should have raised error")
            return False
        except AssertionError:
            print("  ✓ assert_json_valid correctly raises errors")

        return True
    except Exception as e:
        print(f"  ✗ assertion_utils validation failed: {e}")
        return False


def validate_generators():
    """Validate generators functionality."""
    print("\nValidating generators...")

    try:
        # Test Python class generation
        code = generate_python_class("TestClass", methods=3)
        assert "class TestClass:" in code
        assert "def method_1" in code
        print("  ✓ generate_python_class works")

        # Test metrics generation
        metrics = generate_metrics_data(points=10, metric_type="latency")
        assert len(metrics) == 10
        assert all("timestamp" in m for m in metrics)
        assert all("value" in m for m in metrics)
        print("  ✓ generate_metrics_data works")

        return True
    except Exception as e:
        print(f"  ✗ generators validation failed: {e}")
        return False


def main():
    """Run all validations."""
    print("=" * 60)
    print("Test Utils Package Validation")
    print("=" * 60)

    results = []
    results.append(("Imports", validate_imports()))
    results.append(("file_utils", validate_file_utils()))
    results.append(("mock_utils", validate_mock_utils()))
    results.append(("assertion_utils", validate_assertion_utils()))
    results.append(("generators", validate_generators()))

    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name:20s} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\nAll validations passed! Package is ready to use.")
        return 0
    else:
        print("\nSome validations failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
