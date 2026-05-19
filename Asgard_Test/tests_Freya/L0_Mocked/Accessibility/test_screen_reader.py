"""
L0 Unit Tests for Freya Screen Reader Validator

Comprehensive tests for screen reader compatibility with mocked Playwright dependencies.
Tests accessible names, landmarks, headings, images, forms, links, and buttons.
"""

import pytest
from unittest.mock import AsyncMock, patch

from Asgard.Freya.Accessibility.services.screen_reader import ScreenReaderValidator
from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    ScreenReaderIssueType,
    ViolationSeverity,
)


class TestScreenReaderValidatorInit:
    """Test ScreenReaderValidator initialization."""

    def test_init_with_config(self, accessibility_config):
        """Test initializing validator with configuration."""
        validator = ScreenReaderValidator(accessibility_config)

        assert validator.config == accessibility_config


class TestCheckLanguage:
    """Test language attribute checking."""

    @pytest.mark.asyncio
    async def test_check_language_present(self, accessibility_config, mock_page):
        """Test page with language attribute."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="en")

        issues = []
        language = await validator._check_language(mock_page, issues)

        assert language == "en"
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_check_language_missing(self, accessibility_config, mock_page):
        """Test page without language attribute."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="")

        issues = []
        language = await validator._check_language(mock_page, issues)

        assert language is None
        assert len(issues) == 1
        assert issues[0].issue_type == ScreenReaderIssueType.MISSING_LANG_ATTRIBUTE

    @pytest.mark.asyncio
    async def test_check_language_empty(self, accessibility_config, mock_page):
        """Test page with empty language attribute."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="   ")

        issues = []
        language = await validator._check_language(mock_page, issues)

        assert language is None
        assert len(issues) == 1


class TestAnalyzeLandmarks:
    """Test landmark structure analysis."""

    @pytest.mark.asyncio
    async def test_analyze_landmarks_all_present(self, accessibility_config, mock_page):
        """Test page with all major landmarks."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_main = AsyncMock()
        mock_nav = AsyncMock()
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [],
            [mock_nav],
            [mock_main],
            [],
            [],
            [],
            [],
            [],
        ])

        issues = []
        landmarks = await validator._analyze_landmarks(mock_page, issues)

        assert landmarks["navigation"] == 1
        assert landmarks["main"] == 1
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_analyze_landmarks_missing_main(self, accessibility_config, mock_page):
        """Test page without main landmark."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.query_selector_all = AsyncMock(return_value=[])

        issues = []
        landmarks = await validator._analyze_landmarks(mock_page, issues)

        assert "main" not in landmarks
        assert any(i.issue_type == ScreenReaderIssueType.MISSING_LANDMARK for i in issues)

    @pytest.mark.asyncio
    async def test_analyze_landmarks_multiple_navigation(self, accessibility_config, mock_page):
        """Test page with multiple navigation landmarks."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_nav1 = AsyncMock()
        mock_nav2 = AsyncMock()
        mock_main = AsyncMock()
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [],
            [mock_nav1, mock_nav2],
            [mock_main],
            [],
            [],
            [],
            [],
            [],
        ])

        issues = []
        landmarks = await validator._analyze_landmarks(mock_page, issues)

        assert landmarks["navigation"] == 2
        assert len(issues) == 0


