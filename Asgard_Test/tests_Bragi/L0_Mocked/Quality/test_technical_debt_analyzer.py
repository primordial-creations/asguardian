"""
Tests for Heimdall Technical Debt Analyzer Service

Unit tests for technical debt analysis and quantification.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.debt_models import (
    DebtConfig,
    DebtItem,
    DebtReport,
    DebtSeverity,
    DebtType,
    EffortModels,
    InterestRates,
    ROIAnalysis,
    TimeHorizon,
    TimeProjection,
)
from Asgard.Bragi.Quality.services.technical_debt_analyzer import TechnicalDebtAnalyzer


class TestTechnicalDebtAnalyzer:
    """Tests for TechnicalDebtAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = TechnicalDebtAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.time_horizon == TimeHorizon.QUARTER.value
        assert analyzer.config.effort_models.complexity_reduction_factor == 0.5

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        effort_models = EffortModels(
            complexity_reduction_factor=1.0,
            test_coverage_factor=0.2,
        )
        config = DebtConfig(
            effort_models=effort_models,
            time_horizon=TimeHorizon.YEAR,
        )
        analyzer = TechnicalDebtAnalyzer(config)
        assert analyzer.config.effort_models.complexity_reduction_factor == 1.0
        assert analyzer.config.time_horizon == TimeHorizon.YEAR.value

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = TechnicalDebtAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = TechnicalDebtAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            assert result.total_debt_hours == 0
            assert result.has_debt is False

    def test_analyze_clean_code(self):
        """Test analyzing well-structured code with minimal debt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
"""Clean module."""

def calculate_sum(a, b):
    """Add two numbers."""
    return a + b

def calculate_product(a, b):
    """Multiply two numbers."""
    return a * b
''')

            analyzer = TechnicalDebtAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            # Clean code should have minimal debt (may still detect some items like missing tests)
            # Since this is a small clean module, code debt should be zero
            code_debt = result.debt_by_type.get(DebtType.CODE.value, 0)
            assert code_debt == 0

    def test_detect_code_debt_high_complexity(self):
        """Test detecting high complexity code debt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a highly complex function
            complex_code = '''
def very_complex_function(a, b, c, d, e):
    """This function is too complex."""
    result = 0
'''
            # Add many conditionals to increase complexity
            for i in range(20):
                complex_code += f'''    if a > {i}:
        result += 1
    elif b > {i}:
        result += 2
'''
            complex_code += '    return result\n'

            (tmpdir_path / "complex.py").write_text(complex_code)

            config = DebtConfig(debt_types=[DebtType.CODE.value])
            analyzer = TechnicalDebtAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should detect high complexity
            code_items = result.get_items_by_type(DebtType.CODE)
            assert len(code_items) >= 1

    def test_detect_code_debt_long_method(self):
        """Test detecting long method code debt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a very long method (>50 lines)
            long_method_code = '''
def very_long_function():
    """This function is too long."""
    x = 1
    y = 2
''' + '    z = x + y\n' * 60 + '    return z\n'

            (tmpdir_path / "long_method.py").write_text(long_method_code)

            config = DebtConfig(debt_types=[DebtType.CODE.value])
            analyzer = TechnicalDebtAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should detect long method
            long_method_items = [
                item for item in result.debt_items
                if "Long method" in item.description
            ]
            assert len(long_method_items) >= 1

    def test_detect_design_debt(self):
        """Test detecting design/coupling debt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a file with many imports (high coupling)
            high_coupling_code = '''
"""Module with high coupling."""
import os
import sys
import json
import logging
import datetime
import collections
import functools
import itertools
import contextlib
import pathlib
import typing
import dataclasses
'''

            (tmpdir_path / "coupled.py").write_text(high_coupling_code)

            config = DebtConfig(debt_types=[DebtType.DESIGN.value])
            analyzer = TechnicalDebtAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should detect high coupling (12 imports)
            design_items = result.get_items_by_type(DebtType.DESIGN)
            assert len(design_items) >= 1

    def test_detect_test_debt(self):
        """Test detecting missing test coverage debt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a source file without corresponding test
            (tmpdir_path / "service.py").write_text('''
"""Service module."""

class UserService:
    """User service class."""

    def get_user(self, user_id):
        """Get user by ID."""
        return {"id": user_id, "name": "Test"}

    def create_user(self, name):
        """Create a new user."""
        return {"id": 1, "name": name}
''')

            config = DebtConfig(debt_types=[DebtType.TEST.value])
            analyzer = TechnicalDebtAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should detect missing tests
            test_items = result.get_items_by_type(DebtType.TEST)
            assert len(test_items) >= 1

    def test_detect_documentation_debt(self):
        """Test detecting missing documentation debt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create file with undocumented public functions
            (tmpdir_path / "undocumented.py").write_text('''
"""Module."""

def public_function_one(a, b):
    return a + b

def public_function_two(x):
    return x * 2

def public_function_three():
    return 42

def _private_function():
    """This private function is documented."""
    return True
''')

            config = DebtConfig(debt_types=[DebtType.DOCUMENTATION.value])
            analyzer = TechnicalDebtAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should detect undocumented public functions
            doc_items = result.get_items_by_type(DebtType.DOCUMENTATION)
            assert len(doc_items) >= 1

    def test_detect_dependency_debt(self):
        """Test detecting dependency debt (requirements file exists)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a requirements.txt file
            (tmpdir_path / "requirements.txt").write_text('''
flask==2.0.0
requests==2.25.0
''')

            config = DebtConfig(debt_types=[DebtType.DEPENDENCIES.value])
            analyzer = TechnicalDebtAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should suggest security audit
            dep_items = result.get_items_by_type(DebtType.DEPENDENCIES)
            assert len(dep_items) >= 1

    def test_type_filtering(self):
        """Test filtering debt by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files that would generate various types of debt
            (tmpdir_path / "source.py").write_text('''
def undocumented():
    return 42
''')
            (tmpdir_path / "requirements.txt").write_text('flask==2.0.0\n')

            # Only analyze CODE debt
            config = DebtConfig(debt_types=[DebtType.CODE.value])
            analyzer = TechnicalDebtAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            # Should only have code debt items
            for item in result.debt_items:
                assert item.debt_type == DebtType.CODE.value

    def test_analyze_single_file(self):
        """Test analyzing a single file directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "single.py").write_text('''
def simple_function():
    """Return a value."""
    return 42
''')
            file_path = tmpdir_path / "single.py"

            analyzer = TechnicalDebtAnalyzer()
            result = analyzer.analyze_single_file(file_path)

            assert result is not None

    def test_prioritized_items_ordering(self):
        """Test that prioritized items are sorted by priority score."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create code that generates multiple debt items
            complex_code = '''
def function_one():
'''
            for i in range(25):
                complex_code += f'    if True: x = {i}\n'
            complex_code += '    return x\n\n'

            complex_code += '''
def function_two():
'''
            for i in range(15):
                complex_code += f'    if True: y = {i}\n'
            complex_code += '    return y\n'

            (tmpdir_path / "multi.py").write_text(complex_code)

            analyzer = TechnicalDebtAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            if len(result.prioritized_items) > 1:
                # Verify items are sorted by priority (highest first)
                for i in range(len(result.prioritized_items) - 1):
                    assert result.prioritized_items[i].priority_score >= result.prioritized_items[i + 1].priority_score

    def test_generate_text_report(self):
        """Test generating text report."""
        analyzer = TechnicalDebtAnalyzer()
        report = DebtReport(
            scan_path="/test/path",
            total_debt_hours=10.5,
        )

        text = analyzer.generate_report(report, "text")
        assert "TECHNICAL DEBT REPORT" in text
        assert "/test/path" in text

    def test_generate_json_report(self):
        """Test generating JSON report."""
        import json

        analyzer = TechnicalDebtAnalyzer()
        report = DebtReport(
            scan_path="/test/path",
            total_debt_hours=5.0,
        )

        json_str = analyzer.generate_report(report, "json")
        data = json.loads(json_str)
        assert data["scan_info"]["scan_path"] == "/test/path"
        assert data["summary"]["total_debt_hours"] == 5.0

    def test_generate_markdown_report(self):
        """Test generating Markdown report."""
        analyzer = TechnicalDebtAnalyzer()
        report = DebtReport(
            scan_path="/test/path",
            total_debt_hours=0,
        )

        md = analyzer.generate_report(report, "markdown")
        assert "# Technical Debt Report" in md
        assert "/test/path" in md

    def test_invalid_report_format(self):
        """Test that invalid format raises error."""
        analyzer = TechnicalDebtAnalyzer()
        report = DebtReport(scan_path="/test")

        with pytest.raises(ValueError):
            analyzer.generate_report(report, "invalid_format")


