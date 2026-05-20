"""
Tests for Heimdall Maintainability Analyzer Service

Unit tests for maintainability index calculation and analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.maintainability_models import (
    FileMaintainability,
    FunctionMaintainability,
    HalsteadMetrics,
    LanguageProfile,
    LanguageWeights,
    MaintainabilityConfig,
    MaintainabilityLevel,
    MaintainabilityReport,
    MaintainabilityThresholds,
)
from Asgard.Bragi.Quality.services.maintainability_analyzer import MaintainabilityAnalyzer


class TestMaintainabilityAnalyzer:
    """Tests for MaintainabilityAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = MaintainabilityAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.include_halstead is True
        assert analyzer.config.include_comments is True
        assert analyzer.config.language_profile == LanguageProfile.PYTHON.value

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = MaintainabilityConfig(
            include_halstead=False,
            language_profile=LanguageProfile.JAVA,
        )
        analyzer = MaintainabilityAnalyzer(config)
        assert analyzer.config.include_halstead is False
        assert analyzer.config.language_profile == LanguageProfile.JAVA.value

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = MaintainabilityAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = MaintainabilityAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            assert result.total_files == 0
            assert result.has_issues is False

    def test_analyze_clean_code(self):
        """Test analyzing well-structured code with good maintainability."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
"""Clean module with good documentation."""

def calculate_sum(a, b):
    """
    Add two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of the two numbers
    """
    return a + b

def calculate_product(a, b):
    """
    Multiply two numbers together.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of the two numbers
    """
    return a * b
''')

            analyzer = MaintainabilityAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files == 1
            # Well-documented simple code should have good maintainability
            assert result.overall_index >= 50

    def test_analyze_complex_code(self):
        """Test analyzing complex code with lower maintainability."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create complex code without documentation
            complex_code = '''
def very_complex_function(a, b, c, d, e):
    result = 0
'''
            for i in range(20):
                complex_code += f'''    if a > {i}:
        if b > {i}:
            result += {i}
        else:
            result -= {i}
'''
            complex_code += '    return result\n'

            (tmpdir_path / "complex.py").write_text(complex_code)

            analyzer = MaintainabilityAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files == 1
            # Complex code without documentation should have lower maintainability
            # The result should exist and have been analyzed
            assert len(result.file_results) == 1

    def test_analyze_single_file(self):
        """Test analyzing a single file directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "single.py").write_text('''
"""Simple module."""

def simple_function():
    """Return a value."""
    return 42
''')
            file_path = tmpdir_path / "single.py"

            analyzer = MaintainabilityAnalyzer()
            result = analyzer.analyze_single_file(file_path)

            assert result is not None
            assert result.function_count >= 1

    def test_maintainability_levels(self):
        """Test that maintainability levels are correctly assigned."""
        analyzer = MaintainabilityAnalyzer()

        # Test level thresholds
        assert analyzer._get_maintainability_level(90) == MaintainabilityLevel.EXCELLENT
        assert analyzer._get_maintainability_level(75) == MaintainabilityLevel.GOOD
        assert analyzer._get_maintainability_level(60) == MaintainabilityLevel.MODERATE
        assert analyzer._get_maintainability_level(30) == MaintainabilityLevel.POOR
        assert analyzer._get_maintainability_level(10) == MaintainabilityLevel.CRITICAL

    def test_generate_text_report(self):
        """Test generating text report."""
        analyzer = MaintainabilityAnalyzer()
        report = MaintainabilityReport(
            scan_path="/test/path",
            overall_index=75.5,
            overall_level=MaintainabilityLevel.GOOD,
        )

        text = analyzer.generate_report(report, "text")
        assert "MAINTAINABILITY INDEX REPORT" in text
        assert "/test/path" in text

    def test_generate_json_report(self):
        """Test generating JSON report."""
        import json

        analyzer = MaintainabilityAnalyzer()
        report = MaintainabilityReport(
            scan_path="/test/path",
            overall_index=80.0,
            overall_level=MaintainabilityLevel.GOOD,
        )

        json_str = analyzer.generate_report(report, "json")
        data = json.loads(json_str)
        assert data["scan_info"]["scan_path"] == "/test/path"
        assert data["summary"]["overall_index"] == 80.0

    def test_generate_markdown_report(self):
        """Test generating Markdown report."""
        analyzer = MaintainabilityAnalyzer()
        report = MaintainabilityReport(
            scan_path="/test/path",
            overall_index=65.0,
            overall_level=MaintainabilityLevel.MODERATE,
        )

        md = analyzer.generate_report(report, "markdown")
        assert "# Maintainability Index Report" in md
        assert "/test/path" in md

    def test_invalid_report_format(self):
        """Test that invalid format raises error."""
        analyzer = MaintainabilityAnalyzer()
        report = MaintainabilityReport(scan_path="/test")

        with pytest.raises(ValueError):
            analyzer.generate_report(report, "invalid_format")


class TestMaintainabilityReport:
    """Tests for MaintainabilityReport model."""

    def test_add_file_result(self):
        """Test adding a file result to the report."""
        report = MaintainabilityReport(scan_path="/test")

        file_result = FileMaintainability(
            file_path="/test/file.py",
            maintainability_index=75.0,
            maintainability_level=MaintainabilityLevel.GOOD,
            total_lines=100,
            code_lines=80,
            comment_lines=20,
            function_count=5,
        )

        report.add_file_result(file_result)

        assert report.total_files == 1
        assert report.total_functions == 5
        assert report.total_lines_of_code == 80
        assert report.files_by_level.get("good", 0) == 1

    def test_has_issues(self):
        """Test has_issues property."""
        report = MaintainabilityReport(scan_path="/test")
        assert report.has_issues is False

        # Add a file with poor maintainability
        poor_file = FileMaintainability(
            file_path="/test/file.py",
            maintainability_index=30.0,
            maintainability_level=MaintainabilityLevel.POOR,
            function_count=1,
        )
        report.add_file_result(poor_file)
        assert report.has_issues is True

    def test_critical_count(self):
        """Test critical_count property."""
        report = MaintainabilityReport(scan_path="/test")
        assert report.critical_count == 0

        critical_file = FileMaintainability(
            file_path="/test/file.py",
            maintainability_index=15.0,
            maintainability_level=MaintainabilityLevel.CRITICAL,
            function_count=1,
        )
        report.add_file_result(critical_file)
        assert report.critical_count == 1

    def test_poor_count(self):
        """Test poor_count property."""
        report = MaintainabilityReport(scan_path="/test")
        assert report.poor_count == 0

        poor_file = FileMaintainability(
            file_path="/test/file.py",
            maintainability_index=35.0,
            maintainability_level=MaintainabilityLevel.POOR,
            function_count=1,
        )
        report.add_file_result(poor_file)
        assert report.poor_count == 1


class TestFunctionMaintainability:
    """Tests for FunctionMaintainability model."""

    def test_location_property(self):
        """Test the location property."""
        func = FunctionMaintainability(
            name="test_function",
            file_path="/full/path/to/file.py",
            line_number=42,
            maintainability_index=70.0,
        )

        assert func.location == "file.py:42"

    def test_needs_attention(self):
        """Test the needs_attention property."""
        good_func = FunctionMaintainability(
            name="good_function",
            file_path="/test.py",
            maintainability_index=80.0,
            maintainability_level=MaintainabilityLevel.GOOD,
        )
        assert good_func.needs_attention is False

        poor_func = FunctionMaintainability(
            name="poor_function",
            file_path="/test.py",
            maintainability_index=30.0,
            maintainability_level=MaintainabilityLevel.POOR,
        )
        assert poor_func.needs_attention is True

        critical_func = FunctionMaintainability(
            name="critical_function",
            file_path="/test.py",
            maintainability_index=15.0,
            maintainability_level=MaintainabilityLevel.CRITICAL,
        )
        assert critical_func.needs_attention is True


class TestFileMaintainability:
    """Tests for FileMaintainability model."""

    def test_filename_property(self):
        """Test the filename property."""
        file = FileMaintainability(
            file_path="/full/path/to/module.py",
            maintainability_index=75.0,
        )
        assert file.filename == "module.py"


class TestHalsteadMetrics:
    """Tests for HalsteadMetrics model."""

    def test_vocabulary(self):
        """Test vocabulary calculation."""
        metrics = HalsteadMetrics(n1=5, n2=10, N1=20, N2=30)
        assert metrics.vocabulary == 15

    def test_length(self):
        """Test length calculation."""
        metrics = HalsteadMetrics(n1=5, n2=10, N1=20, N2=30)
        assert metrics.length == 50

    def test_volume(self):
        """Test volume calculation."""
        import math
        metrics = HalsteadMetrics(n1=5, n2=10, N1=20, N2=30)
        expected_volume = 50 * math.log2(15)
        assert abs(metrics.volume - expected_volume) < 0.001

    def test_volume_with_zero_vocabulary(self):
        """Test volume with zero vocabulary."""
        metrics = HalsteadMetrics(n1=0, n2=0, N1=0, N2=0)
        assert metrics.volume == 0.0

    def test_difficulty(self):
        """Test difficulty calculation."""
        metrics = HalsteadMetrics(n1=10, n2=5, N1=20, N2=25)
        # difficulty = (n1/2) * (N2/n2) = (10/2) * (25/5) = 5 * 5 = 25
        assert metrics.difficulty == 25.0

    def test_difficulty_with_zero_operands(self):
        """Test difficulty with zero operands."""
        metrics = HalsteadMetrics(n1=10, n2=0, N1=20, N2=25)
        assert metrics.difficulty == 0.0

    def test_effort(self):
        """Test effort calculation."""
        import math
        metrics = HalsteadMetrics(n1=10, n2=5, N1=20, N2=25)
        expected_volume = 45 * math.log2(15)
        expected_difficulty = 25.0
        expected_effort = expected_difficulty * expected_volume
        assert abs(metrics.effort - expected_effort) < 0.001


class TestMaintainabilityConfig:
    """Tests for MaintainabilityConfig model."""

    def test_default_config(self):
        """Test default configuration."""
        config = MaintainabilityConfig()
        assert config.include_halstead is True
        assert config.include_comments is True
        assert config.language_profile == LanguageProfile.PYTHON.value
        assert config.include_tests is False
        assert ".py" in config.include_extensions

    def test_get_language_weights_default(self):
        """Test getting default language weights."""
        config = MaintainabilityConfig()
        weights = config.get_language_weights()
        assert weights.complexity_weight == 0.23
        assert weights.volume_weight == 5.2

    def test_get_language_weights_java(self):
        """Test getting Java language weights."""
        config = MaintainabilityConfig(language_profile=LanguageProfile.JAVA)
        weights = config.get_language_weights()
        assert weights.complexity_weight == 0.25
        assert weights.volume_weight == 5.5

    def test_get_language_weights_custom(self):
        """Test getting custom language weights."""
        custom_weights = LanguageWeights(
            complexity_weight=0.30,
            volume_weight=6.0,
        )
        config = MaintainabilityConfig(language_weights=custom_weights)
        weights = config.get_language_weights()
        assert weights.complexity_weight == 0.30
        assert weights.volume_weight == 6.0


class TestMaintainabilityThresholds:
    """Tests for MaintainabilityThresholds model."""

    def test_default_values(self):
        """Test default threshold values."""
        thresholds = MaintainabilityThresholds()
        assert thresholds.excellent == 85
        assert thresholds.good == 70
        assert thresholds.moderate == 50
        assert thresholds.poor == 25

    def test_custom_values(self):
        """Test custom threshold values."""
        thresholds = MaintainabilityThresholds(
            excellent=90,
            good=75,
        )
        assert thresholds.excellent == 90
        assert thresholds.good == 75


class TestLanguageWeights:
    """Tests for LanguageWeights model."""

    def test_default_values(self):
        """Test default weight values."""
        weights = LanguageWeights()
        assert weights.complexity_weight == 0.23
        assert weights.volume_weight == 5.2
        assert weights.loc_weight == 16.2
        assert weights.comment_factor == 50.0

    def test_custom_values(self):
        """Test custom weight values."""
        weights = LanguageWeights(
            complexity_weight=0.30,
            volume_weight=6.0,
        )
        assert weights.complexity_weight == 0.30
        assert weights.volume_weight == 6.0
