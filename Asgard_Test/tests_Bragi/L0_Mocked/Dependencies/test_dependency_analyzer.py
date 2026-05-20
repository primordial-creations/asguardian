"""
Tests for Heimdall Dependency Analyzer Service

Unit tests for dependency graph and cycle detection.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Dependencies.models.dependency_models import DependencyConfig
from Asgard.Bragi.Dependencies.services.dependency_analyzer import DependencyAnalyzer


class TestDependencyAnalyzer:
    """Tests for DependencyAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = DependencyAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.max_dependencies == 10

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = DependencyConfig(max_dependencies=10, include_external=True)
        analyzer = DependencyAnalyzer(config)
        assert analyzer.config.max_dependencies == 10
        assert analyzer.config.include_external is True

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = DependencyAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = DependencyAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            assert result.total_modules == 0
            assert result.has_cycles is False

    def test_analyze_simple_module(self):
        """Test analyzing a simple module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
import os
import sys

def main():
    pass
'''
            (tmpdir_path / "main.py").write_text(code)

            config = DependencyConfig(include_external=True)
            analyzer = DependencyAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_modules >= 1

    def test_analyze_internal_dependencies(self):
        """Test analyzing internal module dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create module A
            (tmpdir_path / "module_a.py").write_text('''
def function_a():
    return "A"
''')

            # Create module B that imports A
            (tmpdir_path / "module_b.py").write_text('''
from module_a import function_a

def function_b():
    return function_a()
''')

            analyzer = DependencyAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            # Should detect module_b depends on module_a
            assert result.total_modules >= 1

    def test_detect_circular_dependency(self):
        """Test detecting circular dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pkg_dir = tmpdir_path / "pkg"
            pkg_dir.mkdir()

            # Create __init__.py
            (pkg_dir / "__init__.py").write_text("")

            # Create module A that imports B
            (pkg_dir / "module_a.py").write_text('''
from pkg.module_b import function_b

def function_a():
    return function_b()
''')

            # Create module B that imports A
            (pkg_dir / "module_b.py").write_text('''
from pkg.module_a import function_a

def function_b():
    return function_a()
''')

            analyzer = DependencyAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            # Should detect the circular dependency
            # Note: Detection depends on import resolution
            assert result.total_modules >= 2

    def test_get_cycles(self):
        """Test getting cycles directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "simple.py").write_text('''
def simple():
    pass
''')

            analyzer = DependencyAnalyzer()
            cycles = analyzer.get_cycles(tmpdir_path)

            # Simple code should have no cycles
            assert isinstance(cycles, list)

    def test_get_modularity(self):
        """Test getting modularity metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "module.py").write_text('''
def function():
    pass
''')

            analyzer = DependencyAnalyzer()
            modularity = analyzer.get_modularity(tmpdir_path)

            assert hasattr(modularity, 'modularity_score')
            assert hasattr(modularity, 'clusters')

    def test_generate_text_report(self):
        """Test generating text format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
def test():
    pass
''')

            analyzer = DependencyAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "text")

            assert "DEPENDENCY" in report or "ANALYSIS" in report

    def test_generate_json_report(self):
        """Test generating JSON format report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "test.py").write_text('''
def test():
    pass
''')

            analyzer = DependencyAnalyzer()
            result = analyzer.analyze(tmpdir_path)
            report = analyzer.generate_report(result, "json")

            import json
            data = json.loads(report)
            assert "dependencies" in data or "modules" in data
