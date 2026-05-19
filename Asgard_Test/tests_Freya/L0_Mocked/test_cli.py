"""
L0 Unit Tests for Freya CLI

Comprehensive tests for CLI functionality including argument parsing,
command execution, and output formatting.
"""

import pytest
import argparse
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
from datetime import datetime

from Asgard.Freya.cli._parser import create_parser
from Asgard.Freya.cli._formatters import (
    format_accessibility_text,
    format_accessibility_markdown,
    format_accessibility_html,
    format_contrast_text,
    format_keyboard_text,
    format_aria_text,
    format_screen_reader_text,
    format_layout_text,
    format_style_text,
    format_breakpoint_text,
    format_touch_text,
    format_viewport_text,
    format_mobile_text,
    format_unified_text,
)
from Asgard.Freya.cli._handlers_accessibility import (
    run_accessibility_audit,
    run_contrast_check,
    run_keyboard_test,
    run_aria_validation,
    run_screen_reader_test,
)
from Asgard.Freya.cli._handlers_visual_responsive import (
    run_visual_capture,
    run_visual_compare,
    run_layout_validation,
    run_style_validation,
    run_breakpoint_test,
    run_touch_validation,
    run_viewport_test,
    run_mobile_test,
)
from Asgard.Freya.cli._handlers_images_integration import (
    run_unified_test,
    run_baseline_update,
    run_baseline_compare,
    run_baseline_list,
    run_baseline_delete,
    run_crawl,
)

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    WCAGLevel,
    ViolationSeverity,
)


class TestCreateParser:
    """Test argument parser creation."""

    def test_create_parser_returns_parser(self):
        """Test creating parser returns ArgumentParser instance."""
        parser = create_parser()

        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "freya"

    def test_parser_has_version_argument(self):
        """Test parser has version argument."""
        parser = create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])

        assert exc_info.value.code == 0

    def test_parser_has_verbose_argument(self):
        """Test parser has verbose argument."""
        parser = create_parser()

        args = parser.parse_args(["--verbose", "test", "https://example.com"])

        assert args.verbose is True

    def test_parser_accessibility_command(self):
        """Test parser handles accessibility commands."""
        parser = create_parser()

        args = parser.parse_args(["accessibility", "audit", "https://example.com"])

        assert args.command == "accessibility"
        assert args.accessibility_command == "audit"
        assert args.url == "https://example.com"

    def test_parser_visual_command(self):
        """Test parser handles visual commands."""
        parser = create_parser()

        args = parser.parse_args(["visual", "capture", "https://example.com"])

        assert args.command == "visual"
        assert args.visual_command == "capture"
        assert args.url == "https://example.com"

    def test_parser_responsive_command(self):
        """Test parser handles responsive commands."""
        parser = create_parser()

        args = parser.parse_args(["responsive", "breakpoints", "https://example.com"])

        assert args.command == "responsive"
        assert args.responsive_command == "breakpoints"
        assert args.url == "https://example.com"

    def test_parser_test_command(self):
        """Test parser handles unified test command."""
        parser = create_parser()

        args = parser.parse_args(["test", "https://example.com"])

        assert args.command == "test"
        assert args.url == "https://example.com"

    def test_parser_crawl_command(self):
        """Test parser handles crawl command."""
        parser = create_parser()

        args = parser.parse_args(["crawl", "https://example.com"])

        assert args.command == "crawl"
        assert args.url == "https://example.com"
        assert args.depth == 3
        assert args.max_pages == 100

    def test_parser_baseline_command(self):
        """Test parser handles baseline commands."""
        parser = create_parser()

        args = parser.parse_args(["baseline", "update", "https://example.com", "--name", "test"])

        assert args.command == "baseline"
        assert args.baseline_command == "update"
        assert args.url == "https://example.com"
        assert args.name == "test"


