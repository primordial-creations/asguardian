"""
Tests for Heimdall NewCodePeriodDetector

Unit tests for detecting new and modified code files relative to a configured
reference point. Tests use temp directories with real files.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from Asgard.Shared.common.new_code_period import (
    NewCodePeriodConfig,
    NewCodePeriodDetector,
    NewCodePeriodResult,
    NewCodePeriodType,
)
from Asgard.Shared.common import _new_code_git
from Asgard.Shared.common import new_code_period as _ncp_module

# Resolve forward reference to Path in NewCodePeriodConfig.baseline_path
NewCodePeriodConfig.model_rebuild(_types_namespace={"Path": Path})


class TestNewCodePeriodDetectorNonGit:
    """Tests for NewCodePeriodDetector in non-git directories (mtime fallback)."""

    def test_empty_directory_returns_empty_result(self):
        """A directory with no Python files returns empty new and modified lists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=datetime.now() - timedelta(days=30),
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)

            assert result.new_files == []
            assert result.modified_files == []
            assert result.total_new_code_files == 0

    def test_non_git_directory_does_not_crash(self):
        """Detecting new code in a non-git directory does not raise an exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=datetime.now() - timedelta(days=1),
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)
            assert isinstance(result, NewCodePeriodResult)

    def test_since_date_mtime_detects_recently_modified_files(self):
        """Files modified after the reference date are included in modified_files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            py_file = tmpdir_path / "recent.py"
            py_file.write_text("x = 1\n")

            reference_date = datetime.now() - timedelta(hours=1)
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=reference_date,
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)

            assert "recent.py" in result.modified_files

    def test_since_date_mtime_excludes_old_files(self):
        """Files not modified after the reference date are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            py_file = tmpdir_path / "old.py"
            py_file.write_text("y = 2\n")

            import os
            old_mtime = (datetime.now() - timedelta(days=10)).timestamp()
            os.utime(str(py_file), (old_mtime, old_mtime))

            reference_date = datetime.now() - timedelta(days=5)
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=reference_date,
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)

            assert "old.py" not in result.modified_files

    def test_days_period_type_falls_back_gracefully(self):
        """SINCE_LAST_ANALYSIS period type in non-git dir returns a result without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_LAST_ANALYSIS,
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)
            assert isinstance(result, NewCodePeriodResult)


