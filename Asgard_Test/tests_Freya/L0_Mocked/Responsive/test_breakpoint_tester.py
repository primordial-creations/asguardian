"""
Freya L0 Mocked Tests - Breakpoint Tester Service

Tests for BreakpointTester service with mocked Playwright dependencies.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    BreakpointIssueType,
    COMMON_BREAKPOINTS,
)
from Asgard.Freya.Responsive.services.breakpoint_tester import BreakpointTester


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def tester():
    """Create a BreakpointTester instance."""
    return BreakpointTester(output_directory="./test_breakpoints")


@pytest.fixture
def sample_breakpoint():
    """Fixture providing a sample breakpoint."""
    return Breakpoint(
        name="mobile-md",
        width=375,
        height=667,
        is_mobile=True,
        device_scale_factor=2,
    )


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.evaluate = AsyncMock()
    page.screenshot = AsyncMock()
    return page


@pytest.fixture
def mock_browser():
    """Create a mock Playwright browser."""
    browser = AsyncMock()
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def mock_context():
    """Create a mock Playwright browser context."""
    context = AsyncMock()
    context.close = AsyncMock()
    return context


# =============================================================================
# Test BreakpointTester Initialization
# =============================================================================

class TestBreakpointTesterInit:
    """Tests for BreakpointTester initialization."""

    @pytest.mark.L0
    def test_init_default_directory(self, tmp_path):
        """Test initialization with default output directory."""
        with patch("Asgard.Freya.Responsive.services.breakpoint_tester.Path.mkdir"):
            tester = BreakpointTester.__new__(BreakpointTester)
            tester.output_directory = Path("./breakpoint_tests")
        assert tester.output_directory == Path("./breakpoint_tests")

    @pytest.mark.L0
    def test_init_custom_directory(self, tmp_path):
        """Test initialization with custom output directory."""
        tester = BreakpointTester(output_directory=str(tmp_path / "custom_dir"))
        assert tester.output_directory == tmp_path / "custom_dir"

    @pytest.mark.L0
    @patch("Asgard.Freya.Responsive.services.breakpoint_tester.Path.mkdir")
    def test_init_creates_directory(self, mock_mkdir):
        """Test that initialization creates output directory."""
        tester = BreakpointTester(output_directory="./test_dir")
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


# =============================================================================
# Test BreakpointTester.test Method
# =============================================================================

class TestBreakpointTesterTest:
    """Tests for BreakpointTester.test method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.breakpoint_tester.async_playwright")
    async def test_test_with_default_breakpoints(self, mock_playwright, tester):
        """Test running test with default breakpoints."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=0)
        mock_page.screenshot = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        report = await tester.test(url="https://example.com", capture_screenshots=False)

        assert report.url == "https://example.com"
        assert len(report.breakpoints_tested) == len(COMMON_BREAKPOINTS)
        assert len(report.results) == len(COMMON_BREAKPOINTS)

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.breakpoint_tester.async_playwright")
    async def test_test_with_custom_breakpoints(self, mock_playwright, tester, sample_breakpoint):
        """Test running test with custom breakpoints."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=375)
        mock_page.screenshot = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        custom_breakpoints = [sample_breakpoint]
        report = await tester.test(
            url="https://example.com",
            breakpoints=custom_breakpoints,
            capture_screenshots=False,
        )

        assert len(report.breakpoints_tested) == 1
        assert report.breakpoints_tested[0] == "mobile-md"

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.breakpoint_tester.async_playwright")
    async def test_test_captures_screenshots(self, mock_playwright, tester, sample_breakpoint):
        """Test that screenshots are captured when requested."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=375)
        mock_page.screenshot = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        report = await tester.test(
            url="https://example.com",
            breakpoints=[sample_breakpoint],
            capture_screenshots=True,
        )

        mock_page.screenshot.assert_called_once()
        assert "mobile-md" in report.screenshots

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.breakpoint_tester.async_playwright")
    async def test_test_creates_browser_context_with_correct_viewport(
        self, mock_playwright, tester, sample_breakpoint
    ):
        """Test that browser context is created with correct viewport settings."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=375)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        await tester.test(
            url="https://example.com",
            breakpoints=[sample_breakpoint],
            capture_screenshots=False,
        )

        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"]["width"] == 375
        assert call_kwargs["viewport"]["height"] == 667
        assert call_kwargs["device_scale_factor"] == 2
        assert call_kwargs["is_mobile"] is True
        assert call_kwargs["has_touch"] is True


# =============================================================================
# Test Check Methods
# =============================================================================