class TestAccessibilityFormatting:
    """Test accessibility report formatting."""

    def test_format_accessibility_text_no_violations(self):
        """Test formatting accessibility report with no violations."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.wcag_level = "AA"
        mock_result.score = 100.0
        mock_result.tested_at = "2024-01-01T00:00:00"
        mock_result.has_violations = False
        mock_result.total_violations = 0
        mock_result.critical_count = 0
        mock_result.serious_count = 0
        mock_result.moderate_count = 0
        mock_result.minor_count = 0
        mock_result.violations = []

        output = format_accessibility_text(mock_result)

        assert "FREYA ACCESSIBILITY REPORT" in output
        assert "https://example.com" in output
        assert "100.0%" in output
        assert "No accessibility violations found" in output

    def test_format_accessibility_text_with_violations(self):
        """Test formatting accessibility report with violations."""
        violation = Mock()
        violation.severity = "serious"
        violation.description = "Missing alt text"
        violation.wcag_reference = "1.1.1"
        violation.element_selector = "img.logo"
        violation.suggested_fix = "Add alt attribute"

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.wcag_level = "AA"
        mock_result.score = 75.0
        mock_result.tested_at = "2024-01-01T00:00:00"
        mock_result.has_violations = True
        mock_result.total_violations = 1
        mock_result.critical_count = 0
        mock_result.serious_count = 1
        mock_result.moderate_count = 0
        mock_result.minor_count = 0
        mock_result.violations = [violation]

        output = format_accessibility_text(mock_result)

        assert "VIOLATIONS" in output
        assert "Missing alt text" in output
        assert "1.1.1" in output

    def test_format_accessibility_markdown(self):
        """Test formatting accessibility report as markdown."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.wcag_level = "AA"
        mock_result.score = 90.0
        mock_result.tested_at = "2024-01-01T00:00:00"
        mock_result.has_violations = False
        mock_result.total_violations = 0
        mock_result.critical_count = 0
        mock_result.serious_count = 0
        mock_result.moderate_count = 0
        mock_result.minor_count = 0
        mock_result.violations = []

        output = format_accessibility_markdown(mock_result)

        assert "# Freya Accessibility Report" in output
        assert "**URL:** https://example.com" in output
        assert "**Score:** 90.0%" in output

    def test_format_accessibility_html(self):
        """Test formatting accessibility report as HTML."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.wcag_level = "AA"
        mock_result.score = 85.0
        mock_result.tested_at = "2024-01-01T00:00:00"
        mock_result.has_violations = False
        mock_result.violations = []

        output = format_accessibility_html(mock_result)

        assert "<!DOCTYPE html>" in output
        assert "Freya Accessibility Report" in output
        assert "https://example.com" in output


class TestContrastFormatting:
    """Test color contrast report formatting."""

    def test_format_contrast_text_no_issues(self):
        """Test formatting contrast report with no issues."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_elements = 100
        mock_result.passing_count = 100
        mock_result.failing_count = 0
        mock_result.has_violations = False
        mock_result.issues = []

        output = format_contrast_text(mock_result)

        assert "FREYA COLOR CONTRAST REPORT" in output
        assert "Passing:      100" in output

    def test_format_contrast_text_with_issues(self):
        """Test formatting contrast report with issues."""
        issue = Mock()
        issue.element_selector = "p.text"
        issue.foreground_color = "#777777"
        issue.background_color = "#FFFFFF"
        issue.contrast_ratio = 3.5
        issue.required_ratio = 4.5

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_elements = 10
        mock_result.passing_count = 9
        mock_result.failing_count = 1
        mock_result.has_violations = True
        mock_result.issues = [issue]

        output = format_contrast_text(mock_result)

        assert "CONTRAST ISSUES" in output
        assert "p.text" in output
        assert "3.50:1" in output


class TestKeyboardFormatting:
    """Test keyboard navigation report formatting."""

    def test_format_keyboard_text_no_issues(self):
        """Test formatting keyboard report with no issues."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_focusable = 20
        mock_result.accessible_count = 20
        mock_result.issue_count = 0
        mock_result.has_issues = False
        mock_result.issues = []

        output = format_keyboard_text(mock_result)

        assert "FREYA KEYBOARD NAVIGATION REPORT" in output
        assert "Focusable Elements:     20" in output

    def test_format_keyboard_text_with_issues(self):
        """Test formatting keyboard report with issues."""
        issue = Mock()
        issue.issue_type = "missing-focus-indicator"
        issue.element_selector = "a.link"
        issue.description = "No visible focus indicator"

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_focusable = 10
        mock_result.accessible_count = 9
        mock_result.issue_count = 1
        mock_result.has_issues = True
        mock_result.issues = [issue]

        output = format_keyboard_text(mock_result)

        assert "ISSUES" in output
        assert "missing-focus-indicator" in output


class TestARIAFormatting:
    """Test ARIA validation report formatting."""

    def test_format_aria_text_no_violations(self):
        """Test formatting ARIA report with no violations."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_aria_elements = 15
        mock_result.valid_count = 15
        mock_result.invalid_count = 0
        mock_result.has_violations = False
        mock_result.violations = []

        output = format_aria_text(mock_result)

        assert "FREYA ARIA VALIDATION REPORT" in output
        assert "Valid:        15" in output


