"""
Tests for Heimdall File Length Analyzer Service

Unit tests for the core file analysis service.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.analysis_models import (
    AnalysisConfig,
    SeverityLevel,
)
from Asgard.Bragi.Quality.services.file_length_analyzer import FileAnalyzer


class TestFileAnalyzer:
    """Tests for FileAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = FileAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.threshold == 300

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = AnalysisConfig(threshold=500)
        analyzer = FileAnalyzer(config)
        assert analyzer.config.threshold == 500

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = FileAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = FileAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            assert result.total_files_scanned == 0
            assert result.files_exceeding_threshold == 0
            assert result.has_violations is False
            assert result.compliance_rate == 100.0

    def test_analyze_compliant_files(self):
        """Test analyzing files that are within threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a small file (under threshold)
            content = "line\n" * 100  # 100 lines
            (tmpdir_path / "small.py").write_text(content)

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.files_exceeding_threshold == 0
            assert result.has_violations is False
            assert result.compliance_rate == 100.0

    def test_analyze_files_exceeding_threshold(self):
        """Test analyzing files that exceed the threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a large file (over threshold)
            content = "line\n" * 400  # 400 lines, threshold is 300
            (tmpdir_path / "large.py").write_text(content)

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.files_exceeding_threshold == 1
            assert result.has_violations is True
            assert len(result.violations) == 1

            violation = result.violations[0]
            assert violation.line_count == 400
            assert violation.lines_over == 100
            assert violation.severity == SeverityLevel.MODERATE.value

    def test_analyze_mixed_files(self):
        """Test analyzing a mix of compliant and non-compliant files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files of various sizes
            (tmpdir_path / "small.py").write_text("line\n" * 100)     # 100 lines
            (tmpdir_path / "medium.py").write_text("line\n" * 250)    # 250 lines
            (tmpdir_path / "large.py").write_text("line\n" * 400)     # 400 lines
            (tmpdir_path / "huge.py").write_text("line\n" * 600)      # 600 lines

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 4
            assert result.files_exceeding_threshold == 2  # large.py and huge.py
            assert result.compliance_rate == 50.0

    def test_analyze_with_extension_thresholds(self):
        """Test analyzing with per-extension thresholds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files
            (tmpdir_path / "app.py").write_text("line\n" * 350)      # 350 lines
            (tmpdir_path / "styles.css").write_text("line\n" * 450)  # 450 lines

            config = AnalysisConfig(
                threshold=300,  # Default for .py
                extension_thresholds={".css": 500}  # Higher for .css
            )
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 2
            # Only app.py should exceed (350 > 300)
            # styles.css is under its threshold (450 < 500)
            assert result.files_exceeding_threshold == 1
            assert result.violations[0].file_extension == ".py"

    def test_analyze_sorts_by_line_count(self):
        """Test that violations are sorted by line count (worst first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files of various sizes (all over threshold)
            (tmpdir_path / "a.py").write_text("line\n" * 350)
            (tmpdir_path / "b.py").write_text("line\n" * 500)
            (tmpdir_path / "c.py").write_text("line\n" * 400)

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert len(result.violations) == 3
            # Should be sorted worst first
            assert result.violations[0].line_count == 500
            assert result.violations[1].line_count == 400
            assert result.violations[2].line_count == 350

    def test_get_scan_preview(self):
        """Test getting a preview of files to be scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create some files
            (tmpdir_path / "app.py").write_text("code")
            (tmpdir_path / "utils.ts").write_text("code")
            (tmpdir_path / "readme.txt").write_text("text")  # Not a code file

            analyzer = FileAnalyzer()
            files = analyzer.get_scan_preview(tmpdir_path)

            # Should only include code files
            assert len(files) == 2
            extensions = {f.suffix for f in files}
            assert extensions == {".py", ".ts"}

    def test_get_scan_preview_nonexistent_path(self):
        """Test getting scan preview for nonexistent path."""
        analyzer = FileAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.get_scan_preview(Path("/nonexistent/path"))

    def test_analyze_tracks_scan_duration(self):
        """Test that analysis tracks scan duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "app.py").write_text("code")

            analyzer = FileAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.scan_duration_seconds >= 0

    def test_analyze_uses_config_scan_path(self):
        """Test that analyze uses config scan_path when not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "app.py").write_text("code")

            config = AnalysisConfig(scan_path=tmpdir_path)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze()  # No path provided

            assert result.total_files_scanned == 1