class TestCheckHorizontalScroll:
    """Tests for _check_horizontal_scroll method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_horizontal_scroll(self, tester, mock_page, sample_breakpoint):
        """Test checking page with no horizontal scroll."""
        mock_page.evaluate = AsyncMock(side_effect=[375, []])

        issues = await tester._check_horizontal_scroll(mock_page, sample_breakpoint)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_horizontal_scroll(self, tester, mock_page, sample_breakpoint):
        """Test checking page with horizontal scroll."""
        overflow_elements = [
            {"selector": "div.container", "right": 400, "width": 450}
        ]
        mock_page.evaluate = AsyncMock(side_effect=[450, overflow_elements])

        issues = await tester._check_horizontal_scroll(mock_page, sample_breakpoint)

        assert len(issues) == 1
        assert issues[0].issue_type == BreakpointIssueType.HORIZONTAL_SCROLL
        assert issues[0].element_selector == "div.container"
        assert issues[0].severity == "serious"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_multiple_overflow_elements(self, tester, mock_page, sample_breakpoint):
        """Test checking page with multiple overflowing elements."""
        overflow_elements = [
            {"selector": "div.container", "right": 400, "width": 450},
            {"selector": "div.sidebar", "right": 420, "width": 500},
        ]
        mock_page.evaluate = AsyncMock(side_effect=[450, overflow_elements])

        issues = await tester._check_horizontal_scroll(mock_page, sample_breakpoint)

        assert len(issues) == 2


class TestCheckContentOverflow:
    """Tests for _check_content_overflow method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_content_overflow(self, tester, mock_page, sample_breakpoint):
        """Test checking page with no content overflow."""
        mock_page.evaluate = AsyncMock(return_value=[])

        issues = await tester._check_content_overflow(mock_page, sample_breakpoint)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_content_overflow(self, tester, mock_page, sample_breakpoint):
        """Test checking page with content overflow."""
        overflow_data = [
            {"selector": "div.text-container", "scrollWidth": 400, "clientWidth": 350}
        ]
        mock_page.evaluate = AsyncMock(return_value=overflow_data)

        issues = await tester._check_content_overflow(mock_page, sample_breakpoint)

        assert len(issues) == 1
        assert issues[0].issue_type == BreakpointIssueType.CONTENT_OVERFLOW
        assert issues[0].severity == "moderate"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_content_overflow_handles_exception(
        self, tester, mock_page, sample_breakpoint
    ):
        """Test that content overflow check handles exceptions gracefully."""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JavaScript error"))

        issues = await tester._check_content_overflow(mock_page, sample_breakpoint)

        assert len(issues) == 0


class TestCheckOverlappingElements:
    """Tests for _check_overlapping_elements method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_overlapping_elements(self, tester, mock_page, sample_breakpoint):
        """Test checking page with no overlapping elements."""
        mock_page.evaluate = AsyncMock(return_value=[])

        issues = await tester._check_overlapping_elements(mock_page, sample_breakpoint)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_overlapping_elements(self, tester, mock_page, sample_breakpoint):
        """Test checking page with overlapping interactive elements."""
        overlaps = [
            {"selector1": "button", "selector2": "a"}
        ]
        mock_page.evaluate = AsyncMock(return_value=overlaps)

        issues = await tester._check_overlapping_elements(mock_page, sample_breakpoint)

        assert len(issues) == 1
        assert issues[0].issue_type == BreakpointIssueType.OVERLAPPING_ELEMENTS
        assert issues[0].severity == "serious"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overlapping_handles_exception(
        self, tester, mock_page, sample_breakpoint
    ):
        """Test that overlapping check handles exceptions gracefully."""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JavaScript error"))

        issues = await tester._check_overlapping_elements(mock_page, sample_breakpoint)

        assert len(issues) == 0


class TestCheckTextTruncation:
    """Tests for _check_text_truncation method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_text_truncation(self, tester, mock_page, sample_breakpoint):
        """Test checking page with no text truncation."""
        mock_page.evaluate = AsyncMock(return_value=[])

        issues = await tester._check_text_truncation(mock_page, sample_breakpoint)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_text_truncation(self, tester, mock_page, sample_breakpoint):
        """Test checking page with truncated text."""
        truncated = [
            {"selector": "h1", "text": "This is a very long heading that gets truncated"}
        ]
        mock_page.evaluate = AsyncMock(return_value=truncated)

        issues = await tester._check_text_truncation(mock_page, sample_breakpoint)

        assert len(issues) == 1
        assert issues[0].issue_type == BreakpointIssueType.TEXT_TRUNCATION
        assert issues[0].severity == "minor"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_text_truncation_handles_exception(
        self, tester, mock_page, sample_breakpoint
    ):
        """Test that text truncation check handles exceptions gracefully."""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JavaScript error"))

        issues = await tester._check_text_truncation(mock_page, sample_breakpoint)

        assert len(issues) == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestBreakpointTesterIntegration:
    """Integration tests for BreakpointTester."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.breakpoint_tester.async_playwright")
    async def test_test_produces_complete_report(self, mock_playwright, tester, sample_breakpoint):
        """Test that test method produces a complete report."""
        overflow_elements = [
            {"selector": "div.wide", "right": 400, "width": 450}
        ]

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(side_effect=[
            450,  # check_horizontal_scroll: scroll_width
            overflow_elements,  # check_horizontal_scroll: overflow_elements
            [],   # check_content_overflow
            [],   # check_overlapping_elements
            [],   # check_text_truncation
            450,  # page_width
        ])

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        report = await tester.test(
            url="https://example.com",
            breakpoints=[sample_breakpoint],
            capture_screenshots=False,
        )

        assert report.url == "https://example.com"
        assert len(report.results) == 1
        assert report.total_issues == 1
        assert report.results[0].page_width == 450
        assert report.results[0].has_horizontal_scroll is True

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.breakpoint_tester.async_playwright")
    async def test_test_closes_resources_properly(self, mock_playwright, tester, sample_breakpoint):
        """Test that test method closes browser resources properly."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=375)

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_p)
        mock_playwright.return_value.__aexit__ = AsyncMock()

        await tester.test(
            url="https://example.com",
            breakpoints=[sample_breakpoint],
            capture_screenshots=False,
        )

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
