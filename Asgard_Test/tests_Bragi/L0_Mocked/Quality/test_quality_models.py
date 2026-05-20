"""
Tests for Heimdall Quality Models

Unit tests for the Pydantic models used in code quality analysis.
"""

import pytest
from datetime import datetime

from Asgard.Bragi.Quality.models.analysis_models import (
    AnalysisConfig,
    AnalysisResult,
    FileAnalysis,
    SeverityLevel,
    DEFAULT_EXTENSION_THRESHOLDS,
)


class TestSeverityLevel:
    """Tests for SeverityLevel enum."""

    def test_severity_values(self):
        """Test that severity levels have correct string values."""
        assert SeverityLevel.WARNING.value == "warning"
        assert SeverityLevel.MODERATE.value == "moderate"
        assert SeverityLevel.SEVERE.value == "severe"
        assert SeverityLevel.CRITICAL.value == "critical"


class TestFileAnalysis:
    """Tests for FileAnalysis model."""

    def test_calculate_severity_warning(self):
        """Test severity calculation for warning level (1-50 lines over)."""
        assert FileAnalysis.calculate_severity(1) == SeverityLevel.WARNING
        assert FileAnalysis.calculate_severity(25) == SeverityLevel.WARNING
        assert FileAnalysis.calculate_severity(50) == SeverityLevel.WARNING

    def test_calculate_severity_moderate(self):
        """Test severity calculation for moderate level (51-100 lines over)."""
        assert FileAnalysis.calculate_severity(51) == SeverityLevel.MODERATE
        assert FileAnalysis.calculate_severity(75) == SeverityLevel.MODERATE
        assert FileAnalysis.calculate_severity(100) == SeverityLevel.MODERATE

    def test_calculate_severity_severe(self):
        """Test severity calculation for severe level (101-200 lines over)."""
        assert FileAnalysis.calculate_severity(101) == SeverityLevel.SEVERE
        assert FileAnalysis.calculate_severity(150) == SeverityLevel.SEVERE
        assert FileAnalysis.calculate_severity(200) == SeverityLevel.SEVERE

    def test_calculate_severity_critical(self):
        """Test severity calculation for critical level (200+ lines over)."""
        assert FileAnalysis.calculate_severity(201) == SeverityLevel.CRITICAL
        assert FileAnalysis.calculate_severity(500) == SeverityLevel.CRITICAL
        assert FileAnalysis.calculate_severity(1000) == SeverityLevel.CRITICAL

    def test_file_analysis_creation(self):
        """Test creating a FileAnalysis instance."""
        analysis = FileAnalysis(
            file_path="/path/to/file.py",
            line_count=450,
            threshold=300,
            lines_over=150,
            severity=SeverityLevel.SEVERE,
            file_extension=".py",
            relative_path="file.py",
        )

        assert analysis.file_path == "/path/to/file.py"
        assert analysis.line_count == 450
        assert analysis.threshold == 300
        assert analysis.lines_over == 150
        assert analysis.severity == SeverityLevel.SEVERE.value
        assert analysis.file_extension == ".py"
        assert analysis.relative_path == "file.py"

    def test_format_display(self):
        """Test the format_display method."""
        analysis = FileAnalysis(
            file_path="/path/to/file.py",
            line_count=450,
            threshold=300,
            lines_over=150,
            severity=SeverityLevel.SEVERE,
            file_extension=".py",
            relative_path="file.py",
        )

        display = analysis.format_display()
        assert "file.py" in display
        assert "450" in display
        assert "+150" in display


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    def test_analysis_result_defaults(self):
        """Test AnalysisResult default values."""
        result = AnalysisResult(
            default_threshold=300,
            scan_path="/test/path",
        )

        assert result.total_files_scanned == 0
        assert result.files_exceeding_threshold == 0
        assert result.violations == []
        assert result.longest_file is None
        assert result.has_violations is False
        assert result.compliance_rate == 100.0

    def test_add_violation(self):
        """Test adding violations to the result."""
        result = AnalysisResult(
            default_threshold=300,
            scan_path="/test/path",
        )

        violation = FileAnalysis(
            file_path="/path/to/file.py",
            line_count=450,
            threshold=300,
            lines_over=150,
            severity=SeverityLevel.SEVERE,
            file_extension=".py",
            relative_path="file.py",
        )

        result.add_violation(violation)

        assert result.files_exceeding_threshold == 1
        assert len(result.violations) == 1
        assert result.longest_file == violation
        assert result.has_violations is True

    def test_increment_files_scanned(self):
        """Test incrementing the files scanned counter."""
        result = AnalysisResult(
            default_threshold=300,
            scan_path="/test/path",
        )

        result.increment_files_scanned()
        result.increment_files_scanned()
        result.increment_files_scanned()

        assert result.total_files_scanned == 3

    def test_compliance_rate_calculation(self):
        """Test compliance rate calculation."""
        result = AnalysisResult(
            default_threshold=300,
            scan_path="/test/path",
        )

        # Add 10 files scanned
        for _ in range(10):
            result.increment_files_scanned()

        # Add 2 violations
        for _ in range(2):
            violation = FileAnalysis(
                file_path="/path/to/file.py",
                line_count=450,
                threshold=300,
                lines_over=150,
                severity=SeverityLevel.SEVERE,
                file_extension=".py",
                relative_path="file.py",
            )
            result.add_violation(violation)

        # 8 out of 10 files are compliant = 80%
        assert result.compliance_rate == 80.0

    def test_get_violations_by_severity(self):
        """Test grouping violations by severity."""
        result = AnalysisResult(
            default_threshold=300,
            scan_path="/test/path",
        )

        # Add violations of different severities
        severities = [
            (SeverityLevel.WARNING, 25),
            (SeverityLevel.MODERATE, 75),
            (SeverityLevel.SEVERE, 150),
            (SeverityLevel.CRITICAL, 300),
        ]

        for severity, lines_over in severities:
            violation = FileAnalysis(
                file_path=f"/path/{severity.value}.py",
                line_count=300 + lines_over,
                threshold=300,
                lines_over=lines_over,
                severity=severity,
                file_extension=".py",
                relative_path=f"{severity.value}.py",
            )
            result.add_violation(violation)

        by_severity = result.get_violations_by_severity()

        assert len(by_severity["warning"]) == 1
        assert len(by_severity["moderate"]) == 1
        assert len(by_severity["severe"]) == 1
        assert len(by_severity["critical"]) == 1


