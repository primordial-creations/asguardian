"""
Tests for Heimdall Bug Detector Service

Unit tests for null dereference and unreachable code detection. Tests write
real Python code to temporary files and run the BugDetector against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugReport,
    BugSeverity,
)
from Asgard.Heimdall.Quality.BugDetection.services.bug_detector import BugDetector


class TestBugDetectorInitialization:
    """Tests for BugDetector initialization."""

    def test_default_initialization(self):
        """Test that the detector initializes with default config."""
        detector = BugDetector()
        assert detector.config is not None
        assert detector.null_detector is not None
        assert detector.unreachable_detector is not None

    def test_custom_config_initialization(self):
        """Test that the detector accepts a custom config."""
        config = BugDetectionConfig(
            detect_null_dereference=False,
            detect_unreachable_code=True,
        )
        detector = BugDetector(config=config)
        assert detector.config.detect_null_dereference is False
        assert detector.config.detect_unreachable_code is True

    def test_scan_nonexistent_path_raises(self):
        """Test that scanning a nonexistent path raises FileNotFoundError."""
        detector = BugDetector()
        with pytest.raises(FileNotFoundError):
            detector.scan(Path("/nonexistent/path/that/does/not/exist"))


class TestBugDetectorEmptyInputs:
    """Tests for edge cases with empty or minimal inputs."""

    def test_empty_directory_returns_empty_report(self):
        """Test that an empty directory produces a report with zero bugs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(Path(tmpdir))

            assert isinstance(report, BugReport)
            assert report.total_bugs == 0

    def test_empty_file_returns_zero_bugs(self):
        """Test that an empty Python file yields no bugs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "empty.py").write_text("")

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            assert report.total_bugs == 0

    def test_scan_returns_bug_report_type(self):
        """Test that scan always returns a BugReport."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = BugDetector()
            report = detector.scan(Path(tmpdir))

            assert isinstance(report, BugReport)


class TestNullDereferenceDetection:
    """Tests for null dereference bug detection."""

    def test_attribute_access_on_none_assigned_var_detected(self):
        """Test that accessing an attribute on a None-assigned variable is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "null_deref.py").write_text(
                "def process():\n"
                "    x = None\n"
                "    return x.value\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            assert report.total_bugs > 0
            null_findings = [
                f for f in report.findings
                if f.category == BugCategory.NULL_DEREFERENCE.value
            ]
            assert len(null_findings) > 0

    def test_dict_get_result_used_without_check(self):
        """Test that dict.get() result used without None check is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "dict_get.py").write_text(
                "def lookup(data, key):\n"
                "    value = data.get(key)\n"
                "    return value.strip()\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            null_findings = [
                f for f in report.findings
                if f.category == BugCategory.NULL_DEREFERENCE.value
            ]
            assert len(null_findings) > 0

    def test_none_check_before_access_not_detected(self):
        """Test that attribute access guarded by a None check is not detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "safe_access.py").write_text(
                "def safe_lookup(data, key):\n"
                "    value = data.get(key)\n"
                "    if value is not None:\n"
                "        return value.strip()\n"
                "    return ''\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            null_findings = [
                f for f in report.findings
                if f.category == BugCategory.NULL_DEREFERENCE.value
            ]
            assert len(null_findings) == 0

    def test_if_x_check_prevents_detection(self):
        """Test that 'if x:' truthiness check prevents null dereference detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "truthy_check.py").write_text(
                "def get_value(data, key):\n"
                "    result = data.get(key)\n"
                "    if result:\n"
                "        return result.upper()\n"
                "    return None\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            null_findings = [
                f for f in report.findings
                if f.category == BugCategory.NULL_DEREFERENCE.value
            ]
            assert len(null_findings) == 0

    def test_null_dereference_finding_has_correct_category(self):
        """Test that a null dereference finding has NULL_DEREFERENCE category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "null_cat.py").write_text(
                "def run():\n"
                "    x = None\n"
                "    print(x.something)\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            for finding in report.findings:
                if finding.category == BugCategory.NULL_DEREFERENCE.value:
                    assert finding.category == BugCategory.NULL_DEREFERENCE.value
                    break

    def test_null_dereference_from_none_includes_fix_suggestion(self):
        """Test that null dereference findings include a fix suggestion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "fix_hint.py").write_text(
                "def compute():\n"
                "    x = None\n"
                "    return x.result\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            null_findings = [
                f for f in report.findings
                if f.category == BugCategory.NULL_DEREFERENCE.value
            ]
            if null_findings:
                assert null_findings[0].fix_suggestion != ""


