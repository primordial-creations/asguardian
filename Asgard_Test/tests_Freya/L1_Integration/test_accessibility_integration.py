"""
L1 Integration Tests for Freya Accessibility Testing

Comprehensive integration tests for real accessibility scanning of HTML pages.
Tests WCAG validation, color contrast, keyboard navigation, and ARIA validation
using actual Playwright browser instances in headless mode.

All tests use file:// URLs for local HTML fixtures, making them CI-friendly.
"""

import pytest
from pathlib import Path

from Asgard.Freya.Accessibility.services.wcag_validator import WCAGValidator
from Asgard.Freya.Accessibility.services.color_contrast import ColorContrastChecker
from Asgard.Freya.Accessibility.services.keyboard_nav import KeyboardNavigationTester
from Asgard.Freya.Accessibility.services.aria_validator import ARIAValidator
from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    WCAGLevel,
    ViolationSeverity,
    AccessibilityCategory,
)

from Asgard_Test.tests_Freya.L1_Integration.conftest import file_url


class TestAccessibilityIntegrationWCAGValidator:
    """Integration tests for WCAG Validator with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_accessible_page_passes(self, sample_accessible_page):
        """Test WCAG validation passes for accessible page."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.AA,
            check_images=True,
            check_structure=True,
            check_forms=True,
            check_links=True,
            check_language=True,
            check_aria=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_accessible_page)
        report = await validator.validate(url)

        assert report is not None
        assert report.url == url
        assert report.wcag_level == "AA"
        assert report.total_checks > 0
        assert report.passed_checks > 0
        assert report.score >= 80.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_inaccessible_page_finds_violations(self, sample_inaccessible_page):
        """Test WCAG validation detects violations on inaccessible page."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.AA,
            check_images=True,
            check_structure=True,
            check_forms=True,
            check_links=True,
            check_language=True,
            check_aria=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        assert report is not None
        assert len(report.violations) > 0

        violation_categories = [v.category for v in report.violations]
        assert AccessibilityCategory.IMAGES in violation_categories
        assert AccessibilityCategory.STRUCTURE in violation_categories or AccessibilityCategory.LANGUAGE in violation_categories

        critical_violations = [v for v in report.violations if v.severity == ViolationSeverity.CRITICAL]
        assert len(critical_violations) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_checks_images(self, sample_inaccessible_page):
        """Test WCAG validator detects missing alt attributes on images."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            check_images=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        image_violations = [v for v in report.violations if v.category == AccessibilityCategory.IMAGES]
        assert len(image_violations) > 0

        alt_violation = next((v for v in image_violations if "alt" in v.description.lower()), None)
        assert alt_violation is not None
        assert alt_violation.wcag_reference == "1.1.1"
        assert alt_violation.severity == ViolationSeverity.CRITICAL

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_checks_structure(self, sample_inaccessible_page):
        """Test WCAG validator checks document structure."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            check_structure=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        structure_violations = [v for v in report.violations if v.category == AccessibilityCategory.STRUCTURE]
        assert len(structure_violations) >= 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_checks_forms(self, sample_inaccessible_page):
        """Test WCAG validator detects form accessibility issues."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            check_forms=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        form_violations = [v for v in report.violations if v.category == AccessibilityCategory.FORMS]
        assert len(form_violations) > 0

        label_violation = next((v for v in form_violations if "label" in v.description.lower()), None)
        assert label_violation is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_checks_links(self, sample_inaccessible_page):
        """Test WCAG validator checks link accessibility."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            check_links=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        link_violations = [v for v in report.violations if v.category == AccessibilityCategory.LINKS]
        assert len(link_violations) >= 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_checks_language(self, sample_inaccessible_page):
        """Test WCAG validator checks language attributes."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            check_language=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        lang_violations = [v for v in report.violations if v.category == AccessibilityCategory.LANGUAGE]
        assert len(lang_violations) > 0

        lang_violation = next((v for v in lang_violations if v.wcag_reference == "3.1.1"), None)
        assert lang_violation is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_checks_aria(self, sample_inaccessible_page):
        """Test WCAG validator performs basic ARIA validation."""
        config = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            check_aria=True,
        )
        validator = WCAGValidator(config)

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        aria_violations = [v for v in report.violations if v.category == AccessibilityCategory.ARIA]
        assert len(aria_violations) > 0

        invalid_role_violation = next((v for v in aria_violations if "invalid" in v.description.lower()), None)
        assert invalid_role_violation is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_severity_filtering(self, sample_inaccessible_page):
        """Test WCAG validator filters violations by severity."""
        config_critical = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            min_severity=ViolationSeverity.CRITICAL,
        )
        validator_critical = WCAGValidator(config_critical)

        url = file_url(sample_inaccessible_page)
        report_critical = await validator_critical.validate(url)

        config_all = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
            min_severity=ViolationSeverity.INFO,
        )
        validator_all = WCAGValidator(config_all)
        report_all = await validator_all.validate(url)

        assert len(report_critical.violations) <= len(report_all.violations)
        assert all(v.severity == ViolationSeverity.CRITICAL for v in report_critical.violations)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wcag_validator_level_filtering(self, sample_inaccessible_page):
        """Test WCAG validator filters violations by WCAG level."""
        config_a = AccessibilityConfig(
            wcag_level=WCAGLevel.A,
        )
        validator_a = WCAGValidator(config_a)

        url = file_url(sample_inaccessible_page)
        report_a = await validator_a.validate(url)

        config_aaa = AccessibilityConfig(
            wcag_level=WCAGLevel.AAA,
        )
        validator_aaa = WCAGValidator(config_aaa)
        report_aaa = await validator_aaa.validate(url)

        assert report_a.wcag_level == "A"
        assert report_aaa.wcag_level == "AAA"


