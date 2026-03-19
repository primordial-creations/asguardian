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

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                has_skip_link = await self._check_skip_link(page)
                if not has_skip_link:
                    issues.append(KeyboardIssue(
                        issue_type=KeyboardIssueType.SKIP_LINK_MISSING,
                        element_selector="body",
                        description="Page is missing a skip to main content link",
                        severity=ViolationSeverity.SERIOUS,
                        wcag_reference="2.4.1",
                        suggested_fix="Add a skip link at the beginning of the page that links to main content",
                    ))

                focusable_elements = await self._get_focusable_elements(page)
                tab_order, focus_indicators, tab_issues = await self._test_tab_order(
                    page, focusable_elements
                )
                issues.extend(tab_issues)

                focus_issues = await self._test_focus_indicators(page, focusable_elements)
                issues.extend(focus_issues)

                trap_issues, focus_traps = await self._test_focus_traps(page, focusable_elements)
                issues.extend(trap_issues)

                interactive_issues = await self._test_interactive_elements(page)
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
        skip_selectors = [
            'a[href="#main"]',
            'a[href="#content"]',
            'a[href="#main-content"]',
            'a[href="#maincontent"]',
            'a[href="#skip"]',
            '.skip-link',
            '.skip-to-content',
            '[class*="skip"]',
            'a:first-child[href^="#"]',
        ]

        for selector in skip_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    text = await elem.inner_text()
                    if text and any(
                        keyword in text.lower()
                        for keyword in ["skip", "main", "content", "navigation"]
                    ):
                        return True
            except Exception:
                continue

        return False

    async def _get_focusable_elements(self, page: Page) -> List[dict]:
        """Get all focusable elements on the page."""
        focusable_selector = """
            a[href],
            button:not([disabled]),
            input:not([disabled]):not([type="hidden"]),
            select:not([disabled]),
            textarea:not([disabled]),
            [tabindex]:not([tabindex="-1"]),
            details,
            summary,
            [contenteditable="true"]
        """

        elements = []

        try:
            found = await page.query_selector_all(focusable_selector)

            for elem in found:
                try:
                    is_visible = await elem.evaluate("""
                        el => {
                            const style = getComputedStyle(el);
                            const rect = el.getBoundingClientRect();
                            return style.display !== 'none' &&
                                   style.visibility !== 'hidden' &&
                                   style.opacity !== '0' &&
                                   rect.width > 0 &&
                                   rect.height > 0;
                        }
                    """)

                    if is_visible:
                        tag_name = await elem.evaluate("el => el.tagName.toLowerCase()")
                        tabindex = await elem.get_attribute("tabindex")
                        box = await elem.bounding_box()

                        elements.append({
                            "element": elem,
                            "tag": tag_name,
                            "tabindex": int(tabindex) if tabindex else 0,
                            "box": box,
                        })
                except Exception:
                    continue

        except Exception:
            pass

        elements.sort(key=lambda x: (x["tabindex"] if x["tabindex"] > 0 else 1000, x["box"]["y"] if x["box"] else 0, x["box"]["x"] if x["box"] else 0))

        return elements

    async def _test_tab_order(
        self,
        page: Page,
        elements: List[dict]
    ) -> tuple[List[str], Dict[str, bool], List[KeyboardIssue]]:
        """Test tab order through focusable elements."""
        tab_order: list[Any] = []
        focus_indicators: dict[Any, Any] = {}
        issues: list[Any] = []

        try:
            await page.keyboard.press("Tab")

            for i, elem_data in enumerate(elements[:20]):
                element = elem_data["element"]
                tag = elem_data["tag"]

                try:
                    selector = await self._get_selector(page, element)
                    tab_order.append(selector)

                    is_focused = await element.evaluate("el => document.activeElement === el")

                    if not is_focused and i < 5:
                        issues.append(KeyboardIssue(
                            issue_type=KeyboardIssueType.TAB_ORDER_ISSUE,
                            element_selector=selector,
                            description=f"Expected {tag} to receive focus but it did not",
                            severity=ViolationSeverity.MODERATE,
                            wcag_reference="2.4.3",
                            suggested_fix="Ensure the element is focusable and in the correct tab order",
                        ))

                    await page.keyboard.press("Tab")

                except Exception:
                    continue

        except Exception:
            pass

        return tab_order, focus_indicators, issues

    async def _test_focus_indicators(
        self,
        page: Page,
        elements: List[dict]
    ) -> List[KeyboardIssue]:
        """Test focus indicators on elements."""
        issues = []

        for elem_data in elements[:30]:
            element = elem_data["element"]
            tag = elem_data["tag"]

            try:
                selector = await self._get_selector(page, element)

                styles_before = await page.evaluate("""
                    (element) => {
                        const computed = getComputedStyle(element);
                        return {
                            outline: computed.outline,
                            outlineColor: computed.outlineColor,
                            outlineWidth: computed.outlineWidth,
                            outlineStyle: computed.outlineStyle,
                            boxShadow: computed.boxShadow,
                            border: computed.border,
                            backgroundColor: computed.backgroundColor,
                        };
                    }
                """, element)

                await element.focus()

                styles_after = await page.evaluate("""
                    (element) => {
                        const computed = getComputedStyle(element);
                        return {
                            outline: computed.outline,
                            outlineColor: computed.outlineColor,
                            outlineWidth: computed.outlineWidth,
                            outlineStyle: computed.outlineStyle,
                            boxShadow: computed.boxShadow,
                            border: computed.border,
                            backgroundColor: computed.backgroundColor,
                        };
                    }
                """, element)

                has_visible_focus = (
                    styles_after["outlineStyle"] not in ["none", ""] or
                    styles_after["boxShadow"] != styles_before["boxShadow"] or
                    styles_after["border"] != styles_before["border"] or
                    styles_after["backgroundColor"] != styles_before["backgroundColor"]
                )

                if styles_after["outlineStyle"] == "none" and styles_after["outlineWidth"] == "0px":
                    has_visible_focus = (
                        styles_after["boxShadow"] != "none" and
                        styles_after["boxShadow"] != styles_before["boxShadow"]
                    ) or (
                        styles_after["backgroundColor"] != styles_before["backgroundColor"]
                    )

                if not has_visible_focus:
                    issues.append(KeyboardIssue(
                        issue_type=KeyboardIssueType.NO_FOCUS_INDICATOR,
                        element_selector=selector,
                        description=f"{tag} element has no visible focus indicator",
                        severity=ViolationSeverity.SERIOUS,
                        wcag_reference="2.4.7",
                        suggested_fix="Add a visible focus style using :focus or :focus-visible CSS",
                    ))

            except Exception:
                continue

        return issues

    async def _test_focus_traps(
        self,
        page: Page,
        elements: List[dict]
    ) -> tuple[List[KeyboardIssue], List[str]]:
        """Test for focus traps."""
        issues = []
        focus_traps = []

        modals = await page.query_selector_all('[role="dialog"], [aria-modal="true"], .modal')

        for modal in modals:
            try:
                is_visible = await modal.evaluate("""
                    el => {
                        const style = getComputedStyle(el);
                        return style.display !== 'none' && style.visibility !== 'hidden';
                    }
                """)

                if is_visible:
                    close_button = await modal.query_selector(
                        'button[aria-label*="close"], '
                        'button[class*="close"], '
                        '[role="button"][aria-label*="close"]'
                    )

                    if not close_button:
                        selector = await self._get_selector(page, modal)
                        focus_traps.append(selector)
                        issues.append(KeyboardIssue(
                            issue_type=KeyboardIssueType.FOCUS_TRAP,
                            element_selector=selector,
                            description="Modal dialog may trap focus without escape mechanism",
                            severity=ViolationSeverity.CRITICAL,
                            wcag_reference="2.1.2",
                            suggested_fix="Ensure modals can be closed via keyboard (Escape key or close button)",
                        ))
            except Exception:
                continue

        return issues, focus_traps

    async def _test_interactive_elements(self, page: Page) -> List[KeyboardIssue]:
        """Test interactive elements for keyboard accessibility."""
        issues = []

        click_handlers = await page.query_selector_all(
            '[onclick]:not(a):not(button):not(input), '
            '[class*="clickable"]:not(a):not(button), '
            '[class*="btn"]:not(a):not(button):not(input)'
        )

        for elem in click_handlers[:20]:
            try:
                tag_name = await elem.evaluate("el => el.tagName.toLowerCase()")
                tabindex = await elem.get_attribute("tabindex")
                role = await elem.get_attribute("role")

                if tag_name not in ["a", "button", "input", "select", "textarea"]:
                    if not tabindex or int(tabindex) < 0:
                        selector = await self._get_selector(page, elem)
                        issues.append(KeyboardIssue(
                            issue_type=KeyboardIssueType.NO_KEYBOARD_ACCESS,
                            element_selector=selector,
                            description=f"Interactive {tag_name} element is not keyboard accessible",
                            severity=ViolationSeverity.CRITICAL,
                            wcag_reference="2.1.1",
                            suggested_fix='Add tabindex="0" and appropriate role, or use a native interactive element',
                        ))

                    if not role or role not in ["button", "link", "checkbox", "tab", "menuitem"]:
                        selector = await self._get_selector(page, elem)
                        issues.append(KeyboardIssue(
                            issue_type=KeyboardIssueType.NO_KEYBOARD_ACCESS,
                            element_selector=selector,
                            description=f"Interactive {tag_name} element is missing appropriate role",
                            severity=ViolationSeverity.SERIOUS,
                            wcag_reference="4.1.2",
                            suggested_fix="Add appropriate ARIA role to indicate the element's purpose",
                        ))

            except Exception:
                continue

        return issues

    async def _get_selector(self, page: Page, element) -> str:
        """Generate a selector for an element."""
        try:
            selector = await page.evaluate("""
                (element) => {
                    if (element.id) return '#' + element.id;

                    const tag = element.tagName.toLowerCase();
                    const classes = Array.from(element.classList).slice(0, 2).join('.');

                    if (classes) return tag + '.' + classes;
                    return tag;
                }
            """, element)
            return cast(str, selector)
        except Exception:
            return "unknown"
