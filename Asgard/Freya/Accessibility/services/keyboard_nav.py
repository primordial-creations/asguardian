"""
Freya Keyboard Navigation Tester

Tests keyboard accessibility including focus management,
tab order, focus indicators, and keyboard traps.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    KeyboardNavigationReport,
    KeyboardIssue,
    KeyboardIssueType,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.services._keyboard_nav_checks import (
    check_skip_link,
    get_focusable_elements,
    test_tab_order,
    test_focus_indicators,
    test_focus_traps,
    test_interactive_elements,
    get_selector,
)


class KeyboardNavigationTester:
    """
    Keyboard accessibility tester.

    Tests focus management, tab order, focus indicators,
    keyboard traps, and skip links.
    """

    def __init__(self, config: AccessibilityConfig):
        """
        Initialize the Keyboard Navigation Tester.

        Args:
            config: Accessibility configuration
        """
        self.config = config

    async def test(self, url: str) -> KeyboardNavigationReport:
        """
        Test keyboard navigation on a page.

        Args:
            url: URL to test

        Returns:
            KeyboardNavigationReport with all findings
        """
        issues: list[Any] = []
        tab_order: list[Any] = []
        focus_indicators: dict[Any, Any] = {}
        focus_traps: list[Any] = []
        has_skip_link = False
        focusable_elements: list[Any] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                has_skip_link = await check_skip_link(page)
                if not has_skip_link:
                    issues.append(KeyboardIssue(
                        issue_type=KeyboardIssueType.SKIP_LINK_MISSING,
                        element_selector="body",
                        description="Page is missing a skip to main content link",
                        severity=ViolationSeverity.SERIOUS,
                        wcag_reference="2.4.1",
                        suggested_fix="Add a skip link at the beginning of the page that links to main content",
                    ))

                focusable_elements = await get_focusable_elements(page)
                tab_order, focus_indicators, tab_issues = await test_tab_order(
                    page, focusable_elements
                )
                issues.extend(tab_issues)

                focus_issues = await test_focus_indicators(page, focusable_elements)
                issues.extend(focus_issues)

                trap_issues, focus_traps = await test_focus_traps(page, focusable_elements)
                issues.extend(trap_issues)

                interactive_issues = await test_interactive_elements(page)
                issues.extend(interactive_issues)

            finally:
                await browser.close()

        accessible_count = len(focusable_elements) - len([
            i for i in issues if i.issue_type in [
                KeyboardIssueType.NOT_FOCUSABLE,
                KeyboardIssueType.NO_KEYBOARD_ACCESS,
            ]
        ])

        return KeyboardNavigationReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            total_focusable=len(focusable_elements),
            accessible_count=accessible_count,
            tab_order=tab_order,
            focus_indicators=focus_indicators,
            issues=issues,
            has_skip_link=has_skip_link,
            focus_traps=focus_traps,
        )

    async def _check_skip_link(self, page: Page) -> bool:
        """Check if page has a skip to content link."""
        return await check_skip_link(page)

    async def _get_focusable_elements(self, page: Page) -> List[dict]:
        """Get all focusable elements on the page."""
        return await get_focusable_elements(page)

    async def _test_tab_order(self, page: Page, elements: List[dict]):
        """Test tab order through focusable elements."""
        return await test_tab_order(page, elements)

    async def _test_focus_indicators(self, page: Page, elements: List[dict]) -> List[KeyboardIssue]:
        """Test focus indicators on elements."""
        return await test_focus_indicators(page, elements)

    async def _test_focus_traps(self, page: Page, elements: List[dict]):
        """Test for focus traps."""
        return await test_focus_traps(page, elements)

    async def _test_interactive_elements(self, page: Page) -> List[KeyboardIssue]:
        """Test interactive elements for keyboard accessibility."""
        return await test_interactive_elements(page)

    async def _get_selector(self, page: Page, element) -> str:
        """Generate a selector for an element."""
        return await get_selector(page, element)
