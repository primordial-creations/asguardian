"""
Freya Breakpoint Tester check functions.

Check functions extracted from breakpoint_tester.py.
"""

from typing import List

from playwright.async_api import Page

from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    BreakpointIssue,
    BreakpointIssueType,
)


async def check_horizontal_scroll(
    page: Page,
    breakpoint: Breakpoint
) -> List[BreakpointIssue]:
    """Check for horizontal scrolling."""
    issues = []

    scroll_width = await page.evaluate(
        "() => document.documentElement.scrollWidth"
    )

    if scroll_width > breakpoint.width:
        overflow_elements = await page.evaluate(f"""
            () => {{
                const results = [];
                const elements = document.querySelectorAll('*');
                for (const el of elements) {{
                    const rect = el.getBoundingClientRect();
                    if (rect.right > {breakpoint.width}) {{
                        const selector = el.id ? '#' + el.id :
                                          el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] :
                                          el.tagName.toLowerCase();
                        results.push({{
                            selector: selector,
                            right: rect.right,
                            width: rect.width
                        }});
                    }}
                }}
                return results.slice(0, 5);
            }}
        """)

        for elem in overflow_elements:
            issues.append(BreakpointIssue(
                issue_type=BreakpointIssueType.HORIZONTAL_SCROLL,
                breakpoint=breakpoint.name,
                viewport_width=breakpoint.width,
                element_selector=elem["selector"],
                description=f"Element extends beyond viewport (right: {elem['right']:.0f}px)",
                severity="serious",
                suggested_fix="Use max-width: 100% or adjust element width",
            ))

    return issues


async def check_content_overflow(
    page: Page,
    breakpoint: Breakpoint
) -> List[BreakpointIssue]:
    """Check for content overflow issues."""
    issues = []

    try:
        overflows = await page.evaluate("""
            () => {
                const results = [];
                const elements = document.querySelectorAll('*');

                for (const el of elements) {
                    const style = getComputedStyle(el);

                    if (el.scrollWidth > el.clientWidth &&
                        style.overflowX !== 'scroll' &&
                        style.overflowX !== 'auto' &&
                        style.overflowX !== 'hidden' &&
                        el.clientWidth > 0) {

                        const selector = el.id ? '#' + el.id :
                                          el.tagName.toLowerCase();

                        results.push({
                            selector: selector,
                            scrollWidth: el.scrollWidth,
                            clientWidth: el.clientWidth
                        });
                    }
                }

                return results.slice(0, 5);
            }
        """)

        for overflow in overflows:
            issues.append(BreakpointIssue(
                issue_type=BreakpointIssueType.CONTENT_OVERFLOW,
                breakpoint=breakpoint.name,
                viewport_width=breakpoint.width,
                element_selector=overflow["selector"],
                description=f"Content overflows container ({overflow['scrollWidth']}px > {overflow['clientWidth']}px)",
                severity="moderate",
                suggested_fix="Add overflow: hidden/auto or use word-wrap/overflow-wrap",
            ))

    except Exception:
        pass

    return issues


async def check_overlapping_elements(
    page: Page,
    breakpoint: Breakpoint
) -> List[BreakpointIssue]:
    """Check for overlapping interactive elements."""
    issues = []

    try:
        overlaps = await page.evaluate("""
            () => {
                const results = [];
                const interactive = document.querySelectorAll('a, button, input, select');
                const checked = new Set();

                for (let i = 0; i < interactive.length && i < 50; i++) {
                    for (let j = i + 1; j < interactive.length && j < 50; j++) {
                        const rect1 = interactive[i].getBoundingClientRect();
                        const rect2 = interactive[j].getBoundingClientRect();

                        if (rect1.width === 0 || rect1.height === 0 ||
                            rect2.width === 0 || rect2.height === 0) continue;

                        const overlap = !(rect1.right < rect2.left ||
                                         rect1.left > rect2.right ||
                                         rect1.bottom < rect2.top ||
                                         rect1.top > rect2.bottom);

                        if (overlap) {
                            const sel1 = interactive[i].tagName.toLowerCase();
                            const sel2 = interactive[j].tagName.toLowerCase();
                            const key = sel1 + '-' + sel2;

                            if (!checked.has(key)) {
                                checked.add(key);
                                results.push({
                                    selector1: sel1,
                                    selector2: sel2
                                });
                            }
                        }
                    }
                }

                return results.slice(0, 5);
            }
        """)

        for overlap in overlaps:
            issues.append(BreakpointIssue(
                issue_type=BreakpointIssueType.OVERLAPPING_ELEMENTS,
                breakpoint=breakpoint.name,
                viewport_width=breakpoint.width,
                element_selector=overlap["selector1"],
                description=f"Interactive elements overlap: {overlap['selector1']} and {overlap['selector2']}",
                severity="serious",
                suggested_fix="Adjust layout or use media queries to prevent overlap",
            ))

    except Exception:
        pass

    return issues


async def check_text_truncation(
    page: Page,
    breakpoint: Breakpoint
) -> List[BreakpointIssue]:
    """Check for unintended text truncation."""
    issues = []

    try:
        truncated = await page.evaluate("""
            () => {
                const results = [];
                const textElements = document.querySelectorAll('h1, h2, h3, h4, button, a');

                for (const el of textElements) {
                    const style = getComputedStyle(el);

                    if (style.textOverflow === 'ellipsis' &&
                        el.scrollWidth > el.clientWidth) {

                        const selector = el.id ? '#' + el.id :
                                          el.tagName.toLowerCase();

                        results.push({
                            selector: selector,
                            text: el.textContent.substring(0, 50)
                        });
                    }
                }

                return results.slice(0, 5);
            }
        """)

        for item in truncated:
            issues.append(BreakpointIssue(
                issue_type=BreakpointIssueType.TEXT_TRUNCATION,
                breakpoint=breakpoint.name,
                viewport_width=breakpoint.width,
                element_selector=item["selector"],
                description=f"Text is truncated: '{item['text'][:30]}...'",
                severity="minor",
                suggested_fix="Consider using responsive font sizes or allowing text to wrap",
            ))

    except Exception:
        pass

    return issues