class TestScreenReaderFormatting:
    """Test screen reader report formatting."""

    def test_format_screen_reader_text(self):
        """Test formatting screen reader report."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_elements = 50
        mock_result.labeled_count = 48
        mock_result.missing_labels = 2
        mock_result.landmark_structure = {"main": 1, "nav": 1, "footer": 1}
        mock_result.heading_structure = [
            {"level": 1, "text": "Main Heading"},
            {"level": 2, "text": "Subheading"}
        ]

        output = format_screen_reader_text(mock_result)

        assert "FREYA SCREEN READER COMPATIBILITY REPORT" in output
        assert "LANDMARK STRUCTURE" in output
        assert "HEADING STRUCTURE" in output


class TestLayoutFormatting:
    """Test layout validation report formatting."""

    def test_format_layout_text_no_issues(self):
        """Test formatting layout report with no issues."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.issues = []

        output = format_layout_text(mock_result)

        assert "FREYA LAYOUT VALIDATION REPORT" in output
        assert "Issues:       0" in output


class TestStyleFormatting:
    """Test style validation report formatting."""

    def test_format_style_text_no_issues(self):
        """Test formatting style report with no issues."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.issues = []

        output = format_style_text(mock_result)

        assert "FREYA STYLE VALIDATION REPORT" in output


class TestBreakpointFormatting:
    """Test breakpoint testing report formatting."""

    def test_format_breakpoint_text(self):
        """Test formatting breakpoint report."""
        bp_result = Mock()
        bp_result.breakpoint = Mock(name="mobile", width=375, height=667)
        bp_result.issues = []
        bp_result.has_horizontal_scroll = False

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.breakpoints_tested = ["mobile"]
        mock_result.total_issues = 0
        mock_result.results = [bp_result]

        output = format_breakpoint_text(mock_result)

        assert "FREYA BREAKPOINT TEST REPORT" in output


class TestTouchFormatting:
    """Test touch target validation report formatting."""

    def test_format_touch_text(self):
        """Test formatting touch target report."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_interactive_elements = 20
        mock_result.passing_count = 18
        mock_result.failing_count = 2
        mock_result.min_touch_size = 44
        mock_result.issues = []

        output = format_touch_text(mock_result)

        assert "FREYA TOUCH TARGET VALIDATION REPORT" in output


class TestViewportFormatting:
    """Test viewport testing report formatting."""

    def test_format_viewport_text(self):
        """Test formatting viewport report."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.viewport_meta = "width=device-width, initial-scale=1"
        mock_result.content_width = 1200
        mock_result.viewport_width = 1200
        mock_result.has_horizontal_scroll = False
        mock_result.issues = []

        output = format_viewport_text(mock_result)

        assert "FREYA VIEWPORT TEST REPORT" in output


class TestMobileFormatting:
    """Test mobile compatibility report formatting."""

    def test_format_mobile_text(self):
        """Test formatting mobile compatibility report."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.devices_tested = ["iPhone 14", "Pixel 7"]
        mock_result.load_time_ms = 1500
        mock_result.page_size_bytes = 500000
        mock_result.resource_count = 25
        mock_result.mobile_friendly_score = 85.0
        mock_result.issues = []

        output = format_mobile_text(mock_result)

        assert "FREYA MOBILE COMPATIBILITY REPORT" in output


class TestUnifiedFormatting:
    """Test unified test report formatting."""

    def test_format_unified_text(self):
        """Test formatting unified test report."""
        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.duration_ms = 2000
        mock_result.overall_score = 85.0
        mock_result.accessibility_score = 80.0
        mock_result.visual_score = 90.0
        mock_result.responsive_score = 85.0
        mock_result.total_tests = 100
        mock_result.passed = 95
        mock_result.failed = 5
        mock_result.critical_count = 1
        mock_result.serious_count = 2
        mock_result.moderate_count = 1
        mock_result.minor_count = 1

        output = format_unified_text(mock_result)

        assert "FREYA UNIFIED TEST REPORT" in output
        assert "Overall Score:    85" in output


