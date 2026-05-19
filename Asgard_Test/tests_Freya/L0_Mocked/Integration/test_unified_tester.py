"""
Freya Unified Tester Tests

Comprehensive L0 unit tests for UnifiedTester service.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from Asgard.Freya.Integration.models.integration_models import (
    TestCategory,
    TestSeverity,
    UnifiedTestConfig,
    UnifiedTestResult,
    UnifiedTestReport,
)
from Asgard.Freya.Integration.services.unified_tester import UnifiedTester


@pytest.fixture
def mock_unified_config():
    """Create a mock UnifiedTestConfig."""
    return UnifiedTestConfig(
        url="https://example.com",
        categories=[TestCategory.ALL],
        min_severity=TestSeverity.MINOR,
        capture_screenshots=True,
        output_directory="/tmp/test_output"
    )


@pytest.fixture
def mock_wcag_report():
    """Create a mock WCAG validation report."""
    violation = Mock()
    violation.severity = "serious"
    violation.description = "Missing alt text"
    violation.element_selector = "img.logo"
    violation.suggested_fix = "Add alt attribute"
    violation.wcag_criterion = "1.1.1"
    violation.rule_id = "image-alt"

    report = Mock()
    report.violations = [violation]
    return report


@pytest.fixture
def mock_contrast_report():
    """Create a mock color contrast report."""
    issue = Mock()
    issue.severity = "moderate"
    issue.description = "Insufficient contrast"
    issue.element_selector = ".text"
    issue.suggested_fix = "Increase contrast ratio"
    issue.wcag_criterion = "1.4.3"
    issue.foreground_color = "#777777"
    issue.background_color = "#FFFFFF"
    issue.contrast_ratio = 3.5

    report = Mock()
    report.issues = [issue]
    return report


@pytest.fixture
def mock_keyboard_report():
    """Create a mock keyboard navigation report."""
    issue = Mock()
    issue.severity = "critical"
    issue.description = "No keyboard focus visible"
    issue.element_selector = ".button"
    issue.suggested_fix = "Add focus indicator"
    issue.wcag_reference = "2.4.7"

    report = Mock()
    report.issues = [issue]
    return report


@pytest.fixture
def mock_aria_report():
    """Create a mock ARIA validation report."""
    violation = Mock()
    violation.severity = "serious"
    violation.description = "Invalid ARIA attribute"
    violation.element_selector = "div[role='button']"
    violation.suggested_fix = "Use valid ARIA role"

    report = Mock()
    report.violations = [violation]
    return report


@pytest.fixture
def mock_layout_report():
    """Create a mock layout validation report."""
    issue = Mock()
    issue.severity = "moderate"
    issue.description = "Layout overflow"
    issue.element_selector = ".container"
    issue.suggested_fix = "Add overflow handling"

    report = Mock()
    report.issues = [issue]
    return report


@pytest.fixture
def mock_style_report():
    """Create a mock style validation report."""
    issue = Mock()
    issue.severity = "minor"
    issue.description = "Inconsistent font size"
    issue.element_selector = "p"
    issue.suggested_fix = "Use consistent typography"

    report = Mock()
    report.issues = [issue]
    return report


@pytest.fixture
def mock_breakpoint_report():
    """Create a mock breakpoint testing report."""
    issue = Mock()
    issue.severity = "serious"
    issue.description = "Layout breaks at 768px"
    issue.element_selector = ".grid"
    issue.suggested_fix = "Add responsive grid"

    breakpoint = Mock()
    breakpoint.name = "tablet"

    result = Mock()
    result.breakpoint = breakpoint
    result.issues = [issue]

    report = Mock()
    report.results = [result]
    report.screenshots = {"tablet": "/tmp/tablet.png"}
    report.total_issues = 1
    return report


@pytest.fixture
def mock_touch_target_report():
    """Create a mock touch target validation report."""
    issue = Mock()
    issue.severity = "moderate"
    issue.description = "Touch target too small"
    issue.element_selector = ".small-button"
    issue.suggested_fix = "Increase button size"
    issue.width = 30
    issue.height = 30

    report = Mock()
    report.issues = [issue]
    return report


@pytest.fixture
def mock_viewport_report():
    """Create a mock viewport testing report."""
    issue = Mock()
    issue.severity = "serious"
    issue.description = "Missing viewport meta tag"
    issue.suggested_fix = "Add viewport meta tag"
    issue.wcag_reference = "1.4.10"

    report = Mock()
    report.issues = [issue]
    return report


@pytest.fixture
def mock_mobile_compat_report():
    """Create a mock mobile compatibility report."""
    issue = Mock()
    issue.severity = "moderate"
    issue.description = "Horizontal scroll on mobile"
    issue.element_selector = ".wide-content"
    issue.suggested_fix = "Use responsive width"
    issue.affected_devices = ["iphone-14", "pixel-7"]

    report = Mock()
    report.issues = [issue]
    return report


class TestUnifiedTesterInit:
    """Tests for UnifiedTester initialization."""

    def test_init_without_config(self, tmp_path):
        """Test UnifiedTester initialization without config."""

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))

        assert isinstance(tester.config, UnifiedTestConfig)

    def test_init_with_config(self, mock_unified_config):
        """Test UnifiedTester initialization with config."""

        tester = UnifiedTester(config=mock_unified_config)

        assert tester.config == mock_unified_config
        # Verify Path was called with the configured output directory
        assert tester.output_dir is not None


class TestUnifiedTesterTest:
    """Tests for test method."""

    def test_test_all_categories(self, tmp_path):
        """Test running tests with all categories."""

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))

        with patch('Asgard.Freya.Integration.services.unified_tester.run_accessibility_tests',
                   AsyncMock(return_value=[])), \
             patch('Asgard.Freya.Integration.services.unified_tester.run_visual_tests',
                   AsyncMock(return_value=([], {}))), \
             patch('Asgard.Freya.Integration.services.unified_tester.run_responsive_tests',
                   AsyncMock(return_value=([], {}))):

            import asyncio
            report = asyncio.run(tester.test("https://example.com"))

        assert isinstance(report, UnifiedTestReport)
        assert report.url == "https://example.com"
        assert report.total_tests >= 0

    def test_test_specific_category(self, tmp_path):
        """Test running tests for specific category."""

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))

        mock_accessibility_fn = AsyncMock(return_value=[])
        mock_visual_fn = AsyncMock(return_value=([], {}))
        mock_responsive_fn = AsyncMock(return_value=([], {}))

        with patch('Asgard.Freya.Integration.services.unified_tester.run_accessibility_tests',
                   mock_accessibility_fn), \
             patch('Asgard.Freya.Integration.services.unified_tester.run_visual_tests',
                   mock_visual_fn), \
             patch('Asgard.Freya.Integration.services.unified_tester.run_responsive_tests',
                   mock_responsive_fn):

            import asyncio
            report = asyncio.run(tester.test(
                "https://example.com",
                categories=[TestCategory.ACCESSIBILITY]
            ))

        mock_accessibility_fn.assert_called_once()
        mock_visual_fn.assert_not_called()
        mock_responsive_fn.assert_not_called()

    def test_test_calculates_scores(self, tmp_path):
        """Test that scores are calculated correctly."""

        passing_result = UnifiedTestResult(
            category=TestCategory.ACCESSIBILITY,
            test_name="Test",
            passed=True,
            message="Passed"
        )

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        tester._run_accessibility_tests = AsyncMock(return_value=[passing_result])
        tester._run_visual_tests = AsyncMock(return_value=([], {}))
        tester._run_responsive_tests = AsyncMock(return_value=([], {}))

        import asyncio
        report = asyncio.run(tester.test("https://example.com"))

        assert report.accessibility_score > 0
        assert report.overall_score > 0


class TestUnifiedTesterRunAccessibilityTests:
    """Tests for run_accessibility_tests function."""

    def test_run_accessibility_wcag_success(self):
        """Test running WCAG validation with no violations."""
        from Asgard.Freya.Integration.services._unified_tester_runners import run_accessibility_tests

        mock_wcag_instance = AsyncMock()
        mock_wcag_instance.validate = AsyncMock(return_value=Mock(violations=[]))
        mock_contrast_instance = AsyncMock()
        mock_contrast_instance.check = AsyncMock(return_value=Mock(issues=[]))
        mock_keyboard_instance = AsyncMock()
        mock_keyboard_instance.test = AsyncMock(return_value=Mock(issues=[]))
        mock_aria_instance = AsyncMock()
        mock_aria_instance.validate = AsyncMock(return_value=Mock(violations=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_runners.WCAGValidator',
                   return_value=mock_wcag_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ColorContrastChecker',
                   return_value=mock_contrast_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.KeyboardNavigationTester',
                   return_value=mock_keyboard_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ARIAValidator',
                   return_value=mock_aria_instance):

            import asyncio
            results = asyncio.run(run_accessibility_tests("https://example.com"))

        assert any(r.test_name == "WCAG Validation" and r.passed for r in results)

    def test_run_accessibility_wcag_failures(self, mock_wcag_report):
        """Test running WCAG validation with violations."""
        from Asgard.Freya.Integration.services._unified_tester_runners import run_accessibility_tests

        mock_wcag_instance = AsyncMock()
        mock_wcag_instance.validate = AsyncMock(return_value=mock_wcag_report)
        mock_contrast_instance = AsyncMock()
        mock_contrast_instance.check = AsyncMock(return_value=Mock(issues=[]))
        mock_keyboard_instance = AsyncMock()
        mock_keyboard_instance.test = AsyncMock(return_value=Mock(issues=[]))
        mock_aria_instance = AsyncMock()
        mock_aria_instance.validate = AsyncMock(return_value=Mock(violations=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_runners.WCAGValidator',
                   return_value=mock_wcag_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ColorContrastChecker',
                   return_value=mock_contrast_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.KeyboardNavigationTester',
                   return_value=mock_keyboard_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ARIAValidator',
                   return_value=mock_aria_instance):

            import asyncio
            results = asyncio.run(run_accessibility_tests("https://example.com"))

        wcag_failures = [r for r in results if r.test_name == "WCAG Validation" and not r.passed]
        assert len(wcag_failures) > 0
        assert any("Missing alt text" in r.message for r in wcag_failures)

    def test_run_accessibility_contrast_failures(self, mock_contrast_report):
        """Test running contrast checks with issues."""
        from Asgard.Freya.Integration.services._unified_tester_runners import run_accessibility_tests

        mock_wcag_instance = AsyncMock()
        mock_wcag_instance.validate = AsyncMock(return_value=Mock(violations=[]))
        mock_contrast_instance = AsyncMock()
        mock_contrast_instance.check = AsyncMock(return_value=mock_contrast_report)
        mock_keyboard_instance = AsyncMock()
        mock_keyboard_instance.test = AsyncMock(return_value=Mock(issues=[]))
        mock_aria_instance = AsyncMock()
        mock_aria_instance.validate = AsyncMock(return_value=Mock(violations=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_runners.WCAGValidator',
                   return_value=mock_wcag_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ColorContrastChecker',
                   return_value=mock_contrast_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.KeyboardNavigationTester',
                   return_value=mock_keyboard_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ARIAValidator',
                   return_value=mock_aria_instance):

            import asyncio
            results = asyncio.run(run_accessibility_tests("https://example.com"))

        contrast_failures = [r for r in results if r.test_name == "Color Contrast" and not r.passed]
        assert len(contrast_failures) > 0

    def test_run_accessibility_exception_handling(self):
        """Test exception handling in accessibility tests."""
        from Asgard.Freya.Integration.services._unified_tester_runners import run_accessibility_tests

        mock_wcag_instance = AsyncMock()
        mock_wcag_instance.validate = AsyncMock(side_effect=Exception("Test error"))
        mock_contrast_instance = AsyncMock()
        mock_contrast_instance.check = AsyncMock(return_value=Mock(issues=[]))
        mock_keyboard_instance = AsyncMock()
        mock_keyboard_instance.test = AsyncMock(return_value=Mock(issues=[]))
        mock_aria_instance = AsyncMock()
        mock_aria_instance.validate = AsyncMock(return_value=Mock(violations=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_runners.WCAGValidator',
                   return_value=mock_wcag_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ColorContrastChecker',
                   return_value=mock_contrast_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.KeyboardNavigationTester',
                   return_value=mock_keyboard_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.ARIAValidator',
                   return_value=mock_aria_instance):

            import asyncio
            results = asyncio.run(run_accessibility_tests("https://example.com"))

        error_results = [r for r in results if not r.passed and "failed" in r.message]
        assert len(error_results) > 0


class TestUnifiedTesterRunVisualTests:
    """Tests for run_visual_tests function."""

    def test_run_visual_tests_success(self):
        """Test running visual tests with no issues."""
        from Asgard.Freya.Integration.services._unified_tester_runners import run_visual_tests

        mock_layout_instance = AsyncMock()
        mock_layout_instance.validate = AsyncMock(return_value=Mock(issues=[]))
        mock_style_instance = AsyncMock()
        mock_style_instance.validate = AsyncMock(return_value=Mock(issues=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_runners.LayoutValidator',
                   return_value=mock_layout_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.StyleValidator',
                   return_value=mock_style_instance):

            import asyncio
            results, screenshots = asyncio.run(run_visual_tests("https://example.com"))

        passing_results = [r for r in results if r.passed]
        assert len(passing_results) > 0

    def test_run_visual_tests_failures(self, mock_layout_report):
        """Test running visual tests with failures."""
        from Asgard.Freya.Integration.services._unified_tester_runners import run_visual_tests

        mock_layout_instance = AsyncMock()
        mock_layout_instance.validate = AsyncMock(return_value=mock_layout_report)
        mock_style_instance = AsyncMock()
        mock_style_instance.validate = AsyncMock(return_value=Mock(issues=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_runners.LayoutValidator',
                   return_value=mock_layout_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_runners.StyleValidator',
                   return_value=mock_style_instance):

            import asyncio
            results, screenshots = asyncio.run(run_visual_tests("https://example.com"))

        layout_failures = [r for r in results if r.test_name == "Layout Validation" and not r.passed]
        assert len(layout_failures) > 0


class TestUnifiedTesterRunResponsiveTests:
    """Tests for run_responsive_tests function."""

    def test_run_responsive_tests_success(self):
        """Test running responsive tests with no issues."""
        from Asgard.Freya.Integration.services._unified_tester_responsive import run_responsive_tests
        from pathlib import Path

        mock_bp_instance = AsyncMock()
        mock_bp_instance.test = AsyncMock(return_value=Mock(
            results=[],
            screenshots={},
            total_issues=0
        ))

        mock_empty_instance = AsyncMock()
        mock_empty_instance.validate = AsyncMock(return_value=Mock(issues=[]))
        mock_empty_instance.test = AsyncMock(return_value=Mock(issues=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_responsive.BreakpointTester',
                   return_value=mock_bp_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.TouchTargetValidator',
                   return_value=mock_empty_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.ViewportTester',
                   return_value=mock_empty_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.MobileCompatibilityTester',
                   return_value=mock_empty_instance):

            import asyncio
            results, screenshots = asyncio.run(
                run_responsive_tests("https://example.com", Path("/tmp"), False)
            )

        passing_results = [r for r in results if r.passed]
        assert len(passing_results) > 0

    def test_run_responsive_tests_breakpoint_failures(self, mock_breakpoint_report):
        """Test running breakpoint tests with failures."""
        from Asgard.Freya.Integration.services._unified_tester_responsive import run_responsive_tests
        from pathlib import Path

        mock_bp_instance = AsyncMock()
        mock_bp_instance.test = AsyncMock(return_value=mock_breakpoint_report)

        mock_empty_instance = AsyncMock()
        mock_empty_instance.validate = AsyncMock(return_value=Mock(issues=[]))
        mock_empty_instance.test = AsyncMock(return_value=Mock(issues=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_responsive.BreakpointTester',
                   return_value=mock_bp_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.TouchTargetValidator',
                   return_value=mock_empty_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.ViewportTester',
                   return_value=mock_empty_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.MobileCompatibilityTester',
                   return_value=mock_empty_instance):

            import asyncio
            results, screenshots = asyncio.run(
                run_responsive_tests("https://example.com", Path("/tmp"), False)
            )

        bp_failures = [r for r in results if "Breakpoint" in r.test_name and not r.passed]
        assert len(bp_failures) > 0

    def test_run_responsive_tests_touch_target_failures(self, mock_touch_target_report):
        """Test running touch target validation with failures."""
        from Asgard.Freya.Integration.services._unified_tester_responsive import run_responsive_tests
        from pathlib import Path

        mock_bp_instance = AsyncMock()
        mock_bp_instance.test = AsyncMock(return_value=Mock(
            results=[], screenshots={}, total_issues=0
        ))

        mock_touch_instance = AsyncMock()
        mock_touch_instance.validate = AsyncMock(return_value=mock_touch_target_report)

        mock_empty_instance = AsyncMock()
        mock_empty_instance.validate = AsyncMock(return_value=Mock(issues=[]))
        mock_empty_instance.test = AsyncMock(return_value=Mock(issues=[]))

        with patch('Asgard.Freya.Integration.services._unified_tester_responsive.BreakpointTester',
                   return_value=mock_bp_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.TouchTargetValidator',
                   return_value=mock_touch_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.ViewportTester',
                   return_value=mock_empty_instance), \
             patch('Asgard.Freya.Integration.services._unified_tester_responsive.MobileCompatibilityTester',
                   return_value=mock_empty_instance):

            import asyncio
            results, screenshots = asyncio.run(
                run_responsive_tests("https://example.com", Path("/tmp"), False)
            )

        touch_failures = [r for r in results if r.test_name == "Touch Targets" and not r.passed]
        assert len(touch_failures) > 0
        assert any(r.details.get("width") == 30 for r in touch_failures)


class TestUnifiedTesterMapSeverity:
    """Tests for _map_severity method."""

    def test_map_severity_critical(self, tmp_path):
        """Test mapping critical severity."""

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        result = tester._map_severity("critical")

        assert result == TestSeverity.CRITICAL

    def test_map_severity_case_insensitive(self, tmp_path):
        """Test severity mapping is case insensitive."""

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        result = tester._map_severity("SERIOUS")

        assert result == TestSeverity.SERIOUS

    def test_map_severity_unknown(self, tmp_path):
        """Test mapping unknown severity defaults to moderate."""

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        result = tester._map_severity("unknown")

        assert result == TestSeverity.MODERATE


class TestUnifiedTesterFilterBySeverity:
    """Tests for _filter_by_severity method."""

    def test_filter_by_severity_critical_only(self, tmp_path):
        """Test filtering to show only critical issues."""

        results = [
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 1",
                passed=False,
                severity=TestSeverity.CRITICAL,
                message="Critical issue"
            ),
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 2",
                passed=False,
                severity=TestSeverity.MODERATE,
                message="Moderate issue"
            )
        ]

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        filtered = tester._filter_by_severity(results, TestSeverity.CRITICAL)

        assert len(filtered) == 1
        assert filtered[0].severity == TestSeverity.CRITICAL

    def test_filter_by_severity_includes_passed(self, tmp_path):
        """Test filtering includes passed tests."""

        results = [
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 1",
                passed=True,
                message="Passed"
            ),
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 2",
                passed=False,
                severity=TestSeverity.MINOR,
                message="Minor issue"
            )
        ]

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        filtered = tester._filter_by_severity(results, TestSeverity.CRITICAL)

        passed_tests = [r for r in filtered if r.passed]
        assert len(passed_tests) == 1


class TestUnifiedTesterCalculateCategoryScore:
    """Tests for _calculate_category_score method."""

    def test_calculate_category_score_all_passed(self, tmp_path):
        """Test score calculation with all tests passed."""

        results = [
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 1",
                passed=True,
                message="Passed"
            ),
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 2",
                passed=True,
                message="Passed"
            )
        ]

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        score = tester._calculate_category_score(results)

        assert score == 100.0

    def test_calculate_category_score_with_failures(self, tmp_path):
        """Test score calculation with failures."""

        results = [
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 1",
                passed=False,
                severity=TestSeverity.CRITICAL,
                message="Critical issue"
            ),
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test 2",
                passed=True,
                message="Passed"
            )
        ]

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        score = tester._calculate_category_score(results)

        assert score < 100.0
        assert score >= 0.0

    def test_calculate_category_score_empty_results(self, tmp_path):
        """Test score calculation with no results."""

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        score = tester._calculate_category_score([])

        assert score == 100.0

    def test_calculate_category_score_severity_penalties(self, tmp_path):
        """Test that different severities have different penalties."""

        critical_result = [
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test",
                passed=False,
                severity=TestSeverity.CRITICAL,
                message="Critical"
            )
        ]

        minor_result = [
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name="Test",
                passed=False,
                severity=TestSeverity.MINOR,
                message="Minor"
            )
        ]

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        critical_score = tester._calculate_category_score(critical_result)
        minor_score = tester._calculate_category_score(minor_result)

        assert critical_score < minor_score

    def test_calculate_category_score_bounds(self, tmp_path):
        """Test score is bounded between 0 and 100."""

        # Create many critical failures
        results = [
            UnifiedTestResult(
                category=TestCategory.ACCESSIBILITY,
                test_name=f"Test {i}",
                passed=False,
                severity=TestSeverity.CRITICAL,
                message="Critical"
            )
            for i in range(20)
        ]

        tester = UnifiedTester(config=UnifiedTestConfig(url="", output_directory=str(tmp_path / "output")))
        score = tester._calculate_category_score(results)

        assert score >= 0.0
        assert score <= 100.0
