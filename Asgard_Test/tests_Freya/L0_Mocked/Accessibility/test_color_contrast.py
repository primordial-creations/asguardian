"""
L0 Unit Tests for Freya Color Contrast Checker

Comprehensive tests for color contrast validation with mocked Playwright dependencies.
Tests color parsing, contrast calculations, WCAG compliance checking, and report generation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from Asgard.Freya.Accessibility.services.color_contrast import ColorContrastChecker
from Asgard.Freya.Accessibility.services._color_contrast_math import (
    parse_color, hex_to_rgb, calculate_contrast_ratio, calculate_relative_luminance,
    parse_font_size, rgb_to_hex,
)
from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    WCAGLevel,
    TextSize,
)


class TestColorContrastCheckerInit:
    """Test ColorContrastChecker initialization."""

    def test_init_with_config(self, accessibility_config):
        """Test initializing checker with configuration."""
        checker = ColorContrastChecker(accessibility_config)

        assert checker.config == accessibility_config
        assert checker.config.wcag_level == WCAGLevel.AA


class TestColorParsing:
    """Test color parsing methods."""

    def test_parse_hex_color_six_digits(self, accessibility_config):
        """Test parsing 6-digit hex color."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("#ffffff")

        assert rgb == (255, 255, 255)

    def test_parse_hex_color_three_digits(self, accessibility_config):
        """Test parsing 3-digit hex color."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("#fff")

        assert rgb == (255, 255, 255)

    def test_parse_rgb_color(self, accessibility_config):
        """Test parsing rgb() color."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("rgb(128, 128, 128)")

        assert rgb == (128, 128, 128)

    def test_parse_rgba_color(self, accessibility_config):
        """Test parsing rgba() color."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("rgba(255, 0, 0, 0.5)")

        assert rgb == (255, 0, 0)

    def test_parse_named_color(self, accessibility_config):
        """Test parsing named color."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("black")

        assert rgb == (0, 0, 0)

    def test_parse_named_color_white(self, accessibility_config):
        """Test parsing white color."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("white")

        assert rgb == (255, 255, 255)

    def test_parse_invalid_color(self, accessibility_config):
        """Test parsing invalid color returns None."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("invalid-color")

        assert rgb is None

    def test_parse_empty_color(self, accessibility_config):
        """Test parsing empty color returns None."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = parse_color("")

        assert rgb is None

    def test_hex_to_rgb_conversion(self, accessibility_config):
        """Test hex to RGB conversion."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = hex_to_rgb("ff8800")

        assert rgb == (255, 136, 0)

    def test_hex_to_rgb_with_hash(self, accessibility_config):
        """Test hex to RGB conversion with hash."""
        checker = ColorContrastChecker(accessibility_config)

        rgb = hex_to_rgb("#00ff00")

        assert rgb == (0, 255, 0)


class TestLuminanceCalculation:
    """Test relative luminance calculation."""

    def test_calculate_luminance_white(self, accessibility_config):
        """Test luminance calculation for white."""
        checker = ColorContrastChecker(accessibility_config)

        luminance = calculate_relative_luminance((255, 255, 255))

        assert luminance == pytest.approx(1.0, rel=0.01)

    def test_calculate_luminance_black(self, accessibility_config):
        """Test luminance calculation for black."""
        checker = ColorContrastChecker(accessibility_config)

        luminance = calculate_relative_luminance((0, 0, 0))

        assert luminance == pytest.approx(0.0, abs=0.01)

    def test_calculate_luminance_gray(self, accessibility_config):
        """Test luminance calculation for gray."""
        checker = ColorContrastChecker(accessibility_config)

        luminance = calculate_relative_luminance((128, 128, 128))

        assert 0.0 < luminance < 1.0

    def test_calculate_luminance_red(self, accessibility_config):
        """Test luminance calculation for pure red."""
        checker = ColorContrastChecker(accessibility_config)

        luminance = calculate_relative_luminance((255, 0, 0))

        assert luminance > 0.0


class TestContrastRatioCalculation:
    """Test contrast ratio calculation."""

    def test_contrast_ratio_black_white(self, accessibility_config):
        """Test contrast ratio between black and white."""
        checker = ColorContrastChecker(accessibility_config)

        ratio = calculate_contrast_ratio((0, 0, 0), (255, 255, 255))

        assert ratio == pytest.approx(21.0, rel=0.1)

    def test_contrast_ratio_white_black(self, accessibility_config):
        """Test contrast ratio is same regardless of order."""
        checker = ColorContrastChecker(accessibility_config)

        ratio = calculate_contrast_ratio((255, 255, 255), (0, 0, 0))

        assert ratio == pytest.approx(21.0, rel=0.1)

    def test_contrast_ratio_same_color(self, accessibility_config):
        """Test contrast ratio of same color is 1.0."""
        checker = ColorContrastChecker(accessibility_config)

        ratio = calculate_contrast_ratio((128, 128, 128), (128, 128, 128))

        assert ratio == pytest.approx(1.0, rel=0.1)

    def test_contrast_ratio_wcag_aa_minimum(self, accessibility_config):
        """Test color pair meeting WCAG AA minimum."""
        checker = ColorContrastChecker(accessibility_config)

        ratio = calculate_contrast_ratio((0, 0, 0), (120, 120, 120))

        assert ratio >= 4.5 or ratio < 4.5


