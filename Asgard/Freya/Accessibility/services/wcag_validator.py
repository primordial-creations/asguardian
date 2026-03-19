"""
Freya WCAG Validator

Comprehensive WCAG 2.1 compliance validation.
Tests against WCAG 2.1 Level A, AA, and AAA success criteria.
"""

import hashlib
from datetime import datetime
from typing import Any, List, Optional, cast

from playwright.async_api import async_playwright, Page, Browser

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    AccessibilityReport,
    AccessibilityViolation,
    AccessibilityCategory,
    ViolationSeverity,
    WCAGLevel,
)


WCAG_CRITERIA = {
    "1.1.1": {
        "name": "Non-text Content",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.IMAGES,
        "severity": ViolationSeverity.CRITICAL,
    },
    "1.3.1": {
        "name": "Info and Relationships",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.3.2": {
        "name": "Meaningful Sequence",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.4.1": {
        "name": "Use of Color",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.CONTRAST,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.4.3": {
        "name": "Contrast (Minimum)",
        "level": WCAGLevel.AA,
        "category": AccessibilityCategory.CONTRAST,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.4.6": {
        "name": "Contrast (Enhanced)",
        "level": WCAGLevel.AAA,
        "category": AccessibilityCategory.CONTRAST,
        "severity": ViolationSeverity.MODERATE,
    },
    "2.1.1": {
        "name": "Keyboard",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.CRITICAL,
    },
    "2.1.2": {
        "name": "No Keyboard Trap",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.CRITICAL,
    },
    "2.4.1": {
        "name": "Bypass Blocks",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.NAVIGATION,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.2": {
        "name": "Page Titled",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.3": {
        "name": "Focus Order",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.4": {
        "name": "Link Purpose (In Context)",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.LINKS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.6": {
        "name": "Headings and Labels",
        "level": WCAGLevel.AA,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.MODERATE,
    },
    "2.4.7": {
        "name": "Focus Visible",
        "level": WCAGLevel.AA,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.1.1": {
        "name": "Language of Page",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.LANGUAGE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.2.1": {
        "name": "On Focus",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.OPERABLE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.2.2": {
        "name": "On Input",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.FORMS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.3.1": {
        "name": "Error Identification",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.FORMS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.3.2": {
        "name": "Labels or Instructions",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.FORMS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "4.1.1": {
        "name": "Parsing",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.ROBUST,
        "severity": ViolationSeverity.MODERATE,
    },
    "4.1.2": {
        "name": "Name, Role, Value",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.ARIA,
        "severity": ViolationSeverity.CRITICAL,
    },
}


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
                    img_violations, img_passed = await self._check_images(page)
                    violations.extend(img_violations)
                    passed_checks += img_passed
                    total_checks += len(img_violations) + img_passed

                if self.config.check_structure:
                    struct_violations, struct_passed = await self._check_structure(page)
                    violations.extend(struct_violations)
                    passed_checks += struct_passed
                    total_checks += len(struct_violations) + struct_passed

                if self.config.check_forms:
                    form_violations, form_passed = await self._check_forms(page)
                    violations.extend(form_violations)
                    passed_checks += form_passed
                    total_checks += len(form_violations) + form_passed

                if self.config.check_links:
                    link_violations, link_passed = await self._check_links(page)
                    violations.extend(link_violations)
                    passed_checks += link_passed
                    total_checks += len(link_violations) + link_passed

                if self.config.check_language:
                    lang_violations, lang_passed = await self._check_language(page)
                    violations.extend(lang_violations)
                    passed_checks += lang_passed
                    total_checks += len(lang_violations) + lang_passed

                if self.config.check_aria:
                    aria_violations, aria_passed = await self._check_aria_basic(page)
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

    async def _check_images(self, page: Page) -> tuple[List[AccessibilityViolation], int]:
        """Check images for accessibility."""
        violations = []
        passed = 0

        images = await page.query_selector_all("img")

        for img in images:
            alt = await img.get_attribute("alt")
            src = await img.get_attribute("src") or "unknown"
            role = await img.get_attribute("role")

            if role == "presentation" or role == "none":
                passed += 1
                continue

            if alt is None:
                element_html = await self._get_element_html(img) if self.config.include_element_html else None
                violations.append(AccessibilityViolation(
                    id=self._generate_id("img-alt", src),
                    wcag_reference="1.1.1",
                    category=AccessibilityCategory.IMAGES,
                    severity=ViolationSeverity.CRITICAL,
                    description="Image missing alt attribute",
                    element_selector=f'img[src="{src}"]',
                    element_html=element_html,
                    suggested_fix="Add an alt attribute describing the image content, or alt='' for decorative images",
                    impact="Screen reader users cannot understand the image content",
                    help_url="https://www.w3.org/WAI/WCAG21/Understanding/non-text-content.html",
                ))
            elif alt.strip() == "" and role not in ["presentation", "none"]:
                passed += 1
            else:
                passed += 1

        return violations, passed

    async def _check_structure(self, page: Page) -> tuple[List[AccessibilityViolation], int]:
        """Check document structure."""
        violations = []
        passed = 0

        title = await page.title()
        if not title or title.strip() == "":
            violations.append(AccessibilityViolation(
                id=self._generate_id("page-title", "missing"),
                wcag_reference="2.4.2",
                category=AccessibilityCategory.STRUCTURE,
                severity=ViolationSeverity.SERIOUS,
                description="Page is missing a title",
                element_selector="head > title",
                suggested_fix="Add a descriptive <title> element to the page head",
                impact="Users cannot identify the page purpose from the browser tab or assistive technology",
            ))
        else:
            passed += 1

        headings = await page.query_selector_all("h1, h2, h3, h4, h5, h6")
        heading_levels = []

        for heading in headings:
            tag_name = await heading.evaluate("el => el.tagName.toLowerCase()")
            level = int(tag_name[1])
            heading_levels.append(level)

        if heading_levels:
            if heading_levels[0] != 1:
                violations.append(AccessibilityViolation(
                    id=self._generate_id("heading-order", "first"),
                    wcag_reference="1.3.1",
                    category=AccessibilityCategory.STRUCTURE,
                    severity=ViolationSeverity.MODERATE,
                    description="First heading is not h1",
                    element_selector=f"h{heading_levels[0]}",
                    suggested_fix="Start with an h1 heading to define the main content",
                    impact="Document structure may be confusing for screen reader users",
                ))
            else:
                passed += 1

            for i in range(1, len(heading_levels)):
                if heading_levels[i] > heading_levels[i-1] + 1:
                    violations.append(AccessibilityViolation(
                        id=self._generate_id("heading-skip", str(i)),
                        wcag_reference="1.3.1",
                        category=AccessibilityCategory.STRUCTURE,
                        severity=ViolationSeverity.MODERATE,
                        description=f"Heading level skipped from h{heading_levels[i-1]} to h{heading_levels[i]}",
                        element_selector=f"h{heading_levels[i]}",
                        suggested_fix="Do not skip heading levels; use sequential heading levels",
                        impact="Document outline is broken, confusing navigation",
                    ))
                else:
                    passed += 1

        main_landmarks = await page.query_selector_all("main, [role='main']")
        if len(main_landmarks) == 0:
            violations.append(AccessibilityViolation(
                id=self._generate_id("landmark", "main"),
                wcag_reference="1.3.1",
                category=AccessibilityCategory.STRUCTURE,
                severity=ViolationSeverity.MODERATE,
                description="Page missing main landmark",
                element_selector="body",
                suggested_fix="Add a <main> element or role='main' to identify main content",
                impact="Screen reader users cannot quickly navigate to main content",
            ))
        else:
            passed += 1

        return violations, passed

    async def _check_forms(self, page: Page) -> tuple[List[AccessibilityViolation], int]:
        """Check form accessibility."""
        violations = []
        passed = 0

        inputs = await page.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='reset']), "
            "select, textarea"
        )

        for input_elem in inputs:
            input_id = await input_elem.get_attribute("id")
            aria_label = await input_elem.get_attribute("aria-label")
            aria_labelledby = await input_elem.get_attribute("aria-labelledby")
            title = await input_elem.get_attribute("title")
            placeholder = await input_elem.get_attribute("placeholder")

            has_label = False

            if input_id:
                label = await page.query_selector(f'label[for="{input_id}"]')
                if label:
                    has_label = True

            if aria_label or aria_labelledby or title:
                has_label = True

            if not has_label:
                parent_label = await input_elem.evaluate(
                    "el => el.closest('label') !== null"
                )
                if parent_label:
                    has_label = True

            if not has_label:
                input_type = await input_elem.get_attribute("type") or "text"
                name = await input_elem.get_attribute("name") or "unknown"
                element_html = await self._get_element_html(input_elem) if self.config.include_element_html else None

                violations.append(AccessibilityViolation(
                    id=self._generate_id("form-label", name),
                    wcag_reference="3.3.2",
                    category=AccessibilityCategory.FORMS,
                    severity=ViolationSeverity.SERIOUS,
                    description=f"Form input ({input_type}) is missing a label",
                    element_selector=f'input[name="{name}"]',
                    element_html=element_html,
                    suggested_fix="Add a <label> element with for attribute, or aria-label/aria-labelledby",
                    impact="Users may not understand what information to enter",
                ))
            else:
                passed += 1

        buttons = await page.query_selector_all("button, input[type='submit'], input[type='button']")

        for button in buttons:
            text = await button.inner_text() if await button.evaluate("el => el.tagName.toLowerCase()") == "button" else None
            value = await button.get_attribute("value")
            aria_label = await button.get_attribute("aria-label")

            has_accessible_name = bool(text and text.strip()) or bool(value and value.strip()) or bool(aria_label)

            if not has_accessible_name:
                element_html = await self._get_element_html(button) if self.config.include_element_html else None
                violations.append(AccessibilityViolation(
                    id=self._generate_id("button-name", str(hash(str(button)))),
                    wcag_reference="4.1.2",
                    category=AccessibilityCategory.FORMS,
                    severity=ViolationSeverity.CRITICAL,
                    description="Button has no accessible name",
                    element_selector="button",
                    element_html=element_html,
                    suggested_fix="Add text content, value attribute, or aria-label to the button",
                    impact="Screen reader users cannot understand the button purpose",
                ))
            else:
                passed += 1

        return violations, passed

    async def _check_links(self, page: Page) -> tuple[List[AccessibilityViolation], int]:
        """Check link accessibility."""
        violations = []
        passed = 0

        links = await page.query_selector_all("a[href]")

        for link in links:
            text = await link.inner_text()
            aria_label = await link.get_attribute("aria-label")
            title = await link.get_attribute("title")
            href = await link.get_attribute("href")

            images = await link.query_selector_all("img[alt]")
            img_alts = []
            for img in images:
                alt = await img.get_attribute("alt")
                if alt:
                    img_alts.append(alt)

            accessible_name = (text.strip() if text else "") or aria_label or " ".join(img_alts)

            if not accessible_name:
                element_html = await self._get_element_html(link) if self.config.include_element_html else None
                violations.append(AccessibilityViolation(
                    id=self._generate_id("link-name", href or "unknown"),
                    wcag_reference="2.4.4",
                    category=AccessibilityCategory.LINKS,
                    severity=ViolationSeverity.SERIOUS,
                    description="Link has no accessible name",
                    element_selector=f'a[href="{href}"]',
                    element_html=element_html,
                    suggested_fix="Add descriptive text content or aria-label to the link",
                    impact="Screen reader users cannot understand where the link leads",
                ))
            else:
                passed += 1

            if accessible_name and accessible_name.lower() in ["click here", "here", "read more", "learn more", "more"]:
                element_html = await self._get_element_html(link) if self.config.include_element_html else None
                violations.append(AccessibilityViolation(
                    id=self._generate_id("link-purpose", href or "unknown"),
                    wcag_reference="2.4.4",
                    category=AccessibilityCategory.LINKS,
                    severity=ViolationSeverity.MODERATE,
                    description=f'Link text "{accessible_name}" is not descriptive',
                    element_selector=f'a[href="{href}"]',
                    element_html=element_html,
                    suggested_fix="Use descriptive link text that indicates the destination or purpose",
                    impact="Users cannot understand the link purpose without surrounding context",
                ))

        return violations, passed

    async def _check_language(self, page: Page) -> tuple[List[AccessibilityViolation], int]:
        """Check language attributes."""
        violations = []
        passed = 0

        html_lang = await page.evaluate("() => document.documentElement.lang")

        if not html_lang or html_lang.strip() == "":
            violations.append(AccessibilityViolation(
                id=self._generate_id("lang", "html"),
                wcag_reference="3.1.1",
                category=AccessibilityCategory.LANGUAGE,
                severity=ViolationSeverity.SERIOUS,
                description="Page is missing language attribute",
                element_selector="html",
                suggested_fix='Add lang attribute to the html element (e.g., lang="en")',
                impact="Screen readers may not use correct pronunciation",
            ))
        else:
            passed += 1

        return violations, passed

    async def _check_aria_basic(self, page: Page) -> tuple[List[AccessibilityViolation], int]:
        """Basic ARIA checks (full validation in ARIAValidator)."""
        violations = []
        passed = 0

        aria_elements = await page.query_selector_all("[role]")

        valid_roles = {
            "alert", "alertdialog", "application", "article", "banner", "button",
            "cell", "checkbox", "columnheader", "combobox", "complementary",
            "contentinfo", "definition", "dialog", "directory", "document", "feed",
            "figure", "form", "grid", "gridcell", "group", "heading", "img",
            "link", "list", "listbox", "listitem", "log", "main", "marquee",
            "math", "menu", "menubar", "menuitem", "menuitemcheckbox",
            "menuitemradio", "meter", "navigation", "none", "note", "option",
            "presentation", "progressbar", "radio", "radiogroup", "region",
            "row", "rowgroup", "rowheader", "scrollbar", "search", "searchbox",
            "separator", "slider", "spinbutton", "status", "switch", "tab",
            "table", "tablist", "tabpanel", "term", "textbox", "timer",
            "toolbar", "tooltip", "tree", "treegrid", "treeitem",
        }

        for elem in aria_elements:
            role = await elem.get_attribute("role")

            if role and role.lower() not in valid_roles:
                element_html = await self._get_element_html(elem) if self.config.include_element_html else None
                violations.append(AccessibilityViolation(
                    id=self._generate_id("aria-role", role),
                    wcag_reference="4.1.2",
                    category=AccessibilityCategory.ARIA,
                    severity=ViolationSeverity.SERIOUS,
                    description=f'Invalid ARIA role: "{role}"',
                    element_selector=f'[role="{role}"]',
                    element_html=element_html,
                    suggested_fix=f"Use a valid ARIA role from the WAI-ARIA specification",
                    impact="Assistive technologies may not interpret the element correctly",
                ))
            else:
                passed += 1

        return violations, passed

    async def _get_element_html(self, element) -> str:
        """Get outer HTML of an element (truncated)."""
        try:
            html = cast(str, await element.evaluate("el => el.outerHTML"))
            if len(html) > 500:
                html = html[:500] + "..."
            return html
        except Exception:
            return ""

    def _generate_id(self, prefix: str, identifier: str) -> str:
        """Generate a unique violation ID."""
        return hashlib.md5(f"{prefix}:{identifier}".encode()).hexdigest()[:12]

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
