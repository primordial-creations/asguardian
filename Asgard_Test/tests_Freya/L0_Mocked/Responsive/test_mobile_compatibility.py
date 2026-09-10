"""
Freya L0 Mocked Tests - Mobile Compatibility Tester Service

Tests for MobileCompatibilityTester service with mocked Playwright dependencies.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from Asgard.Freya.Responsive.models.responsive_models import (
    MobileCompatibilityIssueType,
    MOBILE_DEVICES,
)
from Asgard.Freya.Responsive.services.mobile_compatibility import MobileCompatibilityTester
from Asgard.Freya.Responsive.services._mobile_compatibility_checks import MobileCheckError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def tester():
    """Create a MobileCompatibilityTester instance."""
    return MobileCompatibilityTester()


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.evaluate = AsyncMock()
    return page


# =============================================================================
# Test MobileCompatibilityTester Initialization
# =============================================================================

class TestMobileCompatibilityTesterInit:
    """Tests for MobileCompatibilityTester initialization."""

    @pytest.mark.L0
    def test_init(self):
        """Test initialization."""
        tester = MobileCompatibilityTester()
        assert tester is not None


# =============================================================================
# Test MobileCompatibilityTester.test Method
# =============================================================================

class TestMobileCompatibilityTesterTest:
    """Tests for MobileCompatibilityTester.test method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.async_playwright")
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.time")
    async def test_test_with_default_devices(self, mock_time, mock_playwright, tester):
        """Test running test with default devices."""
        mock_time.time.side_effect = [0, 2.5]

        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.evaluate = AsyncMock(side_effect=[
            0,
            [],
            [],
            [],
            {"resourceCount": 25, "totalSize": 1024000},
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

        report = await tester.test(url="https://example.com")

        assert report.url == "https://example.com"
        assert len(report.devices_tested) == 3
        assert "iphone-14" in report.devices_tested
        assert "pixel-7" in report.devices_tested
        assert "ipad" in report.devices_tested

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.async_playwright")
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.time")
    async def test_test_with_custom_devices(self, mock_time, mock_playwright, tester):
        """Test running test with custom devices."""
        mock_time.time.side_effect = [0, 1.5]

        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.evaluate = AsyncMock(side_effect=[
            0,
            [],
            [],
            [],
            {"resourceCount": 20, "totalSize": 512000},
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

        report = await tester.test(url="https://example.com", devices=["iphone-14"])

        assert len(report.devices_tested) == 1
        assert "iphone-14" in report.devices_tested

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.async_playwright")
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.time")
    async def test_test_detects_slow_loading(self, mock_time, mock_playwright, tester):
        """Test that slow loading is detected."""
        mock_time.time.side_effect = [0, 3.5]

        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.evaluate = AsyncMock(side_effect=[
            0,
            [],
            [],
            [],
            {"resourceCount": 50, "totalSize": 2048000},
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

        report = await tester.test(url="https://example.com", devices=["iphone-14"])

        slow_loading_issues = [
            i for i in report.issues
            if i.issue_type == MobileCompatibilityIssueType.SLOW_LOADING
        ]
        assert len(slow_loading_issues) > 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.async_playwright")
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.time")
    async def test_test_creates_device_results(self, mock_time, mock_playwright, tester):
        """Test that device results are created."""
        mock_time.time.side_effect = [0, 2.0]

        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.evaluate = AsyncMock(side_effect=[
            0,
            [],
            [],
            [],
            {"resourceCount": 30, "totalSize": 1536000},
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

        report = await tester.test(url="https://example.com", devices=["pixel-7"])

        assert "pixel-7" in report.device_results
        assert "load_time_ms" in report.device_results["pixel-7"]
        assert "viewport" in report.device_results["pixel-7"]


# =============================================================================
# Test Check Methods
# =============================================================================

class TestCheckFlashContent:
    """Tests for _check_flash_content method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_flash(self, tester, mock_page):
        """Test checking page with no Flash content."""
        mock_page.evaluate = AsyncMock(return_value=0)

        issues = await tester._check_flash_content(mock_page)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_flash(self, tester, mock_page):
        """Test checking page with Flash content."""
        mock_page.evaluate = AsyncMock(return_value=2)

        issues = await tester._check_flash_content(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == MobileCompatibilityIssueType.FLASH_CONTENT
        assert issues[0].severity == "critical"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_flash_handles_exception(self, tester, mock_page):
        """Test that Flash check handles exceptions gracefully."""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JavaScript error"))

        with pytest.raises(MobileCheckError):
            await tester._check_flash_content(mock_page)


class TestCheckHoverDependencies:
    """Tests for _check_hover_dependencies method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_hover_dependencies(self, tester, mock_page):
        """Test checking page with no hover dependencies."""
        mock_page.evaluate = AsyncMock(return_value=[])

        issues = await tester._check_hover_dependencies(mock_page)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_hover_dependencies(self, tester, mock_page):
        """Test checking page with hover-dependent elements."""
        hover_elements = [
            {"selector": "nav ul ul", "type": "hidden-menu"}
        ]
        mock_page.evaluate = AsyncMock(return_value=hover_elements)

        issues = await tester._check_hover_dependencies(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == MobileCompatibilityIssueType.HOVER_DEPENDENT
        assert issues[0].severity == "moderate"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_hover_handles_exception(self, tester, mock_page):
        """Test that hover check handles exceptions gracefully."""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JavaScript error"))

        with pytest.raises(MobileCheckError):
            await tester._check_hover_dependencies(mock_page)


class TestCheckSmallText:
    """Tests for _check_small_text method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_small_text(self, tester, mock_page):
        """Test checking page with no small text."""
        mock_page.evaluate = AsyncMock(return_value=[])

        issues = await tester._check_small_text(mock_page)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_small_text(self, tester, mock_page):
        """Test checking page with small text."""
        small_text = [
            {"selector": "p.disclaimer", "fontSize": 10},
            {"selector": "span.footnote", "fontSize": 8},
        ]
        mock_page.evaluate = AsyncMock(return_value=small_text)

        issues = await tester._check_small_text(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == MobileCompatibilityIssueType.SMALL_TEXT
        assert issues[0].severity == "moderate"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_small_text_handles_exception(self, tester, mock_page):
        """Test that small text check handles exceptions gracefully."""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JavaScript error"))

        with pytest.raises(MobileCheckError):
            await tester._check_small_text(mock_page)


class TestCheckFixedPositioning:
    """Tests for _check_fixed_positioning method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_no_fixed_positioning(self, tester, mock_page):
        """Test checking page with no problematic fixed positioning."""
        mock_page.evaluate = AsyncMock(return_value=[])

        issues = await tester._check_fixed_positioning(mock_page)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_with_fixed_positioning(self, tester, mock_page):
        """Test checking page with large fixed elements."""
        fixed_elements = [
            {"selector": "header.fixed", "coverage": 0.3}
        ]
        mock_page.evaluate = AsyncMock(return_value=fixed_elements)

        issues = await tester._check_fixed_positioning(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == MobileCompatibilityIssueType.FIXED_POSITIONING
        assert issues[0].severity == "moderate"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_fixed_positioning_handles_exception(self, tester, mock_page):
        """Test that fixed positioning check handles exceptions gracefully."""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JavaScript error"))

        with pytest.raises(MobileCheckError):
            await tester._check_fixed_positioning(mock_page)


# =============================================================================
# Test Utility Methods
# =============================================================================

class TestDeduplicateIssues:
    """Tests for _deduplicate_issues method."""

    @pytest.mark.L0
    def test_deduplicate_no_duplicates(self, tester):
        """Test deduplication with no duplicate issues."""
        from Asgard.Freya.Responsive.models.responsive_models import MobileCompatibilityIssue

        issues = [
            MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.FLASH_CONTENT,
                description="Flash detected",
                severity="critical",
                suggested_fix="Remove Flash",
                affected_devices=["iphone-14"],
            ),
            MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.SMALL_TEXT,
                description="Small text",
                severity="moderate",
                suggested_fix="Increase font size",
                affected_devices=["pixel-7"],
            ),
        ]

        result = tester._deduplicate_issues(issues)

        assert len(result) == 2

    @pytest.mark.L0
    def test_deduplicate_with_duplicates(self, tester):
        """Test deduplication with duplicate issues."""
        from Asgard.Freya.Responsive.models.responsive_models import MobileCompatibilityIssue

        issues = [
            MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.SMALL_TEXT,
                element_selector="p.text",
                description="Text too small",
                severity="moderate",
                suggested_fix="Fix it",
                affected_devices=["iphone-14"],
            ),
            MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.SMALL_TEXT,
                element_selector="p.text",
                description="Text too small",
                severity="moderate",
                suggested_fix="Fix it",
                affected_devices=["pixel-7"],
            ),
        ]

        result = tester._deduplicate_issues(issues)

        assert len(result) == 1
        assert len(result[0].affected_devices) == 2
        assert "iphone-14" in result[0].affected_devices
        assert "pixel-7" in result[0].affected_devices


class TestCalculateScore:
    """Tests for _calculate_score method."""

    @pytest.mark.L0
    def test_calculate_score_perfect(self, tester):
        """Test score calculation with no issues."""
        score = tester._calculate_score([], 2000, 1024000)

        assert score == 100.0

    @pytest.mark.L0
    def test_calculate_score_with_issues(self, tester):
        """Test score calculation with issues."""
        from Asgard.Freya.Responsive.models.responsive_models import MobileCompatibilityIssue

        issues = [
            MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.FLASH_CONTENT,
                description="Flash",
                severity="critical",
                suggested_fix="Fix",
            ),
            MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.SMALL_TEXT,
                description="Small",
                severity="moderate",
                suggested_fix="Fix",
            ),
        ]

        score = tester._calculate_score(issues, 2000, 1024000)

        assert score < 100.0
        assert score >= 0.0

    @pytest.mark.L0
    def test_calculate_score_with_slow_loading(self, tester):
        """Test score calculation with slow loading."""
        score = tester._calculate_score([], 5500, 1024000)

        assert score < 100.0

    @pytest.mark.L0
    def test_calculate_score_with_large_page_size(self, tester):
        """Test score calculation with large page size."""
        score = tester._calculate_score([], 2000, 6 * 1024 * 1024)

        assert score < 100.0

    @pytest.mark.L0
    def test_calculate_score_minimum_is_zero(self, tester):
        """Test that score never goes below zero."""
        from Asgard.Freya.Responsive.models.responsive_models import MobileCompatibilityIssue

        many_issues = [
            MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.FLASH_CONTENT,
                description="Flash",
                severity="critical",
                suggested_fix="Fix",
            )
            for _ in range(20)
        ]

        score = tester._calculate_score(many_issues, 10000, 50 * 1024 * 1024)

        assert score == 0.0

    @pytest.mark.L0
    def test_calculate_score_maximum_is_hundred(self, tester):
        """Test that score never exceeds 100."""
        score = tester._calculate_score([], 500, 100000)

        assert score == 100.0


# =============================================================================
# Integration Tests
# =============================================================================

class TestMobileCompatibilityTesterIntegration:
    """Integration tests for MobileCompatibilityTester."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.async_playwright")
    @patch("Asgard.Freya.Responsive.services.mobile_compatibility.time")
    async def test_test_produces_complete_report(self, mock_time, mock_playwright, tester):
        """Test that test method produces a complete report."""
        mock_time.time.side_effect = [0, 2.5]

        mock_page = AsyncMock()
        mock_response = MagicMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.evaluate = AsyncMock(side_effect=[
            2,
            [{"selector": "nav", "type": "hidden-menu"}],
            [{"selector": "p", "fontSize": 10}],
            [],
            {"resourceCount": 30, "totalSize": 1536000},
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

        report = await tester.test(url="https://example.com", devices=["iphone-14"])

        assert report.url == "https://example.com"
        assert len(report.issues) > 0
        assert report.load_time_ms is not None
        assert report.mobile_friendly_score < 100.0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