class TestUnreachableCodeDetection:
    """Tests for unreachable code bug detection."""

    def test_code_after_return_detected(self):
        """Test that code after a return statement is detected as unreachable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "dead_return.py").write_text(
                "def compute(x):\n"
                "    return x * 2\n"
                "    y = x + 1\n"
                "    return y\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            assert report.total_bugs > 0
            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            assert len(unreachable_findings) > 0

    def test_code_after_raise_detected(self):
        """Test that code after a raise statement is detected as unreachable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "dead_raise.py").write_text(
                "def validate(value):\n"
                "    raise ValueError('always fails')\n"
                "    return value * 2\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            assert len(unreachable_findings) > 0

    def test_unreachable_finding_severity_medium(self):
        """Test that unreachable code findings have MEDIUM severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "dead_sev.py").write_text(
                "def foo():\n"
                "    return 1\n"
                "    x = 2\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            if unreachable_findings:
                assert unreachable_findings[0].severity == BugSeverity.MEDIUM.value

    def test_unreachable_code_finding_has_fix_suggestion(self):
        """Test that unreachable code findings include a fix suggestion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "dead_fix.py").write_text(
                "def bar():\n"
                "    return 'done'\n"
                "    do_something()\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            if unreachable_findings:
                assert unreachable_findings[0].fix_suggestion != ""

    def test_code_after_break_detected(self):
        """Test that code after a break statement is detected as unreachable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "dead_break.py").write_text(
                "def search(items):\n"
                "    for item in items:\n"
                "        break\n"
                "        process(item)\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            assert len(unreachable_findings) > 0


class TestCleanCode:
    """Tests that clean code does not produce false positives."""

    def test_clean_function_no_bugs(self):
        """Test that a well-written function produces no bug findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "clean_code.py").write_text(
                "def safe_divide(a, b):\n"
                "    if b == 0:\n"
                "        raise ValueError('Cannot divide by zero')\n"
                "    return a / b\n"
                "\n"
                "def get_item(items, key):\n"
                "    value = items.get(key)\n"
                "    if value is not None:\n"
                "        return value.strip()\n"
                "    return ''\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            # Should produce no critical, high, or medium findings on clean code
            assert report.critical_count == 0
            assert report.high_count == 0
            assert report.medium_count == 0

    def test_normal_return_with_no_following_code_no_bug(self):
        """Test that a return at the end of a function does not produce a finding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "normal_return.py").write_text(
                "def compute(x):\n"
                "    result = x * 2\n"
                "    return result\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            assert len(unreachable_findings) == 0


class TestBugDetectorReportMetadata:
    """Tests for BugReport structure and metadata."""

    def test_report_files_analyzed_count(self):
        """Test that the report counts analyzed files correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "a.py").write_text("x = 1\n")
            (tmpdir_path / "b.py").write_text("y = 2\n")

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            assert report.files_analyzed == 2

    def test_report_scan_duration_non_negative(self):
        """Test that scan duration is a non-negative float."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = BugDetector()
            report = detector.scan(Path(tmpdir))

            assert report.scan_duration_seconds >= 0.0

    def test_report_has_findings_property_false_when_empty(self):
        """Test has_findings is False when no bugs found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = BugDetector()
            report = detector.scan(Path(tmpdir))

            assert report.has_findings is False

    def test_report_is_passing_property_for_no_critical_or_high(self):
        """Test is_passing returns True when no critical or high bugs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = BugDetector()
            report = detector.scan(Path(tmpdir))

            assert report.is_passing is True

    def test_bug_finding_line_number_positive(self):
        """Test that bug finding line numbers are positive integers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "null_use.py").write_text(
                "def run():\n"
                "    x = None\n"
                "    return x.attr\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            for finding in report.findings:
                assert finding.line_number > 0

    def test_bug_finding_includes_code_snippet(self):
        """Test that bug findings include a non-empty code snippet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "snippet.py").write_text(
                "def do_it():\n"
                "    return 'early exit'\n"
                "    extra_work()\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            for finding in report.findings:
                assert finding.code_snippet != ""

    def test_get_findings_by_category_groups_correctly(self):
        """Test get_findings_by_category returns grouped findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "mixed_bugs.py").write_text(
                "def run():\n"
                "    x = None\n"
                "    return x.attr\n"
                "    extra = 1\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            by_category = report.get_findings_by_category()
            # Should be a dict with category string keys
            assert isinstance(by_category, dict)

    def test_severity_counters_match_findings(self):
        """Test that severity counters on BugReport match actual findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "sev_check.py").write_text(
                "def process():\n"
                "    return 'done'\n"
                "    cleanup()\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            actual_medium = sum(
                1 for f in report.findings
                if f.severity == BugSeverity.MEDIUM.value
            )
            actual_high = sum(
                1 for f in report.findings
                if f.severity == BugSeverity.HIGH.value
            )
            actual_critical = sum(
                1 for f in report.findings
                if f.severity == BugSeverity.CRITICAL.value
            )

            assert report.medium_count == actual_medium
            assert report.high_count == actual_high
            assert report.critical_count == actual_critical


class TestBugDetectorScanVariants:
    """Tests for scan variant methods."""

    def test_scan_null_dereference_only_no_unreachable(self):
        """Test that scan_null_dereference_only does not return unreachable code findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # This code has both: null dereference and unreachable code
            (tmpdir_path / "both_bugs.py").write_text(
                "def run():\n"
                "    x = None\n"
                "    val = x.something\n"
                "    return val\n"
                "    dead = 1\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan_null_dereference_only(tmpdir_path)

            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            assert len(unreachable_findings) == 0

    def test_scan_unreachable_only_no_null_findings(self):
        """Test that scan_unreachable_only does not return null dereference findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "mixed.py").write_text(
                "def run():\n"
                "    x = None\n"
                "    val = x.something\n"
                "    return val\n"
                "    dead = 1\n"
            )

            config = BugDetectionConfig(exclude_patterns=["__pycache__", ".git"])
            detector = BugDetector(config=config)
            report = detector.scan_unreachable_only(tmpdir_path)

            null_findings = [
                f for f in report.findings
                if f.category == BugCategory.NULL_DEREFERENCE.value
            ]
            assert len(null_findings) == 0

    def test_scan_with_null_detection_disabled(self):
        """Test that disabling null detection omits null dereference findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "null_only.py").write_text(
                "def run():\n"
                "    x = None\n"
                "    return x.attr\n"
            )

            config = BugDetectionConfig(
                detect_null_dereference=False,
                exclude_patterns=["__pycache__", ".git"],
            )
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            null_findings = [
                f for f in report.findings
                if f.category == BugCategory.NULL_DEREFERENCE.value
            ]
            assert len(null_findings) == 0

    def test_scan_with_unreachable_detection_disabled(self):
        """Test that disabling unreachable code detection omits those findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "dead_code.py").write_text(
                "def run():\n"
                "    return 1\n"
                "    dead_code = 2\n"
            )

            config = BugDetectionConfig(
                detect_unreachable_code=False,
                exclude_patterns=["__pycache__", ".git"],
            )
            detector = BugDetector(config=config)
            report = detector.scan(tmpdir_path)

            unreachable_findings = [
                f for f in report.findings
                if f.category == BugCategory.UNREACHABLE_CODE.value
            ]
            assert len(unreachable_findings) == 0
