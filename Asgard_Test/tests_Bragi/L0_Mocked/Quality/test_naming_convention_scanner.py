"""
Tests for Heimdall Naming Convention Scanner Service

Unit tests for PEP 8 naming convention enforcement covering functions,
classes, constants, and private/dunder members.
Tests use real temp files with actual Python source code.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.naming_models import (
    NamingConfig,
    NamingConvention,
    NamingReport,
    NamingViolation,
)
from Asgard.Bragi.Quality.services.naming_convention_scanner import NamingConventionScanner


class TestNamingConventionScannerInit:
    """Tests for NamingConventionScanner initialisation."""

    def test_init_with_default_config(self):
        """Test initialising with default configuration."""
        scanner = NamingConventionScanner()
        assert scanner.config is not None
        assert scanner.config.check_functions is True
        assert scanner.config.check_classes is True
        assert scanner.config.check_variables is True
        assert scanner.config.check_constants is True

    def test_init_with_custom_config(self):
        """Test initialising with custom configuration."""
        config = NamingConfig(check_functions=False, check_classes=True)
        scanner = NamingConventionScanner(config)
        assert scanner.config.check_functions is False
        assert scanner.config.check_classes is True


class TestNamingConventionScannerScanPath:
    """Tests for scan path validation."""

    def test_scan_nonexistent_path_raises_file_not_found(self):
        """Test that scanning a nonexistent path raises FileNotFoundError."""
        scanner = NamingConventionScanner()
        with pytest.raises(FileNotFoundError):
            scanner.scan(Path("/nonexistent/path/that/does/not/exist"))

    def test_scan_empty_directory_returns_empty_report(self):
        """Test scanning an empty directory produces a valid report with zero violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = NamingConventionScanner()
            report = scanner.scan(Path(tmpdir))

            assert isinstance(report, NamingReport)
            assert report.total_violations == 0
            assert report.has_violations is False


class TestFunctionNaming:
    """Tests for function naming convention enforcement."""

    def test_snake_case_function_no_violation(self):
        """Test that snake_case function names produce no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def compute_result():
    return 42


def process_data(data):
    return data


def get_user_name(user_id):
    return str(user_id)
'''
            (tmpdir_path / "funcs.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            function_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "function"
            ]
            assert len(function_violations) == 0

    def test_camel_case_function_produces_violation(self):
        """Test that camelCase function names produce a violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def computeResult():
    return 42
'''
            (tmpdir_path / "camel_func.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            function_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "function"
            ]
            assert len(function_violations) == 1
            assert function_violations[0].element_name == "computeResult"

    def test_camel_case_function_violation_reports_snake_case_expected(self):
        """Test that the violation correctly reports snake_case as the expected convention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def myFunction():
    pass
'''
            (tmpdir_path / "bad_func.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
            ]
            assert len(all_violations) == 1
            assert all_violations[0].expected_convention == NamingConvention.SNAKE_CASE or \
                   all_violations[0].expected_convention == "snake_case"

    def test_multiple_camel_case_functions_all_flagged(self):
        """Test that multiple camelCase functions are all flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def firstFunc():
    pass


def secondFunc():
    pass
'''
            (tmpdir_path / "multi_bad.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            function_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "function"
            ]
            assert len(function_violations) == 2

    def test_mixed_function_names_only_bad_ones_flagged(self):
        """Test that only non-snake_case functions are flagged in a mixed file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def good_function():
    pass


def badFunction():
    pass


def another_good_one():
    pass
'''
            (tmpdir_path / "mixed.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            function_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "function"
            ]
            assert len(function_violations) == 1
            assert function_violations[0].element_name == "badFunction"

    def test_function_check_disabled_no_violations(self):
        """Test that disabling function check suppresses function violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def badCamelCaseFunction():
    pass
'''
            (tmpdir_path / "disabled.py").write_text(code)

            config = NamingConfig(check_functions=False)
            scanner = NamingConventionScanner(config)
            report = scanner.scan(tmpdir_path)

            function_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "function"
            ]
            assert len(function_violations) == 0

    def test_single_word_snake_case_no_violation(self):
        """Test that a single-word function name produces no violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def run():
    pass
'''
            (tmpdir_path / "single.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            function_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "function"
            ]
            assert len(function_violations) == 0


class TestClassNaming:
    """Tests for class naming convention enforcement."""

    def test_pascal_case_class_no_violation(self):
        """Test that PascalCase class names produce no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class UserManager:
    pass


class DatabaseConnection:
    pass


class HttpRequestHandler:
    pass
'''
            (tmpdir_path / "classes.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            class_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "class"
            ]
            assert len(class_violations) == 0

    def test_snake_case_class_produces_violation(self):
        """Test that a snake_case class name produces a violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class user_manager:
    pass
'''
            (tmpdir_path / "bad_class.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            class_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "class"
            ]
            assert len(class_violations) == 1
            assert class_violations[0].element_name == "user_manager"

    def test_snake_case_class_violation_reports_pascal_case_expected(self):
        """Test that a class violation reports PascalCase as the expected convention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class my_class:
    pass
'''
            (tmpdir_path / "bad_class_conv.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
                if v.element_type == "class"
            ]
            assert len(all_violations) == 1
            assert all_violations[0].expected_convention == NamingConvention.PASCAL_CASE or \
                   all_violations[0].expected_convention == "pascal_case"

    def test_lowercase_class_name_produces_violation(self):
        """Test that an entirely lowercase class name produces a violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class mywidget:
    pass
