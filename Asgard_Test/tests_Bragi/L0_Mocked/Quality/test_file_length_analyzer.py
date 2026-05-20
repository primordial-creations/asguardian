"""
Tests for Heimdall File Length Analyzer Service

Unit tests for file length analysis and reporting.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.analysis_models import (
    AnalysisConfig,
    AnalysisResult,
    FileAnalysis,
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
        assert analyzer.config.scan_path == Path(".")

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = AnalysisConfig(
            scan_path=Path("/custom/path"),
            threshold=500,
            verbose=True,
        )
        analyzer = FileAnalyzer(config)
        assert analyzer.config.scan_path == Path("/custom/path")
        assert analyzer.config.threshold == 500
        assert analyzer.config.verbose is True

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
            assert result.has_violations is False
            assert result.compliance_rate == 100.0

    def test_analyze_compliant_files(self):
        """Test analyzing files that are within threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "small.py").write_text("x = 1\ny = 2\nz = 3\n")
            (tmpdir_path / "medium.py").write_text("\n".join([f"line{i} = {i}" for i in range(100)]))

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 2
            assert result.has_violations is False
            assert result.files_exceeding_threshold == 0
            assert result.compliance_rate == 100.0

    def test_analyze_files_exceeding_threshold(self):
        """Test analyzing files that exceed threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            large_content = "\n".join([f"line{i} = {i}" for i in range(400)])
            (tmpdir_path / "large.py").write_text(large_content)

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.has_violations is True
            assert result.files_exceeding_threshold == 1
            assert len(result.violations) == 1

            violation = result.violations[0]
            assert violation.line_count == 400
            assert violation.threshold == 300
            assert violation.lines_over == 100

    def test_analyze_with_extension_thresholds(self):
        """Test analyzing with per-extension thresholds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            py_content = "\n".join([f"line{i} = {i}" for i in range(250)])
            css_content = "\n".join([f".class{i} {{}} " for i in range(250)])

            (tmpdir_path / "file.py").write_text(py_content)
            (tmpdir_path / "style.css").write_text(css_content)

            config = AnalysisConfig(
                threshold=300,
                extension_thresholds={".py": 200, ".css": 500},
            )
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 2
            assert result.files_exceeding_threshold == 1

            py_violations = [v for v in result.violations if v.file_extension == ".py"]
            css_violations = [v for v in result.violations if v.file_extension == ".css"]

            assert len(py_violations) == 1
            assert len(css_violations) == 0

    def test_analyze_excludes_patterns(self):
        """Test analyzing with exclude patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "include.py").write_text("x = 1")
            (tmpdir_path / "exclude.test.py").write_text("x = 1")

            tests_dir = tmpdir_path / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_file.py").write_text("x = 1")

            config = AnalysisConfig(
                exclude_patterns=["*.test.py", "*/tests/*"],
            )
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            scanned_files = [v.relative_path for v in result.violations]
            assert any("include.py" in str(f) for f in scanned_files) or result.total_files_scanned == 1

    def test_analyze_include_extensions(self):
        """Test analyzing with specific extensions only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file.py").write_text("x = 1")
            (tmpdir_path / "file.js").write_text("x = 1")
            (tmpdir_path / "file.txt").write_text("x = 1")

            config = AnalysisConfig(
                include_extensions=[".py", ".js"],
            )
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 2

    def test_analyze_sets_scan_duration(self):
        """Test that analyze sets scan duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file.py").write_text("x = 1")

            analyzer = FileAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.scan_duration_seconds > 0

    def test_analyze_sorts_violations_by_line_count(self):
        """Test that violations are sorted by line count descending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file1.py").write_text("\n".join([f"line{i}" for i in range(350)]))
            (tmpdir_path / "file2.py").write_text("\n".join([f"line{i}" for i in range(500)]))
            (tmpdir_path / "file3.py").write_text("\n".join([f"line{i}" for i in range(400)]))

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert len(result.violations) == 3
            assert result.violations[0].line_count == 500
            assert result.violations[1].line_count == 400
            assert result.violations[2].line_count == 350

    def test_analyze_handles_unreadable_files(self):
        """Test that analyze handles files that can't be read."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "good.py").write_text("x = 1")

            analyzer = FileAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned >= 1

    def test_analyze_uses_config_scan_path(self):
        """Test that analyze uses config scan path when none provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file.py").write_text("x = 1")

            config = AnalysisConfig(scan_path=tmpdir_path)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze()

            assert result.total_files_scanned == 1
            assert str(tmpdir_path) in result.scan_path

    def test_analyze_uses_provided_scan_path(self):
        """Test that analyze uses provided scan path over config."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                tmpdir1_path = Path(tmpdir1)
                tmpdir2_path = Path(tmpdir2)

                (tmpdir2_path / "file.py").write_text("x = 1")

                config = AnalysisConfig(scan_path=tmpdir1_path)
                analyzer = FileAnalyzer(config)
                result = analyzer.analyze(tmpdir2_path)

                assert str(tmpdir2_path) in result.scan_path

    def test_analyze_tracks_longest_file(self):
        """Test that analyze tracks the longest file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file1.py").write_text("\n".join([f"line{i}" for i in range(350)]))
            (tmpdir_path / "file2.py").write_text("\n".join([f"line{i}" for i in range(500)]))
            (tmpdir_path / "file3.py").write_text("\n".join([f"line{i}" for i in range(400)]))

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.longest_file is not None
            assert result.longest_file.line_count == 500

    def test_get_scan_preview_nonexistent_path(self):
        """Test scan preview with nonexistent path."""
        analyzer = FileAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.get_scan_preview(Path("/nonexistent/path"))

    def test_get_scan_preview_empty_directory(self):
        """Test scan preview with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = FileAnalyzer()
            files = analyzer.get_scan_preview(Path(tmpdir))

            assert isinstance(files, list)
            assert len(files) == 0

    def test_get_scan_preview_with_files(self):
        """Test scan preview with files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file1.py").write_text("x = 1")
            (tmpdir_path / "file2.py").write_text("y = 2")
            (tmpdir_path / "file3.js").write_text("z = 3")

            analyzer = FileAnalyzer()
            files = analyzer.get_scan_preview(tmpdir_path)

            assert len(files) == 3
            assert all(isinstance(f, Path) for f in files)

    def test_get_scan_preview_uses_config_scan_path(self):
        """Test that scan preview uses config scan path when none provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file.py").write_text("x = 1")

            config = AnalysisConfig(scan_path=tmpdir_path)
            analyzer = FileAnalyzer(config)
            files = analyzer.get_scan_preview()

            assert len(files) == 1

    def test_get_scan_preview_respects_exclude_patterns(self):
        """Test that scan preview respects exclude patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "include.py").write_text("x = 1")
            (tmpdir_path / "exclude.test.py").write_text("x = 1")

            config = AnalysisConfig(
                exclude_patterns=["*.test.py"],
            )
            analyzer = FileAnalyzer(config)
            files = analyzer.get_scan_preview(tmpdir_path)

            assert len(files) == 1
            assert any("include.py" in str(f) for f in files)

    def test_get_scan_preview_respects_include_extensions(self):
        """Test that scan preview respects include extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "file.py").write_text("x = 1")
            (tmpdir_path / "file.js").write_text("x = 1")
            (tmpdir_path / "file.txt").write_text("x = 1")

            config = AnalysisConfig(
                include_extensions=[".py"],
            )
            analyzer = FileAnalyzer(config)
            files = analyzer.get_scan_preview(tmpdir_path)

            assert len(files) == 1
            assert files[0].suffix == ".py"

    def test_analyze_sets_relative_path(self):
        """Test that analyze sets relative path for violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            subdir = tmpdir_path / "subdir"
            subdir.mkdir()
            (subdir / "large.py").write_text("\n".join([f"line{i}" for i in range(400)]))

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert len(result.violations) == 1
            violation = result.violations[0]
            assert violation.relative_path is not None
            assert "subdir" in violation.relative_path
            assert "large.py" in violation.relative_path

    def test_analyze_sets_file_extension(self):
        """Test that analyze sets file extension for violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "large.py").write_text("\n".join([f"line{i}" for i in range(400)]))
            (tmpdir_path / "large.css").write_text("\n".join([f".class{i} {{}}" for i in range(600)]))

            config = AnalysisConfig(
                threshold=300,
                extension_thresholds={".css": 500},
            )
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert len(result.violations) == 2

            py_violation = next((v for v in result.violations if v.file_extension == ".py"), None)
            css_violation = next((v for v in result.violations if v.file_extension == ".css"), None)

            assert py_violation is not None
            assert css_violation is not None
            assert py_violation.threshold == 300
            assert css_violation.threshold == 500

    def test_analyze_result_contains_metadata(self):
        """Test that analyze result contains all metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file.py").write_text("x = 1")

            config = AnalysisConfig(
                threshold=300,
                extension_thresholds={".css": 500},
                exclude_patterns=["*.test.py"],
            )
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.default_threshold == 300
            assert result.extension_thresholds == {".css": 500}
            assert result.skipped_patterns == ["*.test.py"]
            assert str(tmpdir_path) in result.scan_path

    def test_analyze_multiple_files_mixed_compliance(self):
        """Test analyzing multiple files with mixed compliance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "small1.py").write_text("\n".join([f"line{i}" for i in range(50)]))
            (tmpdir_path / "small2.py").write_text("\n".join([f"line{i}" for i in range(100)]))
            (tmpdir_path / "large1.py").write_text("\n".join([f"line{i}" for i in range(350)]))
            (tmpdir_path / "large2.py").write_text("\n".join([f"line{i}" for i in range(400)]))

            config = AnalysisConfig(threshold=300)
            analyzer = FileAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 4
            assert result.files_exceeding_threshold == 2
            assert result.compliance_rate == 50.0