class TestAccessibilityAuditCommand:
    """Test accessibility audit command execution."""

    @pytest.mark.asyncio
    async def test_run_accessibility_audit_success(self):
        """Test running accessibility audit successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.level = "AA"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.wcag_level = "AA"
        mock_result.score = 100.0
        mock_result.tested_at = "2024-01-01T00:00:00"
        mock_result.has_violations = False
        mock_result.total_violations = 0
        mock_result.critical_count = 0
        mock_result.serious_count = 0
        mock_result.moderate_count = 0
        mock_result.minor_count = 0
        mock_result.violations = []
        mock_result.model_dump_json = Mock(return_value='{"score": 100}')

        with patch('Asgard.Freya.cli._handlers_accessibility.WCAGValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_accessibility_audit(args, verbose=False)

            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_accessibility_audit_with_violations(self):
        """Test running accessibility audit with violations."""
        args = Mock()
        args.url = "https://example.com"
        args.level = "AA"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.has_violations = True
        mock_result.score = 75.0
        mock_result.wcag_level = "AA"
        mock_result.tested_at = "2024-01-01T00:00:00"
        mock_result.total_violations = 1
        mock_result.critical_count = 1
        mock_result.serious_count = 0
        mock_result.moderate_count = 0
        mock_result.minor_count = 0
        mock_result.violations = []

        with patch('Asgard.Freya.cli._handlers_accessibility.WCAGValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_accessibility_audit(args, verbose=False)

            assert exit_code == 1

    @pytest.mark.asyncio
    async def test_run_accessibility_audit_json_output(self):
        """Test running accessibility audit with JSON output."""
        args = Mock()
        args.url = "https://example.com"
        args.level = "AA"
        args.format = "json"
        args.output = None

        mock_result = Mock()
        mock_result.has_violations = False
        mock_result.model_dump_json = Mock(return_value='{"score": 100}')

        with patch('Asgard.Freya.cli._handlers_accessibility.WCAGValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print') as mock_print:
                exit_code = await run_accessibility_audit(args, verbose=False)

            mock_result.model_dump_json.assert_called_once()


class TestContrastCheckCommand:
    """Test color contrast check command execution."""

    @pytest.mark.asyncio
    async def test_run_contrast_check_success(self):
        """Test running contrast check successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.level = "AA"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_elements = 50
        mock_result.passing_count = 50
        mock_result.failing_count = 0
        mock_result.has_violations = False
        mock_result.issues = []
        mock_result.model_dump_json = Mock(return_value='{"passing": 50}')

        with patch('Asgard.Freya.cli._handlers_accessibility.ColorContrastChecker') as mock_checker:
            mock_instance = AsyncMock()
            mock_instance.check = AsyncMock(return_value=mock_result)
            mock_checker.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_contrast_check(args, verbose=False)

            assert exit_code == 0


class TestKeyboardTestCommand:
    """Test keyboard navigation test command execution."""

    @pytest.mark.asyncio
    async def test_run_keyboard_test_success(self):
        """Test running keyboard test successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.level = "AA"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_focusable = 20
        mock_result.accessible_count = 20
        mock_result.issue_count = 0
        mock_result.has_issues = False
        mock_result.issues = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_accessibility.KeyboardNavigationTester') as mock_tester:
            mock_instance = AsyncMock()
            mock_instance.test = AsyncMock(return_value=mock_result)
            mock_tester.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_keyboard_test(args, verbose=False)

            assert exit_code == 0


class TestARIAValidationCommand:
    """Test ARIA validation command execution."""

    @pytest.mark.asyncio
    async def test_run_aria_validation_success(self):
        """Test running ARIA validation successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.level = "AA"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_aria_elements = 10
        mock_result.valid_count = 10
        mock_result.invalid_count = 0
        mock_result.has_violations = False
        mock_result.violations = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_accessibility.ARIAValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_aria_validation(args, verbose=False)

            assert exit_code == 0


