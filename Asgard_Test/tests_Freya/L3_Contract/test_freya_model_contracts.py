"""L3 Contract tests for Freya (frontend quality) models.

Imports models directly from submodules to avoid the playwright dependency
that is loaded by Asgard.Freya.__init__.
"""

import pytest
from pydantic import ValidationError

# Accessibility models (import directly — bypasses playwright)
from Asgard.Freya.Accessibility.models._accessibility_report_models import (
    AccessibilityConfig,
    AccessibilityReport,
    AccessibilityViolation,
)
from Asgard.Freya.Accessibility.models._accessibility_enums import (
    AccessibilityCategory,
    ViolationSeverity,
    WCAGLevel,
)

# Responsive models
from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    BreakpointIssue,
    BreakpointIssueType,
    BreakpointTestResult,
    BreakpointReport,
    MobileCompatibilityReport,
    ViewportReport,
)

# Visual models
from Asgard.Freya.Visual.models.visual_models import (
    DeviceConfig,
    ScreenshotConfig,
    ScreenshotResult,
    ComparisonConfig,
    VisualComparisonResult,
    RegressionReport,
)


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------
class TestAccessibilityConfigContract:
    def test_instantiates_with_defaults(self):
        config = AccessibilityConfig()
        assert config is not None

    def test_has_expected_fields(self):
        config = AccessibilityConfig()
        # Must exist as pydantic model
        assert hasattr(AccessibilityConfig, "model_fields")


class TestAccessibilityReportContract:
    def test_requires_url_and_wcag_level(self):
        with pytest.raises((ValidationError, TypeError)):
            AccessibilityReport()

    def test_instantiates_with_required_fields(self):
        report = AccessibilityReport(url="https://example.com", wcag_level="AA")
        assert report.url == "https://example.com"
        assert report.wcag_level == "AA"

    def test_has_violations_field(self):
        report = AccessibilityReport(url="https://example.com", wcag_level="AA")
        assert hasattr(report, "violations")
        assert isinstance(report.violations, list)

    def test_has_score_field(self):
        report = AccessibilityReport(url="https://example.com", wcag_level="AA")
        assert hasattr(report, "score")

    def test_has_passed_checks_field(self):
        report = AccessibilityReport(url="https://example.com", wcag_level="AA")
        assert hasattr(report, "passed_checks")


class TestAccessibilityViolationContract:
    def test_requires_multiple_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            AccessibilityViolation()

    def test_instantiates_with_required_fields(self):
        violation = AccessibilityViolation(
            id="wcag-1.4.3",
            wcag_reference="1.4.3",
            category=AccessibilityCategory.CONTRAST,
            severity=ViolationSeverity.SERIOUS,
            description="Low contrast",
            element_selector="p.body",
            suggested_fix="Increase contrast ratio",
        )
        assert violation.id == "wcag-1.4.3"

    def test_has_optional_element_html(self):
        violation = AccessibilityViolation(
            id="x",
            wcag_reference="1.1.1",
            category=AccessibilityCategory.IMAGES,
            severity=ViolationSeverity.CRITICAL,
            description="Missing alt",
            element_selector="img",
            suggested_fix="Add alt text",
        )
        assert hasattr(violation, "element_html")


# ---------------------------------------------------------------------------
# Responsive
# ---------------------------------------------------------------------------
class TestBreakpointContract:
    def test_requires_name_and_width(self):
        with pytest.raises((ValidationError, TypeError)):
            Breakpoint()

    def test_instantiates_with_required_fields(self):
        bp = Breakpoint(name="mobile", width=375)
        assert bp.name == "mobile"
        assert bp.width == 375

    def test_has_height_field(self):
        bp = Breakpoint(name="tablet", width=768)
        assert hasattr(bp, "height")

    def test_has_is_mobile_field(self):
        bp = Breakpoint(name="desktop", width=1440)
        assert hasattr(bp, "is_mobile")


class TestBreakpointTestResultContract:
    def test_requires_breakpoint(self):
        with pytest.raises((ValidationError, TypeError)):
            BreakpointTestResult()

    def test_instantiates_with_required_fields(self):
        bp = Breakpoint(name="mobile", width=375)
        result = BreakpointTestResult(breakpoint=bp)
        assert result.breakpoint.name == "mobile"

    def test_has_issues_field(self):
        bp = Breakpoint(name="mobile", width=375)
        result = BreakpointTestResult(breakpoint=bp)
        assert hasattr(result, "issues")
        assert isinstance(result.issues, list)


class TestBreakpointReportContract:
    def test_requires_url(self):
        with pytest.raises((ValidationError, TypeError)):
            BreakpointReport()

    def test_instantiates_with_url(self):
        report = BreakpointReport(url="https://example.com")
        assert report.url == "https://example.com"

    def test_has_tested_at_field(self):
        report = BreakpointReport(url="https://example.com")
        assert hasattr(report, "tested_at")


# ---------------------------------------------------------------------------
# Visual
# ---------------------------------------------------------------------------
class TestDeviceConfigContract:
    def test_requires_name_width_height(self):
        with pytest.raises((ValidationError, TypeError)):
            DeviceConfig()

    def test_instantiates_with_required_fields(self):
        device = DeviceConfig(name="iPhone 14", width=390, height=844)
        assert device.name == "iPhone 14"

    def test_has_is_mobile_field(self):
        device = DeviceConfig(name="iPhone 14", width=390, height=844)
        assert hasattr(device, "is_mobile")

    def test_has_device_scale_factor(self):
        device = DeviceConfig(name="iPhone 14", width=390, height=844)
        assert hasattr(device, "device_scale_factor")


class TestScreenshotConfigContract:
    def test_instantiates_with_defaults(self):
        config = ScreenshotConfig()
        assert config is not None

    def test_has_full_page_field(self):
        config = ScreenshotConfig()
        assert hasattr(config, "full_page")

    def test_has_format_field(self):
        config = ScreenshotConfig()
        assert hasattr(config, "format")


class TestScreenshotResultContract:
    def test_requires_url_and_file_path(self):
        with pytest.raises((ValidationError, TypeError)):
            ScreenshotResult()

    def test_instantiates_with_required_fields(self):
        result = ScreenshotResult(
            url="https://example.com",
            file_path="/tmp/screenshot.png",
            width=1280,
            height=800,
        )
        assert result.url == "https://example.com"

    def test_has_captured_at_field(self):
        result = ScreenshotResult(
            url="https://example.com",
            file_path="/tmp/screenshot.png",
            width=1280,
            height=800,
        )
        assert hasattr(result, "captured_at")


class TestComparisonConfigContract:
    def test_instantiates_with_defaults(self):
        config = ComparisonConfig()
        assert config is not None

    def test_has_model_fields(self):
        assert hasattr(ComparisonConfig, "model_fields")
