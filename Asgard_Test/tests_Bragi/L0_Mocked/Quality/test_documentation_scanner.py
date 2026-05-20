"""
Tests for Heimdall Documentation Scanner Service

Unit tests for comment density and public API documentation coverage analysis.
Tests use real temp files with actual Python source code.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.documentation_models import (
    DocumentationConfig,
    DocumentationReport,
    FileDocumentation,
)
from Asgard.Bragi.Quality.services.documentation_scanner import DocumentationScanner


class TestDocumentationScannerInit:
    """Tests for DocumentationScanner initialisation."""

    def test_init_with_default_config(self):
        """Test initialising with default configuration."""
        scanner = DocumentationScanner()
        assert scanner.config is not None
        assert scanner.config.min_comment_density == 10.0
        assert scanner.config.min_api_coverage == 70.0

    def test_init_with_custom_config(self):
        """Test initialising with custom configuration."""
        config = DocumentationConfig(min_comment_density=20.0, min_api_coverage=90.0)
        scanner = DocumentationScanner(config)
        assert scanner.config.min_comment_density == 20.0
        assert scanner.config.min_api_coverage == 90.0


class TestDocumentationScannerScanPath:
    """Tests for scan path validation."""

    def test_scan_nonexistent_path_raises_file_not_found(self):
        """Test that scanning a nonexistent path raises FileNotFoundError."""
        scanner = DocumentationScanner()
        with pytest.raises(FileNotFoundError):
            scanner.scan(Path("/nonexistent/path/that/does/not/exist"))

    def test_scan_empty_directory_returns_empty_report(self):
        """Test scanning an empty directory produces a valid empty report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = DocumentationScanner()
            report = scanner.scan(Path(tmpdir))

            assert isinstance(report, DocumentationReport)
            assert report.total_files == 0
            assert report.total_public_apis == 0
            assert report.undocumented_apis == 0
            assert report.overall_comment_density == 0.0
            assert report.overall_api_coverage == 0.0


class TestFullDocstringCoverage:
    """Tests for files where all public functions have docstrings."""

    def test_all_functions_documented_100_percent_coverage(self):
        """Test that 100% API coverage is reported when all public functions have docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def add(a, b):
    """Return the sum of a and b."""
    return a + b


def subtract(a, b):
    """Return the difference of a and b."""
    return a - b


def multiply(a, b):
    """Return the product of a and b."""
    return a * b
'''
            (tmpdir_path / "math_ops.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            assert report.total_files == 1
            assert report.overall_api_coverage == 100.0
            assert report.undocumented_apis == 0

    def test_all_documented_file_result_has_100_coverage(self):
        """Test that file-level result shows 100% when all functions documented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def greet(name):
    """Greet the user by name."""
    return f"Hello, {name}"
