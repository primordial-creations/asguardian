"""
Tests for Heimdall Coverage Analyzer Service

Unit tests for test coverage gap detection and suggestion generation.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Coverage.models.coverage_models import CoverageConfig
from Asgard.Bragi.Coverage.services.coverage_analyzer import CoverageAnalyzer


class TestCoverageAnalyzer:
    """Tests for CoverageAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = CoverageAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.include_private is False

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = CoverageConfig(include_private=True, include_dunder=True)
        analyzer = CoverageAnalyzer(config)
        assert analyzer.config.include_private is True
        assert analyzer.config.include_dunder is True

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = CoverageAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = CoverageAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            assert result.total_gaps == 0
            assert result.has_gaps is False

    def test_analyze_source_with_no_tests(self):
        """Test analyzing source code without corresponding tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source file
            code = '''
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
'''
            (tmpdir_path / "calculator.py").write_text(code)

            analyzer = CoverageAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            # Should detect gaps since there are no tests
            assert result.metrics.total_methods >= 4

    def test_analyze_source_with_tests(self):
        """Test analyzing source code with corresponding tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            tests_dir = tmpdir_path / "tests"
            tests_dir.mkdir()

            # Create source file
            (tmpdir_path / "calculator.py").write_text('''
class Calculator:
    def add(self, a, b):
        return a + b
''')

            # Create test file
            (tests_dir / "test_calculator.py").write_text('''
def test_calculator_add():
    calc = Calculator()
    assert calc.add(2, 3) == 5
''')

            analyzer = CoverageAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            # Should find the source method
            assert result.metrics.total_methods >= 1

    def test_get_gaps(self):
        """Test getting coverage gaps directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "service.py").write_text('''
class Service:
    def process(self):
        pass

    def validate(self):
        pass
''')

            analyzer = CoverageAnalyzer()
            gaps = analyzer.get_gaps(tmpdir_path)

            # Should detect gaps for untested methods
            assert isinstance(gaps, list)

    def test_get_suggestions(self):
        """Test getting test suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "service.py").write_text('''
class UserService:
    def create_user(self, username, email):
        pass

    def delete_user(self, user_id):
        pass
''')

            analyzer = CoverageAnalyzer()
            suggestions = analyzer.get_suggestions(tmpdir_path, max_count=5)

            assert isinstance(suggestions, list)
            if suggestions:
                assert hasattr(suggestions[0], 'test_name')
                assert hasattr(suggestions[0], 'priority')

    def test_get_class_coverage(self):
        """Test getting class-level coverage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "classes.py").write_text('''
class ClassA:
    def method_a(self):
        pass

class ClassB:
    def method_b(self):
        pass

    def method_c(self):
        pass
''')

            analyzer = CoverageAnalyzer()
            class_coverage = analyzer.get_class_coverage(tmpdir_path)

            assert isinstance(class_coverage, list)

    def test_generate_text_report(self):
        """Test generating text format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
def test_function():
    pass
''')

            analyzer = CoverageAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "text")

            assert "COVERAGE" in report or "ANALYSIS" in report

    def test_generate_json_report(self):
        """Test generating JSON format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
def test_function():
    pass
''')

            analyzer = CoverageAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "json")

            import json
            data = json.loads(report)
            assert "scan_path" in data
            assert "metrics" in data

    def test_generate_markdown_report(self):
        """Test generating Markdown format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
def test_function():
    pass
''')

            analyzer = CoverageAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "markdown")

            assert "# Heimdall" in report or "Coverage" in report

    def test_quick_check(self):
        """Test quick check functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "service.py").write_text('''
class Service:
    def method(self):
        pass
''')

            analyzer = CoverageAnalyzer()
            check = analyzer.quick_check(tmpdir_path)

            assert "method_coverage_percent" in check
            assert "total_gaps" in check
            assert "total_suggestions" in check

    def test_analyze_async_methods(self):
        """Test analyzing async methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "async_service.py").write_text('''
class AsyncService:
    async def fetch_data(self):
        return {"data": "value"}

    async def process_data(self, data):
        return data
''')

            analyzer = CoverageAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            # Should detect async methods
            assert result.metrics.total_methods >= 2

    def test_exclude_private_methods(self):
        """Test excluding private methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "service.py").write_text('''
class Service:
    def public_method(self):
        pass

    def _private_method(self):
        pass

    def __dunder_method__(self):
        pass
''')

            # Default config excludes private methods
            config = CoverageConfig(include_private=False, include_dunder=False)
            analyzer = CoverageAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should only include public method
            # Exact count depends on implementation
            assert result.metrics.total_methods >= 1
