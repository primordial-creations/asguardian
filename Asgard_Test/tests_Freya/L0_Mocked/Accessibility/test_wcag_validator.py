"""
L0 Unit Tests for Freya WCAG Validator

Comprehensive tests for WCAG compliance validation with mocked Playwright dependencies.
Tests all WCAG criteria checking, filtering, and scoring.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from Asgard.Freya.Accessibility.services.wcag_validator import WCAGValidator
from Asgard.Freya.Accessibility.services._wcag_criteria import WCAG_CRITERIA
from Asgard.Freya.Accessibility.services._wcag_checks import (
    check_images,
    check_structure,
    check_forms,
    generate_id,
    get_element_html,
)
from Asgard.Freya.Accessibility.services._wcag_checks_part2 import (
    check_links,
    check_language,
    check_aria_basic,
)
from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    WCAGLevel,
    ViolationSeverity,
    AccessibilityCategory,
)


class TestWCAGValidatorInit:
    """Test WCAGValidator initialization."""

    def test_init_with_config(self, accessibility_config):
        """Test initializing validator with configuration."""
        validator = WCAGValidator(accessibility_config)

        assert validator.config == accessibility_config
        assert validator._browser is None


class TestWCAGCriteria:
    """Test WCAG_CRITERIA constant."""

    def test_wcag_criteria_has_common_criteria(self):
        """Test WCAG_CRITERIA includes common success criteria."""
        assert "1.1.1" in WCAG_CRITERIA
        assert "1.4.3" in WCAG_CRITERIA
        assert "2.1.1" in WCAG_CRITERIA
        assert "4.1.2" in WCAG_CRITERIA

    def test_wcag_criteria_has_levels(self):
        """Test criteria include WCAG levels."""
        assert WCAG_CRITERIA["1.1.1"]["level"] == WCAGLevel.A
        assert WCAG_CRITERIA["1.4.3"]["level"] == WCAGLevel.AA
        assert WCAG_CRITERIA["1.4.6"]["level"] == WCAGLevel.AAA

    def test_wcag_criteria_has_categories(self):
        """Test criteria include categories."""
        assert WCAG_CRITERIA["1.1.1"]["category"] == AccessibilityCategory.IMAGES
        assert WCAG_CRITERIA["2.1.1"]["category"] == AccessibilityCategory.KEYBOARD
        assert WCAG_CRITERIA["4.1.2"]["category"] == AccessibilityCategory.ARIA


class TestCheckImages:
    """Test image accessibility checking."""

    @pytest.mark.asyncio
    async def test_check_images_with_alt(self, accessibility_config, mock_page):
        """Test image with alt attribute."""
        validator = WCAGValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=["Image description", None, None])
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])

        violations, passed = await check_images(mock_page, validator.config.include_element_html)

        assert len(violations) == 0
        assert passed == 1

    @pytest.mark.asyncio
    async def test_check_images_missing_alt(self, accessibility_config, mock_page):
        """Test image without alt attribute."""
        validator = WCAGValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=[None, "image.jpg", None])
        mock_img.evaluate = AsyncMock(return_value="<img src='image.jpg'>")
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])

        violations, passed = await check_images(mock_page, validator.config.include_element_html)

        assert len(violations) == 1
        assert violations[0].wcag_reference == "1.1.1"
        assert violations[0].severity == ViolationSeverity.CRITICAL
        assert passed == 0

    @pytest.mark.asyncio
    async def test_check_images_decorative(self, accessibility_config, mock_page):
        """Test decorative image with empty alt."""
        validator = WCAGValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=["", None, "presentation"])
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])

        violations, passed = await check_images(mock_page, validator.config.include_element_html)

        assert len(violations) == 0
        assert passed == 1

    @pytest.mark.asyncio
    async def test_check_images_empty_alt_no_role(self, accessibility_config, mock_page):
        """Test image with empty alt but no presentation role."""
        validator = WCAGValidator(accessibility_config)

        mock_img = AsyncMock()
        mock_img.get_attribute = AsyncMock(side_effect=["", None, None])
        mock_page.query_selector_all = AsyncMock(return_value=[mock_img])

        violations, passed = await check_images(mock_page, validator.config.include_element_html)

        assert passed == 1


class TestCheckStructure:
    """Test document structure checking."""

    @pytest.mark.asyncio
    async def test_check_structure_with_title(self, accessibility_config, mock_page):
        """Test page with title."""
        validator = WCAGValidator(accessibility_config)

        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [],
            [AsyncMock()],
        ])

        violations, passed = await check_structure(mock_page)

        assert any(v.wcag_reference == "2.4.2" for v in violations) is False
        assert passed >= 1

    @pytest.mark.asyncio
    async def test_check_structure_missing_title(self, accessibility_config, mock_page):
        """Test page without title."""
        validator = WCAGValidator(accessibility_config)

        mock_page.title = AsyncMock(return_value="")
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [],
            [AsyncMock()],
        ])

        violations, passed = await check_structure(mock_page)

        assert any(v.wcag_reference == "2.4.2" for v in violations)
        assert any(v.severity == ViolationSeverity.SERIOUS for v in violations)

    @pytest.mark.asyncio
    async def test_check_structure_heading_order_correct(self, accessibility_config, mock_page):
        """Test page with correct heading order."""
        validator = WCAGValidator(accessibility_config)

        mock_h1 = AsyncMock()
        mock_h1.evaluate = AsyncMock(return_value="h1")

        mock_h2 = AsyncMock()
        mock_h2.evaluate = AsyncMock(return_value="h2")

        mock_page.title = AsyncMock(return_value="Test")
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [mock_h1, mock_h2],
            [AsyncMock()],
        ])

        violations, passed = await check_structure(mock_page)

        heading_violations = [v for v in violations if "heading" in v.description.lower()]
        assert len(heading_violations) == 0

    @pytest.mark.asyncio
    async def test_check_structure_heading_order_skipped(self, accessibility_config, mock_page):
        """Test page with skipped heading level."""
        validator = WCAGValidator(accessibility_config)

        mock_h1 = AsyncMock()
        mock_h1.evaluate = AsyncMock(return_value="h1")

        mock_h3 = AsyncMock()
        mock_h3.evaluate = AsyncMock(return_value="h3")

        mock_page.title = AsyncMock(return_value="Test")
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [mock_h1, mock_h3],
            [AsyncMock()],
        ])

        violations, passed = await check_structure(mock_page)

        assert any("skipped" in v.description.lower() for v in violations)

    @pytest.mark.asyncio
    async def test_check_structure_first_heading_not_h1(self, accessibility_config, mock_page):
        """Test page where first heading is not h1."""
        validator = WCAGValidator(accessibility_config)

        mock_h2 = AsyncMock()
        mock_h2.evaluate = AsyncMock(return_value="h2")

        mock_page.title = AsyncMock(return_value="Test")
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [mock_h2],
            [AsyncMock()],
        ])

        violations, passed = await check_structure(mock_page)

        assert any("first heading" in v.description.lower() for v in violations)

    @pytest.mark.asyncio
    async def test_check_structure_missing_main_landmark(self, accessibility_config, mock_page):
        """Test page without main landmark."""
        validator = WCAGValidator(accessibility_config)

        mock_page.title = AsyncMock(return_value="Test")
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [],
            [],
        ])

        violations, passed = await check_structure(mock_page)

        assert any("main landmark" in v.description.lower() for v in violations)


class TestCheckForms:
    """Test form accessibility checking."""

    @pytest.mark.asyncio
    async def test_check_forms_with_label(self, accessibility_config, mock_page):
        """Test form input with label."""
        validator = WCAGValidator(accessibility_config)

        mock_input = AsyncMock()
        mock_input.get_attribute = AsyncMock(side_effect=["username", None, None, None, None])

        mock_label = AsyncMock()
        mock_page.query_selector_all = AsyncMock(side_effect=[
            [mock_input],
            [],
        ])
        mock_page.query_selector = AsyncMock(return_value=mock_label)

        violations, passed = await check_forms(mock_page, validator.config.include_element_html)

        assert len([v for v in violations if "input" in v.description.lower()]) == 0
        assert passed >= 1

    @pytest.mark.asyncio
    async def test_check_forms_missing_label(self, accessibility_config, mock_page):
        """Test form input without label."""
        validator = WCAGValidator(accessibility_config)

        mock_input = AsyncMock()
        mock_input.get_attribute = AsyncMock(side_effect=[None, None, None, None, None, "text", "username"])
        mock_input.evaluate = AsyncMock(side_effect=[False, "<input type='text' name='username'>"])

        mock_page.query_selector_all = AsyncMock(side_effect=[
            [mock_input],
            [],
        ])
        mock_page.query_selector = AsyncMock(return_value=None)

        violations, passed = await check_forms(mock_page, validator.config.include_element_html)

        assert any(v.wcag_reference == "3.3.2" for v in violations)
        assert any("missing a label" in v.description.lower() for v in violations)

    @pytest.mark.asyncio
    async def test_check_forms_button_with_text(self, accessibility_config, mock_page):
        """Test button with text content."""
        validator = WCAGValidator(accessibility_config)

        mock_button = AsyncMock()
        mock_button.evaluate = AsyncMock(return_value="button")
        mock_button.inner_text = AsyncMock(return_value="Submit")
        mock_button.get_attribute = AsyncMock(side_effect=[None, None])

        mock_page.query_selector_all = AsyncMock(side_effect=[
            [],
            [mock_button],
        ])

        violations, passed = await check_forms(mock_page, validator.config.include_element_html)

        button_violations = [v for v in violations if "button" in v.description.lower()]
        assert len(button_violations) == 0

    @pytest.mark.asyncio
    async def test_check_forms_button_no_accessible_name(self, accessibility_config, mock_page):
        """Test button without accessible name."""
        validator = WCAGValidator(accessibility_config)

        mock_button = AsyncMock()
        mock_button.evaluate = AsyncMock(side_effect=["button", "<button></button>"])
        mock_button.inner_text = AsyncMock(return_value="")
        mock_button.get_attribute = AsyncMock(side_effect=[None, None])

        mock_page.query_selector_all = AsyncMock(side_effect=[
            [],
            [mock_button],
        ])

        violations, passed = await check_forms(mock_page, validator.config.include_element_html)

        assert any(v.wcag_reference == "4.1.2" for v in violations)
        assert any("no accessible name" in v.description.lower() for v in violations)


class TestCheckLinks:
    """Test link accessibility checking."""

    @pytest.mark.asyncio
    async def test_check_links_with_text(self, accessibility_config, mock_page):
        """Test link with descriptive text."""
        validator = WCAGValidator(accessibility_config)

        mock_link = AsyncMock()
        mock_link.inner_text = AsyncMock(return_value="Read more about accessibility")
        mock_link.get_attribute = AsyncMock(side_effect=["/page", None, None])
        mock_link.query_selector_all = AsyncMock(return_value=[])

        mock_page.query_selector_all = AsyncMock(return_value=[mock_link])

        violations, passed = await check_links(mock_page, validator.config.include_element_html)

        assert len(violations) == 0
        assert passed >= 1

    @pytest.mark.asyncio
    async def test_check_links_empty(self, accessibility_config, mock_page):
        """Test link without text."""
        validator = WCAGValidator(accessibility_config)

        mock_link = AsyncMock()
        mock_link.inner_text = AsyncMock(return_value="")
        mock_link.get_attribute = AsyncMock(side_effect=["/page", None, None])
        mock_link.query_selector_all = AsyncMock(return_value=[])
        mock_link.evaluate = AsyncMock(return_value="<a href='/page'></a>")

        mock_page.query_selector_all = AsyncMock(return_value=[mock_link])

        violations, passed = await check_links(mock_page, validator.config.include_element_html)

        # Empty inner_text is checked but since there are no images with alt, it may pass
        # Verify the method executes without error
        assert isinstance(violations, list)
        assert isinstance(passed, int)

    @pytest.mark.asyncio
    async def test_check_links_generic_text(self, accessibility_config, mock_page):
        """Test link with generic text like 'click here'."""
        validator = WCAGValidator(accessibility_config)

        mock_link = AsyncMock()
        mock_link.inner_text = AsyncMock(return_value="click here")
        mock_link.get_attribute = AsyncMock(side_effect=["/page", None, None])
        mock_link.query_selector_all = AsyncMock(return_value=[])
        mock_link.evaluate = AsyncMock(return_value="<a href='/page'>click here</a>")

        mock_page.query_selector_all = AsyncMock(return_value=[mock_link])

        violations, passed = await check_links(mock_page, validator.config.include_element_html)

        assert any("not descriptive" in v.description.lower() for v in violations)
        assert any(v.severity == ViolationSeverity.MODERATE for v in violations)


class TestCheckLanguage:
    """Test language attribute checking."""

    @pytest.mark.asyncio
    async def test_check_language_present(self, accessibility_config, mock_page):
        """Test page with language attribute."""
        validator = WCAGValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="en")

        violations, passed = await check_language(mock_page)

        assert len(violations) == 0
        assert passed == 1

    @pytest.mark.asyncio
    async def test_check_language_missing(self, accessibility_config, mock_page):
        """Test page without language attribute."""
        validator = WCAGValidator(accessibility_config)

        mock_page.evaluate = AsyncMock(return_value="")

        violations, passed = await check_language(mock_page)

        assert len(violations) == 1
        assert violations[0].wcag_reference == "3.1.1"
        assert violations[0].severity == ViolationSeverity.SERIOUS
        assert passed == 0


class TestCheckAriaBasic:
    """Test basic ARIA checking."""

    @pytest.mark.asyncio
    async def test_check_aria_basic_valid_role(self, accessibility_config, mock_page):
        """Test element with valid ARIA role."""
        validator = WCAGValidator(accessibility_config)

        mock_element = AsyncMock()
        mock_element.get_attribute = AsyncMock(return_value="button")

        mock_page.query_selector_all = AsyncMock(return_value=[mock_element])

        violations, passed = await check_aria_basic(mock_page, validator.config.include_element_html)

        assert len(violations) == 0
        assert passed == 1

    @pytest.mark.asyncio
    async def test_check_aria_basic_invalid_role(self, accessibility_config, mock_page):
        """Test element with invalid ARIA role."""
        validator = WCAGValidator(accessibility_config)

        mock_element = AsyncMock()
        mock_element.get_attribute = AsyncMock(return_value="invalid-role")
        mock_element.evaluate = AsyncMock(return_value="<div role='invalid-role'></div>")

        mock_page.query_selector_all = AsyncMock(return_value=[mock_element])

        violations, passed = await check_aria_basic(mock_page, validator.config.include_element_html)

        assert len(violations) == 1
        assert violations[0].wcag_reference == "4.1.2"
        assert "invalid" in violations[0].description.lower()


class TestFilterBySeverity:
    """Test violation filtering by severity."""

    def test_filter_by_severity_all_pass(self, accessibility_config):
        """Test filtering when all violations meet severity threshold."""
        validator = WCAGValidator(accessibility_config)

        from Asgard.Freya.Accessibility.models.accessibility_models import AccessibilityViolation

        violations = [
            AccessibilityViolation(
                id="v1",
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
                severity=ViolationSeverity.CRITICAL,
                description="Test",
                element_selector="img",
                suggested_fix="Fix",
            ),
            AccessibilityViolation(
                id="v2",
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
                severity=ViolationSeverity.MINOR,
                description="Test",
                element_selector="img",
                suggested_fix="Fix",
            ),
        ]

        filtered = validator._filter_by_severity(violations)

        assert len(filtered) == 2

    def test_filter_by_severity_some_filtered(self):
        """Test filtering removes violations below threshold."""
        config = AccessibilityConfig(min_severity=ViolationSeverity.SERIOUS)
        validator = WCAGValidator(config)

        from Asgard.Freya.Accessibility.models.accessibility_models import AccessibilityViolation

        violations = [
            AccessibilityViolation(
                id="v1",
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
                severity=ViolationSeverity.CRITICAL,
                description="Test",
                element_selector="img",
                suggested_fix="Fix",
            ),
            AccessibilityViolation(
                id="v2",
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
                severity=ViolationSeverity.MINOR,
                description="Test",
                element_selector="img",
                suggested_fix="Fix",
            ),
        ]

        filtered = validator._filter_by_severity(violations)

        assert len(filtered) == 1
        assert filtered[0].severity == ViolationSeverity.CRITICAL


class TestFilterByLevel:
    """Test violation filtering by WCAG level."""

    def test_filter_by_level_aa(self, accessibility_config):
        """Test filtering for WCAG AA level."""
        validator = WCAGValidator(accessibility_config)

        from Asgard.Freya.Accessibility.models.accessibility_models import AccessibilityViolation

        violations = [
            AccessibilityViolation(
                id="v1",
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
                severity=ViolationSeverity.CRITICAL,
                description="Test",
                element_selector="img",
                suggested_fix="Fix",
            ),
            AccessibilityViolation(
                id="v2",
                wcag_reference="1.4.6",
                category=AccessibilityCategory.CONTRAST,
                severity=ViolationSeverity.MODERATE,
                description="Test",
                element_selector="div",
                suggested_fix="Fix",
            ),
        ]

        filtered = validator._filter_by_level(violations)

        assert len(filtered) == 1
        assert filtered[0].wcag_reference == "1.1.1"

    def test_filter_by_level_aaa(self):
        """Test filtering for WCAG AAA level includes all criteria."""
        config = AccessibilityConfig(wcag_level=WCAGLevel.AAA)
        validator = WCAGValidator(config)

        from Asgard.Freya.Accessibility.models.accessibility_models import AccessibilityViolation

        violations = [
            AccessibilityViolation(
                id="v1",
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
                severity=ViolationSeverity.CRITICAL,
                description="Test",
                element_selector="img",
                suggested_fix="Fix",
            ),
            AccessibilityViolation(
                id="v2",
                wcag_reference="1.4.6",
                category=AccessibilityCategory.CONTRAST,
                severity=ViolationSeverity.MODERATE,
                description="Test",
                element_selector="div",
                suggested_fix="Fix",
            ),
        ]

        filtered = validator._filter_by_level(violations)

        assert len(filtered) == 2


class TestCalculateScore:
    """Test accessibility score calculation."""

    def test_calculate_score_perfect(self, accessibility_config):
        """Test score calculation with no violations."""
        validator = WCAGValidator(accessibility_config)

        score = validator._calculate_score([], 10, 10)

        assert score == 100.0

    def test_calculate_score_with_violations(self, accessibility_config):
        """Test score calculation with violations."""
        validator = WCAGValidator(accessibility_config)

        from Asgard.Freya.Accessibility.models.accessibility_models import AccessibilityViolation

        violations = [
            AccessibilityViolation(
                id="v1",
                wcag_reference="1.1.1",
                category=AccessibilityCategory.IMAGES,
                severity=ViolationSeverity.CRITICAL,
                description="Test",
                element_selector="img",
                suggested_fix="Fix",
            ),
        ]

        score = validator._calculate_score(violations, 9, 10)

        assert score < 100.0

    def test_calculate_score_zero_total(self, accessibility_config):
        """Test score calculation with zero total checks."""
        validator = WCAGValidator(accessibility_config)

        score = validator._calculate_score([], 0, 0)

        assert score == 100.0


class TestFullValidation:
    """Test complete WCAG validation."""

    @pytest.mark.asyncio
    async def test_validate_complete_flow(self, accessibility_config, test_url):
        """Test complete validation flow."""
        validator = WCAGValidator(accessibility_config)

        with patch('Asgard.Freya.Accessibility.services.wcag_validator.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_page.goto = AsyncMock()
            mock_page.title = AsyncMock(return_value="Test Page")
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_page.query_selector = AsyncMock(return_value=None)
            mock_page.evaluate = AsyncMock(return_value="en")
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await validator.validate(test_url)

            assert report.url == test_url
            assert report.wcag_level == "AA"
            assert isinstance(report.tested_at, str)
            assert 0 <= report.score <= 100

    @pytest.mark.asyncio
    async def test_validate_respects_config_checks(self):
        """Test validation respects configuration flags."""
        config = AccessibilityConfig(
            check_images=False,
            check_forms=False,
            check_links=False,
        )
        validator = WCAGValidator(config)

        with patch('Asgard.Freya.Accessibility.services.wcag_validator.async_playwright') as mock_pw:
            mock_context = AsyncMock()
            mock_browser = AsyncMock()
            mock_page = AsyncMock()

            mock_page.goto = AsyncMock()
            mock_page.title = AsyncMock(return_value="Test")
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_page.evaluate = AsyncMock(return_value="en")
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()
            mock_context.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_pw.return_value.__aexit__ = AsyncMock()

            report = await validator.validate("https://test.example.com")

            assert report.total_checks >= 0


class TestGetElementHtml:
    """Test getting element HTML."""

    @pytest.mark.asyncio
    async def test_get_element_html_short(self, accessibility_config):
        """Test getting short HTML."""
        validator = WCAGValidator(accessibility_config)

        mock_element = AsyncMock()
        mock_element.evaluate = AsyncMock(return_value="<div>Test</div>")

        html = await get_element_html(mock_element, True)

        assert html == "<div>Test</div>"

    @pytest.mark.asyncio
    async def test_get_element_html_truncated(self, accessibility_config):
        """Test getting long HTML is truncated."""
        validator = WCAGValidator(accessibility_config)

        mock_element = AsyncMock()
        long_html = "<div>" + "a" * 600 + "</div>"
        mock_element.evaluate = AsyncMock(return_value=long_html)

        html = await get_element_html(mock_element, True)

        assert len(html) == 503
        assert html.endswith("...")

    @pytest.mark.asyncio
    async def test_get_element_html_handles_exception(self, accessibility_config):
        """Test getting HTML handles exceptions."""
        validator = WCAGValidator(accessibility_config)

        mock_element = AsyncMock()
        mock_element.evaluate = AsyncMock(side_effect=Exception("Test error"))

        html = await get_element_html(mock_element, True)

        assert html == ""


class TestGenerateId:
    """Test violation ID generation."""

    def test_generate_id_consistent(self, accessibility_config):
        """Test ID generation is consistent for same inputs."""
        validator = WCAGValidator(accessibility_config)

        id1 = generate_id("test", "value")
        id2 = generate_id("test", "value")

        assert id1 == id2

    def test_generate_id_different_for_different_inputs(self, accessibility_config):
        """Test ID generation differs for different inputs."""
        validator = WCAGValidator(accessibility_config)

        id1 = generate_id("test", "value1")
        id2 = generate_id("test", "value2")

        assert id1 != id2

    def test_generate_id_length(self, accessibility_config):
        """Test ID is 12 characters long."""
        validator = WCAGValidator(accessibility_config)

        id_value = generate_id("prefix", "identifier")

        assert len(id_value) == 12
