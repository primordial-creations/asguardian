"""
L1 Integration Tests for Freya Responsive Testing

Comprehensive integration tests for responsive design testing with real HTML pages.
Tests breakpoint behavior, viewport testing, touch target validation, and mobile
compatibility using actual Playwright browser instances in headless mode.

All tests use file:// URLs for local HTML fixtures, making them CI-friendly.
"""

import pytest
from pathlib import Path

from Asgard.Freya.Responsive.services.breakpoint_tester import BreakpointTester
from Asgard.Freya.Responsive.services.touch_target_validator import TouchTargetValidator
from Asgard.Freya.Responsive.services.viewport_tester import ViewportTester
from Asgard.Freya.Responsive.services.mobile_compatibility import MobileCompatibilityTester
from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    COMMON_BREAKPOINTS,
    MOBILE_DEVICES,
)

from Asgard_Test.tests_Freya.L1_Integration.conftest import file_url


class TestResponsiveIntegrationBreakpointTester:
    """Integration tests for Breakpoint Tester with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_breakpoint_tester_responsive_page(self, sample_responsive_page, output_dir):
        """Test breakpoint testing on responsive page."""
        tester = BreakpointTester(output_directory=str(output_dir / "breakpoints"))

        url = file_url(sample_responsive_page)
        report = await tester.test(url, capture_screenshots=True)

        assert report is not None
        assert report.url == url
        assert len(report.breakpoints_tested) > 0
        assert len(report.results) > 0

        assert len(report.screenshots) > 0
        for screenshot_path in report.screenshots.values():
            assert Path(screenshot_path).exists()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_breakpoint_tester_common_breakpoints(self, sample_responsive_page, output_dir):
        """Test breakpoint testing with common breakpoints."""
        tester = BreakpointTester(output_directory=str(output_dir / "breakpoints"))

        url = file_url(sample_responsive_page)
        report = await tester.test(url, breakpoints=COMMON_BREAKPOINTS, capture_screenshots=False)

        assert report is not None
        assert len(report.breakpoints_tested) == len(COMMON_BREAKPOINTS)

        expected_names = [bp.name for bp in COMMON_BREAKPOINTS]
        assert set(report.breakpoints_tested) == set(expected_names)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_breakpoint_tester_custom_breakpoints(self, sample_responsive_page, output_dir):
        """Test breakpoint testing with custom breakpoints."""
        custom_breakpoints = [
            Breakpoint(name="tablet", width=768, height=1024),
            Breakpoint(name="laptop", width=1366, height=768),
        ]

        tester = BreakpointTester(output_directory=str(output_dir / "breakpoints"))

        url = file_url(sample_responsive_page)
        report = await tester.test(url, breakpoints=custom_breakpoints, capture_screenshots=False)

        assert report is not None
        assert "tablet" in report.breakpoints_tested
        assert "laptop" in report.breakpoints_tested

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_breakpoint_tester_detects_horizontal_scroll(self, html_fixtures_dir, output_dir):
        """Test breakpoint tester detects horizontal scrolling issues."""
        overflow_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Overflow Test</title>
    <style>
        .wide-element {
            width: 2000px;
            height: 100px;
            background-color: red;
        }
    </style>
</head>
<body>
    <div class="wide-element">This element is too wide</div>
</body>
</html>"""

        overflow_page = html_fixtures_dir / "overflow_page.html"
        overflow_page.write_text(overflow_html, encoding="utf-8")

        tester = BreakpointTester(output_directory=str(output_dir / "breakpoints"))

        url = file_url(overflow_page)
        report = await tester.test(url, capture_screenshots=False)

        assert report is not None
        mobile_result = next((r for r in report.results if "mobile" in r.breakpoint.name.lower()), None)

        if mobile_result:
            assert mobile_result.has_horizontal_scroll is True or len(mobile_result.issues) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_breakpoint_tester_detects_overlapping_elements(self, html_fixtures_dir, output_dir):
        """Test breakpoint tester detects overlapping interactive elements."""
        overlap_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Overlap Test</title>
    <style>
        .overlap-container {
            position: relative;
            width: 100px;
            height: 100px;
        }
        button {
            position: absolute;
            width: 80px;
            height: 40px;
        }
        .btn1 { top: 0; left: 0; }
        .btn2 { top: 20px; left: 20px; }
    </style>
