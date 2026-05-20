"""
Tests for Heimdall Analysis Models

Unit tests for file analysis models and configuration.
"""

import pytest
from datetime import datetime
from pathlib import Path

from Asgard.Bragi.Quality.models.analysis_models import (
    AnalysisConfig,
    AnalysisResult,
    FileAnalysis,
    SeverityLevel,
    DEFAULT_EXTENSION_THRESHOLDS,
)


def create_file_analysis(**kwargs):
    """Helper to create FileAnalysis with defaults for required fields."""
    defaults = {
        "file_path": "/test/file.py",
        "line_count": 400,
        "threshold": 300,
        "lines_over": 100,
        "severity": SeverityLevel.SEVERE,
        "file_extension": ".py",
        "relative_path": "file.py",
    }
    defaults.update(kwargs)
    return FileAnalysis(**defaults)


class TestFileAnalysis:
    """Tests for FileAnalysis model."""

    def test_init_with_required_fields(self):
        """Test initializing FileAnalysis with required fields."""
        analysis = FileAnalysis(
            file_path="/path/to/file.py",
            line_count=500,
            threshold=300,
            lines_over=200,
            severity=SeverityLevel.CRITICAL,
            file_extension=".py",
            relative_path="file.py",
        )

        assert analysis.file_path == "/path/to/file.py"
        assert analysis.line_count == 500
        assert analysis.threshold == 300
        assert analysis.lines_over == 200
        assert analysis.severity == SeverityLevel.CRITICAL

    def test_init_with_optional_fields(self):
        """Test initializing FileAnalysis with optional fields."""
        analysis = FileAnalysis(
            file_path="/path/to/file.py",
            line_count=500,
            threshold=300,
            lines_over=200,
            severity=SeverityLevel.CRITICAL,
            file_extension=".py",
            relative_path="path/to/file.py",
        )

        assert analysis.file_extension == ".py"
        assert analysis.relative_path == "path/to/file.py"

    def test_calculate_severity_warning(self):
        """Test severity calculation for warning level."""
        severity = FileAnalysis.calculate_severity(25)
        assert severity == SeverityLevel.WARNING

    def test_calculate_severity_moderate(self):
        """Test severity calculation for moderate level."""
        severity = FileAnalysis.calculate_severity(75)
        assert severity == SeverityLevel.MODERATE

    def test_calculate_severity_severe(self):
        """Test severity calculation for severe level."""
        severity = FileAnalysis.calculate_severity(125)
        assert severity == SeverityLevel.SEVERE

    def test_calculate_severity_critical(self):
        """Test severity calculation for critical level."""
        severity = FileAnalysis.calculate_severity(250)
        assert severity == SeverityLevel.CRITICAL

    def test_calculate_severity_boundary_conditions(self):
        """Test severity calculation at boundary values."""
        assert FileAnalysis.calculate_severity(0) == SeverityLevel.WARNING
        assert FileAnalysis.calculate_severity(49) == SeverityLevel.WARNING
        assert FileAnalysis.calculate_severity(50) == SeverityLevel.WARNING
        assert FileAnalysis.calculate_severity(51) == SeverityLevel.MODERATE
        assert FileAnalysis.calculate_severity(100) == SeverityLevel.MODERATE
        assert FileAnalysis.calculate_severity(101) == SeverityLevel.SEVERE
        assert FileAnalysis.calculate_severity(200) == SeverityLevel.SEVERE
        assert FileAnalysis.calculate_severity(201) == SeverityLevel.CRITICAL