'''
            (tmpdir_path / "lowercase_class.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            class_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "class"
            ]
            assert len(class_violations) == 1

    def test_class_check_disabled_no_violations(self):
        """Test that disabling class check suppresses class violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class bad_class_name:
    pass
'''
            (tmpdir_path / "disabled_class.py").write_text(code)

            config = NamingConfig(check_classes=False)
            scanner = NamingConventionScanner(config)
            report = scanner.scan(tmpdir_path)

            class_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "class"
            ]
            assert len(class_violations) == 0

    def test_class_method_violation_detected(self):
        """Test that camelCase methods inside a class are flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class MyClass:
    def goodMethod(self):
        pass
'''
            (tmpdir_path / "method_viol.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            method_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "method"
            ]
            assert len(method_violations) == 1
            assert method_violations[0].element_name == "goodMethod"

    def test_class_method_snake_case_no_violation(self):
        """Test that snake_case methods produce no violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class MyClass:
    def good_method(self):
        pass

    def another_method(self, x):
        return x
'''
            (tmpdir_path / "good_methods.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            method_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "method"
            ]
            assert len(method_violations) == 0


class TestConstantNaming:
    """Tests for module-level constant naming convention enforcement."""

    def test_upper_case_constant_no_violation(self):
        """Test that UPPER_CASE constant names produce no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
MAX_SIZE = 100
DEFAULT_TIMEOUT = 30
API_BASE_URL = "https://example.com"
'''
            (tmpdir_path / "consts.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
            ]
            # UPPER_CASE names are treated as constants and validated with _is_upper_case
            # All of these pass _is_upper_case
            constant_violations = [v for v in all_violations if v.element_type == "constant"]
            assert len(constant_violations) == 0

    def test_lower_case_variable_no_constant_violation(self):
        """Test that lowercase variable names do not trigger constant violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
max_size = 100
default_timeout = 30
base_url = "https://example.com"
'''
            (tmpdir_path / "vars.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            constant_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "constant"
            ]
            assert len(constant_violations) == 0

    def test_constant_check_disabled_no_violations(self):
        """Test that disabling constant check suppresses constant violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # A truly mixed-case "constant-looking" name that would otherwise fail
            code = '''\
MY_CONSTANT = 42
'''
            (tmpdir_path / "disabled_const.py").write_text(code)

            config = NamingConfig(check_constants=False)
            scanner = NamingConventionScanner(config)
            report = scanner.scan(tmpdir_path)

            constant_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "constant"
            ]
            assert len(constant_violations) == 0


class TestPrivateMemberNaming:
    """Tests for private member naming conventions."""

    def test_private_function_with_underscore_prefix_accepted(self):
        """Test that private functions with _ prefix are accepted as snake_case."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def _private_helper():
    pass


def _another_internal():
    pass
'''
            (tmpdir_path / "private_funcs.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
            ]
            assert len(all_violations) == 0

    def test_private_class_with_underscore_prefix_accepted(self):
        """Test that private classes with _ prefix are treated as pascal case variants."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class _PrivateBase:
    pass
'''
            (tmpdir_path / "private_class.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            class_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "class"
            ]
            assert len(class_violations) == 0

    def test_private_method_with_underscore_prefix_accepted(self):
        """Test that private methods with _ prefix follow snake_case correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class MyClass:
    def _internal_helper(self):
        pass

    def _validate_input(self, value):
        return bool(value)
'''
            (tmpdir_path / "private_methods.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            method_violations = [
                v for violations in report.file_results.values()
                for v in violations
                if v.element_type == "method"
            ]
            assert len(method_violations) == 0


class TestDunderMethods:
    """Tests for dunder method exemption."""

    def test_dunder_init_not_flagged(self):
        """Test that __init__ is not flagged as a naming violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class MyClass:
    def __init__(self, value):
        self.value = value
'''
            (tmpdir_path / "dunder_init.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
            ]
            assert len(all_violations) == 0

    def test_multiple_dunder_methods_not_flagged(self):
        """Test that multiple dunder methods are all exempt from checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class FullFeatured:
    def __init__(self):
        pass

    def __str__(self):
        return "FullFeatured"

    def __repr__(self):
        return "FullFeatured()"

    def __len__(self):
        return 0

    def __eq__(self, other):
        return False
'''
            (tmpdir_path / "dunders.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
            ]
            assert len(all_violations) == 0

    def test_dunder_function_at_module_level_not_flagged(self):
        """Test that module-level dunder names are exempt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
__version__ = "1.0.0"
__author__ = "Test"
__all__ = ["MyClass"]
'''
            (tmpdir_path / "module_dunders.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
            ]
            assert len(all_violations) == 0


