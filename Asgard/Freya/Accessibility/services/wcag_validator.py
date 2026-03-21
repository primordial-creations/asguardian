"""
Freya WCAG Validator

Comprehensive WCAG 2.1 compliance validation.
Tests against WCAG 2.1 Level A, AA, and AAA success criteria.
"""

from datetime import datetime
from typing import Any, List, Optional

from playwright.async_api import async_playwright, Browser

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    AccessibilityReport,
    AccessibilityViolation,
    AccessibilityCategory,
    ViolationSeverity,
    WCAGLevel,
)
from Asgard.Freya.Accessibility.services._wcag_checks import (
    check_aria_basic,
    check_forms,
    check_images,
    check_language,
    check_links,
    check_structure,
)
from Asgard.Freya.Accessibility.services._wcag_criteria import WCAG_CRITERIA


class WCAGValidator:
    """
    Comprehensive WCAG 2.1 compliance validator.

    Validates web pages against WCAG 2.1 success criteria.
    """

    def __init__(self, config: AccessibilityConfig):
        """
        Initialize the WCAG Validator.

        Args:
            config: Accessibility configuration
        """
        self.config = config
        self._browser: Optional[Browser] = None

    async def validate(self, url: str) -> AccessibilityReport:
        """
        Validate a URL against WCAG criteria.

        Args:
            url: URL to validate

        Returns:
            AccessibilityReport with all findings
        """
        violations: List[Any] = []
        warnings: List[Any] = []
        notices: List[Any] = []
        passed_checks = 0
        total_checks = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                if self.config.check_images:
                    img_violations, img_passed = await check_images(page, self.config.include_element_html)
                    violations.extend(img_violations)
                    passed_checks += img_passed
                    total_checks += len(img_violations) + img_passed

                if self.config.check_structure:
                    struct_violations, struct_passed = await check_structure(page)
                    violations.extend(struct_violations)
                    passed_checks += struct_passed
                    total_checks += len(struct_violations) + struct_passed

                if self.config.check_forms:
                    form_violations, form_passed = await check_forms(page, self.config.include_element_html)
                    violations.extend(form_violations)
                    passed_checks += form_passed
                    total_checks += len(form_violations) + form_passed

                if self.config.check_links:
                    link_violations, link_passed = await check_links(page, self.config.include_element_html)
                    violations.extend(link_violations)
                    passed_checks += link_passed
                    total_checks += len(link_violations) + link_passed

                if self.config.check_language:
                    lang_violations, lang_passed = await check_language(page)
                    violations.extend(lang_violations)
                    passed_checks += lang_passed
                    total_checks += len(lang_violations) + lang_passed

                if self.config.check_aria:
                    aria_violations, aria_passed = await check_aria_basic(page, self.config.include_element_html)
                    violations.extend(aria_violations)
                    passed_checks += aria_passed
                    total_checks += len(aria_violations) + aria_passed

            finally:
                await browser.close()

        violations = self._filter_by_severity(violations)
        violations = self._filter_by_level(violations)

        score = self._calculate_score(violations, passed_checks, total_checks)

        return AccessibilityReport(
            url=url,
            wcag_level=self.config.wcag_level.value,
            tested_at=datetime.now().isoformat(),
            score=score,
            violations=violations,
            warnings=warnings,
            notices=notices,
            passed_checks=passed_checks,
            total_checks=total_checks,
        )

    def _filter_by_severity(self, violations: List[AccessibilityViolation]) -> List[AccessibilityViolation]:
        """Filter violations by minimum severity."""
        severity_order = [
            ViolationSeverity.CRITICAL,
            ViolationSeverity.SERIOUS,
            ViolationSeverity.MODERATE,
            ViolationSeverity.MINOR,
            ViolationSeverity.INFO,
        ]

        min_index = severity_order.index(self.config.min_severity)
        allowed_severities = severity_order[:min_index + 1]

        return [v for v in violations if v.severity in allowed_severities]

    def _filter_by_level(self, violations: List[AccessibilityViolation]) -> List[AccessibilityViolation]:
        """Filter violations by WCAG level."""
        level_order = [WCAGLevel.A, WCAGLevel.AA, WCAGLevel.AAA]
        target_index = level_order.index(self.config.wcag_level)
        allowed_levels = level_order[:target_index + 1]

        filtered = []
        for v in violations:
            criterion = WCAG_CRITERIA.get(v.wcag_reference)
            if criterion and criterion["level"] in allowed_levels:
                filtered.append(v)
            elif not criterion:
                filtered.append(v)

        return filtered

    def _calculate_score(
        self,
        violations: List[AccessibilityViolation],
        passed: int,
        total: int
    ) -> float:
        """Calculate accessibility score."""
        if total == 0:
            return 100.0

        severity_weights = {
            ViolationSeverity.CRITICAL: 10,
            ViolationSeverity.SERIOUS: 5,
            ViolationSeverity.MODERATE: 2,
            ViolationSeverity.MINOR: 1,
            ViolationSeverity.INFO: 0,
        }

        penalty = sum(severity_weights.get(v.severity, 1) for v in violations)

        base_score = (passed / total) * 100 if total > 0 else 100
        final_score = max(0, base_score - penalty)

        return min(100.0, final_score)
