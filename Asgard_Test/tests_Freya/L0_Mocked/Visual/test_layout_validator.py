"""
Freya Visual L0 Mocked Tests - Layout Validator

Comprehensive tests for layout validation service with mocked Playwright.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from Asgard.Freya.Visual.models.visual_models import LayoutIssueType
from Asgard.Freya.Visual.services.layout_validator import LayoutValidator


# =============================================================================
# Test LayoutValidator Initialization
# =============================================================================

class TestLayoutValidatorInit:
    """Tests for LayoutValidator initialization."""

    @pytest.mark.L0
    def test_init(self):
        """Test LayoutValidator initialization."""
        validator = LayoutValidator()

        assert validator is not None


# =============================================================================
# Test validate Method
# =============================================================================

class TestValidate:
    """Tests for validate method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_validate_basic(self, mock_async_playwright, mock_page):
        """Test basic layout validation."""
        validator = LayoutValidator()

        # Mock page.evaluate to return empty results for all checks
        mock_page.evaluate.return_value = []

        with patch("Asgard.Freya.Visual.services.layout_validator.async_playwright", mock_async_playwright):
            report = await validator.validate(
                url="https://example.com",
                viewport_width=1920,
                viewport_height=1080,
            )

        assert report.url == "https://example.com"
        assert report.viewport_width == 1920
        assert report.viewport_height == 1080
        assert report.tested_at is not None
        assert isinstance(report.issues, list)
        assert isinstance(report.overflow_elements, list)
        assert isinstance(report.overlapping_elements, list)

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_validate_custom_viewport(self, mock_async_playwright, mock_page, mock_browser):
        """Test validation with custom viewport size."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        with patch("Asgard.Freya.Visual.services.layout_validator.async_playwright", mock_async_playwright):
            report = await validator.validate(
                url="https://example.com",
                viewport_width=800,
                viewport_height=600,
            )

        # Verify browser context was created with correct viewport
        mock_browser.new_context.assert_called_once()
        context_args = mock_browser.new_context.call_args[1]
        assert context_args["viewport"]["width"] == 800
        assert context_args["viewport"]["height"] == 600

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_validate_browser_closes(self, mock_async_playwright, mock_browser, mock_page):
        """Test that browser is closed after validation."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        with patch("Asgard.Freya.Visual.services.layout_validator.async_playwright", mock_async_playwright):
            await validator.validate(url="https://example.com")

        mock_browser.close.assert_called_once()

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_validate_waits_for_network_idle(self, mock_async_playwright, mock_page):
        """Test that validation waits for network idle."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        with patch("Asgard.Freya.Visual.services.layout_validator.async_playwright", mock_async_playwright):
            await validator.validate(url="https://example.com")

        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args
        assert call_args[1]["wait_until"] == "networkidle"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_validate_calls_all_check_methods(self, mock_async_playwright, mock_page):
        """Test that validate calls all check methods."""
        validator = LayoutValidator()

        # Configure mock to track evaluate calls
        evaluate_calls = []

        async def track_evaluate(script):
            evaluate_calls.append(script)
            if isinstance(script, str) and "querySelectorAll('*').length" in script:
                return 42
            return [] if isinstance(script, str) else 0

        mock_page.evaluate.side_effect = track_evaluate

        with patch("Asgard.Freya.Visual.services.layout_validator.async_playwright", mock_async_playwright):
            report = await validator.validate(url="https://example.com")

        # Should have called evaluate multiple times for different checks
        assert len(evaluate_calls) > 0


# =============================================================================
# Test _check_overflow Method
# =============================================================================

class TestCheckOverflow:
    """Tests for _check_overflow method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overflow_no_issues(self, mock_page):
        """Test overflow check with no issues found."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        issues, overflow_elements = await validator._check_overflow(mock_page)

        assert len(issues) == 0
        assert len(overflow_elements) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overflow_horizontal_overflow(self, mock_page):
        """Test overflow check detects horizontal overflow."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector": ".wide-container",
                "type": "horizontal",
                "scrollWidth": 2000,
                "clientWidth": 1920,
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 100,
            }
        ]

        issues, overflow_elements = await validator._check_overflow(mock_page)

        assert len(issues) == 1
        assert len(overflow_elements) == 1
        assert issues[0].issue_type == LayoutIssueType.OVERFLOW
        assert issues[0].element_selector == ".wide-container"
        assert "overflows horizontally" in issues[0].description
        assert issues[0].severity == "moderate"
        assert ".wide-container" in overflow_elements

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overflow_viewport_overflow(self, mock_page):
        """Test overflow check detects viewport overflow."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector": "#sidebar",
                "type": "viewport",
                "left": -100,
                "right": 2000,
                "viewportWidth": 1920,
                "x": -100,
                "y": 0,
                "width": 300,
                "height": 800,
            }
        ]

        issues, overflow_elements = await validator._check_overflow(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == LayoutIssueType.OVERFLOW
        assert "extends beyond viewport" in issues[0].description
        assert issues[0].affected_area is not None
        assert issues[0].affected_area.selector == "#sidebar"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overflow_multiple_issues(self, mock_page):
        """Test overflow check detects multiple overflow issues."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector": ".container1",
                "type": "horizontal",
                "scrollWidth": 2000,
                "clientWidth": 1920,
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 100,
            },
            {
                "selector": ".container2",
                "type": "viewport",
                "left": 0,
                "right": 2000,
                "viewportWidth": 1920,
                "x": 0,
                "y": 200,
                "width": 2000,
                "height": 100,
            }
        ]

        issues, overflow_elements = await validator._check_overflow(mock_page)

        assert len(issues) == 2
        assert len(overflow_elements) == 2

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overflow_handles_exceptions(self, mock_page):
        """Test overflow check handles exceptions gracefully."""
        validator = LayoutValidator()

        mock_page.evaluate.side_effect = Exception("Evaluation failed")

        issues, overflow_elements = await validator._check_overflow(mock_page)

        # Should return empty lists on error
        assert len(issues) == 0
        assert len(overflow_elements) == 0