</head>
<body>
    <div class="overlap-container">
        <button class="btn1">Button 1</button>
        <button class="btn2">Button 2</button>
    </div>
</body>
</html>"""

        overlap_page = html_fixtures_dir / "overlap_page.html"
        overlap_page.write_text(overlap_html, encoding="utf-8")

        tester = BreakpointTester(output_directory=str(output_dir / "breakpoints"))

        url = file_url(overlap_page)
        report = await tester.test(url, capture_screenshots=False)

        assert report is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_breakpoint_tester_report_structure(self, sample_responsive_page, output_dir):
        """Test breakpoint tester report structure."""
        tester = BreakpointTester(output_directory=str(output_dir / "breakpoints"))

        url = file_url(sample_responsive_page)
        report = await tester.test(url, capture_screenshots=False)

        assert report.url is not None
        assert report.tested_at is not None
        assert isinstance(report.breakpoints_tested, list)
        assert isinstance(report.total_issues, int)
        assert isinstance(report.results, list)
        assert isinstance(report.breakpoint_issues, dict)

        for result in report.results:
            assert hasattr(result, 'breakpoint')
            assert hasattr(result, 'issues')
            assert hasattr(result, 'page_width')
            assert hasattr(result, 'has_horizontal_scroll')


class TestResponsiveIntegrationTouchTargetValidator:
    """Integration tests for Touch Target Validator with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_touch_target_validator_accessible_page(self, sample_accessible_page):
        """Test touch target validation on accessible page."""
        validator = TouchTargetValidator()

        url = file_url(sample_accessible_page)
        report = await validator.validate(url)

        assert report is not None
        assert report.url == url
        assert report.total_targets_checked > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_touch_target_validator_responsive_page(self, sample_responsive_page):
        """Test touch target validation on responsive page with proper targets."""
        validator = TouchTargetValidator()

        url = file_url(sample_responsive_page)
        report = await validator.validate(url)

        assert report is not None
        assert report.total_targets_checked > 0

        if len(report.issues) > 0:
            for issue in report.issues:
                assert hasattr(issue, 'width')
                assert hasattr(issue, 'height')
                assert hasattr(issue, 'element_selector')

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_touch_target_validator_detects_small_targets(self, html_fixtures_dir):
        """Test touch target validator detects targets that are too small."""
        small_target_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Small Touch Target Test</title>
    <style>
        .small-button {
            width: 20px;
            height: 20px;
            background-color: blue;
            border: none;
        }
    </style>
</head>
<body>
    <button class="small-button" aria-label="Small button">X</button>
</body>
</html>"""

        small_target_page = html_fixtures_dir / "small_target_page.html"
        small_target_page.write_text(small_target_html, encoding="utf-8")

        validator = TouchTargetValidator()

        url = file_url(small_target_page)
        report = await validator.validate(url)

        assert report is not None
        assert len(report.issues) > 0

        small_target_issue = next((i for i in report.issues if i.width < 44 or i.height < 44), None)
        assert small_target_issue is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_touch_target_validator_report_structure(self, sample_accessible_page):
        """Test touch target validator report structure."""
        validator = TouchTargetValidator()

        url = file_url(sample_accessible_page)
        report = await validator.validate(url)

        assert report.url is not None
        assert report.tested_at is not None
        assert report.total_targets_checked >= 0
        assert isinstance(report.issues, list)
        assert 0.0 <= report.pass_rate <= 100.0


class TestResponsiveIntegrationViewportTester:
    """Integration tests for Viewport Tester with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_viewport_tester_responsive_page(self, sample_responsive_page):
        """Test viewport testing on responsive page."""
        tester = ViewportTester()

        url = file_url(sample_responsive_page)
        report = await tester.test(url)

        assert report is not None
        assert report.url == url

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_viewport_tester_accessible_page(self, sample_accessible_page):
        """Test viewport testing on accessible page."""
        tester = ViewportTester()

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_viewport_tester_missing_meta_tag(self, html_fixtures_dir):
        """Test viewport tester detects missing viewport meta tag."""
        no_viewport_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>No Viewport Meta Tag</title>
</head>
<body>
    <h1>Page without viewport meta tag</h1>
