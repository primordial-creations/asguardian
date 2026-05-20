"""
Tests for Heimdall Coverage Models

Unit tests for test coverage analysis data models.
"""

import pytest
from datetime import datetime

from Asgard.Bragi.Coverage.models.coverage_models import (
    CoverageConfig,
    CoverageSeverity,
    SuggestionPriority,
    MethodType,
    MethodInfo,
    CoverageGap,
    CoverageMetrics,
    TestSuggestion,
    ClassCoverage,
    CoverageReport,
)


class TestCoverageConfig:
    """Tests for CoverageConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CoverageConfig()
        assert config.include_private is False
        assert config.include_dunder is False
        assert ".py" in config.include_extensions

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CoverageConfig(
            include_private=True,
            include_dunder=True,
        )
        assert config.include_private is True
        assert config.include_dunder is True


class TestCoverageSeverity:
    """Tests for CoverageSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert CoverageSeverity.LOW.value == "low"
        assert CoverageSeverity.MODERATE.value == "moderate"
        assert CoverageSeverity.HIGH.value == "high"
        assert CoverageSeverity.CRITICAL.value == "critical"


class TestSuggestionPriority:
    """Tests for SuggestionPriority enum."""

    def test_priority_values(self):
        """Test priority enum values."""
        assert SuggestionPriority.LOW.value == "low"
        assert SuggestionPriority.MEDIUM.value == "medium"
        assert SuggestionPriority.HIGH.value == "high"
        assert SuggestionPriority.URGENT.value == "urgent"


class TestMethodType:
    """Tests for MethodType enum."""

    def test_method_type_values(self):
        """Test method type enum values."""
        assert MethodType.PUBLIC.value == "public"
        assert MethodType.PRIVATE.value == "private"
        assert MethodType.DUNDER.value == "dunder"


class TestMethodInfo:
    """Tests for MethodInfo class."""

    def test_create_method_info(self):
        """Test creating method info."""
        method = MethodInfo(
            name="test_method",
            class_name="TestClass",
            file_path="/test/path.py",
            line_number=10,
            parameter_count=2,
        )
        assert method.name == "test_method"
        assert method.class_name == "TestClass"
        assert method.parameter_count == 2

    def test_full_name_with_class(self):
        """Test full name with class."""
        method = MethodInfo(
            name="test_method",
            class_name="TestClass",
            file_path="/test/path.py",
            line_number=10,
        )
        assert method.full_name == "TestClass.test_method"

    def test_full_name_without_class(self):
        """Test full name without class."""
        method = MethodInfo(
            name="test_function",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
        )
        assert method.full_name == "test_function"

    def test_method_type_public(self):
        """Test public method type detection."""
        method = MethodInfo(
            name="public_method",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
        )
        assert method.method_type == MethodType.PUBLIC

    def test_method_type_private(self):
        """Test private method type can be set."""
        method = MethodInfo(
            name="_private_method",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
            method_type=MethodType.PRIVATE,
        )
        assert method.method_type == MethodType.PRIVATE

    def test_method_type_dunder(self):
        """Test dunder method type can be set."""
        method = MethodInfo(
            name="__init__",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
            method_type=MethodType.DUNDER,
        )
        assert method.method_type == MethodType.DUNDER


class TestCoverageGap:
    """Tests for CoverageGap class."""

    def test_create_gap(self):
        """Test creating a coverage gap."""
        method = MethodInfo(
            name="untested_method",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
        )
        gap = CoverageGap(
            method=method,
            gap_type="uncovered",
            severity=CoverageSeverity.HIGH,
            message="No test coverage",
        )
        assert gap.method.name == "untested_method"
        assert gap.severity == CoverageSeverity.HIGH

    def test_file_path_property(self):
        """Test file_path property."""
        method = MethodInfo(
            name="method",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
        )
        gap = CoverageGap(
            method=method,
            gap_type="uncovered",
            severity=CoverageSeverity.MODERATE,
            message="No coverage",
        )
        assert gap.file_path == "/test/path.py"

    def test_line_number_property(self):
        """Test line_number property."""
        method = MethodInfo(
            name="method",
            class_name=None,
            file_path="/test/path.py",
            line_number=42,
        )
        gap = CoverageGap(
            method=method,
            gap_type="uncovered",
            severity=CoverageSeverity.MODERATE,
            message="No coverage",
        )
        assert gap.line_number == 42


