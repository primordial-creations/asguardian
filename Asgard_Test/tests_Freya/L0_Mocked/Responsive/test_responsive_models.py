"""
Freya L0 Mocked Tests - Responsive Models

Tests for responsive design models including Breakpoint, BreakpointIssue,
TouchTargetIssue, ViewportIssue, MobileCompatibilityIssue, and related reports.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    BreakpointIssue,
    BreakpointIssueType,
    BreakpointReport,
    BreakpointTestResult,
    COMMON_BREAKPOINTS,
    MobileCompatibilityIssue,
    MobileCompatibilityIssueType,
    MobileCompatibilityReport,
    MOBILE_DEVICES,
    TouchTargetIssue,
    TouchTargetReport,
    ViewportIssue,
    ViewportIssueType,
    ViewportReport,
)


# =============================================================================
# Test Breakpoint Model
# =============================================================================

class TestBreakpoint:
    """Tests for Breakpoint model."""

    @pytest.mark.L0
    def test_create_minimal_breakpoint(self):
        """Test creating breakpoint with minimal required fields."""
        bp = Breakpoint(name="test", width=320)
        assert bp.name == "test"
        assert bp.width == 320
        assert bp.height == 800
        assert bp.is_mobile is False
        assert bp.device_scale_factor == 1.0

    @pytest.mark.L0
    def test_create_full_breakpoint(self):
        """Test creating breakpoint with all fields."""
        bp = Breakpoint(
            name="mobile",
            width=375,
            height=667,
            is_mobile=True,
            device_scale_factor=2.0,
        )
        assert bp.name == "mobile"
        assert bp.width == 375
        assert bp.height == 667
        assert bp.is_mobile is True
        assert bp.device_scale_factor == 2.0

    @pytest.mark.L0
    def test_breakpoint_serialization(self):
        """Test breakpoint model serialization."""
        bp = Breakpoint(
            name="tablet",
            width=768,
            height=1024,
            is_mobile=True,
            device_scale_factor=2.0,
        )
        data = bp.model_dump()
        assert data["name"] == "tablet"
        assert data["width"] == 768
        assert data["height"] == 1024
        assert data["is_mobile"] is True
        assert data["device_scale_factor"] == 2.0


class TestCommonBreakpoints:
    """Tests for COMMON_BREAKPOINTS constant."""

    @pytest.mark.L0
    def test_common_breakpoints_exists(self):
        """Test that COMMON_BREAKPOINTS is defined."""
        assert COMMON_BREAKPOINTS is not None
        assert isinstance(COMMON_BREAKPOINTS, list)
        assert len(COMMON_BREAKPOINTS) > 0

    @pytest.mark.L0
    def test_common_breakpoints_has_mobile(self):
        """Test that common breakpoints include mobile sizes."""
        mobile_breakpoints = [bp for bp in COMMON_BREAKPOINTS if bp.is_mobile]
        assert len(mobile_breakpoints) > 0

    @pytest.mark.L0
    def test_common_breakpoints_has_desktop(self):
        """Test that common breakpoints include desktop sizes."""
        desktop_breakpoints = [bp for bp in COMMON_BREAKPOINTS if not bp.is_mobile]
        assert len(desktop_breakpoints) > 0

    @pytest.mark.L0
    def test_common_breakpoints_sorted_by_width(self):
        """Test that breakpoints are sorted by width."""
        widths = [bp.width for bp in COMMON_BREAKPOINTS]
        assert widths == sorted(widths)


class TestMobileDevices:
    """Tests for MOBILE_DEVICES constant."""

    @pytest.mark.L0
    def test_mobile_devices_exists(self):
        """Test that MOBILE_DEVICES is defined."""
        assert MOBILE_DEVICES is not None
        assert isinstance(MOBILE_DEVICES, dict)
        assert len(MOBILE_DEVICES) > 0

    @pytest.mark.L0
    def test_mobile_devices_has_iphone(self):
        """Test that mobile devices include iPhone models."""
        iphone_keys = [k for k in MOBILE_DEVICES.keys() if "iphone" in k.lower()]
        assert len(iphone_keys) > 0

    @pytest.mark.L0
    def test_mobile_devices_has_android(self):
        """Test that mobile devices include Android models."""
        android_keys = [k for k in MOBILE_DEVICES.keys() if "pixel" in k.lower() or "galaxy" in k.lower()]
        assert len(android_keys) > 0

    @pytest.mark.L0
    def test_mobile_devices_all_are_mobile(self):
        """Test that all devices are marked as mobile."""
        for device in MOBILE_DEVICES.values():
            assert device.is_mobile is True


# =============================================================================
# Test BreakpointIssueType Enum
# =============================================================================

class TestBreakpointIssueType:
    """Tests for BreakpointIssueType enum."""

    @pytest.mark.L0
    def test_horizontal_scroll_value(self):
        """Test HORIZONTAL_SCROLL enum value."""
        assert BreakpointIssueType.HORIZONTAL_SCROLL.value == "horizontal_scroll"

    @pytest.mark.L0
    def test_content_overflow_value(self):
        """Test CONTENT_OVERFLOW enum value."""
        assert BreakpointIssueType.CONTENT_OVERFLOW.value == "content_overflow"

    @pytest.mark.L0
    def test_hidden_content_value(self):
        """Test HIDDEN_CONTENT enum value."""
        assert BreakpointIssueType.HIDDEN_CONTENT.value == "hidden_content"

    @pytest.mark.L0
    def test_overlapping_elements_value(self):
        """Test OVERLAPPING_ELEMENTS enum value."""
        assert BreakpointIssueType.OVERLAPPING_ELEMENTS.value == "overlapping_elements"

    @pytest.mark.L0
    def test_text_truncation_value(self):
        """Test TEXT_TRUNCATION enum value."""
        assert BreakpointIssueType.TEXT_TRUNCATION.value == "text_truncation"

    @pytest.mark.L0
    def test_image_scaling_value(self):
        """Test IMAGE_SCALING enum value."""
        assert BreakpointIssueType.IMAGE_SCALING.value == "image_scaling"

    @pytest.mark.L0
    def test_layout_shift_value(self):
        """Test LAYOUT_SHIFT enum value."""
        assert BreakpointIssueType.LAYOUT_SHIFT.value == "layout_shift"

    @pytest.mark.L0
    def test_missing_media_query_value(self):
        """Test MISSING_MEDIA_QUERY enum value."""
        assert BreakpointIssueType.MISSING_MEDIA_QUERY.value == "missing_media_query"


# =============================================================================
# Test BreakpointIssue Model
# =============================================================================

class TestBreakpointIssue:
    """Tests for BreakpointIssue model."""

    @pytest.mark.L0
    def test_create_breakpoint_issue(self):
        """Test creating a breakpoint issue."""
        issue = BreakpointIssue(
            issue_type=BreakpointIssueType.HORIZONTAL_SCROLL,
            breakpoint="mobile-md",
            viewport_width=375,
            element_selector="div.container",
            description="Element extends beyond viewport",
            severity="serious",
            suggested_fix="Use max-width: 100%",
        )
        assert issue.issue_type == BreakpointIssueType.HORIZONTAL_SCROLL
        assert issue.breakpoint == "mobile-md"
        assert issue.viewport_width == 375
        assert issue.element_selector == "div.container"
        assert issue.description == "Element extends beyond viewport"
        assert issue.severity == "serious"
        assert issue.suggested_fix == "Use max-width: 100%"
        assert issue.screenshot_path is None

    @pytest.mark.L0
    def test_breakpoint_issue_with_screenshot(self):
        """Test creating issue with screenshot path."""
        issue = BreakpointIssue(
            issue_type=BreakpointIssueType.CONTENT_OVERFLOW,
            breakpoint="tablet",
            viewport_width=768,
            element_selector="div.content",
            description="Content overflows container",
            severity="moderate",
            suggested_fix="Add overflow: hidden",
            screenshot_path="/path/to/screenshot.png",
        )
        assert issue.screenshot_path == "/path/to/screenshot.png"


# =============================================================================
# Test BreakpointTestResult Model
# =============================================================================

class TestBreakpointTestResult:
    """Tests for BreakpointTestResult model."""

    @pytest.mark.L0
    def test_create_test_result_minimal(self):
        """Test creating test result with minimal data."""
        bp = Breakpoint(name="mobile", width=375)
        result = BreakpointTestResult(breakpoint=bp)
        assert result.breakpoint == bp
        assert result.issues == []
        assert result.screenshot_path is None
        assert result.page_width == 0
        assert result.has_horizontal_scroll is False

    @pytest.mark.L0
    def test_create_test_result_with_issues(self):
        """Test creating test result with issues."""
        bp = Breakpoint(name="mobile", width=375)
        issue = BreakpointIssue(
            issue_type=BreakpointIssueType.HORIZONTAL_SCROLL,
            breakpoint="mobile",
            viewport_width=375,
            element_selector="div",
            description="Test issue",
            severity="serious",
            suggested_fix="Fix it",
        )
        result = BreakpointTestResult(
            breakpoint=bp,
            issues=[issue],
            screenshot_path="/test.png",
            page_width=400,
            has_horizontal_scroll=True,
        )
        assert len(result.issues) == 1
        assert result.issues[0] == issue
        assert result.page_width == 400
        assert result.has_horizontal_scroll is True


# =============================================================================
# Test BreakpointReport Model
# =============================================================================

class TestBreakpointReport:
    """Tests for BreakpointReport model."""

    @pytest.mark.L0
    def test_create_minimal_report(self):
        """Test creating minimal breakpoint report."""
        report = BreakpointReport(url="https://example.com")
        assert report.url == "https://example.com"
        assert report.tested_at is not None
        assert report.breakpoints_tested == []
        assert report.total_issues == 0
        assert report.results == []
        assert report.breakpoint_issues == {}
        assert report.screenshots == {}

    @pytest.mark.L0
    def test_report_has_issues_property(self):
        """Test has_issues property."""
        report1 = BreakpointReport(url="https://example.com", total_issues=0)
        assert report1.has_issues is False

        report2 = BreakpointReport(url="https://example.com", total_issues=5)
        assert report2.has_issues is True

    @pytest.mark.L0
    def test_create_full_report(self):
        """Test creating full breakpoint report."""
        bp = Breakpoint(name="mobile", width=375)
        issue = BreakpointIssue(
            issue_type=BreakpointIssueType.HORIZONTAL_SCROLL,
            breakpoint="mobile",
            viewport_width=375,
            element_selector="div",
            description="Test",
            severity="serious",
            suggested_fix="Fix",
        )
        result = BreakpointTestResult(breakpoint=bp, issues=[issue])
        report = BreakpointReport(
            url="https://example.com",
            breakpoints_tested=["mobile"],
            total_issues=1,
            results=[result],
            breakpoint_issues={"mobile": [issue]},
            screenshots={"mobile": "/test.png"},
        )
        assert report.total_issues == 1
        assert len(report.results) == 1
        assert "mobile" in report.breakpoint_issues


# =============================================================================
# Test TouchTargetIssue Model
# =============================================================================

class TestTouchTargetIssue:
    """Tests for TouchTargetIssue model."""

    @pytest.mark.L0
    def test_create_touch_target_issue(self):
        """Test creating touch target issue."""
        issue = TouchTargetIssue(
            element_selector="button.submit",
            element_type="button",
            width=30.0,
            height=30.0,
            min_required=44,
            description="Button too small",
            severity="serious",
            suggested_fix="Increase to 44x44px",
        )
        assert issue.element_selector == "button.submit"
        assert issue.element_type == "button"
        assert issue.width == 30.0
        assert issue.height == 30.0
        assert issue.min_required == 44
        assert issue.severity == "serious"

    @pytest.mark.L0
    def test_touch_target_issue_defaults(self):
        """Test touch target issue default values."""
        issue = TouchTargetIssue(
            element_selector="a",
            element_type="link",
            width=40.0,
            height=40.0,
            description="Link too small",
            severity="moderate",
            suggested_fix="Increase size",
        )
        assert issue.min_required == 44


# =============================================================================
# Test TouchTargetReport Model
# =============================================================================

class TestTouchTargetReport:
    """Tests for TouchTargetReport model."""

    @pytest.mark.L0
    def test_create_minimal_touch_report(self):
        """Test creating minimal touch target report."""
        report = TouchTargetReport(
            url="https://example.com",
            viewport_width=375,
            viewport_height=667,
        )
        assert report.url == "https://example.com"
        assert report.viewport_width == 375
        assert report.viewport_height == 667
        assert report.total_interactive_elements == 0
        assert report.passing_count == 0
        assert report.failing_count == 0
        assert report.issues == []
        assert report.min_touch_size == 44

    @pytest.mark.L0
    def test_touch_report_has_issues_property(self):
        """Test has_issues property."""
        report1 = TouchTargetReport(
            url="https://example.com",
            viewport_width=375,
            viewport_height=667,
            failing_count=0,
        )
        assert report1.has_issues is False

        report2 = TouchTargetReport(
            url="https://example.com",
            viewport_width=375,
            viewport_height=667,
            failing_count=5,
        )
        assert report2.has_issues is True

    @pytest.mark.L0
    def test_create_full_touch_report(self):
        """Test creating full touch target report."""
        issue = TouchTargetIssue(
            element_selector="button",
            element_type="button",
            width=30.0,
            height=30.0,
            description="Too small",
            severity="serious",
            suggested_fix="Increase size",
        )
        report = TouchTargetReport(
            url="https://example.com",
            viewport_width=375,
            viewport_height=667,
            total_interactive_elements=10,
            passing_count=9,
            failing_count=1,
            issues=[issue],
            min_touch_size=44,
        )
        assert report.total_interactive_elements == 10
        assert report.passing_count == 9
        assert report.failing_count == 1
        assert len(report.issues) == 1


# =============================================================================
# Test ViewportIssueType Enum
# =============================================================================

class TestViewportIssueType:
    """Tests for ViewportIssueType enum."""

    @pytest.mark.L0
    def test_missing_viewport_meta_value(self):
        """Test MISSING_VIEWPORT_META enum value."""
        assert ViewportIssueType.MISSING_VIEWPORT_META.value == "missing_viewport_meta"

    @pytest.mark.L0
    def test_fixed_width_viewport_value(self):
        """Test FIXED_WIDTH_VIEWPORT enum value."""
        assert ViewportIssueType.FIXED_WIDTH_VIEWPORT.value == "fixed_width_viewport"

    @pytest.mark.L0
    def test_user_scalable_disabled_value(self):
        """Test USER_SCALABLE_DISABLED enum value."""
        assert ViewportIssueType.USER_SCALABLE_DISABLED.value == "user_scalable_disabled"

    @pytest.mark.L0
    def test_maximum_scale_too_low_value(self):
        """Test MAXIMUM_SCALE_TOO_LOW enum value."""
        assert ViewportIssueType.MAXIMUM_SCALE_TOO_LOW.value == "maximum_scale_too_low"

    @pytest.mark.L0
    def test_content_wider_than_viewport_value(self):
        """Test CONTENT_WIDER_THAN_VIEWPORT enum value."""
        assert ViewportIssueType.CONTENT_WIDER_THAN_VIEWPORT.value == "content_wider_than_viewport"

    @pytest.mark.L0
    def test_text_too_small_value(self):
        """Test TEXT_TOO_SMALL enum value."""
        assert ViewportIssueType.TEXT_TOO_SMALL.value == "text_too_small"


# =============================================================================
# Test ViewportIssue Model
# =============================================================================

class TestViewportIssue:
    """Tests for ViewportIssue model."""

    @pytest.mark.L0
    def test_create_viewport_issue(self):
        """Test creating viewport issue."""
        issue = ViewportIssue(
            issue_type=ViewportIssueType.MISSING_VIEWPORT_META,
            description="Missing viewport meta tag",
            severity="critical",
            suggested_fix='Add <meta name="viewport" content="width=device-width">',
        )
        assert issue.issue_type == ViewportIssueType.MISSING_VIEWPORT_META
        assert issue.description == "Missing viewport meta tag"
        assert issue.severity == "critical"
        assert issue.current_value is None
        assert issue.wcag_reference is None

    @pytest.mark.L0
    def test_viewport_issue_with_wcag(self):
        """Test creating viewport issue with WCAG reference."""
        issue = ViewportIssue(
            issue_type=ViewportIssueType.USER_SCALABLE_DISABLED,
            description="User zooming disabled",
            severity="serious",
            current_value="user-scalable=no",
            suggested_fix="Remove user-scalable=no",
            wcag_reference="1.4.4",
        )
        assert issue.current_value == "user-scalable=no"
        assert issue.wcag_reference == "1.4.4"


# =============================================================================
# Test ViewportReport Model
# =============================================================================

class TestViewportReport:
    """Tests for ViewportReport model."""

    @pytest.mark.L0
    def test_create_minimal_viewport_report(self):
        """Test creating minimal viewport report."""
        report = ViewportReport(url="https://example.com")
        assert report.url == "https://example.com"
        assert report.tested_at is not None
        assert report.viewport_meta is None
        assert report.content_width == 0
        assert report.viewport_width == 0
        assert report.has_horizontal_scroll is False
        assert report.issues == []
        assert report.text_sizes == {}
        assert report.minimum_text_size is None

    @pytest.mark.L0
    def test_viewport_report_has_issues_property(self):
        """Test has_issues property."""
        report1 = ViewportReport(url="https://example.com", issues=[])
        assert report1.has_issues is False

        issue = ViewportIssue(
            issue_type=ViewportIssueType.MISSING_VIEWPORT_META,
            description="Missing",
            severity="critical",
            suggested_fix="Add meta",
        )
        report2 = ViewportReport(url="https://example.com", issues=[issue])
        assert report2.has_issues is True

    @pytest.mark.L0
    def test_create_full_viewport_report(self):
        """Test creating full viewport report."""
        issue = ViewportIssue(
            issue_type=ViewportIssueType.TEXT_TOO_SMALL,
            description="Text too small",
            severity="moderate",
            suggested_fix="Increase font size",
        )
        report = ViewportReport(
            url="https://example.com",
            viewport_meta="width=device-width, initial-scale=1",
            content_width=375,
            viewport_width=375,
            has_horizontal_scroll=False,
            issues=[issue],
            text_sizes={"12px": 5, "16px": 10},
            minimum_text_size=12.0,
        )
        assert report.viewport_meta == "width=device-width, initial-scale=1"
        assert report.content_width == 375
        assert report.minimum_text_size == 12.0
        assert len(report.text_sizes) == 2


# =============================================================================
# Test MobileCompatibilityIssueType Enum
# =============================================================================

class TestMobileCompatibilityIssueType:
    """Tests for MobileCompatibilityIssueType enum."""

    @pytest.mark.L0
    def test_flash_content_value(self):
        """Test FLASH_CONTENT enum value."""
        assert MobileCompatibilityIssueType.FLASH_CONTENT.value == "flash_content"

    @pytest.mark.L0
    def test_fixed_positioning_value(self):
        """Test FIXED_POSITIONING enum value."""
        assert MobileCompatibilityIssueType.FIXED_POSITIONING.value == "fixed_positioning"

    @pytest.mark.L0
    def test_hover_dependent_value(self):
        """Test HOVER_DEPENDENT enum value."""
        assert MobileCompatibilityIssueType.HOVER_DEPENDENT.value == "hover_dependent"

    @pytest.mark.L0
    def test_small_text_value(self):
        """Test SMALL_TEXT enum value."""
        assert MobileCompatibilityIssueType.SMALL_TEXT.value == "small_text"

    @pytest.mark.L0
    def test_unplayable_media_value(self):
        """Test UNPLAYABLE_MEDIA enum value."""
        assert MobileCompatibilityIssueType.UNPLAYABLE_MEDIA.value == "unplayable_media"

    @pytest.mark.L0
    def test_slow_loading_value(self):
        """Test SLOW_LOADING enum value."""
        assert MobileCompatibilityIssueType.SLOW_LOADING.value == "slow_loading"

    @pytest.mark.L0
    def test_incompatible_plugin_value(self):
        """Test INCOMPATIBLE_PLUGIN enum value."""
        assert MobileCompatibilityIssueType.INCOMPATIBLE_PLUGIN.value == "incompatible_plugin"


# =============================================================================
# Test MobileCompatibilityIssue Model
# =============================================================================

class TestMobileCompatibilityIssue:
    """Tests for MobileCompatibilityIssue model."""

    @pytest.mark.L0
    def test_create_mobile_compatibility_issue(self):
        """Test creating mobile compatibility issue."""
        issue = MobileCompatibilityIssue(
            issue_type=MobileCompatibilityIssueType.FLASH_CONTENT,
            description="Page contains Flash elements",
            severity="critical",
            suggested_fix="Replace with HTML5",
        )
        assert issue.issue_type == MobileCompatibilityIssueType.FLASH_CONTENT
        assert issue.description == "Page contains Flash elements"
        assert issue.severity == "critical"
        assert issue.element_selector is None
        assert issue.affected_devices == []

    @pytest.mark.L0
    def test_mobile_issue_with_devices(self):
        """Test creating issue with affected devices."""
        issue = MobileCompatibilityIssue(
            issue_type=MobileCompatibilityIssueType.SMALL_TEXT,
            element_selector="p.content",
            description="Text too small",
            severity="moderate",
            suggested_fix="Use larger font",
            affected_devices=["iphone-14", "pixel-7"],
        )
        assert issue.element_selector == "p.content"
        assert len(issue.affected_devices) == 2
        assert "iphone-14" in issue.affected_devices


# =============================================================================
# Test MobileCompatibilityReport Model
# =============================================================================

class TestMobileCompatibilityReport:
    """Tests for MobileCompatibilityReport model."""

    @pytest.mark.L0
    def test_create_minimal_mobile_report(self):
        """Test creating minimal mobile compatibility report."""
        report = MobileCompatibilityReport(url="https://example.com")
        assert report.url == "https://example.com"
        assert report.tested_at is not None
        assert report.devices_tested == []
        assert report.issues == []
        assert report.load_time_ms is None
        assert report.page_size_bytes is None
        assert report.resource_count == 0
        assert report.mobile_friendly_score is None
        assert not report.is_complete
        assert report.device_results == {}

    @pytest.mark.L0
    def test_mobile_report_has_issues_property(self):
        """Test has_issues property."""
        report1 = MobileCompatibilityReport(url="https://example.com", issues=[])
        assert report1.has_issues is False

        issue = MobileCompatibilityIssue(
            issue_type=MobileCompatibilityIssueType.FLASH_CONTENT,
            description="Flash detected",
            severity="critical",
            suggested_fix="Remove Flash",
        )
        report2 = MobileCompatibilityReport(url="https://example.com", issues=[issue])
        assert report2.has_issues is True

    @pytest.mark.L0
    def test_create_full_mobile_report(self):
        """Test creating full mobile compatibility report."""
        issue = MobileCompatibilityIssue(
            issue_type=MobileCompatibilityIssueType.SLOW_LOADING,
            description="Slow loading time",
            severity="moderate",
            suggested_fix="Optimize resources",
            affected_devices=["iphone-14"],
        )
        report = MobileCompatibilityReport(
            url="https://example.com",
            devices_tested=["iphone-14", "pixel-7"],
            issues=[issue],
            load_time_ms=3500,
            page_size_bytes=2048000,
            resource_count=45,
            mobile_friendly_score=85.0,
            check_outcomes={device: {name: {"status": "succeeded"}
                            for name in ("navigation", "flash", "hover", "text", "fixed", "resources")}
                            for device in ("iphone-14", "pixel-7")},
            device_results={"iphone-14": {"load_time_ms": 3500}},
        )
        assert len(report.devices_tested) == 2
        assert report.load_time_ms == 3500
        assert report.page_size_bytes == 2048000
        assert report.resource_count == 45
        assert report.mobile_friendly_score == 85.0
        assert "iphone-14" in report.device_results


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