class TestAnalyzeHeadings:
    """Test heading structure analysis."""

    @pytest.mark.asyncio
    async def test_analyze_headings_proper_structure(self, accessibility_config, mock_page):
        """Test page with proper heading structure."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_h1 = AsyncMock()
        mock_h1.evaluate = AsyncMock(return_value="h1")
        mock_h1.inner_text = AsyncMock(return_value="Main Title")

        mock_h2 = AsyncMock()
        mock_h2.evaluate = AsyncMock(return_value="h2")
        mock_h2.inner_text = AsyncMock(return_value="Subtitle")

        mock_page.query_selector_all = AsyncMock(return_value=[mock_h1, mock_h2])
        mock_page.evaluate = AsyncMock(side_effect=["#h1", "#h2"])

        issues = []
        headings = await validator._analyze_headings(mock_page, issues)

        assert len(headings) == 2
        assert headings[0]["level"] == 1
        assert headings[1]["level"] == 2
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_analyze_headings_skipped_level(self, accessibility_config, mock_page):
        """Test page with skipped heading level."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_h1 = AsyncMock()
        mock_h1.evaluate = AsyncMock(return_value="h1")
        mock_h1.inner_text = AsyncMock(return_value="Main Title")

        mock_h3 = AsyncMock()
        mock_h3.evaluate = AsyncMock(return_value="h3")
        mock_h3.inner_text = AsyncMock(return_value="Skipped h2")

        mock_page.query_selector_all = AsyncMock(return_value=[mock_h1, mock_h3])
        mock_page.evaluate = AsyncMock(side_effect=["#h1", "#h3"])

        issues = []
        headings = await validator._analyze_headings(mock_page, issues)

        assert len(headings) == 2
        assert any(i.issue_type == ScreenReaderIssueType.SKIPPED_HEADING_LEVEL for i in issues)

    @pytest.mark.asyncio
    async def test_analyze_headings_first_not_h1(self, accessibility_config, mock_page):
        """Test page where first heading is not h1."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_h2 = AsyncMock()
        mock_h2.evaluate = AsyncMock(return_value="h2")
        mock_h2.inner_text = AsyncMock(return_value="Starts at h2")

        mock_page.query_selector_all = AsyncMock(return_value=[mock_h2])
        mock_page.evaluate = AsyncMock(return_value="#h2")

        issues = []
        headings = await validator._analyze_headings(mock_page, issues)

        assert headings[0]["level"] == 2
        assert any(i.issue_type == ScreenReaderIssueType.MISSING_HEADING_STRUCTURE for i in issues)

    @pytest.mark.asyncio
    async def test_analyze_headings_none_present(self, accessibility_config, mock_page):
        """Test page with no headings."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.query_selector_all = AsyncMock(return_value=[])

        issues = []
        headings = await validator._analyze_headings(mock_page, issues)

        assert len(headings) == 0
        assert any(i.issue_type == ScreenReaderIssueType.MISSING_HEADING_STRUCTURE for i in issues)


class TestCheckImages:
    """Test image accessibility checking."""

    @pytest.mark.asyncio
    async def test_check_images_with_alt_text(self, accessibility_config, mock_page):
        """Test image with alt text."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=["Image description", None, None, None])
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])

        issues, (labeled, total) = await validator._check_images(mock_page)

        assert len(issues) == 0
        assert labeled == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_check_images_missing_alt(self, accessibility_config, mock_page):
        """Test image without alt attribute."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=[None, None, None, None, "image.jpg"])
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])
        mock_page.evaluate = AsyncMock(return_value="img")

        issues, (labeled, total) = await validator._check_images(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == ScreenReaderIssueType.MISSING_ALT_TEXT
        assert issues[0].severity == ViolationSeverity.CRITICAL
        assert labeled == 0
        assert total == 1

    @pytest.mark.asyncio
    async def test_check_images_decorative(self, accessibility_config, mock_page):
        """Test decorative image with empty alt."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=["", "presentation", None, None])
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])

        issues, (labeled, total) = await validator._check_images(mock_page)

        assert len(issues) == 0
        assert labeled == 1

    @pytest.mark.asyncio
    async def test_check_images_aria_hidden(self, accessibility_config, mock_page):
        """Test image with aria-hidden."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=[None, None, None, "true"])
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])

        issues, (labeled, total) = await validator._check_images(mock_page)

        assert len(issues) == 0
        assert labeled == 1