# =============================================================================
# Test _check_overlap Method
# =============================================================================

class TestCheckOverlap:
    """Tests for _check_overlap method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overlap_no_issues(self, mock_page):
        """Test overlap check with no issues found."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        issues, overlapping_pairs = await validator._check_overlap(mock_page)

        assert len(issues) == 0
        assert len(overlapping_pairs) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overlap_detects_overlapping_elements(self, mock_page):
        """Test overlap check detects overlapping interactive elements."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector1": "#button1",
                "selector2": "#button2",
                "rect1": {"x": 10, "y": 20, "width": 100, "height": 50},
                "rect2": {"x": 50, "y": 30, "width": 100, "height": 50},
            }
        ]

        issues, overlapping_pairs = await validator._check_overlap(mock_page)

        assert len(issues) == 1
        assert len(overlapping_pairs) == 1
        assert issues[0].issue_type == LayoutIssueType.OVERLAP
        assert issues[0].element_selector == "#button1"
        assert "#button2" in issues[0].description
        assert issues[0].severity == "serious"
        assert "#button2" in issues[0].related_elements
        assert overlapping_pairs[0] == ("#button1", "#button2")

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overlap_multiple_overlaps(self, mock_page):
        """Test overlap check detects multiple overlaps."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector1": "button",
                "selector2": "a",
                "rect1": {"x": 10, "y": 20, "width": 100, "height": 50},
                "rect2": {"x": 50, "y": 30, "width": 100, "height": 50},
            },
            {
                "selector1": "input",
                "selector2": "select",
                "rect1": {"x": 200, "y": 20, "width": 100, "height": 50},
                "rect2": {"x": 240, "y": 30, "width": 100, "height": 50},
            }
        ]

        issues, overlapping_pairs = await validator._check_overlap(mock_page)

        assert len(issues) == 2
        assert len(overlapping_pairs) == 2

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_overlap_handles_exceptions(self, mock_page):
        """Test overlap check handles exceptions gracefully."""
        validator = LayoutValidator()

        mock_page.evaluate.side_effect = Exception("Evaluation failed")

        issues, overlapping_pairs = await validator._check_overlap(mock_page)

        assert len(issues) == 0
        assert len(overlapping_pairs) == 0


