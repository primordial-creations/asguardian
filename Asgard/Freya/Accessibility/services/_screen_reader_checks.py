"""
Freya Screen Reader check functions.

Check functions extracted from screen_reader.py.
"""

from typing import Any, Dict, List, Optional, cast

from playwright.async_api import Page

from Asgard.Freya.Accessibility.models.accessibility_models import (
    ScreenReaderIssue,
    ScreenReaderIssueType,
    ViolationSeverity,
)


async def check_language(page: Page, issues: List[ScreenReaderIssue]) -> Optional[str]:
    """Check page language attribute."""
    lang = await page.evaluate("() => document.documentElement.lang")

    if not lang or lang.strip() == "":
        issues.append(ScreenReaderIssue(
            issue_type=ScreenReaderIssueType.MISSING_LANG_ATTRIBUTE,
            element_selector="html",
            description="Page is missing a language attribute",
            severity=ViolationSeverity.SERIOUS,
            wcag_reference="3.1.1",
            suggested_fix='Add lang attribute to html element (e.g., lang="en")',
        ))
        return None

    return cast(Optional[str], lang)


async def analyze_landmarks(
    page: Page,
    issues: List[ScreenReaderIssue]
) -> Dict[str, int]:
    """Analyze landmark regions."""
    landmarks = {}

    landmark_selectors = {
        "banner": 'header:not([role]), [role="banner"]',
        "navigation": "nav, [role='navigation']",
        "main": "main, [role='main']",
        "contentinfo": 'footer:not([role]), [role="contentinfo"]',
        "complementary": "aside, [role='complementary']",
        "search": "[role='search']",
        "form": "[role='form']",
        "region": "[role='region'][aria-label], [role='region'][aria-labelledby]",
    }

    for role, selector in landmark_selectors.items():
        try:
            elements = await page.query_selector_all(selector)
            count = len(elements)
            if count > 0:
                landmarks[role] = count
        except Exception:
            continue

    if "main" not in landmarks:
        issues.append(ScreenReaderIssue(
            issue_type=ScreenReaderIssueType.MISSING_LANDMARK,
            element_selector="body",
            description="Page is missing a main landmark",
            severity=ViolationSeverity.MODERATE,
            wcag_reference="1.3.1",
            suggested_fix="Add a <main> element or role='main' to identify main content",
        ))

    if "navigation" not in landmarks:
        nav_like = await page.query_selector_all("ul > li > a, .nav, .menu, .navigation")
        if len(nav_like) > 3:
            issues.append(ScreenReaderIssue(
                issue_type=ScreenReaderIssueType.MISSING_LANDMARK,
                element_selector="body",
                description="Page has navigation-like content but no navigation landmark",
                severity=ViolationSeverity.MINOR,
                wcag_reference="1.3.1",
                suggested_fix="Wrap navigation in a <nav> element or add role='navigation'",
            ))

    return landmarks


async def analyze_headings(
    page: Page,
    issues: List[ScreenReaderIssue]
) -> List[Dict[str, Any]]:
    """Analyze heading structure."""
    heading_structure = []

    try:
        headings = await page.query_selector_all("h1, h2, h3, h4, h5, h6")

        prev_level = 0
        for heading in headings:
            tag = await heading.evaluate("el => el.tagName.toLowerCase()")
            text = await heading.inner_text()
            level = int(tag[1])

            selector = await get_selector(page, heading)

            heading_structure.append({
                "level": level,
                "text": text.strip()[:100],
                "selector": selector,
            })

            if level > prev_level + 1 and prev_level > 0:
                issues.append(ScreenReaderIssue(
                    issue_type=ScreenReaderIssueType.SKIPPED_HEADING_LEVEL,
                    element_selector=selector,
                    description=f"Heading level skipped from h{prev_level} to h{level}",
                    severity=ViolationSeverity.MODERATE,
                    wcag_reference="1.3.1",
                    suggested_fix="Use sequential heading levels without skipping",
                ))

            prev_level = level

        if heading_structure and heading_structure[0]["level"] != 1:
            issues.append(ScreenReaderIssue(
                issue_type=ScreenReaderIssueType.MISSING_HEADING_STRUCTURE,
                element_selector=heading_structure[0]["selector"],
                description="First heading is not h1",
                severity=ViolationSeverity.MODERATE,
                wcag_reference="1.3.1",
                suggested_fix="Start with an h1 heading to define the main content",
            ))

        if not heading_structure:
            issues.append(ScreenReaderIssue(
                issue_type=ScreenReaderIssueType.MISSING_HEADING_STRUCTURE,
                element_selector="body",
                description="Page has no heading structure",
                severity=ViolationSeverity.SERIOUS,
                wcag_reference="1.3.1",
                suggested_fix="Add headings to organize content hierarchically",
            ))

    except Exception:
        pass

    return heading_structure