class TestDebtReport:
    """Tests for DebtReport model."""

    def test_add_debt_item(self):
        """Test adding a debt item to the report."""
        report = DebtReport(scan_path="/test")
        item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=10,
            description="Test debt item",
            severity=DebtSeverity.HIGH,
            effort_hours=5.0,
            business_impact=0.8,
            interest_rate=0.1,
            remediation_strategy="Fix it",
        )

        report.add_debt_item(item)

        assert report.total_debt_hours == 5.0
        assert report.debt_by_type.get("code", 0) == 5.0
        assert report.debt_by_severity.get("high", 0) == 1

    def test_has_debt(self):
        """Test has_debt property."""
        report = DebtReport(scan_path="/test")
        assert report.has_debt is False

        item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=1,
            description="Test",
            effort_hours=1.0,
        )
        report.add_debt_item(item)
        assert report.has_debt is True

    def test_critical_count(self):
        """Test critical_count property."""
        report = DebtReport(scan_path="/test")
        assert report.critical_count == 0

        item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=1,
            description="Critical debt",
            severity=DebtSeverity.CRITICAL,
            effort_hours=10.0,
        )
        report.add_debt_item(item)
        assert report.critical_count == 1

    def test_high_count(self):
        """Test high_count property."""
        report = DebtReport(scan_path="/test")
        assert report.high_count == 0

        item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=1,
            description="High severity debt",
            severity=DebtSeverity.HIGH,
            effort_hours=5.0,
        )
        report.add_debt_item(item)
        assert report.high_count == 1

    def test_get_items_by_type(self):
        """Test get_items_by_type method."""
        report = DebtReport(scan_path="/test")

        code_item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=1,
            description="Code debt",
            effort_hours=2.0,
        )
        test_item = DebtItem(
            debt_type=DebtType.TEST,
            file_path="/test/file.py",
            line_number=1,
            description="Test debt",
            effort_hours=3.0,
        )

        report.add_debt_item(code_item)
        report.add_debt_item(test_item)

        code_items = report.get_items_by_type(DebtType.CODE)
        assert len(code_items) == 1
        assert code_items[0].description == "Code debt"

    def test_get_items_by_severity(self):
        """Test get_items_by_severity method."""
        report = DebtReport(scan_path="/test")

        high_item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=1,
            description="High severity",
            severity=DebtSeverity.HIGH,
            effort_hours=5.0,
        )
        low_item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=2,
            description="Low severity",
            severity=DebtSeverity.LOW,
            effort_hours=1.0,
        )

        report.add_debt_item(high_item)
        report.add_debt_item(low_item)

        high_items = report.get_items_by_severity(DebtSeverity.HIGH)
        assert len(high_items) == 1
        assert high_items[0].description == "High severity"