'''
            (tmpdir_path / "greet.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert file_result.public_api_coverage == 100.0
            assert file_result.undocumented_count == 0


class TestNoDocstringCoverage:
    """Tests for files where no functions have docstrings."""

    def test_no_functions_documented_zero_coverage(self):
        """Test that 0% API coverage is reported when no public functions have docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def add(a, b):
    return a + b


def subtract(a, b):
    return a - b
'''
            (tmpdir_path / "undoc.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            assert report.total_files == 1
            assert report.overall_api_coverage == 0.0
            assert report.undocumented_apis == 2

    def test_undocumented_functions_count_correct(self):
        """Test that the count of undocumented functions is correct."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def func_one():
    pass


def func_two():
    pass


def func_three():
    pass
'''
            (tmpdir_path / "three_funcs.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert file_result.undocumented_count == 3


class TestClassDocumentation:
    """Tests for class and method documentation scanning."""

    def test_class_with_docstring_counted_as_documented(self):
        """Test that a class with a docstring is counted as documented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class Calculator:
    """A simple calculator class."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b
'''
            (tmpdir_path / "calc.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert len(file_result.classes) == 1
            cls_doc = file_result.classes[0]
            assert cls_doc.name == "Calculator"
            assert cls_doc.has_docstring is True

    def test_class_without_docstring_counted_as_undocumented(self):
        """Test that a class without a docstring is counted as undocumented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class Widget:
    def render(self):
        return "<widget />"
'''
            (tmpdir_path / "widget.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            cls_doc = file_result.classes[0]
            assert cls_doc.has_docstring is False
            assert file_result.undocumented_count >= 1

    def test_class_methods_documented_coverage_100(self):
        """Test full coverage when class and all its methods have docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class FullyDocumented:
    """This class is fully documented."""

    def method_one(self):
        """First method."""
        pass

    def method_two(self):
        """Second method."""
        pass
'''
            (tmpdir_path / "full_doc.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert file_result.public_api_coverage == 100.0
            assert file_result.undocumented_count == 0

    def test_class_methods_undocumented_coverage_partial(self):
        """Test partial coverage when class has docstring but methods do not."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class PartialDoc:
    """Class docstring present."""

    def first_method(self):
        pass

    def second_method(self):
        pass
'''
            (tmpdir_path / "partial.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            # 1 class (documented) + 2 methods (undocumented) = 3 total
            # 1 documented, 2 undocumented -> 33.3% coverage
            assert file_result.public_api_coverage < 100.0
            assert file_result.undocumented_count == 2

    def test_private_class_not_counted_in_public_api(self):
        """Test that private classes (underscore prefix) are not counted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class _PrivateHelper:
    def _do_something(self):
        pass
'''
            (tmpdir_path / "private_class.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            # Private class and private method - no public API to document
            file_result = report.file_results[0]
            assert file_result.classes[0].is_public is False
            assert file_result.public_api_coverage == 100.0

    def test_private_function_not_counted_in_public_api(self):
        """Test that private functions (underscore prefix) are not counted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
def _private_helper():
    pass


def public_function():
    """This is documented."""
    pass
'''
            (tmpdir_path / "mixed_visibility.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            # Only public_function is in the public API
            assert file_result.public_api_coverage == 100.0
            assert file_result.undocumented_count == 0

    def test_dunder_methods_not_counted_as_public_api(self):
        """Test that dunder methods (__init__ etc.) are not counted in public API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
class MyClass:
    """Documented class."""

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"MyClass({self.value})"

    def public_method(self):
        """A public method."""
        return self.value
'''
            (tmpdir_path / "dunder.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            # MyClass (documented) + public_method (documented) = 2 public, 0 undocumented
            assert file_result.public_api_coverage == 100.0
            assert file_result.undocumented_count == 0


class TestCommentDensity:
    """Tests for comment density calculation."""

    def test_file_with_comments_has_positive_density(self):
        """Test that files with comments produce a positive comment density."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
# This is a comment
# Another comment
def my_function():
    # Inner comment
    return 42
'''
            (tmpdir_path / "commented.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert file_result.comment_density > 0.0

    def test_file_without_comments_has_zero_density(self):
        """Test that a file with no comments has zero or near-zero comment density."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
x = 1
y = 2
z = x + y
'''
            (tmpdir_path / "no_comments.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert file_result.comment_density == 0.0

    def test_overall_comment_density_aggregated_across_files(self):
        """Test that overall comment density is aggregated from all files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # File with comments
            (tmpdir_path / "with_comments.py").write_text(
                "# comment\n# comment\n# comment\nx = 1\n"
            )
            # File without comments
            (tmpdir_path / "no_comments.py").write_text(
                "a = 1\nb = 2\nc = 3\n"
            )

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            # Density should be between 0 and 100
            assert 0.0 <= report.overall_comment_density <= 100.0
            assert report.total_files == 2

    def test_comment_density_only_counts_non_blank_lines(self):
        """Test that blank lines are excluded from the density denominator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
# comment one

# comment two

x = 1
'''
            (tmpdir_path / "spaced.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert file_result.blank_lines >= 2
            # 2 comment lines out of 3 non-blank lines = ~66.7%
            assert file_result.comment_density > 0.0

    def test_line_counts_add_up(self):
        """Test that total_lines == code_lines + comment_lines + blank_lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''\
# A comment

def foo():
    return 1
'''
            (tmpdir_path / "counts.py").write_text(code)

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert (
                file_result.code_lines
                + file_result.comment_lines
                + file_result.blank_lines
                == file_result.total_lines
            )


class TestEmptyFile:
    """Tests for scanning an empty Python file."""

    def test_empty_file_produces_valid_result(self):
        """Test that an empty file produces a valid FileDocumentation record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "empty.py").write_text("")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            assert report.total_files == 1
            file_result = report.file_results[0]
            assert file_result.total_lines == 0
            assert file_result.public_api_coverage == 100.0
            assert file_result.undocumented_count == 0

    def test_empty_file_has_zero_comment_density(self):
        """Test that an empty file has zero comment density."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "empty.py").write_text("")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            file_result = report.file_results[0]
            assert file_result.comment_density == 0.0


class TestMultipleFiles:
    """Tests involving multiple Python files."""

    def test_multiple_files_all_counted(self):
        """Test that all Python files in a directory are scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "a.py").write_text("def fa(): pass\n")
            (tmpdir_path / "b.py").write_text("def fb(): pass\n")
            (tmpdir_path / "c.py").write_text("def fc(): pass\n")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            assert report.total_files == 3

    def test_non_python_files_excluded(self):
        """Test that non-Python files are not included in results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "code.py").write_text("def f(): pass\n")
            (tmpdir_path / "readme.txt").write_text("Some text\n")
            (tmpdir_path / "data.json").write_text("{}\n")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            assert report.total_files == 1

    def test_aggregate_undocumented_count_across_files(self):
        """Test that undocumented APIs are summed across all files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "first.py").write_text("def func_a(): pass\ndef func_b(): pass\n")
            (tmpdir_path / "second.py").write_text("def func_c(): pass\n")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)

            assert report.undocumented_apis == 3
            assert report.total_public_apis == 3


class TestDocumentationScannerReports:
    """Tests for report generation methods."""

    def test_generate_text_report_returns_string(self):
        """Test that generate_report with text format returns a non-empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "code.py").write_text("def f(): pass\n")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)
            output = scanner.generate_report(report, output_format="text")

            assert isinstance(output, str)
            assert len(output) > 0

    def test_generate_json_report_returns_valid_string(self):
        """Test that generate_report with json format returns a non-empty string."""
        import json as json_module

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "code.py").write_text("def f(): pass\n")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)
            output = scanner.generate_report(report, output_format="json")

            parsed = json_module.loads(output)
            assert "summary" in parsed

    def test_generate_markdown_report_returns_string(self):
        """Test that generate_report with markdown format returns a non-empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "code.py").write_text("def f(): pass\n")

            config = DocumentationConfig(include_tests=True)
            scanner = DocumentationScanner(config)
            report = scanner.scan(tmpdir_path)
            output = scanner.generate_report(report, output_format="markdown")

            assert "# Documentation Coverage Report" in output

    def test_generate_unsupported_format_raises_value_error(self):
        """Test that an unsupported format raises ValueError."""
        scanner = DocumentationScanner()
        report = DocumentationReport()

        with pytest.raises(ValueError):
            scanner.generate_report(report, output_format="xml")

    def test_scan_duration_recorded(self):
        """Test that scan duration is recorded in the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = DocumentationScanner()
            report = scanner.scan(Path(tmpdir))

            assert report.scan_duration_seconds >= 0.0

    def test_scan_path_recorded_in_report(self):
        """Test that the scan path is stored in the report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = DocumentationScanner()
            report = scanner.scan(Path(tmpdir))

            assert str(tmpdir) in report.scan_path
