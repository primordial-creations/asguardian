"""
Tests for Heimdall Dependency Models

Unit tests for dependency analysis data models.
"""

import pytest
from datetime import datetime

from Asgard.Bragi.Dependencies.models.dependency_models import (
    CircularDependency,
    DependencyConfig,
    DependencyInfo,
    DependencyReport,
    DependencySeverity,
    DependencyType,
    ModularityMetrics,
    ModuleDependencies,
)


class TestDependencyConfig:
    """Tests for DependencyConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DependencyConfig()
        assert config.max_dependencies == 10
        assert config.include_external is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DependencyConfig(
            max_dependencies=20,
            include_external=True,
        )
        assert config.max_dependencies == 20
        assert config.include_external is True


class TestDependencySeverity:
    """Tests for DependencySeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert DependencySeverity.LOW.value == "low"
        assert DependencySeverity.MODERATE.value == "moderate"
        assert DependencySeverity.HIGH.value == "high"
        assert DependencySeverity.CRITICAL.value == "critical"


class TestDependencyType:
    """Tests for DependencyType enum."""

    def test_dependency_type_values(self):
        """Test dependency type values."""
        assert DependencyType.IMPORT.value == "import"
        assert DependencyType.FROM_IMPORT.value == "from_import"
        assert DependencyType.INHERITANCE.value == "inheritance"


class TestDependencyInfo:
    """Tests for DependencyInfo class."""

    def test_create_dependency_info(self):
        """Test creating dependency info."""
        dep = DependencyInfo(
            source="module_a",
            target="module_b",
            dependency_type=DependencyType.IMPORT,
            line_number=5,
        )
        assert dep.source == "module_a"
        assert dep.target == "module_b"
        assert dep.dependency_type == DependencyType.IMPORT

    def test_key_property(self):
        """Test key property."""
        dep = DependencyInfo(
            source="module_a",
            target="module_b",
            dependency_type=DependencyType.IMPORT,
        )
        assert dep.key == "module_a->module_b"


class TestModuleDependencies:
    """Tests for ModuleDependencies class."""

    def test_create_module_dependencies(self):
        """Test creating module dependencies."""
        mod_deps = ModuleDependencies(
            module_name="module_a",
            file_path="/test/module_a.py",
            relative_path="module_a.py",
        )
        assert mod_deps.module_name == "module_a"
        assert mod_deps.total_dependencies == 0

    def test_add_dependency(self):
        """Test adding a dependency."""
        mod_deps = ModuleDependencies(
            module_name="module_a",
            file_path="/test/module_a.py",
            relative_path="module_a.py",
        )
        dep = DependencyInfo(
            source="module_a",
            target="module_b",
            dependency_type=DependencyType.IMPORT,
        )
        mod_deps.add_dependency(dep)
        assert mod_deps.total_dependencies == 1
        assert "module_b" in mod_deps.all_dependencies


class TestCircularDependency:
    """Tests for CircularDependency class."""

    def test_create_cycle(self):
        """Test creating a circular dependency."""
        cycle = CircularDependency(
            cycle=["module_a", "module_b", "module_a"],
        )
        assert len(cycle.cycle) == 3
        assert cycle.severity == DependencySeverity.CRITICAL

    def test_cycle_length(self):
        """Test cycle length property."""
        cycle = CircularDependency(
            cycle=["a", "b", "c", "a"],
        )
        assert cycle.cycle_length == 4

    def test_as_string(self):
        """Test cycle string representation."""
        cycle = CircularDependency(
            cycle=["module_a", "module_b"],
        )
        cycle_str = cycle.as_string
        assert "module_a" in cycle_str
        assert "module_b" in cycle_str


class TestModularityMetrics:
    """Tests for ModularityMetrics class."""

    def test_create_metrics(self):
        """Test creating modularity metrics."""
        metrics = ModularityMetrics(
            total_modules=5,
            total_dependencies=10,
            modularity_score=0.75,
        )
        assert metrics.modularity_score == 0.75
        assert metrics.total_modules == 5


class TestDependencyReport:
    """Tests for DependencyReport class."""

    def test_create_report(self):
        """Test creating a dependency report."""
        report = DependencyReport(scan_path="/test/path")
        assert report.scan_path == "/test/path"
        assert report.modules == []
        assert report.circular_dependencies == []

    def test_add_module(self):
        """Test adding module to report."""
        report = DependencyReport(scan_path="/test/path")
        mod_deps = ModuleDependencies(
            module_name="module_a",
            file_path="/test/module_a.py",
            relative_path="module_a.py",
        )
        report.add_module(mod_deps)
        assert report.total_modules == 1

    def test_has_cycles(self):
        """Test has_cycles detection."""
        report = DependencyReport(scan_path="/test/path")
        assert report.has_cycles is False

        cycle = CircularDependency(
            cycle=["a", "b", "a"],
        )
        report.add_cycle(cycle)
        assert report.has_cycles is True
        assert report.total_cycles == 1

    def test_get_module(self):
        """Test getting a module by name."""
        report = DependencyReport(scan_path="/test/path")
        mod_deps = ModuleDependencies(
            module_name="module_a",
            file_path="/test/module_a.py",
            relative_path="module_a.py",
        )
        report.add_module(mod_deps)
        found = report.get_module("module_a")
        assert found is not None
        assert found.module_name == "module_a"

        not_found = report.get_module("nonexistent")
        assert not_found is None