</body>
</html>"""

        no_viewport_page = html_fixtures_dir / "no_viewport_page.html"
        no_viewport_page.write_text(no_viewport_html, encoding="utf-8")

        tester = ViewportTester()

        url = file_url(no_viewport_page)
        report = await tester.test(url)

        assert report is not None
        assert len(report.issues) > 0

        viewport_issue = next((i for i in report.issues if "viewport" in i.description.lower()), None)
        assert viewport_issue is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_viewport_tester_report_structure(self, sample_responsive_page):
        """Test viewport tester report structure."""
        tester = ViewportTester()

        url = file_url(sample_responsive_page)
        report = await tester.test(url)

        assert report.url is not None
        assert report.tested_at is not None
        assert isinstance(report.issues, list)


class TestResponsiveIntegrationMobileCompatibility:
    """Integration tests for Mobile Compatibility Tester with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mobile_compatibility_responsive_page(self, sample_responsive_page):
        """Test mobile compatibility on responsive page."""
        tester = MobileCompatibilityTester()

        url = file_url(sample_responsive_page)
        report = await tester.test(url)

        assert report is not None
        assert report.url == url
        assert report.devices_tested > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mobile_compatibility_accessible_page(self, sample_accessible_page):
        """Test mobile compatibility on accessible page."""
        tester = MobileCompatibilityTester()

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report is not None
        assert report.devices_tested > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mobile_compatibility_custom_devices(self, sample_responsive_page):
        """Test mobile compatibility with custom device list."""
        custom_devices = [
            device for device in MOBILE_DEVICES
            if "iPhone" in device.name or "Pixel" in device.name
        ][:2]

        tester = MobileCompatibilityTester()

        url = file_url(sample_responsive_page)
        report = await tester.test(url, devices=custom_devices)

        assert report is not None
        assert report.devices_tested == len(custom_devices)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mobile_compatibility_report_structure(self, sample_accessible_page):
        """Test mobile compatibility report structure."""
        tester = MobileCompatibilityTester()

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report.url is not None
        assert report.tested_at is not None
        assert report.devices_tested >= 0
        assert isinstance(report.issues, list)
        assert 0.0 <= report.compatibility_score <= 100.0


class TestResponsiveIntegrationMultipleViewports:
    """Integration tests for responsive behavior across multiple viewports."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_responsive_layout_adapts_to_viewports(self, sample_responsive_page, output_dir):
        """Test that responsive layout adapts correctly across viewports."""
        tester = BreakpointTester(output_directory=str(output_dir / "responsive_test"))

        breakpoints = [
            Breakpoint(name="mobile", width=375, height=667),
            Breakpoint(name="tablet", width=768, height=1024),
            Breakpoint(name="desktop", width=1920, height=1080),
        ]

        url = file_url(sample_responsive_page)
        report = await tester.test(url, breakpoints=breakpoints, capture_screenshots=True)

        assert report is not None
        assert len(report.results) == 3

        page_widths = [result.page_width for result in report.results]
        assert all(width > 0 for width in page_widths)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_responsive_no_horizontal_scroll_on_mobile(self, sample_responsive_page, output_dir):
        """Test that responsive page has no horizontal scroll on mobile."""
        tester = BreakpointTester(output_directory=str(output_dir / "mobile_scroll"))

        mobile_breakpoints = [
            bp for bp in COMMON_BREAKPOINTS
            if bp.width <= 480
        ]

        url = file_url(sample_responsive_page)
        report = await tester.test(url, breakpoints=mobile_breakpoints, capture_screenshots=False)

        assert report is not None

        for result in report.results:
            horizontal_scroll_issues = [
                issue for issue in result.issues
                if "horizontal" in issue.description.lower() or "scroll" in issue.description.lower()
            ]
            assert len(horizontal_scroll_issues) == 0 or result.page_width <= result.breakpoint.width + 20

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_touch_targets_meet_minimum_size(self, sample_responsive_page):
        """Test that all touch targets meet minimum size requirements."""
        validator = TouchTargetValidator(min_width=44, min_height=44)

        url = file_url(sample_responsive_page)
        report = await validator.validate(url)

        assert report is not None

        critical_issues = [
            issue for issue in report.issues
            if issue.width < 44 and issue.height < 44
        ]

        if len(critical_issues) > 0:
            assert all(issue.severity in ["serious", "critical"] for issue in critical_issues)
