"""
Freya Layout Validator

Validates element layout including overflow, overlap,
alignment, and spacing issues.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Visual.models.visual_models import (
    LayoutReport,
    LayoutIssue,
    LayoutIssueType,
    ElementBox,
)
from Asgard.Freya.Visual.services._layout_validator_checks import (
    check_overflow,
    check_overlap,
    check_alignment,
    check_spacing,
    check_visibility,
)


class LayoutValidator:
    """
    Layout validation service.

    Detects overflow, overlap, alignment, and spacing issues.
    """

    def __init__(self):
        """Initialize the Layout Validator."""
        pass

    async def validate(
        self,
        url: str,
        viewport_width: int = 1920,
        viewport_height: int = 1080
    ) -> LayoutReport:
        """
        Validate layout on a page.

        Args:
            url: URL to validate
            viewport_width: Viewport width
            viewport_height: Viewport height

        Returns:
            LayoutReport with findings
        """
        issues = []
        overflow_elements = []
        overlapping_elements = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height}
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                overflow_issues, overflow = await check_overflow(page)
                issues.extend(overflow_issues)
                overflow_elements = overflow

                overlap_issues, overlaps = await check_overlap(page)
                issues.extend(overlap_issues)
                overlapping_elements = overlaps

                alignment_issues = await check_alignment(page)
                issues.extend(alignment_issues)

                spacing_issues = await check_spacing(page)
                issues.extend(spacing_issues)

                visibility_issues = await check_visibility(page)
                issues.extend(visibility_issues)

                total_elements = await page.evaluate("() => document.querySelectorAll('*').length")

            finally:
                await browser.close()

        return LayoutReport(
            url=url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            tested_at=datetime.now().isoformat(),
            total_elements=total_elements,
            issues=issues,
            overflow_elements=overflow_elements,
            overlapping_elements=overlapping_elements,
        )

    async def _check_overflow(self, page: Page) -> Tuple[List[LayoutIssue], List[str]]:
        """Check for elements that overflow their containers."""
        return await check_overflow(page)

    async def _check_overlap(self, page: Page) -> Tuple[List[LayoutIssue], List[Tuple[str, str]]]:
        """Check for overlapping elements."""
        return await check_overlap(page)

    async def _check_alignment(self, page: Page) -> List[LayoutIssue]:
        """Check for alignment issues."""
        return await check_alignment(page)

    async def _check_spacing(self, page: Page) -> List[LayoutIssue]:
        """Check for spacing issues."""
        return await check_spacing(page)

    async def _check_visibility(self, page: Page) -> List[LayoutIssue]:
        """Check for visibility issues."""
        return await check_visibility(page)
