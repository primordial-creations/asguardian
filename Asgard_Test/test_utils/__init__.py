"""
Asgard Test Utilities

Shared testing utilities for all Asgard test suites. This package provides
reusable helpers for file operations, mocking, assertions, and test data generation.

Usage:
    from test_utils import create_temp_python_file, mock_playwright_page, assert_json_valid

    # Create test files
    file_path = create_temp_python_file("class MyClass: pass")

    # Create mocks
    page = mock_playwright_page()

    # Custom assertions
    assert_json_valid('{"key": "value"}')
"""

from Asgard_Test.test_utils.assertion_utils import (
    assert_approximate,
    assert_directory_structure,
    assert_file_exists,
    assert_json_schema,
    assert_json_valid,
    assert_yaml_valid,
)
from Asgard_Test.test_utils.file_utils import (
    create_temp_directory_structure,
    create_temp_json_file,
    create_temp_python_file,
    create_temp_yaml_file,
    load_fixture,
)
from Asgard_Test.test_utils.generators import (
    generate_graphql_schema,
    generate_metrics_data,
    generate_openapi_spec,
    generate_python_class,
    generate_python_module,
    generate_web_vitals_data,
)
from Asgard_Test.test_utils.mock_utils import (
    mock_database_connection,
    mock_file_system,
    mock_http_response,
    mock_playwright_browser,
    mock_playwright_page,
)

__all__ = [
    # File utilities
    "create_temp_python_file",
    "create_temp_yaml_file",
    "create_temp_json_file",
    "load_fixture",
    "create_temp_directory_structure",
    # Mock utilities
    "mock_playwright_page",
    "mock_playwright_browser",
    "mock_database_connection",
    "mock_http_response",
    "mock_file_system",
    # Assertion utilities
    "assert_yaml_valid",
    "assert_json_valid",
    "assert_json_schema",
    "assert_approximate",
    "assert_file_exists",
    "assert_directory_structure",
    # Generator utilities
    "generate_python_class",
    "generate_python_module",
    "generate_openapi_spec",
    "generate_graphql_schema",
    "generate_metrics_data",
    "generate_web_vitals_data",
]

__version__ = "1.0.0"