class TestDebtItem:
    """Tests for DebtItem model."""

    def test_priority_score_calculation(self):
        """Test the priority score calculation."""
        item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test/file.py",
            line_number=10,
            description="Test item",
            severity=DebtSeverity.HIGH,
            effort_hours=2.0,
            business_impact=0.8,
            interest_rate=0.1,
        )

        # priority_score = (business_impact * interest_rate) / effort * severity_multiplier
        # = (0.8 * 0.1) / 2.0 * 3 (HIGH multiplier)
        # = 0.08 / 2.0 * 3 = 0.12
        expected_score = (0.8 * 0.1) / 2.0 * 3
        assert abs(item.priority_score - expected_score) < 0.001

    def test_location_property(self):
        """Test the location property."""
        item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/full/path/to/file.py",
            line_number=42,
            description="Test",
            effort_hours=1.0,
        )

        assert item.location == "file.py:42"

    def test_default_values(self):
        """Test default values for DebtItem."""
        item = DebtItem(
            debt_type=DebtType.CODE,
            file_path="/test.py",
            description="Test item",
        )

        assert item.line_number == 1
        assert item.severity == DebtSeverity.MEDIUM.value
        assert item.effort_hours == 0.0
        assert item.business_impact == 0.5
        assert item.interest_rate == 0.05
        assert item.confidence == 0.8