class TestAnalysisConfig:
    """Tests for AnalysisConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AnalysisConfig()

        assert config.threshold == 300
        assert config.output_format == "text"
        assert config.include_extensions is None
        assert config.verbose is False
        assert "__pycache__" in config.exclude_patterns
        assert "node_modules" in config.exclude_patterns

    def test_get_threshold_for_extension(self):
        """Test getting threshold for specific extensions."""
        config = AnalysisConfig()

        # CSS should have higher threshold
        assert config.get_threshold_for_extension(".css") == 500
        assert config.get_threshold_for_extension(".scss") == 500

        # JSON/YAML should have higher threshold
        assert config.get_threshold_for_extension(".json") == 500
        assert config.get_threshold_for_extension(".yaml") == 500

        # Other extensions should use default
        assert config.get_threshold_for_extension(".py") == 300
        assert config.get_threshold_for_extension(".ts") == 300

    def test_custom_threshold(self):
        """Test setting a custom default threshold."""
        config = AnalysisConfig(threshold=500)

        assert config.threshold == 500
        assert config.get_threshold_for_extension(".py") == 500

    def test_custom_extension_thresholds(self):
        """Test setting custom extension thresholds."""
        config = AnalysisConfig(
            threshold=300,
            extension_thresholds={".py": 200, ".ts": 400}
        )

        assert config.get_threshold_for_extension(".py") == 200
        assert config.get_threshold_for_extension(".ts") == 400
        assert config.get_threshold_for_extension(".js") == 300  # Default


class TestDefaultExtensionThresholds:
    """Tests for DEFAULT_EXTENSION_THRESHOLDS constant."""

    def test_style_files_have_higher_threshold(self):
        """Test that style files have 500-line threshold."""
        assert DEFAULT_EXTENSION_THRESHOLDS.get(".css") == 500
        assert DEFAULT_EXTENSION_THRESHOLDS.get(".scss") == 500
        assert DEFAULT_EXTENSION_THRESHOLDS.get(".sass") == 500
        assert DEFAULT_EXTENSION_THRESHOLDS.get(".less") == 500

    def test_config_files_have_higher_threshold(self):
        """Test that config files have 500-line threshold."""
        assert DEFAULT_EXTENSION_THRESHOLDS.get(".json") == 500
        assert DEFAULT_EXTENSION_THRESHOLDS.get(".yaml") == 500
        assert DEFAULT_EXTENSION_THRESHOLDS.get(".yml") == 500