class TestScreenReaderTestCommand:
    """Test screen reader test command execution."""

    @pytest.mark.asyncio
    async def test_run_screen_reader_test_success(self):
        """Test running screen reader test successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.level = "AA"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_elements = 50
        mock_result.labeled_count = 50
        mock_result.missing_labels = 0
        mock_result.has_issues = False
        mock_result.landmark_structure = {}
        mock_result.heading_structure = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_accessibility.ScreenReaderValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_screen_reader_test(args, verbose=False)

            assert exit_code == 0


class TestVisualCaptureCommand:
    """Test visual capture command execution."""

    @pytest.mark.asyncio
    async def test_run_visual_capture_viewport(self):
        """Test capturing viewport screenshot."""
        args = Mock()
        args.url = "https://example.com"
        args.output = None
        args.device = None
        args.full_page = False

        mock_result = Mock()
        mock_result.file_path = "/tmp/screenshot.png"

        with patch('Asgard.Freya.cli._handlers_visual_responsive.ScreenshotCapture') as mock_capture:
            mock_instance = Mock()
            mock_instance.capture_viewport = AsyncMock(return_value=mock_result)
            mock_capture.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_visual_capture(args, verbose=False)

            assert exit_code == 0


class TestVisualCompareCommand:
    """Test visual comparison command execution."""

    @pytest.mark.asyncio
    async def test_run_visual_compare_match(self):
        """Test visual comparison with matching images."""
        args = Mock()
        args.baseline = "/tmp/baseline.png"
        args.current = "/tmp/current.png"
        args.threshold = 0.95
        args.format = "text"

        mock_result = Mock()
        mock_result.has_difference = False
        mock_result.difference_percentage = 0.5
        mock_result.diff_image_path = None
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_visual_responsive.VisualRegressionTester') as mock_tester:
            mock_instance = Mock()
            mock_instance.compare = Mock(return_value=mock_result)
            mock_tester.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_visual_compare(args, verbose=False)

            assert exit_code == 0


class TestLayoutValidationCommand:
    """Test layout validation command execution."""

    @pytest.mark.asyncio
    async def test_run_layout_validation_success(self):
        """Test running layout validation successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.issues = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_visual_responsive.LayoutValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_layout_validation(args, verbose=False)

            assert exit_code == 0


class TestStyleValidationCommand:
    """Test style validation command execution."""

    @pytest.mark.asyncio
    async def test_run_style_validation_success(self):
        """Test running style validation successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "text"
        args.output = None
        args.theme = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.issues = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_visual_responsive.StyleValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_style_validation(args, verbose=False)

            assert exit_code == 0


class TestBreakpointTestCommand:
    """Test breakpoint testing command execution."""

    @pytest.mark.asyncio
    async def test_run_breakpoint_test_success(self):
        """Test running breakpoint test successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "text"
        args.output = None
        args.screenshots = False

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.breakpoints_tested = []
        mock_result.total_issues = 0
        mock_result.results = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_visual_responsive.BreakpointTester') as mock_tester:
            mock_instance = AsyncMock()
            mock_instance.test = AsyncMock(return_value=mock_result)
            mock_tester.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_breakpoint_test(args, verbose=False)

            assert exit_code == 0


class TestTouchValidationCommand:
    """Test touch target validation command execution."""

    @pytest.mark.asyncio
    async def test_run_touch_validation_success(self):
        """Test running touch target validation successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "text"
        args.output = None
        args.min_size = 44

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.total_interactive_elements = 20
        mock_result.passing_count = 20
        mock_result.failing_count = 0
        mock_result.min_touch_size = 44
        mock_result.issues = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_visual_responsive.TouchTargetValidator') as mock_validator:
            mock_instance = AsyncMock()
            mock_instance.validate = AsyncMock(return_value=mock_result)
            mock_validator.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_touch_validation(args, verbose=False)

            assert exit_code == 0


class TestViewportTestCommand:
    """Test viewport testing command execution."""

    @pytest.mark.asyncio
    async def test_run_viewport_test_success(self):
        """Test running viewport test successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "text"
        args.output = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.viewport_meta = "width=device-width"
        mock_result.content_width = 1200
        mock_result.viewport_width = 1200
        mock_result.has_horizontal_scroll = False
        mock_result.issues = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_visual_responsive.ViewportTester') as mock_tester:
            mock_instance = AsyncMock()
            mock_instance.test = AsyncMock(return_value=mock_result)
            mock_tester.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_viewport_test(args, verbose=False)

            assert exit_code == 0


