"""
Test Imports

Verify that all test_utils modules can be imported correctly.
"""

import pytest


class TestImports:
    """Tests for test_utils imports."""

    def test_import_test_utils(self):
        """Test that test_utils package can be imported."""
        import Asgard_Test.test_utils as test_utils
        assert test_utils is not None

    def test_import_file_utils(self):
        """Test that file_utils module can be imported."""
        from Asgard_Test.test_utils import file_utils
        assert file_utils is not None

    def test_import_mock_utils(self):
        """Test that mock_utils module can be imported."""
        from Asgard_Test.test_utils import mock_utils
        assert mock_utils is not None

    def test_import_assertion_utils(self):
        """Test that assertion_utils module can be imported."""
        from Asgard_Test.test_utils import assertion_utils
        assert assertion_utils is not None

    def test_import_generators(self):
        """Test that generators module can be imported."""
        from Asgard_Test.test_utils import generators
        assert generators is not None

    def test_import_file_functions_from_root(self):
        """Test importing file utility functions from root."""
        from Asgard_Test.test_utils import (
            create_temp_python_file,
            create_temp_yaml_file,
            create_temp_json_file,
            load_fixture,
            create_temp_directory_structure,
        )
        assert create_temp_python_file is not None
        assert create_temp_yaml_file is not None
        assert create_temp_json_file is not None
        assert load_fixture is not None
        assert create_temp_directory_structure is not None

    def test_import_mock_functions_from_root(self):
        """Test importing mock utility functions from root."""
        from Asgard_Test.test_utils import (
            mock_playwright_page,
            mock_playwright_browser,
            mock_database_connection,
            mock_http_response,
            mock_file_system,
        )
        assert mock_playwright_page is not None
        assert mock_playwright_browser is not None
        assert mock_database_connection is not None
        assert mock_http_response is not None
        assert mock_file_system is not None

    def test_import_assertion_functions_from_root(self):
        """Test importing assertion utility functions from root."""
        from Asgard_Test.test_utils import (
            assert_yaml_valid,
            assert_json_valid,
            assert_json_schema,
            assert_approximate,
            assert_file_exists,
            assert_directory_structure,
        )
        assert assert_yaml_valid is not None
        assert assert_json_valid is not None
        assert assert_json_schema is not None
        assert assert_approximate is not None
        assert assert_file_exists is not None
        assert assert_directory_structure is not None

    def test_import_generator_functions_from_root(self):
        """Test importing generator utility functions from root."""
        from Asgard_Test.test_utils import (
            generate_python_class,
            generate_python_module,
            generate_openapi_spec,
            generate_graphql_schema,
            generate_metrics_data,
            generate_web_vitals_data,
        )
        assert generate_python_class is not None
        assert generate_python_module is not None
        assert generate_openapi_spec is not None
        assert generate_graphql_schema is not None
        assert generate_metrics_data is not None
        assert generate_web_vitals_data is not None

    def test_all_exports_available(self):
        """Test that all exports in __all__ are available."""
        import Asgard_Test.test_utils as test_utils
        assert hasattr(test_utils, "__all__")
        for name in test_utils.__all__:
            assert hasattr(test_utils, name), f"Export '{name}' not found"

    def test_version_available(self):
        """Test that version is available."""
        import Asgard_Test.test_utils as test_utils
        assert hasattr(test_utils, "__version__")
        assert isinstance(test_utils.__version__, str)
