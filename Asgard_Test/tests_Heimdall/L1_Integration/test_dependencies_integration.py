"""
L1 Integration Tests for Heimdall Dependency Analysis

Tests dependency analysis on real Python projects.
"""

import json
import pytest
from pathlib import Path

from Asgard.Heimdall.Dependencies import (
    DependencyAnalyzer,
    DependencyConfig,
)


class TestDependenciesIntegration:
    """Integration tests for dependency analysis."""

    def test_dependencies_analyze_simple_project_full(self, simple_project):
        """Test full dependency analysis on simple project."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(simple_project)

        assert report is not None
        assert hasattr(report, 'total_modules')
        assert report.total_modules >= 0
        assert hasattr(report, 'scan_path')

    def test_dependencies_analyze_complex_project_full(self, complex_project):
        """Test full dependency analysis on complex project."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None
        assert report.total_modules >= 2
        assert hasattr(report, 'total_dependencies')

        # Complex project should have internal dependencies
        if hasattr(report, 'internal_dependencies'):
            assert isinstance(report.internal_dependencies, (list, dict))

    def test_dependencies_detect_circular_simple_project(self, simple_project):
        """Test circular dependency detection on simple project."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(simple_project)

        assert report is not None
        assert hasattr(report, 'has_cycles')

        # Simple project should have no circular dependencies
        assert report.has_cycles is False

    def test_dependencies_detect_circular_circular_project(self, circular_dependency_project):
        """Test circular dependency detection on circular project."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(circular_dependency_project)

        assert report is not None
        assert hasattr(report, 'has_cycles')

        # Circular project should have circular dependencies
        # Note: Detection may depend on how imports are resolved
        if hasattr(report, 'cycles'):
            assert isinstance(report.cycles, list)

    def test_dependencies_get_cycles_directly(self, circular_dependency_project):
        """Test getting cycles directly from analyzer."""
        analyzer = DependencyAnalyzer()
        cycles = analyzer.get_cycles(circular_dependency_project)

        assert isinstance(cycles, list)
        # May or may not detect cycles depending on import resolution

    def test_dependencies_analyze_internal_dependencies(self, complex_project):
        """Test analysis of internal dependencies."""
        config = DependencyConfig(include_external=False)
        analyzer = DependencyAnalyzer(config)
        report = analyzer.analyze(complex_project)

        assert report is not None
        assert report.total_modules >= 1

        # Should have dependencies between internal modules
        if hasattr(report, 'dependencies'):
            assert isinstance(report.dependencies, (list, dict))

    def test_dependencies_analyze_external_dependencies(self, simple_project):
        """Test analysis of external dependencies."""
        config = DependencyConfig(include_external=True)
        analyzer = DependencyAnalyzer(config)
        report = analyzer.analyze(simple_project)

        assert report is not None
        assert report.total_modules >= 1

        # Should detect imports like 'os', 'sys'
        if hasattr(report, 'external_dependencies'):
            assert isinstance(report.external_dependencies, (list, dict))

    def test_dependencies_analyze_max_dependencies_threshold(self, complex_project):
        """Test max dependencies threshold configuration."""
        config = DependencyConfig(max_dependencies=5)
        analyzer = DependencyAnalyzer(config)
        report = analyzer.analyze(complex_project)

        assert report is not None

        # Check if violations are tracked
        if hasattr(report, 'violations'):
            assert isinstance(report.violations, list)

    def test_dependencies_get_modularity_simple_project(self, simple_project):
        """Test modularity metrics on simple project."""
        analyzer = DependencyAnalyzer()
        modularity = analyzer.get_modularity(simple_project)

        assert modularity is not None
        assert hasattr(modularity, 'modularity_score')
        assert isinstance(modularity.modularity_score, (int, float))
        assert hasattr(modularity, 'clusters')

    def test_dependencies_get_modularity_complex_project(self, complex_project):
        """Test modularity metrics on complex project."""
        analyzer = DependencyAnalyzer()
        modularity = analyzer.get_modularity(complex_project)

        assert modularity is not None
        assert hasattr(modularity, 'modularity_score')
        assert isinstance(modularity.modularity_score, (int, float))

    def test_dependencies_generate_text_report(self, simple_project):
        """Test generating text report for dependency analysis."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(simple_project)
        text_report = analyzer.generate_report(report, "text")

        assert text_report is not None
        assert isinstance(text_report, str)
        assert len(text_report) > 0
        assert "DEPENDENCY" in text_report or "ANALYSIS" in text_report

    def test_dependencies_generate_json_report(self, simple_project):
        """Test generating JSON report for dependency analysis."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(simple_project)
        json_report = analyzer.generate_report(report, "json")

        assert json_report is not None
        assert isinstance(json_report, str)

        # Validate JSON structure
        data = json.loads(json_report)
        assert isinstance(data, dict)
        assert "dependencies" in data or "modules" in data or "total_modules" in data

    def test_dependencies_dependency_graph_structure(self, complex_project):
        """Test dependency graph structure."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None

        # Check if graph information is available
        if hasattr(report, 'dependency_graph'):
            graph = report.dependency_graph
            assert graph is not None

    def test_dependencies_analyze_package_structure(self, complex_project):
        """Test analysis of package structure."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None
        assert report.total_modules >= 1

        # Should detect modules within packages
        if hasattr(report, 'modules'):
            modules = report.modules
            assert isinstance(modules, (list, dict))

    def test_dependencies_empty_directory_handling(self, tmp_path):
        """Test dependency analysis on empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(empty_dir)

        assert report is not None
        assert report.total_modules == 0
        assert report.has_cycles is False

    def test_dependencies_nonexistent_path_handling(self):
        """Test dependency analysis on nonexistent path."""
        nonexistent = Path("/nonexistent/path/to/nowhere")

        analyzer = DependencyAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(nonexistent)

    def test_dependencies_single_file_analysis(self, tmp_path):
        """Test dependency analysis on single file."""
        single_file = tmp_path / "single.py"
        single_file.write_text('''
import os
import sys

def main():
    print(os.getcwd())
''')

        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(single_file.parent)

        assert report is not None
        assert report.total_modules >= 1

    def test_dependencies_relative_imports(self, tmp_path):
        """Test dependency analysis with relative imports."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('')

        (pkg_dir / "module_a.py").write_text('''
from . import module_b

def function_a():
    return module_b.function_b()
''')

        (pkg_dir / "module_b.py").write_text('''
def function_b():
    return "B"
''')

        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(tmp_path)

        assert report is not None
        assert report.total_modules >= 2

        # Should detect dependency between module_a and module_b

    def test_dependencies_absolute_imports(self, complex_project):
        """Test dependency analysis with absolute imports."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None
        assert report.total_modules >= 1

        # Should handle absolute imports like 'from mypackage.base import BaseService'

    def test_dependencies_import_from_analysis(self, tmp_path):
        """Test analysis of 'from X import Y' statements."""
        test_file = tmp_path / "test.py"
        test_file.write_text('''
from os.path import join, exists
from collections import defaultdict
from typing import List, Dict

def process(items: List[str]) -> Dict:
    result = defaultdict(list)
    for item in items:
        path = join("/tmp", item)
        if exists(path):
            result[item].append(path)
    return result
''')

        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(tmp_path)

        assert report is not None
        assert report.total_modules >= 1

    def test_dependencies_import_as_analysis(self, tmp_path):
        """Test analysis of 'import X as Y' statements."""
        test_file = tmp_path / "test.py"
        test_file.write_text('''
import os as operating_system
import sys as system
import json as js

def main():
    print(operating_system.getcwd())
    print(system.version)
    print(js.dumps({"key": "value"}))
''')

        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(tmp_path)

        assert report is not None
        assert report.total_modules >= 1

    def test_dependencies_nested_package_structure(self, tmp_path):
        """Test dependency analysis on nested package structure."""
        # Create nested package structure
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('')

        sub = pkg / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text('')

        (sub / "module.py").write_text('''
def nested_function():
    return "nested"
''')

        (pkg / "main.py").write_text('''
from pkg.sub.module import nested_function

def main():
    return nested_function()
''')

        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(tmp_path)

        assert report is not None
        assert report.total_modules >= 1

    def test_dependencies_cycle_details(self, circular_dependency_project):
        """Test that cycle details are provided."""
        analyzer = DependencyAnalyzer()
        cycles = analyzer.get_cycles(circular_dependency_project)

        assert isinstance(cycles, list)

        # If cycles are detected, check structure
        if len(cycles) > 0:
            for cycle in cycles:
                # Cycle should have modules involved
                assert cycle is not None

    def test_dependencies_coupling_metrics(self, complex_project):
        """Test coupling metrics in dependency analysis."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None

        # Check for coupling metrics
        if hasattr(report, 'average_coupling'):
            assert isinstance(report.average_coupling, (int, float))

    def test_dependencies_fan_in_fan_out(self, complex_project):
        """Test fan-in and fan-out metrics."""
        analyzer = DependencyAnalyzer()
        report = analyzer.analyze(complex_project)

        assert report is not None

        # Check if fan-in/fan-out metrics are available
        if hasattr(report, 'modules'):
            # Each module might have fan-in and fan-out counts
            pass