class TestAnalysisConfig:
    """Tests for AnalysisConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AnalysisConfig()

        assert config.scan_path == Path(".")
        assert config.threshold == 300
        assert ".css" in config.extension_thresholds
        assert len(config.exclude_patterns) > 0
        assert config.include_extensions is None
        assert config.output_format == "text"
        assert config.verbose is False

    def test_custom_config(self):
        """Test custom configuration values."""
        custom_thresholds = {".py": 200, ".ts": 400}
        custom_excludes = ["*.test.py", "*/vendor/*"]

        config = AnalysisConfig(
            scan_path=Path("/custom/path"),
            threshold=500,
            extension_thresholds=custom_thresholds,
            exclude_patterns=custom_excludes,
            include_extensions=[".py", ".ts"],
            output_format="json",
            verbose=True,
        )

        assert config.scan_path == Path("/custom/path")
        assert config.threshold == 500
        assert config.extension_thresholds == custom_thresholds
        assert config.exclude_patterns == custom_excludes
        assert config.include_extensions == [".py", ".ts"]
        assert config.output_format == "json"
        assert config.verbose is True

    def test_get_threshold_for_extension_custom(self):
        """Test getting custom threshold for specific extension."""
        config = AnalysisConfig(
            threshold=300,
            extension_thresholds={".css": 500, ".py": 200},
        )

        assert config.get_threshold_for_extension(".css") == 500
        assert config.get_threshold_for_extension(".py") == 200

    def test_get_threshold_for_extension_default(self):
        """Test getting default threshold for unknown extension."""
        config = AnalysisConfig(
            threshold=300,
            extension_thresholds={".css": 500},
        )

        assert config.get_threshold_for_extension(".unknown") == 300
        assert config.get_threshold_for_extension(".txt") == 300

    def test_get_threshold_for_extension_empty_string(self):
        """Test getting threshold when extension is empty string."""
        config = AnalysisConfig(threshold=300)
        assert config.get_threshold_for_extension("") == 300


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    def test_init_with_defaults(self):
        """Test initializing AnalysisResult with default values."""
        result = AnalysisResult(
            scan_path="/test/path",
            default_threshold=300,
        )

        assert result.scan_path == "/test/path"
        assert result.default_threshold == 300
        assert result.total_files_scanned == 0
        assert result.violations == []
        assert isinstance(result.scanned_at, datetime)
        assert result.scan_duration_seconds == 0.0
        assert result.extension_thresholds == {}
        assert result.skipped_patterns == []

    def test_init_with_custom_values(self):
        """Test initializing AnalysisResult with custom values."""
        custom_thresholds = {".py": 200}
        custom_patterns = ["*.test.py"]
        custom_time = datetime.now()

        result = AnalysisResult(
            scan_path="/test/path",
            default_threshold=300,
            extension_thresholds=custom_thresholds,
            scanned_at=custom_time,
            skipped_patterns=custom_patterns,
        )

        assert result.extension_thresholds == custom_thresholds
        assert result.scanned_at == custom_time
        assert result.skipped_patterns == custom_patterns

    def test_increment_files_scanned(self):
        """Test incrementing files scanned counter."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        assert result.total_files_scanned == 0

        result.increment_files_scanned()
        assert result.total_files_scanned == 1

        result.increment_files_scanned()
        result.increment_files_scanned()
        assert result.total_files_scanned == 3

    def test_add_violation(self):
        """Test adding violations."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        assert len(result.violations) == 0

        violation1 = create_file_analysis(file_path="/test/file1.py", relative_path="file1.py")
        result.add_violation(violation1)

        assert len(result.violations) == 1
        assert result.violations[0] == violation1

        violation2 = create_file_analysis(
            file_path="/test/file2.py",
            line_count=500,
            lines_over=200,
            severity=SeverityLevel.CRITICAL,
            relative_path="file2.py",
        )
        result.add_violation(violation2)

        assert len(result.violations) == 2

    def test_files_exceeding_threshold(self):
        """Test files_exceeding_threshold property."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        assert result.files_exceeding_threshold == 0

        result.add_violation(create_file_analysis(file_path="/test/file1.py", relative_path="file1.py"))
        assert result.files_exceeding_threshold == 1

        result.add_violation(
            create_file_analysis(
                file_path="/test/file2.py",
                line_count=500,
                lines_over=200,
                severity=SeverityLevel.CRITICAL,
                relative_path="file2.py",
            )
        )
        assert result.files_exceeding_threshold == 2

    def test_has_violations_false(self):
        """Test has_violations property when no violations."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        assert result.has_violations is False

    def test_has_violations_true(self):
        """Test has_violations property when violations exist."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        result.add_violation(create_file_analysis())
        assert result.has_violations is True

    def test_compliance_rate_perfect(self):
        """Test compliance rate when all files comply."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        result.increment_files_scanned()
        result.increment_files_scanned()
        result.increment_files_scanned()

        assert result.compliance_rate == 100.0

    def test_compliance_rate_partial(self):
        """Test compliance rate with some violations."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)

        # Increment for compliant files
        for _ in range(6):
            result.increment_files_scanned()

        # Add violations (this increments files_exceeding_threshold but not total_files_scanned)
        for i in range(2):
            result.increment_files_scanned()  # Must manually increment for violation files
            result.add_violation(create_file_analysis(file_path=f"/test/file{i}.py", relative_path=f"file{i}.py"))

        # Total 8 files: 6 compliant + 2 violations = 75% compliance
        assert result.total_files_scanned == 8
        assert result.files_exceeding_threshold == 2
        assert result.compliance_rate == 75.0

    def test_compliance_rate_no_files(self):
        """Test compliance rate when no files scanned."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        assert result.compliance_rate == 100.0

    def test_longest_file_none(self):
        """Test longest_file property when no violations."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        assert result.longest_file is None

    def test_longest_file_single_violation(self):
        """Test longest_file property with single violation."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        violation = create_file_analysis()
        result.add_violation(violation)

        assert result.longest_file == violation

    def test_longest_file_multiple_violations(self):
        """Test longest_file property with multiple violations."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)

        violation1 = create_file_analysis(file_path="/test/file1.py", line_count=400, relative_path="file1.py")
        violation2 = create_file_analysis(
            file_path="/test/file2.py",
            line_count=600,
            lines_over=300,
            severity=SeverityLevel.CRITICAL,
            relative_path="file2.py",
        )
        violation3 = create_file_analysis(
            file_path="/test/file3.py",
            line_count=350,
            lines_over=50,
            severity=SeverityLevel.MODERATE,
            relative_path="file3.py",
        )

        result.add_violation(violation1)
        result.add_violation(violation2)
        result.add_violation(violation3)

        assert result.longest_file == violation2
        assert result.longest_file.line_count == 600

    def test_get_violations_by_severity(self):
        """Test get_violations_by_severity method."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)

        critical = create_file_analysis(
            file_path="/test/critical.py",
            line_count=600,
            lines_over=300,
            severity=SeverityLevel.CRITICAL,
            relative_path="critical.py",
        )
        severe = create_file_analysis(
            file_path="/test/severe.py",
            line_count=450,
            lines_over=150,
            severity=SeverityLevel.SEVERE,
            relative_path="severe.py",
        )
        moderate = create_file_analysis(
            file_path="/test/moderate.py",
            line_count=375,
            lines_over=75,
            severity=SeverityLevel.MODERATE,
            relative_path="moderate.py",
        )
        warning = create_file_analysis(
            file_path="/test/warning.py",
            line_count=325,
            lines_over=25,
            severity=SeverityLevel.WARNING,
            relative_path="warning.py",
        )

        result.add_violation(critical)
        result.add_violation(severe)
        result.add_violation(moderate)
        result.add_violation(warning)

        by_severity = result.get_violations_by_severity()

        assert len(by_severity[SeverityLevel.CRITICAL.value]) == 1
        assert len(by_severity[SeverityLevel.SEVERE.value]) == 1
        assert len(by_severity[SeverityLevel.MODERATE.value]) == 1
        assert len(by_severity[SeverityLevel.WARNING.value]) == 1

        assert by_severity[SeverityLevel.CRITICAL.value][0] == critical
        assert by_severity[SeverityLevel.SEVERE.value][0] == severe
        assert by_severity[SeverityLevel.MODERATE.value][0] == moderate
        assert by_severity[SeverityLevel.WARNING.value][0] == warning

    def test_get_violations_by_severity_empty(self):
        """Test get_violations_by_severity with no violations."""
        result = AnalysisResult(scan_path="/test/path", default_threshold=300)
        by_severity = result.get_violations_by_severity()

        assert len(by_severity[SeverityLevel.CRITICAL.value]) == 0
        assert len(by_severity[SeverityLevel.SEVERE.value]) == 0
        assert len(by_severity[SeverityLevel.MODERATE.value]) == 0
        assert len(by_severity[SeverityLevel.WARNING.value]) == 0


class TestConstants:
    """Tests for module constants."""

    def test_default_extension_thresholds(self):
        """Test DEFAULT_EXTENSION_THRESHOLDS constant."""
        assert isinstance(DEFAULT_EXTENSION_THRESHOLDS, dict)
        assert ".css" in DEFAULT_EXTENSION_THRESHOLDS
        assert ".scss" in DEFAULT_EXTENSION_THRESHOLDS
        assert DEFAULT_EXTENSION_THRESHOLDS[".css"] == 500
        assert DEFAULT_EXTENSION_THRESHOLDS[".scss"] == 500

    def test_default_exclude_patterns(self):
        """Test default exclude patterns in config."""
        config = AnalysisConfig()
        assert isinstance(config.exclude_patterns, list)
        assert len(config.exclude_patterns) > 0
        assert any("node_modules" in pattern for pattern in config.exclude_patterns)
        assert any("__pycache__" in pattern for pattern in config.exclude_patterns)


class TestSeverityLevel:
    """Tests for SeverityLevel enum."""

    def test_severity_levels_exist(self):
        """Test that all severity levels are defined."""
        assert hasattr(SeverityLevel, "WARNING")
        assert hasattr(SeverityLevel, "MODERATE")
        assert hasattr(SeverityLevel, "SEVERE")
        assert hasattr(SeverityLevel, "CRITICAL")

    def test_severity_values(self):
        """Test severity level string values."""
        assert SeverityLevel.WARNING.value == "warning"
        assert SeverityLevel.MODERATE.value == "moderate"
        assert SeverityLevel.SEVERE.value == "severe"
        assert SeverityLevel.CRITICAL.value == "critical"