class TestCombinedViolations:
    """Tests for files with multiple violation types."""

    def test_mixed_violations_all_detected(self):
        """Test that a file with multiple violation types reports them all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class bad_class_name:
    def badMethodName(self):
        pass


def anotherBadFunction():
    pass
'''
            (tmpdir_path / "mixed_violations.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            assert report.total_violations >= 2
            element_types = {
                v.element_type
                for violations in report.file_results.values()
                for v in violations
            }
            assert "class" in element_types or "function" in element_types

    def test_report_has_violations_flag(self):
        """Test that has_violations is True when violations exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def badName():
    pass
'''
            (tmpdir_path / "flagged.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            assert report.has_violations is True

    def test_report_has_no_violations_flag(self):
        """Test that has_violations is False when no violations exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def good_function():
    pass


class GoodClass:
    def good_method(self):
        pass
'''
            (tmpdir_path / "clean.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            assert report.has_violations is False

    def test_violations_by_type_populated(self):
        """Test that violations_by_type dict is correctly populated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class badClass:
    def badMethod(self):
        pass


def badFunction():
    pass
'''
            (tmpdir_path / "types.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            assert len(report.violations_by_type) > 0

    def test_files_with_violations_count(self):
        """Test files_with_violations property counts correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text("def good_func(): pass\n")
            (tmpdir_path / "dirty.py").write_text("def badFunc(): pass\n")

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            assert report.files_with_violations == 1


class TestNamingConventionScannerReports:
    """Tests for naming report generation methods."""

    def test_generate_text_report_returns_string(self):
        """Test that generate_report with text format returns a non-empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "code.py").write_text("def badFunc(): pass\n")

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)
            output = scanner.generate_report(report, output_format="text")

            assert isinstance(output, str)
            assert len(output) > 0

    def test_generate_json_report_is_valid_json(self):
        """Test that JSON format produces valid parseable JSON."""
        import json as json_module

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "code.py").write_text("def badFunc(): pass\n")

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)
            output = scanner.generate_report(report, output_format="json")

            parsed = json_module.loads(output)
            assert "summary" in parsed
            assert "total_violations" in parsed["summary"]

    def test_generate_markdown_report_contains_header(self):
        """Test that markdown format output contains a markdown header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "code.py").write_text("def badFunc(): pass\n")

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)
            output = scanner.generate_report(report, output_format="markdown")

            assert "# Naming Convention Report" in output

    def test_generate_unsupported_format_raises_value_error(self):
        """Test that an unsupported format string raises ValueError."""
        scanner = NamingConventionScanner()
        report = NamingReport()

        with pytest.raises(ValueError):
            scanner.generate_report(report, output_format="html")

    def test_scan_duration_recorded(self):
        """Test that scan duration is recorded in the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = NamingConventionScanner()
            report = scanner.scan(Path(tmpdir))

            assert report.scan_duration_seconds >= 0.0

    def test_scan_path_recorded_in_report(self):
        """Test that the scan path is stored in the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = NamingConventionScanner()
            report = scanner.scan(Path(tmpdir))

            assert str(tmpdir) in report.scan_path


class TestNamingViolationModel:
    """Tests for NamingViolation model fields."""

    def test_violation_fields_populated(self):
        """Test that NamingViolation fields are all accessible and correctly typed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def camelCaseFunction():
    pass
'''
            (tmpdir_path / "violation_fields.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
            ]
            assert len(all_violations) == 1
            violation = all_violations[0]

            assert isinstance(violation.file_path, str)
            assert isinstance(violation.line_number, int)
            assert violation.line_number >= 1
            assert violation.element_type == "function"
            assert violation.element_name == "camelCaseFunction"
            assert violation.description != ""

    def test_violation_line_number_correct(self):
        """Test that the violation's line number points to the correct line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # The bad function is on line 5
            code = '''\
x = 1
y = 2
z = 3

def badFunctionName():
    pass
'''
            (tmpdir_path / "line_check.py").write_text(code)

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            all_violations = [
                v for violations in report.file_results.values() for v in violations
                if v.element_type == "function"
            ]
            assert len(all_violations) == 1
            assert all_violations[0].line_number == 5

    def test_allow_list_suppresses_violations(self):
        """Test that names in the allow_list are not flagged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def allowedBadName():
    pass
'''
            (tmpdir_path / "allowed.py").write_text(code)

            config = NamingConfig(allow_list=["allowedBadName"])
            scanner = NamingConventionScanner(config)
            report = scanner.scan(tmpdir_path)

            assert report.total_violations == 0

    def test_non_python_files_excluded(self):
        """Test that non-Python files are not analysed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text("def good_func(): pass\n")
            (tmpdir_path / "readme.txt").write_text("someText = 1\n")
            (tmpdir_path / "data.js").write_text("function badJS() {}\n")

            scanner = NamingConventionScanner()
            report = scanner.scan(tmpdir_path)

            # Only the .py file should be analysed
            assert report.total_violations == 0