class TestMobileTestCommand:
    """Test mobile compatibility test command execution."""

    @pytest.mark.asyncio
    async def test_run_mobile_test_success(self):
        """Test running mobile compatibility test successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "text"
        args.output = None
        args.devices = None

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.devices_tested = []
        mock_result.load_time_ms = 1000
        mock_result.page_size_bytes = 500000
        mock_result.resource_count = 20
        mock_result.mobile_friendly_score = 90.0
        mock_result.issues = []
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_visual_responsive.MobileCompatibilityTester') as mock_tester:
            mock_instance = AsyncMock()
            mock_instance.test = AsyncMock(return_value=mock_result)
            mock_tester.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_mobile_test(args, verbose=False)

            assert exit_code == 0


class TestUnifiedTestCommand:
    """Test unified test command execution."""

    @pytest.mark.asyncio
    async def test_run_unified_test_all_categories(self):
        """Test running unified test with all categories."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "text"
        args.output = None
        args.severity = "minor"
        args.skip_accessibility = False
        args.skip_visual = False
        args.skip_responsive = False

        mock_result = Mock()
        mock_result.url = "https://example.com"
        mock_result.duration_ms = 2000
        mock_result.overall_score = 90.0
        mock_result.accessibility_score = 85.0
        mock_result.visual_score = 95.0
        mock_result.responsive_score = 90.0
        mock_result.total_tests = 100
        mock_result.passed = 95
        mock_result.failed = 0
        mock_result.critical_count = 0
        mock_result.serious_count = 0
        mock_result.moderate_count = 0
        mock_result.minor_count = 0
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_integration.UnifiedTester') as mock_tester:
            mock_instance = AsyncMock()
            mock_instance.test = AsyncMock(return_value=mock_result)
            mock_tester.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_unified_test(args, verbose=False)

            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_unified_test_html_output(self):
        """Test running unified test with HTML output."""
        args = Mock()
        args.url = "https://example.com"
        args.format = "html"
        args.output = None
        args.severity = "minor"
        args.skip_accessibility = False
        args.skip_visual = False
        args.skip_responsive = False

        mock_result = Mock()
        mock_result.failed = 0
        mock_result.model_dump_json = Mock(return_value='{}')

        with patch('Asgard.Freya.cli._handlers_integration.UnifiedTester') as mock_tester, \
             patch('Asgard.Freya.cli._handlers_integration.HTMLReporter') as mock_reporter:
            mock_tester_instance = AsyncMock()
            mock_tester_instance.test = AsyncMock(return_value=mock_result)
            mock_tester.return_value = mock_tester_instance

            mock_reporter_instance = Mock()
            mock_reporter_instance.generate = Mock()
            mock_reporter.return_value = mock_reporter_instance

            with patch('builtins.print'):
                exit_code = await run_unified_test(args, verbose=False)

            mock_reporter_instance.generate.assert_called_once()