# =============================================================================
# Test _check_alignment Method
# =============================================================================

class TestCheckAlignment:
    """Tests for _check_alignment method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_alignment_no_issues(self, mock_page):
        """Test alignment check with no issues found."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        issues = await validator._check_alignment(mock_page)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_alignment_detects_misalignment(self, mock_page):
        """Test alignment check detects misaligned elements."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector": ".flex-container",
                "variance": 12.5,
            }
        ]

        issues = await validator._check_alignment(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == LayoutIssueType.MISALIGNMENT
        assert issues[0].element_selector == ".flex-container"
        assert "12.5" in issues[0].description
        assert issues[0].severity == "minor"
        assert "align-items" in issues[0].suggested_fix

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_alignment_multiple_issues(self, mock_page):
        """Test alignment check detects multiple misalignments."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {"selector": ".container1", "variance": 10.0},
            {"selector": ".container2", "variance": 15.5},
        ]

        issues = await validator._check_alignment(mock_page)

        assert len(issues) == 2

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_alignment_handles_exceptions(self, mock_page):
        """Test alignment check handles exceptions gracefully."""
        validator = LayoutValidator()

        mock_page.evaluate.side_effect = Exception("Evaluation failed")

        issues = await validator._check_alignment(mock_page)

        assert len(issues) == 0


# =============================================================================
# Test _check_spacing Method
# =============================================================================

class TestCheckSpacing:
    """Tests for _check_spacing method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_spacing_no_issues(self, mock_page):
        """Test spacing check with no issues found."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        issues = await validator._check_spacing(mock_page)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_spacing_detects_tight_line_height(self, mock_page):
        """Test spacing check detects tight line height."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector": "p",
                "type": "line-height",
                "lineHeight": 16.0,
                "fontSize": 16.0,
            }
        ]

        issues = await validator._check_spacing(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == LayoutIssueType.SPACING
        assert issues[0].element_selector == "p"
        assert "too tight" in issues[0].description
        assert issues[0].severity == "minor"
        assert "1.5x" in issues[0].suggested_fix

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_spacing_multiple_issues(self, mock_page):
        """Test spacing check detects multiple spacing issues."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {"selector": "p", "type": "line-height", "lineHeight": 14.0, "fontSize": 14.0},
            {"selector": "h1", "type": "line-height", "lineHeight": 20.0, "fontSize": 18.0},
        ]

        issues = await validator._check_spacing(mock_page)

        assert len(issues) == 2

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_spacing_handles_exceptions(self, mock_page):
        """Test spacing check handles exceptions gracefully."""
        validator = LayoutValidator()

        mock_page.evaluate.side_effect = Exception("Evaluation failed")

        issues = await validator._check_spacing(mock_page)

        assert len(issues) == 0


# =============================================================================
# Test _check_visibility Method
# =============================================================================