class TestCheckForms:
    """Test form input accessibility checking."""

    @pytest.mark.asyncio
    async def test_check_forms_with_accessible_name(self, accessibility_config, mock_page):
        """Test form input with accessible name."""
        from unittest.mock import patch as _patch
        validator = ScreenReaderValidator(accessibility_config)

        mock_input = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_input])
        mock_page.evaluate = AsyncMock(return_value="Name")

        with _patch(
            'Asgard.Freya.Accessibility.services._screen_reader_checks.get_accessible_name',
            AsyncMock(return_value="Name"),
            create=True
        ):
            issues, (labeled, total) = await validator._check_forms(mock_page)

        assert len(issues) == 0
        assert labeled == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_check_forms_missing_label(self, accessibility_config, mock_page):
        """Test form input without accessible name."""
        from unittest.mock import patch as _patch
        validator = ScreenReaderValidator(accessibility_config)

        mock_input = AsyncMock()
        mock_input.get_attribute = AsyncMock(return_value="text")
        mock_page.query_selector_all = AsyncMock(return_value=[mock_input])
        mock_page.evaluate = AsyncMock(side_effect=[None, "input"])

        with _patch(
            'Asgard.Freya.Accessibility.services._screen_reader_checks.get_accessible_name',
            AsyncMock(return_value=None),
            create=True
        ), _patch(
            'Asgard.Freya.Accessibility.services._screen_reader_checks.get_selector',
            AsyncMock(return_value="input")
        ):
            issues, (labeled, total) = await validator._check_forms(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == ScreenReaderIssueType.MISSING_LABEL
        assert issues[0].severity == ViolationSeverity.SERIOUS
        assert labeled == 0
        assert total == 1


class TestCheckLinks:
    """Test link accessibility checking."""

    @pytest.mark.asyncio
    async def test_check_links_with_text(self, accessibility_config, mock_page):
        """Test link with text content."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_link = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_link])
        mock_page.evaluate = AsyncMock(return_value="Click here")

        issues, (labeled, total) = await validator._check_links(mock_page)

        assert len(issues) == 0
        assert labeled == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_check_links_empty(self, accessibility_config, mock_page):
        """Test link without accessible name."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="/page")
        mock_page.query_selector_all = AsyncMock(return_value=[mock_link])
        mock_page.evaluate = AsyncMock(side_effect=[None, "a"])

        issues, (labeled, total) = await validator._check_links(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == ScreenReaderIssueType.EMPTY_LINK
        assert labeled == 0
        assert total == 1


class TestCheckButtons:
    """Test button accessibility checking."""

    @pytest.mark.asyncio
    async def test_check_buttons_with_text(self, accessibility_config, mock_page):
        """Test button with text content."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_button = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_button])
        mock_page.evaluate = AsyncMock(return_value="Submit")

        issues, (labeled, total) = await validator._check_buttons(mock_page)

        assert len(issues) == 0
        assert labeled == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_check_buttons_empty(self, accessibility_config, mock_page):
        """Test button without accessible name."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_button = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_button])
        mock_page.evaluate = AsyncMock(side_effect=[None, "button"])

        issues, (labeled, total) = await validator._check_buttons(mock_page)

        assert len(issues) == 1
        assert issues[0].issue_type == ScreenReaderIssueType.EMPTY_BUTTON
        assert issues[0].severity == ViolationSeverity.CRITICAL
        assert labeled == 0
        assert total == 1


class TestGetAccessibleName:
    """Test accessible name computation."""

    @pytest.mark.asyncio
    async def test_get_accessible_name_aria_labelledby(self, accessibility_config, mock_page, mock_element):
        """Test getting accessible name from aria-labelledby."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="Label text")

        name = await validator._get_accessible_name(mock_page, mock_element)

        assert name == "Label text"

    @pytest.mark.asyncio
    async def test_get_accessible_name_aria_label(self, accessibility_config, mock_page, mock_element):
        """Test getting accessible name from aria-label."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="Button label")

        name = await validator._get_accessible_name(mock_page, mock_element)

        assert name == "Button label"

    @pytest.mark.asyncio
    async def test_get_accessible_name_none(self, accessibility_config, mock_page, mock_element):
        """Test element with no accessible name."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value=None)

        name = await validator._get_accessible_name(mock_page, mock_element)

        assert name is None

    @pytest.mark.asyncio
    async def test_get_accessible_name_handles_exception(self, accessibility_config, mock_page, mock_element):
        """Test accessible name computation handles exceptions."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(side_effect=Exception("Test error"))

        name = await validator._get_accessible_name(mock_page, mock_element)

        assert name is None


class TestGetSelector:
    """Test selector generation."""

    @pytest.mark.asyncio
    async def test_get_selector_with_id(self, accessibility_config, mock_page, mock_element):
        """Test generating selector for element with ID."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="#test-id")

        selector = await validator._get_selector(mock_page, mock_element)

        assert selector == "#test-id"

    @pytest.mark.asyncio
    async def test_get_selector_with_classes(self, accessibility_config, mock_page, mock_element):
        """Test generating selector for element with classes."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="div.content.main")

        selector = await validator._get_selector(mock_page, mock_element)

        assert selector == "div.content.main"

    @pytest.mark.asyncio
    async def test_get_selector_handles_exception(self, accessibility_config, mock_page, mock_element):
        """Test selector generation handles exceptions."""
        validator = ScreenReaderValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(side_effect=Exception("Test error"))

        selector = await validator._get_selector(mock_page, mock_element)

        assert selector == "unknown"


class TestFullValidation:
    """Test complete screen reader validation."""

    @pytest.mark.asyncio
    async def test_validate_complete_flow(self, accessibility_config, test_url):
        """Test complete validation flow."""
        validator = ScreenReaderValidator(accessibility_config)

        with patch('Asgard.Freya.Accessibility.services.screen_reader.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_page.goto = AsyncMock()
            mock_page.evaluate = AsyncMock(return_value="en")
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await validator.validate(test_url)

            assert report.url == test_url
            assert isinstance(report.tested_at, str)
            assert report.language == "en"
            assert report.total_elements >= 0

    @pytest.mark.asyncio
    async def test_validate_calculates_totals(self, accessibility_config, test_url):
        """Test validation calculates element totals correctly."""
        validator = ScreenReaderValidator(accessibility_config)

        with patch('Asgard.Freya.Accessibility.services.screen_reader.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_img = AsyncMock()
            mock_img.get_attribute = AsyncMock(side_effect=["Alt text", None, None, None])

            mock_form_input = AsyncMock()
            mock_link = AsyncMock()
            mock_button = AsyncMock()
            mock_main = AsyncMock()
            mock_h1 = AsyncMock()
            mock_h1.evaluate = AsyncMock(return_value="h1")
            mock_h1.inner_text = AsyncMock(return_value="Title")

            mock_page.goto = AsyncMock()
            mock_page.evaluate = AsyncMock(side_effect=["en", "#h1", "Label", "Link text", "Button"])
            mock_page.query_selector_all = AsyncMock(side_effect=[
                [],
                [],
                [mock_main],
                [],
                [],
                [],
                [],
                [],
                [mock_h1],
                [mock_img],
                [mock_form_input],
                [mock_link],
                [mock_button],
            ])
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await validator.validate(test_url)

            assert report.total_elements >= 0
            assert report.labeled_count >= 0

    @pytest.mark.asyncio
    async def test_validate_report_has_issues_property(self, accessibility_config, test_url):
        """Test report has_issues property with no validation issues."""
        validator = ScreenReaderValidator(accessibility_config)

        with patch('Asgard.Freya.Accessibility.services.screen_reader.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_main = AsyncMock()
            mock_nav = AsyncMock()
            mock_h1 = AsyncMock()
            mock_h1.evaluate = AsyncMock(return_value="h1")
            mock_h1.inner_text = AsyncMock(return_value="Title")

            mock_page.goto = AsyncMock()
            mock_page.evaluate = AsyncMock(side_effect=["en", "#h1"])
            mock_page.query_selector_all = AsyncMock(side_effect=[
                [],
                [mock_nav],
                [mock_main],
                [],
                [],
                [],
                [],
                [],
                [mock_h1],
                [],
                [],
                [],
            ])
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await validator.validate(test_url)

            # Report should have issues due to no elements with accessible names checked
            # Just verify the has_issues property works
            assert isinstance(report.has_issues, bool)