class TestNewCodePeriodDetectorWithGitMock:
    """Tests for NewCodePeriodDetector using mocked git commands."""

    def test_since_date_git_returns_modified_files(self):
        """SINCE_DATE with git available returns files from git log output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=datetime(2025, 1, 1),
            )
            detector = NewCodePeriodDetector()

            def mock_run_git(args, cwd):
                if args and args[0] == "log":
                    return "src/new_feature.py\nsrc/utils.py\n"
                return None

            with patch.object(_ncp_module, "git_available", return_value=True), \
                 patch.object(_new_code_git, "run_git", side_effect=mock_run_git):
                result = detector.detect(tmpdir, config)

            assert "src/new_feature.py" in result.modified_files
            assert "src/utils.py" in result.modified_files

    def test_since_branch_point_returns_new_and_modified_files(self):
        """SINCE_BRANCH_POINT returns new and modified files from git diff --name-status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_BRANCH_POINT,
                reference_branch="main",
            )
            detector = NewCodePeriodDetector()

            def mock_run_git(args, cwd):
                if args and args[0] == "diff" and "--name-status" in args:
                    return "A\tsrc/added_file.py\nM\tsrc/modified_file.py\nD\tsrc/deleted_file.py\n"
                return None

            with patch.object(_ncp_module, "git_available", return_value=True), \
                 patch.object(_new_code_git, "run_git", side_effect=mock_run_git):
                result = detector.detect(tmpdir, config)

            assert "src/added_file.py" in result.new_files
            assert "src/modified_file.py" in result.modified_files
            assert "src/deleted_file.py" not in result.new_files
            assert "src/deleted_file.py" not in result.modified_files

    def test_since_last_analysis_no_baseline(self):
        """SINCE_LAST_ANALYSIS without a baseline uses git diff HEAD~1 HEAD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_LAST_ANALYSIS,
                baseline_path=None,
            )
            detector = NewCodePeriodDetector()

            captured_args = []

            def mock_run_git(args, cwd):
                captured_args.append(args)
                if args and args[0] == "diff" and "--name-status" in args:
                    return "M\tsrc/changed.py\n"
                return "0"

            with patch.object(_ncp_module, "git_available", return_value=True), \
                 patch.object(_new_code_git, "run_git", side_effect=mock_run_git):
                detector.detect(tmpdir, config)

            diff_calls = [a for a in captured_args if a and a[0] == "diff"]
            assert any("HEAD~1" in a for a in diff_calls)

    def test_since_version_returns_new_and_modified(self):
        """SINCE_VERSION with a tag uses git diff --name-status tag...HEAD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_VERSION,
                reference_version="v1.0.0",
            )
            detector = NewCodePeriodDetector()

            def mock_run_git(args, cwd):
                if args and args[0] == "diff" and "--name-status" in args:
                    return "A\tsrc/brand_new.py\nM\tsrc/updated.py\n"
                return "0"

            with patch.object(_ncp_module, "git_available", return_value=True), \
                 patch.object(_new_code_git, "run_git", side_effect=mock_run_git):
                result = detector.detect(tmpdir, config)

            assert "src/brand_new.py" in result.new_files
            assert "src/updated.py" in result.modified_files

    def test_since_version_no_version_configured_returns_empty(self):
        """SINCE_VERSION with no reference_version returns empty result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_VERSION,
                reference_version=None,
            )
            detector = NewCodePeriodDetector()

            with patch.object(_ncp_module, "git_available", return_value=True):
                result = detector.detect(tmpdir, config)

            assert result.new_files == []
            assert result.modified_files == []

    def test_result_total_new_code_files_is_sum(self):
        """total_new_code_files equals len(new_files) + len(modified_files)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_BRANCH_POINT,
                reference_branch="main",
            )
            detector = NewCodePeriodDetector()

            def mock_run_git(args, cwd):
                if args and args[0] == "diff":
                    return "A\tfile1.py\nA\tfile2.py\nM\tfile3.py\n"
                return "0"

            with patch.object(_ncp_module, "git_available", return_value=True), \
                 patch.object(_new_code_git, "run_git", side_effect=mock_run_git):
                result = detector.detect(tmpdir, config)

            expected = len(result.new_files) + len(result.modified_files)
            assert result.total_new_code_files == expected

    def test_git_failure_falls_back_to_mtime(self):
        """When git is unavailable, detector falls back to mtime-based detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            py_file = tmpdir_path / "myfile.py"
            py_file.write_text("z = 3\n")

            reference_date = datetime.now() - timedelta(hours=1)
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=reference_date,
            )
            detector = NewCodePeriodDetector()

            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)

            assert "myfile.py" in result.modified_files


class TestNewCodePeriodResult:
    """Tests for NewCodePeriodResult model properties."""

    def test_result_period_type_stored(self):
        """NewCodePeriodResult stores the period type used for detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=datetime.now() - timedelta(days=1),
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)
            assert result.period_type == NewCodePeriodType.SINCE_DATE

    def test_result_reference_point_is_set(self):
        """NewCodePeriodResult has a non-empty reference_point description."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=datetime.now() - timedelta(days=1),
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)
            assert result.reference_point != ""

    def test_result_detected_at_is_set(self):
        """NewCodePeriodResult has a detected_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = NewCodePeriodConfig(
                period_type=NewCodePeriodType.SINCE_DATE,
                reference_date=datetime.now() - timedelta(days=1),
            )
            detector = NewCodePeriodDetector()
            with patch.object(_ncp_module, "git_available", return_value=False):
                result = detector.detect(tmpdir, config)
            assert result.detected_at is not None
            assert isinstance(result.detected_at, datetime)


class TestNewCodePeriodParseNameStatus:
    """Tests for the parse_name_status helper."""

    def test_parse_added_files(self):
        """Added files (A status) are placed in new_files."""
        output = "A\tsrc/new_file.py\nA\tsrc/another.py\n"
        new_files, modified_files = _new_code_git.parse_name_status(output)
        assert "src/new_file.py" in new_files
        assert "src/another.py" in new_files
        assert modified_files == []

    def test_parse_modified_files(self):
        """Modified files (M status) are placed in modified_files."""
        output = "M\tsrc/existing.py\n"
        new_files, modified_files = _new_code_git.parse_name_status(output)
        assert new_files == []
        assert "src/existing.py" in modified_files

    def test_parse_deleted_files_excluded(self):
        """Deleted files (D status) are excluded from both lists."""
        output = "D\tsrc/removed.py\n"
        new_files, modified_files = _new_code_git.parse_name_status(output)
        assert new_files == []
        assert modified_files == []

    def test_parse_renamed_files_go_to_modified(self):
        """Renamed files (R status) are placed in modified_files."""
        output = "R100\tsrc/old_name.py\tsrc/new_name.py\n"
        new_files, modified_files = _new_code_git.parse_name_status(output)
        assert new_files == []
        assert "src/new_name.py" in modified_files

    def test_parse_none_output_returns_empty(self):
        """None output returns two empty lists."""
        new_files, modified_files = _new_code_git.parse_name_status(None)
        assert new_files == []
        assert modified_files == []

    def test_parse_empty_string_returns_empty(self):
        """Empty string output returns two empty lists."""
        new_files, modified_files = _new_code_git.parse_name_status("")
        assert new_files == []
        assert modified_files == []