class TestCheckVisibility:
    """Tests for _check_visibility method."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_visibility_no_issues(self, mock_page):
        """Test visibility check with no issues found."""
        validator = LayoutValidator()
        mock_page.evaluate.return_value = []

        issues = await validator._check_visibility(mock_page)

        assert len(issues) == 0

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_visibility_detects_small_elements(self, mock_page):
        """Test visibility check detects elements that are too small."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector": "button",
                "type": "too_small",
                "width": 20,
                "height": 20,
            }
        ]

        issues = await validator._check_visibility(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == LayoutIssueType.VISIBILITY
        assert issues[0].element_selector == "button"
        assert "too small" in issues[0].description
        assert "20x20" in issues[0].description
        assert issues[0].severity == "moderate"
        assert "44x44" in issues[0].suggested_fix

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_visibility_detects_invisible_elements(self, mock_page):
        """Test visibility check detects invisible elements."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {
                "selector": "a",
                "type": "invisible",
            }
        ]

        issues = await validator._check_visibility(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == LayoutIssueType.VISIBILITY
        assert issues[0].element_selector == "a"
        assert "zero opacity" in issues[0].description
        assert issues[0].severity == "serious"

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_visibility_multiple_issues(self, mock_page):
        """Test visibility check detects multiple visibility issues."""
        validator = LayoutValidator()

        mock_page.evaluate.return_value = [
            {"selector": "button", "type": "too_small", "width": 15, "height": 15},
            {"selector": "input", "type": "invisible"},
            {"selector": "a", "type": "too_small", "width": 10, "height": 30},
        ]

        issues = await validator._check_visibility(mock_page)

        assert len(issues) == 3

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_check_visibility_handles_exceptions(self, mock_page):
        """Test visibility check handles exceptions gracefully."""
        validator = LayoutValidator()

        mock_page.evaluate.side_effect = Exception("Evaluation failed")

        issues = await validator._check_visibility(mock_page)

        assert len(issues) == 0


# =============================================================================
# Test Integration
# =============================================================================

class TestLayoutValidatorIntegration:
    """Integration tests for LayoutValidator."""

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_validate_combines_all_issues(self, mock_async_playwright, mock_page):
        """Test that validate combines issues from all check methods."""
        validator = LayoutValidator()

        # Track which JavaScript function was called
        call_count = [0]

        async def mock_evaluate(script):
            call_count[0] += 1
            # Return different mock data based on call order
            if call_count[0] == 1:  # overflow check
                return [{"selector": ".overflow", "type": "horizontal", "scrollWidth": 2000,
                         "clientWidth": 1920, "x": 0, "y": 0, "width": 1920, "height": 100}]
            elif call_count[0] == 2:  # overlap check
                return [{"selector1": "#btn1", "selector2": "#btn2",
                         "rect1": {"x": 10, "y": 20, "width": 100, "height": 50},
                         "rect2": {"x": 50, "y": 30, "width": 100, "height": 50}}]
            elif call_count[0] == 3:  # alignment check
                return [{"selector": ".flex", "variance": 10.0}]
            elif call_count[0] == 4:  # spacing check
                return [{"selector": "p", "type": "line-height", "lineHeight": 14.0, "fontSize": 14.0}]
            elif call_count[0] == 5:  # visibility check
                return [{"selector": "button", "type": "too_small", "width": 20, "height": 20}]
            else:  # total elements count
                return 150

        mock_page.evaluate.side_effect = mock_evaluate

        with patch("Asgard.Freya.Visual.services.layout_validator.async_playwright", mock_async_playwright):
            report = await validator.validate(url="https://example.com")

        # Should have issues from all checks
        assert len(report.issues) == 5
        assert report.total_elements == 150

        # Verify issue types
        issue_types = {issue.issue_type for issue in report.issues}
        assert LayoutIssueType.OVERFLOW in issue_types
        assert LayoutIssueType.OVERLAP in issue_types
        assert LayoutIssueType.MISALIGNMENT in issue_types
        assert LayoutIssueType.SPACING in issue_types
        assert LayoutIssueType.VISIBILITY in issue_types

    @pytest.mark.L0
    @pytest.mark.asyncio
    async def test_validate_error_recovery(self, mock_async_playwright, mock_page):
        """Test that validate recovers from errors in individual checks."""
        validator = LayoutValidator()

        # Make some checks fail
        call_count = [0]

        async def mock_evaluate(script):
            call_count[0] += 1
            if call_count[0] in [1, 3]:  # overflow and alignment fail
                raise Exception("Check failed")
            elif call_count[0] == 2:  # overlap succeeds
                return [{"selector1": "#btn1", "selector2": "#btn2",
                         "rect1": {"x": 10, "y": 20, "width": 100, "height": 50},
                         "rect2": {"x": 50, "y": 30, "width": 100, "height": 50}}]
            elif call_count[0] == 6:  # total elements
                return 100
            else:
                return []

        mock_page.evaluate.side_effect = mock_evaluate

        with patch("Asgard.Freya.Visual.services.layout_validator.async_playwright", mock_async_playwright):
            report = await validator.validate(url="https://example.com")

        # Should still return a report with issues from successful checks
        assert report is not None
        assert len(report.issues) >= 1  # At least the overlap issue
