"""
Freya Mobile Compatibility check functions.

Check functions extracted from mobile_compatibility.py.
"""

from typing import List, Optional

from playwright.async_api import Page

from Asgard.Freya.Responsive.models.responsive_models import (
    MobileCompatibilityIssue,
    MobileCompatibilityIssueType,
)


async def check_flash_content(page: Page) -> List[MobileCompatibilityIssue]:
    """Check for Flash content."""
    issues = []

    try:
        flash_elements = await page.evaluate("""
            () => {
                const flash = document.querySelectorAll(
                    'object[type*="flash"], embed[type*="flash"], ' +
                    'object[data*=".swf"], embed[src*=".swf"]'
                );
                return flash.length;
            }
        """)

        if flash_elements > 0:
            issues.append(MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.FLASH_CONTENT,
                description=f"Page contains {flash_elements} Flash element(s)",
                severity="critical",
                suggested_fix="Replace Flash content with HTML5 alternatives",
                affected_devices=[],
            ))

    except Exception:
        pass

    return issues


async def check_hover_dependencies(page: Page) -> List[MobileCompatibilityIssue]:
    """Check for hover-dependent functionality."""
    issues = []

    try:
        hover_elements = await page.evaluate("""
            () => {
                const results = [];

                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    const style = getComputedStyle(el);

                    if (el.matches(':hover') === false) {
                        const hoverRules = Array.from(document.styleSheets).some(sheet => {
                            try {
                                return Array.from(sheet.cssRules || []).some(rule => {
                                    return rule.selectorText &&
                                           rule.selectorText.includes(':hover') &&
                                           el.matches(rule.selectorText.replace(':hover', ''));
                                });
                            } catch (e) {
                                return false;
                            }
                        });
                    }
                }

                const dropdowns = document.querySelectorAll(
                    '[class*="dropdown"], [class*="menu"], nav ul ul'
                );

                for (const dropdown of dropdowns) {
                    const style = getComputedStyle(dropdown);
                    if (style.display === 'none' || style.visibility === 'hidden') {
                        results.push({
                            selector: dropdown.className || dropdown.tagName.toLowerCase(),
                            type: 'hidden-menu'
                        });
                    }
                }

                return results.slice(0, 5);
            }
        """)

        for elem in hover_elements:
            issues.append(MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.HOVER_DEPENDENT,
                element_selector=elem["selector"],
                description="Element appears to require hover interaction",
                severity="moderate",
                suggested_fix="Add touch/click alternatives for hover-based interactions",
                affected_devices=[],
            ))

    except Exception:
        pass

    return issues


async def check_small_text(page: Page) -> List[MobileCompatibilityIssue]:
    """Check for text that's too small on mobile."""
    issues = []

    try:
        small_text = await page.evaluate("""
            () => {
                const results = [];
                const textElements = document.querySelectorAll('p, span, div, li, a');

                for (const el of textElements) {
                    const style = getComputedStyle(el);
                    const text = el.textContent || '';

                    if (text.trim().length < 5) continue;

                    const fontSize = parseFloat(style.fontSize);

                    if (fontSize < 12) {
                        const selector = el.id ? '#' + el.id :
                                          el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] :
                                          el.tagName.toLowerCase();

                        results.push({
                            selector: selector,
                            fontSize: fontSize
                        });
                    }
                }

                return results.slice(0, 5);
            }
        """)

        if small_text:
            issues.append(MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.SMALL_TEXT,
                description=f"Found {len(small_text)} elements with text smaller than 12px",
                severity="moderate",
                suggested_fix="Use a minimum font size of 16px for body text on mobile",
                affected_devices=[],
            ))

    except Exception:
        pass

    return issues


async def check_fixed_positioning(page: Page) -> List[MobileCompatibilityIssue]:
    """Check for problematic fixed positioning."""
    issues = []

    try:
        fixed_elements = await page.evaluate("""
            () => {
                const results = [];
                const elements = document.querySelectorAll('*');

                for (const el of elements) {
                    const style = getComputedStyle(el);

                    if (style.position === 'fixed') {
                        const rect = el.getBoundingClientRect();

                        const viewportCoverage = (rect.width * rect.height) /
                                                 (window.innerWidth * window.innerHeight);

                        if (viewportCoverage > 0.2) {
                            const selector = el.id ? '#' + el.id :
                                              el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] :
                                              el.tagName.toLowerCase();

                            results.push({
                                selector: selector,
                                coverage: viewportCoverage
                            });
                        }
                    }
                }

                return results;
            }
        """)

        for elem in fixed_elements:
            issues.append(MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.FIXED_POSITIONING,
                element_selector=elem["selector"],
                description=f"Fixed element covers {elem['coverage']*100:.0f}% of viewport",
                severity="moderate",
                suggested_fix="Consider making fixed elements smaller or collapsible on mobile",
                affected_devices=[],
            ))

    except Exception:
        pass

    return issues


def deduplicate_issues(
    issues: List[MobileCompatibilityIssue],
) -> List[MobileCompatibilityIssue]:
    """Remove duplicate issues, merging affected devices."""
    seen: dict[str, MobileCompatibilityIssue] = {}

    for issue in issues:
        key = f"{issue.issue_type}:{issue.element_selector}:{issue.description}"

        if key in seen:
            for device in issue.affected_devices:
                if device not in seen[key].affected_devices:
                    seen[key].affected_devices.append(device)
        else:
            seen[key] = issue

    return list(seen.values())


def calculate_score(
    issues: List[MobileCompatibilityIssue],
    load_time_ms: Optional[int],
    page_size_bytes: int,
) -> float:
    """Calculate mobile-friendly score."""
    score = 100.0

    severity_penalties = {
        "critical": 20,
        "serious": 10,
        "moderate": 5,
        "minor": 2,
    }

    for issue in issues:
        penalty = severity_penalties.get(issue.severity, 5)
        score -= penalty

    if load_time_ms:
        if load_time_ms > 5000:
            score -= 15
        elif load_time_ms > 3000:
            score -= 10
        elif load_time_ms > 2000:
            score -= 5

    if page_size_bytes:
        mb = page_size_bytes / (1024 * 1024)
        if mb > 5:
            score -= 10
        elif mb > 2:
            score -= 5

    return max(0, min(100, score))