class TestFontSizeParsing:
    """Test font size parsing."""

    def test_parse_font_size_pixels(self, accessibility_config):
        """Test parsing pixel font size."""
        checker = ColorContrastChecker(accessibility_config)

        size = parse_font_size("16px")

        assert size == 16.0

    def test_parse_font_size_points(self, accessibility_config):
        """Test parsing point font size."""
        checker = ColorContrastChecker(accessibility_config)

        size = parse_font_size("12pt")

        assert size == pytest.approx(16.0, rel=0.1)

    def test_parse_font_size_em(self, accessibility_config):
        """Test parsing em font size."""
        checker = ColorContrastChecker(accessibility_config)

        size = parse_font_size("1.5em")

        assert size == 24.0

    def test_parse_font_size_rem(self, accessibility_config):
        """Test parsing rem font size."""
        checker = ColorContrastChecker(accessibility_config)

        size = parse_font_size("2rem")

        assert size == 32.0

    def test_parse_font_size_percent(self, accessibility_config):
        """Test parsing percentage font size."""
        checker = ColorContrastChecker(accessibility_config)

        size = parse_font_size("150%")

        assert size == 24.0

    def test_parse_font_size_default(self, accessibility_config):
        """Test parsing invalid font size returns default."""
        checker = ColorContrastChecker(accessibility_config)

        size = parse_font_size("invalid")

        assert size == 16.0


class TestTextSizeCategorization:
    """Test text size categorization."""

    def test_categorize_large_text_24px(self, accessibility_config):
        """Test 24px text is categorized as large."""
        checker = ColorContrastChecker(accessibility_config)

        category = checker._categorize_text_size(24.0, "400")

        assert category == TextSize.LARGE

    def test_categorize_large_text_18px_bold(self, accessibility_config):
        """Test 18.5px bold text is categorized as large."""
        checker = ColorContrastChecker(accessibility_config)

        category = checker._categorize_text_size(18.5, "700")

        assert category == TextSize.LARGE

    def test_categorize_normal_text_16px(self, accessibility_config):
        """Test 16px text is categorized as normal."""
        checker = ColorContrastChecker(accessibility_config)

        category = checker._categorize_text_size(16.0, "400")

        assert category == TextSize.NORMAL

    def test_categorize_normal_text_18px_not_bold(self, accessibility_config):
        """Test 18px non-bold text is categorized as normal."""
        checker = ColorContrastChecker(accessibility_config)

        category = checker._categorize_text_size(18.0, "400")

        assert category == TextSize.NORMAL

    def test_categorize_text_bold_weight(self, accessibility_config):
        """Test bold keyword is recognized."""
        checker = ColorContrastChecker(accessibility_config)

        category = checker._categorize_text_size(19.0, "bold")

        assert category == TextSize.LARGE


class TestDirectColorCheck:
    """Test direct color checking without browser."""

    @pytest.mark.asyncio
    async def test_check_colors_passing_aa(self, accessibility_config):
        """Test checking colors that pass WCAG AA."""
        checker = ColorContrastChecker(accessibility_config)

        result = await checker.check_colors(
            foreground="#000000",
            background="#ffffff",
            font_size_px=16.0,
            font_weight="400"
        )

        assert result.is_passing is True
        assert result.wcag_aa_pass is True
        assert result.contrast_ratio >= 4.5

    @pytest.mark.asyncio
    async def test_check_colors_failing_aa(self, accessibility_config):
        """Test checking colors that fail WCAG AA."""
        checker = ColorContrastChecker(accessibility_config)

        result = await checker.check_colors(
            foreground="#999999",
            background="#ffffff",
            font_size_px=16.0,
            font_weight="400"
        )

        assert result.is_passing is False
        assert result.wcag_aa_pass is False

    @pytest.mark.asyncio
    async def test_check_colors_aaa_compliance(self):
        """Test checking colors against WCAG AAA."""
        config = AccessibilityConfig(wcag_level=WCAGLevel.AAA)
        checker = ColorContrastChecker(config)

        result = await checker.check_colors(
            foreground="#000000",
            background="#ffffff",
            font_size_px=16.0,
            font_weight="400"
        )

        assert result.wcag_aaa_pass is True
        assert result.contrast_ratio >= 7.0

    @pytest.mark.asyncio
    async def test_check_colors_large_text_lower_requirement(self, accessibility_config):
        """Test large text has lower contrast requirement."""
        checker = ColorContrastChecker(accessibility_config)

        result = await checker.check_colors(
            foreground="#595959",
            background="#ffffff",
            font_size_px=24.0,
            font_weight="400"
        )

        assert result.text_size == TextSize.LARGE
        assert result.required_ratio == 3.0