class TestCoverageMetrics:
    """Tests for CoverageMetrics class."""

    def test_create_metrics(self):
        """Test creating coverage metrics."""
        metrics = CoverageMetrics(
            total_methods=100,
            covered_methods=75,
        )
        assert metrics.total_methods == 100
        assert metrics.covered_methods == 75

    def test_coverage_percent(self):
        """Test coverage percentage calculation."""
        metrics = CoverageMetrics(
            total_methods=100,
            covered_methods=75,
        )
        assert metrics.method_coverage_percent == 75.0

    def test_coverage_percent_zero_methods(self):
        """Test coverage percentage with zero methods."""
        metrics = CoverageMetrics(
            total_methods=0,
            covered_methods=0,
        )
        assert metrics.method_coverage_percent == 100.0


class TestTestSuggestion:
    """Tests for TestSuggestion class."""

    def test_create_suggestion(self):
        """Test creating a test suggestion."""
        method = MethodInfo(
            name="calculate_total",
            class_name="Calculator",
            file_path="/test/calc.py",
            line_number=10,
        )
        suggestion = TestSuggestion(
            method=method,
            test_name="test_calculator_calculate_total",
            test_type="unit_test",
            priority=SuggestionPriority.HIGH,
            description="Test the calculate_total method",
        )
        assert suggestion.test_name == "test_calculator_calculate_total"
        assert suggestion.priority == SuggestionPriority.HIGH


class TestClassCoverage:
    """Tests for ClassCoverage class."""

    def test_create_class_coverage(self):
        """Test creating class coverage."""
        coverage = ClassCoverage(
            class_name="TestClass",
            file_path="/test/path.py",
            total_methods=10,
            covered_methods=7,
            uncovered_methods=["method_a", "method_b", "method_c"],
        )
        assert coverage.class_name == "TestClass"
        assert coverage.total_methods == 10
        assert coverage.covered_methods == 7

    def test_coverage_percent(self):
        """Test coverage percentage calculation."""
        coverage = ClassCoverage(
            class_name="TestClass",
            file_path="/test/path.py",
            total_methods=10,
            covered_methods=7,
            uncovered_methods=["a", "b", "c"],
            coverage_percent=70.0,
        )
        assert coverage.coverage_percent == 70.0


class TestCoverageReport:
    """Tests for CoverageReport class."""

    def test_create_report(self):
        """Test creating a coverage report."""
        report = CoverageReport(scan_path="/test/path")
        assert report.scan_path == "/test/path"
        assert report.gaps == []
        assert report.suggestions == []

    def test_total_gaps(self):
        """Test total gaps count."""
        method = MethodInfo(
            name="method",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
        )
        gap = CoverageGap(
            method=method,
            gap_type="uncovered",
            severity=CoverageSeverity.HIGH,
            message="No coverage",
        )
        report = CoverageReport(
            scan_path="/test/path",
            gaps=[gap],
        )
        assert report.total_gaps == 1

    def test_has_gaps(self):
        """Test has_gaps property."""
        report_empty = CoverageReport(scan_path="/test/path")
        assert report_empty.has_gaps is False

        method = MethodInfo(
            name="method",
            class_name=None,
            file_path="/test/path.py",
            line_number=10,
        )
        gap = CoverageGap(
            method=method,
            gap_type="uncovered",
            severity=CoverageSeverity.HIGH,
            message="No coverage",
        )
        report_with_gaps = CoverageReport(
            scan_path="/test/path",
            gaps=[gap],
        )
        assert report_with_gaps.has_gaps is True
