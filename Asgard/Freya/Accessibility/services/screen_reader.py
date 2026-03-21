"""
Freya Screen Reader Validator

Tests screen reader compatibility including accessible names,
landmark structure, heading structure, and form labels.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    ScreenReaderReport,
    ScreenReaderIssue,
    ScreenReaderIssueType,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.services._screen_reader_checks import (
    check_language,
    analyze_landmarks,
    analyze_headings,
    check_images,
    check_forms,
    check_links,
    check_buttons,
    get_accessible_name,
    get_selector,
)


class ScreenReaderValidator:
    """
    Screen reader compatibility validator.

    Tests accessible names, landmarks, headings,
    and other screen reader requirements.
    """

    def __init__(self, config: AccessibilityConfig):
        """
        Initialize the Screen Reader Validator.

        Args:
            config: Accessibility configuration
        """
        self.config = config

    async def validate(self, url: str) -> ScreenReaderReport:
        """
        Validate screen reader compatibility.

        Args:
            url: URL to validate

        Returns:
            ScreenReaderReport with all findings
        """
        issues: List[Any] = []
        landmark_structure: Dict[str, int] = {}
        heading_structure: List[Any] = []
        language = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                language = await check_language(page, issues)

                landmark_structure = await analyze_landmarks(page, issues)

                heading_structure = await analyze_headings(page, issues)

                img_issues, img_labeled = await check_images(page)
                issues.extend(img_issues)

                form_issues, form_labeled = await check_forms(page)
                issues.extend(form_issues)

                link_issues, link_labeled = await check_links(page)
                issues.extend(link_issues)

                button_issues, button_labeled = await check_buttons(page)
                issues.extend(button_issues)

                total_elements = img_labeled[1] + form_labeled[1] + link_labeled[1] + button_labeled[1]
                labeled_count = img_labeled[0] + form_labeled[0] + link_labeled[0] + button_labeled[0]

            finally:
                await browser.close()

        return ScreenReaderReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            total_elements=total_elements,
            labeled_count=labeled_count,
            missing_labels=total_elements - labeled_count,
            issues=issues,
            landmark_structure=landmark_structure,
            heading_structure=heading_structure,
            language=language,
        )

    async def _check_language(self, page, issues):
        """Check page language attribute."""
        return await check_language(page, issues)

    async def _analyze_landmarks(self, page, issues):
        """Analyze landmark regions."""
        return await analyze_landmarks(page, issues)

    async def _analyze_headings(self, page, issues):
        """Analyze heading structure."""
        return await analyze_headings(page, issues)

    async def _check_images(self, page):
        """Check images for accessible names."""
        return await check_images(page)

    async def _check_forms(self, page):
        """Check form inputs for accessible names."""
        return await check_forms(page)

    async def _check_links(self, page):
        """Check links for accessible names."""
        return await check_links(page)

    async def _check_buttons(self, page):
        """Check buttons for accessible names."""
        return await check_buttons(page)

    async def _get_accessible_name(self, page, element):
        """Get the computed accessible name for an element."""
        return await get_accessible_name(page, element)

    async def _get_selector(self, page, element):
        """Generate a selector for an element."""
        return await get_selector(page, element)