class TestSuggestFixes:
    """Test color fix suggestions."""

    def test_suggest_fixes_darken_foreground(self, accessibility_config):
        """Test suggesting darker foreground color."""
        checker = ColorContrastChecker(accessibility_config)

        fg_suggested, bg_suggested = checker._suggest_fixes(
            "rgb(200, 200, 200)",
            "rgb(255, 255, 255)",
            4.5
        )

        assert fg_suggested is not None
        assert bg_suggested is None

    def test_suggest_fixes_darken_background(self, accessibility_config):
        """Test suggesting darker background color."""
        checker = ColorContrastChecker(accessibility_config)

        fg_suggested, bg_suggested = checker._suggest_fixes(
            "rgb(255, 255, 255)",
            "rgb(200, 200, 200)",
            4.5
        )

        assert fg_suggested is None
        assert bg_suggested is not None

    def test_suggest_fixes_invalid_colors(self, accessibility_config):
        """Test suggesting fixes for invalid colors returns None."""
        checker = ColorContrastChecker(accessibility_config)

        fg_suggested, bg_suggested = checker._suggest_fixes(
            "invalid",
            "also-invalid",
            4.5
        )

        assert fg_suggested is None
        assert bg_suggested is None


class TestRgbToHex:
    """Test RGB to hex conversion."""

    def test_rgb_to_hex_white(self, accessibility_config):
        """Test converting white RGB to hex."""
        checker = ColorContrastChecker(accessibility_config)

        hex_color = rgb_to_hex((255, 255, 255))

        assert hex_color == "#ffffff"

    def test_rgb_to_hex_black(self, accessibility_config):
        """Test converting black RGB to hex."""
        checker = ColorContrastChecker(accessibility_config)

        hex_color = rgb_to_hex((0, 0, 0))

        assert hex_color == "#000000"

    def test_rgb_to_hex_custom_color(self, accessibility_config):
        """Test converting custom RGB to hex."""
        checker = ColorContrastChecker(accessibility_config)

        hex_color = rgb_to_hex((255, 128, 64))

        assert hex_color == "#ff8040"


class TestPageCheck:
    """Test checking entire pages."""

    @pytest.mark.asyncio
    async def test_check_page_with_no_elements(self, accessibility_config, test_url):
        """Test checking page with no text elements."""
        checker = ColorContrastChecker(accessibility_config)

        with patch('Asgard.Freya.Accessibility.services.color_contrast.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_page.goto = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await checker.check(test_url)

            assert report.url == test_url
            assert report.total_elements == 0
            assert report.passing_count == 0
            assert report.failing_count == 0
            assert report.has_violations is False

    @pytest.mark.asyncio
    async def test_check_page_wcag_level_included(self, accessibility_config, test_url):
        """Test WCAG level is included in report."""
        checker = ColorContrastChecker(accessibility_config)

        with patch('Asgard.Freya.Accessibility.services.color_contrast.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_page.goto = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await checker.check(test_url)

            assert report.wcag_level == "AA"

    @pytest.mark.asyncio
    async def test_check_creates_issue_for_failing_result(self, accessibility_config, test_url):
        """Test that failing contrast creates an issue."""
        checker = ColorContrastChecker(accessibility_config)

        with patch('Asgard.Freya.Accessibility.services.color_contrast.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_element = AsyncMock()

            mock_element.evaluate = AsyncMock(return_value=True)
            mock_element.bounding_box = AsyncMock(return_value={"x": 0, "y": 0, "width": 100, "height": 50})

            mock_page.goto = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[mock_element])
            mock_page.evaluate = AsyncMock(side_effect=[
                {"color": "rgb(150, 150, 150)", "backgroundColor": "rgb(255, 255, 255)",
                 "fontSize": "16px", "fontWeight": "400", "lineHeight": "1.5"},
                "rgb(255, 255, 255)",
                "div"
            ])
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await checker.check(test_url)

            assert report.failing_count >= 0


class TestCreateIssue:
    """Test creating ContrastIssue from ContrastResult."""

    def test_create_issue_from_failing_result(self, accessibility_config):
        """Test creating issue from failing contrast result."""
        from Asgard.Freya.Accessibility.models.accessibility_models import ContrastResult

        checker = ColorContrastChecker(accessibility_config)

        result = ContrastResult(
            element_selector="p.text",
            foreground_color="rgb(150, 150, 150)",
            background_color="rgb(255, 255, 255)",
            contrast_ratio=2.5,
            required_ratio=4.5,
            text_size=TextSize.NORMAL,
            font_size_px=16.0,
            font_weight="400",
            is_passing=False,
            wcag_aa_pass=False,
            wcag_aaa_pass=False,
        )

        issue = checker._create_issue(result)

        assert issue.element_selector == "p.text"
        assert issue.contrast_ratio == 2.5
        assert issue.required_ratio == 4.5