async def check_images(page: Page) -> tuple[List[ScreenReaderIssue], tuple[int, int]]:
    """Check images for accessible names."""
    issues = []
    labeled = 0
    total = 0

    try:
        images = await page.query_selector_all("img")

        for img in images:
            total += 1
            alt = await img.get_attribute("alt")
            role = await img.get_attribute("role")
            aria_label = await img.get_attribute("aria-label")
            aria_hidden = await img.get_attribute("aria-hidden")

            if aria_hidden == "true" or role in ["presentation", "none"]:
                labeled += 1
                continue

            if alt is None and not aria_label:
                selector = await get_selector(page, img)
                src = await img.get_attribute("src") or "unknown"
                issues.append(ScreenReaderIssue(
                    issue_type=ScreenReaderIssueType.MISSING_ALT_TEXT,
                    element_selector=selector,
                    description=f"Image is missing alt text: {src[:50]}",
                    severity=ViolationSeverity.CRITICAL,
                    wcag_reference="1.1.1",
                    suggested_fix="Add alt attribute describing the image, or alt='' for decorative images",
                ))
            else:
                labeled += 1

    except Exception:
        pass

    return issues, (labeled, total)


async def check_forms(page: Page) -> tuple[List[ScreenReaderIssue], tuple[int, int]]:
    """Check form inputs for accessible names."""
    issues = []
    labeled = 0
    total = 0

    try:
        inputs = await page.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='image']), "
            "select, textarea"
        )

        for input_elem in inputs:
            total += 1
            accessible_name = await get_accessible_name(page, input_elem)

            if accessible_name:
                labeled += 1
            else:
                selector = await get_selector(page, input_elem)
                input_type = await input_elem.get_attribute("type") or "text"
                issues.append(ScreenReaderIssue(
                    issue_type=ScreenReaderIssueType.MISSING_LABEL,
                    element_selector=selector,
                    description=f"Form input ({input_type}) is missing an accessible name",
                    severity=ViolationSeverity.SERIOUS,
                    wcag_reference="3.3.2",
                    suggested_fix="Add a <label> element, aria-label, or aria-labelledby",
                ))

    except Exception:
        pass

    return issues, (labeled, total)


async def check_links(page: Page) -> tuple[List[ScreenReaderIssue], tuple[int, int]]:
    """Check links for accessible names."""
    issues = []
    labeled = 0
    total = 0

    try:
        links = await page.query_selector_all("a[href]")

        for link in links:
            total += 1
            accessible_name = await get_accessible_name(page, link)

            if accessible_name:
                labeled += 1
            else:
                selector = await get_selector(page, link)
                href = await link.get_attribute("href")
                issues.append(ScreenReaderIssue(
                    issue_type=ScreenReaderIssueType.EMPTY_LINK,
                    element_selector=selector,
                    description=f"Link has no accessible name: {href[:50] if href else 'unknown'}",
                    severity=ViolationSeverity.SERIOUS,
                    wcag_reference="2.4.4",
                    suggested_fix="Add descriptive text content or aria-label",
                ))

    except Exception:
        pass

    return issues, (labeled, total)


async def check_buttons(page: Page) -> tuple[List[ScreenReaderIssue], tuple[int, int]]:
    """Check buttons for accessible names."""
    issues = []
    labeled = 0
    total = 0

    try:
        buttons = await page.query_selector_all(
            "button, input[type='submit'], input[type='button'], [role='button']"
        )

        for button in buttons:
            total += 1
            accessible_name = await get_accessible_name(page, button)

            if accessible_name:
                labeled += 1
            else:
                selector = await get_selector(page, button)
                issues.append(ScreenReaderIssue(
                    issue_type=ScreenReaderIssueType.EMPTY_BUTTON,
                    element_selector=selector,
                    description="Button has no accessible name",
                    severity=ViolationSeverity.CRITICAL,
                    wcag_reference="4.1.2",
                    suggested_fix="Add text content, aria-label, or value attribute",
                ))

    except Exception:
        pass

    return issues, (labeled, total)


async def get_accessible_name(page: Page, element) -> Optional[str]:
    """Get the computed accessible name for an element."""
    try:
        name = await page.evaluate("""
            (element) => {
                // Check aria-labelledby
                const labelledby = element.getAttribute('aria-labelledby');
                if (labelledby) {
                    const labels = labelledby.split(' ')
                        .map(id => document.getElementById(id))
                        .filter(el => el)
                        .map(el => el.textContent.trim());
                    if (labels.length > 0) return labels.join(' ');
                }

                // Check aria-label
                const ariaLabel = element.getAttribute('aria-label');
                if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();

                // Check for label element
                const id = element.id;
                if (id) {
                    const label = document.querySelector(`label[for="${id}"]`);
                    if (label && label.textContent.trim()) {
                        return label.textContent.trim();
                    }
                }

                // Check parent label
                const parentLabel = element.closest('label');
                if (parentLabel) {
                    const text = parentLabel.textContent.trim();
                    if (text) return text;
                }

                // Check title attribute
                const title = element.getAttribute('title');
                if (title && title.trim()) return title.trim();

                // Check text content (for buttons, links)
                const text = element.textContent || element.innerText;
                if (text && text.trim()) return text.trim();

                // Check value (for inputs)
                const value = element.value;
                if (value && value.trim()) return value.trim();

                // Check placeholder (last resort)
                const placeholder = element.getAttribute('placeholder');
                if (placeholder && placeholder.trim()) return placeholder.trim();

                // Check for images with alt text inside element
                const img = element.querySelector('img[alt]');
                if (img) {
                    const alt = img.getAttribute('alt');
                    if (alt && alt.trim()) return alt.trim();
                }

                return null;
            }
        """, element)
        return cast(Optional[str], name)
    except Exception:
        return None


async def get_selector(page: Page, element) -> str:
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