class TestROIAnalysis:
    """Tests for ROIAnalysis model."""

    def test_default_values(self):
        """Test default ROI analysis values."""
        roi = ROIAnalysis()
        assert roi.overall_roi == 0.0
        assert roi.roi_by_type == {}
        assert roi.payback_period_months == 0.0
        assert roi.total_effort_hours == 0.0
        assert roi.total_benefit == 0.0

    def test_custom_values(self):
        """Test ROI analysis with custom values."""
        roi = ROIAnalysis(
            overall_roi=2.5,
            roi_by_type={"code": 3.0, "test": 2.0},
            payback_period_months=6.0,
            total_effort_hours=100.0,
            total_benefit=250.0,
        )
        assert roi.overall_roi == 2.5
        assert roi.roi_by_type["code"] == 3.0
        assert roi.payback_period_months == 6.0


class TestTimeProjection:
    """Tests for TimeProjection model."""

    def test_default_values(self):
        """Test default time projection values."""
        proj = TimeProjection()
        assert proj.current_debt_hours == 0.0
        assert proj.projected_debt_hours == 0.0
        assert proj.growth_percentage == 0.0
        assert proj.time_horizon == TimeHorizon.QUARTER.value

    def test_custom_values(self):
        """Test time projection with custom values."""
        proj = TimeProjection(
            current_debt_hours=50.0,
            projected_debt_hours=60.0,
            growth_percentage=20.0,
            time_horizon=TimeHorizon.YEAR,
        )
        assert proj.current_debt_hours == 50.0
        assert proj.projected_debt_hours == 60.0
        assert proj.growth_percentage == 20.0


class TestDebtConfig:
    """Tests for DebtConfig model."""

    def test_default_config(self):
        """Test default configuration."""
        config = DebtConfig()
        assert config.time_horizon == TimeHorizon.QUARTER.value
        assert config.debt_types is None
        assert config.include_tests is False
        assert ".py" in config.include_extensions

    def test_get_enabled_debt_types_all(self):
        """Test getting all debt types when none specified."""
        config = DebtConfig()
        types = config.get_enabled_debt_types()
        assert len(types) == 5
        assert DebtType.CODE.value in types
        assert DebtType.DESIGN.value in types
        assert DebtType.TEST.value in types
        assert DebtType.DOCUMENTATION.value in types
        assert DebtType.DEPENDENCIES.value in types

    def test_get_enabled_debt_types_specific(self):
        """Test getting specific debt types."""
        config = DebtConfig(debt_types=["code", "test"])
        types = config.get_enabled_debt_types()
        assert types == ["code", "test"]


class TestEffortModels:
    """Tests for EffortModels model."""

    def test_default_values(self):
        """Test default effort model values."""
        models = EffortModels()
        assert models.complexity_reduction_factor == 0.5
        assert models.test_coverage_factor == 0.1
        assert models.documentation_factor == 0.25
        assert models.refactoring_log_factor == 2.0
        assert models.dependency_update_hours == 2.0

    def test_custom_values(self):
        """Test custom effort model values."""
        models = EffortModels(
            complexity_reduction_factor=1.0,
            test_coverage_factor=0.2,
        )
        assert models.complexity_reduction_factor == 1.0
        assert models.test_coverage_factor == 0.2


class TestInterestRates:
    """Tests for InterestRates model."""

    def test_default_values(self):
        """Test default interest rate values."""
        rates = InterestRates()
        assert rates.high_complexity == 0.10
        assert rates.no_tests == 0.15
        assert rates.poor_docs == 0.05
        assert rates.outdated_deps == 0.20
        assert rates.design_issues == 0.08

    def test_custom_values(self):
        """Test custom interest rate values."""
        rates = InterestRates(
            high_complexity=0.20,
            no_tests=0.30,
        )
        assert rates.high_complexity == 0.20
        assert rates.no_tests == 0.30