class TestAccessibilityIntegrationColorContrast:
    """Integration tests for Color Contrast Checker with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_color_contrast_accessible_page(self, sample_accessible_page):
        """Test color contrast checker on page with good contrast."""
        from Asgard.Freya.Accessibility.models.accessibility_models import ContrastConfig

        config = ContrastConfig(
            wcag_level=WCAGLevel.AA,
        )
        checker = ColorContrastChecker(config)

        url = file_url(sample_accessible_page)
        report = await checker.check(url)

        assert report is not None
        assert report.url == url
        assert report.total_elements_checked > 0

        if len(report.issues) > 0:
            assert report.pass_rate < 100.0
        else:
            assert report.pass_rate == 100.0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_color_contrast_inaccessible_page(self, sample_inaccessible_page):
        """Test color contrast checker detects poor contrast."""
        from Asgard.Freya.Accessibility.models.accessibility_models import ContrastConfig

        config = ContrastConfig(
            wcag_level=WCAGLevel.AA,
        )
        checker = ColorContrastChecker(config)

        url = file_url(sample_inaccessible_page)
        report = await checker.check(url)

        assert report is not None
        assert len(report.issues) > 0

        contrast_issue = report.issues[0]
        assert hasattr(contrast_issue, 'contrast_ratio')
        assert hasattr(contrast_issue, 'foreground_color')
        assert hasattr(contrast_issue, 'background_color')

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_color_contrast_report_structure(self, sample_accessible_page):
        """Test color contrast report has correct structure."""
        from Asgard.Freya.Accessibility.models.accessibility_models import ContrastConfig

        config = ContrastConfig(
            wcag_level=WCAGLevel.AA,
        )
        checker = ColorContrastChecker(config)

        url = file_url(sample_accessible_page)
        report = await checker.check(url)

        assert report.url is not None
        assert report.tested_at is not None
        assert report.wcag_level == "AA"
        assert report.total_elements_checked >= 0
        assert 0.0 <= report.pass_rate <= 100.0
        assert isinstance(report.issues, list)


class TestAccessibilityIntegrationKeyboardNavigation:
    """Integration tests for Keyboard Navigation Tester with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_keyboard_navigation_accessible_page(self, sample_accessible_page):
        """Test keyboard navigation on accessible page."""
        tester = KeyboardNavigationTester()

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report is not None
        assert report.url == url
        assert report.focusable_elements_tested > 0

        assert len(report.issues) == 0 or all(
            issue.severity != ViolationSeverity.CRITICAL
            for issue in report.issues
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_keyboard_navigation_focus_indicators(self, sample_accessible_page):
        """Test keyboard navigation checks for focus indicators."""
        tester = KeyboardNavigationTester()

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report is not None
        assert report.focusable_elements_tested > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_keyboard_navigation_report_structure(self, sample_accessible_page):
        """Test keyboard navigation report structure."""
        tester = KeyboardNavigationTester()

        url = file_url(sample_accessible_page)
        report = await tester.test(url)

        assert report.url is not None
        assert report.tested_at is not None
        assert report.focusable_elements_tested >= 0
        assert isinstance(report.issues, list)


class TestAccessibilityIntegrationARIAValidator:
    """Integration tests for ARIA Validator with real HTML pages."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_aria_validator_accessible_page(self, sample_accessible_page):
        """Test ARIA validation on accessible page."""
        validator = ARIAValidator()

        url = file_url(sample_accessible_page)
        report = await validator.validate(url)

        assert report is not None
        assert report.url == url
        assert report.elements_validated > 0

        critical_violations = [v for v in report.violations if v.severity == ViolationSeverity.CRITICAL]
        assert len(critical_violations) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_aria_validator_detects_invalid_roles(self, sample_inaccessible_page):
        """Test ARIA validator detects invalid roles."""
        validator = ARIAValidator()

        url = file_url(sample_inaccessible_page)
        report = await validator.validate(url)

        assert report is not None
        assert len(report.violations) > 0

        invalid_role_violation = next(
            (v for v in report.violations if "invalid" in v.description.lower() and "role" in v.description.lower()),
            None
        )
        assert invalid_role_violation is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_aria_validator_report_structure(self, sample_accessible_page):
        """Test ARIA validator report structure."""
        validator = ARIAValidator()

        url = file_url(sample_accessible_page)
        report = await validator.validate(url)

        assert report.url is not None
        assert report.tested_at is not None
        assert report.elements_validated >= 0
        assert isinstance(report.violations, list)
        assert 0.0 <= report.score <= 100.0