class TestBaselineCommands:
    """Test baseline management commands."""

    @pytest.mark.asyncio
    async def test_run_baseline_update_success(self):
        """Test updating baseline successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.name = "homepage"
        args.width = 1920
        args.height = 1080
        args.device = None

        mock_result = Mock()
        mock_result.screenshot_path = "/tmp/baseline.png"
        mock_result.hash = "abc123"

        with patch('Asgard.Freya.cli._handlers_integration.BaselineManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.create_baseline = AsyncMock(return_value=mock_result)
            mock_manager.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_baseline_update(args, verbose=False)

            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_baseline_compare_success(self):
        """Test comparing to baseline successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.name = "homepage"
        args.device = None
        args.threshold = 0.1

        mock_result = {
            "success": True,
            "passed": True,
            "difference_percentage": 0.05,
            "diff_image_path": None
        }

        with patch('Asgard.Freya.cli._handlers_integration.BaselineManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.compare_to_baseline = AsyncMock(return_value=mock_result)
            mock_manager.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_baseline_compare(args, verbose=False)

            assert exit_code == 0

    def test_run_baseline_list_with_results(self):
        """Test listing baselines with results."""
        args = Mock()
        args.url = None

        baseline1 = Mock()
        baseline1.name = "homepage"
        baseline1.url = "https://example.com"
        baseline1.created_at = "2024-01-01T00:00:00"
        baseline1.device = None

        baseline2 = Mock()
        baseline2.name = "about"
        baseline2.url = "https://example.com/about"
        baseline2.created_at = "2024-01-02T00:00:00"
        baseline2.device = "iphone-14"

        with patch('Asgard.Freya.cli._handlers_integration.BaselineManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.list_baselines = Mock(return_value=[baseline1, baseline2])
            mock_manager.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = run_baseline_list(args, verbose=False)

            assert exit_code == 0

    def test_run_baseline_delete_success(self):
        """Test deleting baseline successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.name = "homepage"
        args.device = None

        with patch('Asgard.Freya.cli._handlers_integration.BaselineManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.delete_baseline = Mock(return_value=True)
            mock_manager.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = run_baseline_delete(args, verbose=False)

            assert exit_code == 0

    def test_run_baseline_delete_not_found(self):
        """Test deleting non-existent baseline."""
        args = Mock()
        args.url = "https://example.com"
        args.name = "nonexistent"
        args.device = None

        with patch('Asgard.Freya.cli._handlers_integration.BaselineManager') as mock_manager:
            mock_instance = Mock()
            mock_instance.delete_baseline = Mock(return_value=False)
            mock_manager.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = run_baseline_delete(args, verbose=False)

            assert exit_code == 1


class TestCrawlCommand:
    """Test site crawl command execution."""

    @pytest.mark.asyncio
    async def test_run_crawl_success(self):
        """Test running site crawl successfully."""
        args = Mock()
        args.url = "https://example.com"
        args.depth = 3
        args.max_pages = 100
        args.output = "./test_output"
        args.delay = 0.5
        args.no_screenshots = False
        args.include = []
        args.exclude = []
        args.username = None
        args.password = None
        args.no_headless = False
        args.routes = []

        mock_report = Mock()
        mock_report.start_url = "https://example.com"
        mock_report.total_duration_ms = 5000
        mock_report.pages_discovered = 10
        mock_report.pages_tested = 10
        mock_report.pages_skipped = 0
        mock_report.pages_errored = 0
        mock_report.average_overall_score = 85.0
        mock_report.average_accessibility_score = 80.0
        mock_report.average_visual_score = 90.0
        mock_report.average_responsive_score = 85.0
        mock_report.total_critical = 0
        mock_report.total_serious = 1
        mock_report.total_moderate = 2
        mock_report.total_minor = 3
        mock_report.worst_pages = []
        mock_report.common_issues = []
        mock_report.page_results = []

        with patch('Asgard.Freya.cli._handlers_integration.SiteCrawler') as mock_crawler:
            mock_instance = Mock()
            mock_instance.set_progress_callback = Mock()
            mock_instance.crawl_and_test = AsyncMock(return_value=mock_report)
            mock_crawler.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_crawl(args, verbose=False)

            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_crawl_with_critical_issues(self):
        """Test crawl returns error code with critical issues."""
        args = Mock()
        args.url = "https://example.com"
        args.depth = 3
        args.max_pages = 100
        args.output = "./test_output"
        args.delay = 0.5
        args.no_screenshots = False
        args.include = []
        args.exclude = []
        args.username = None
        args.password = None
        args.no_headless = False
        args.routes = []

        mock_report = Mock()
        mock_report.start_url = "https://example.com"
        mock_report.total_duration_ms = 5000
        mock_report.pages_discovered = 5
        mock_report.pages_tested = 5
        mock_report.pages_skipped = 0
        mock_report.pages_errored = 0
        mock_report.average_overall_score = 60.0
        mock_report.average_accessibility_score = 55.0
        mock_report.average_visual_score = 65.0
        mock_report.average_responsive_score = 60.0
        mock_report.total_critical = 5
        mock_report.total_serious = 3
        mock_report.total_moderate = 2
        mock_report.total_minor = 1
        mock_report.worst_pages = []
        mock_report.common_issues = []
        mock_report.page_results = []

        with patch('Asgard.Freya.cli._handlers_integration.SiteCrawler') as mock_crawler:
            mock_instance = Mock()
            mock_instance.set_progress_callback = Mock()
            mock_instance.crawl_and_test = AsyncMock(return_value=mock_report)
            mock_crawler.return_value = mock_instance

            with patch('builtins.print'):
                exit_code = await run_crawl(args, verbose=False)

            assert exit_code == 1
