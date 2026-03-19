"""
Freya Viewport Tester

Tests viewport configuration and behavior on mobile devices.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Responsive.models.responsive_models import (
    ViewportIssue,
    ViewportIssueType,
    ViewportReport,
)


class ViewportTester:
    """
    Viewport testing service.

    Tests viewport meta tag configuration and behavior.
    """

    def __init__(self):
        """Initialize the Viewport Tester."""
        pass

    async def test(
        self,
        url: str,
        viewport_width: int = 375,
        viewport_height: int = 667
    ) -> ViewportReport:
        """
        Test viewport configuration.

        Args:
            url: URL to test
            viewport_width: Viewport width
            viewport_height: Viewport height

        Returns:
            ViewportReport with findings
        """
        issues = []
        text_sizes: Dict[str, int] = {}
        minimum_text_size = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                is_mobile=True,
                has_touch=True,
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                viewport_meta = await self._get_viewport_meta(page)

                if viewport_meta is None:
                    issues.append(ViewportIssue(
                        issue_type=ViewportIssueType.MISSING_VIEWPORT_META,
                        description="Page is missing viewport meta tag",
                        severity="critical",
                        suggested_fix='Add <meta name="viewport" content="width=device-width, initial-scale=1">',
                        wcag_reference="1.4.4",
                    ))
                else:
                    meta_issues = self._analyze_viewport_meta(viewport_meta)
                    issues.extend(meta_issues)

                content_width = await page.evaluate(
                    "() => document.documentElement.scrollWidth"
                )
                has_horizontal_scroll = content_width > viewport_width

                if has_horizontal_scroll:
                    issues.append(ViewportIssue(
                        issue_type=ViewportIssueType.CONTENT_WIDER_THAN_VIEWPORT,
                        description=f"Content width ({content_width}px) exceeds viewport ({viewport_width}px)",
                        severity="serious",
                        current_value=f"{content_width}px",
                        suggested_fix="Ensure all content fits within the viewport width",
                    ))

                text_data = await self._analyze_text_sizes(page)
                text_sizes = text_data["sizes"]
                minimum_text_size = text_data["minimum"]

                if minimum_text_size and minimum_text_size < 12:
                    issues.append(ViewportIssue(
                        issue_type=ViewportIssueType.TEXT_TOO_SMALL,
                        description=f"Text size ({minimum_text_size}px) is below recommended minimum (12px)",
                        severity="moderate",
                        current_value=f"{minimum_text_size}px",
                        suggested_fix="Use a minimum font size of 12px for readability on mobile",
                        wcag_reference="1.4.4",
                    ))

            finally:
                await browser.close()

        return ViewportReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            viewport_meta=viewport_meta,
            content_width=content_width,
            viewport_width=viewport_width,
            has_horizontal_scroll=has_horizontal_scroll,
            issues=issues,
            text_sizes=text_sizes,
            minimum_text_size=minimum_text_size,
        )

    async def _get_viewport_meta(self, page: Page) -> Optional[str]:
        """Get viewport meta tag content."""
        try:
            content = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[name="viewport"]');
                    return meta ? meta.getAttribute('content') : null;
                }
            """)
            return cast(Optional[str], content)
        except Exception:
            return None

    def _analyze_viewport_meta(self, content: str) -> List[ViewportIssue]:
        """Analyze viewport meta tag content."""
        issues = []

        content_lower = content.lower().replace(" ", "")

        if "width=" in content_lower and "width=device-width" not in content_lower:
            width_match = re.search(r"width=(\d+)", content_lower)
            if width_match:
                issues.append(ViewportIssue(
                    issue_type=ViewportIssueType.FIXED_WIDTH_VIEWPORT,
                    description=f"Viewport has fixed width: {width_match.group(1)}px",
                    severity="serious",
                    current_value=content,
                    suggested_fix="Use width=device-width for responsive layouts",
                ))

        if "user-scalable=no" in content_lower or "user-scalable=0" in content_lower:
            issues.append(ViewportIssue(
                issue_type=ViewportIssueType.USER_SCALABLE_DISABLED,
                description="User zooming is disabled",
                severity="serious",
                current_value=content,
                suggested_fix="Remove user-scalable=no to allow users to zoom",
                wcag_reference="1.4.4",
            ))

        max_scale_match = re.search(r"maximum-scale=([\d.]+)", content_lower)
        if max_scale_match:
            max_scale = float(max_scale_match.group(1))
            if max_scale < 2.0:
                issues.append(ViewportIssue(
                    issue_type=ViewportIssueType.MAXIMUM_SCALE_TOO_LOW,
                    description=f"Maximum scale ({max_scale}) is too restrictive",
                    severity="moderate",
                    current_value=content,
                    suggested_fix="Remove maximum-scale or set it to at least 2.0",
                    wcag_reference="1.4.4",
                ))

        return issues

    async def _analyze_text_sizes(self, page: Page) -> Dict:
        """Analyze text sizes on the page."""
        try:
            result = await page.evaluate("""
                () => {
                    const sizes = {};
                    let minimum = Infinity;

                    const textElements = document.querySelectorAll(
                        'p, span, div, h1, h2, h3, h4, h5, h6, a, li, td, th, label'
                    );

                    for (const el of textElements) {
                        const style = getComputedStyle(el);
                        const text = el.textContent || '';

                        if (text.trim().length === 0) continue;

                        const fontSize = parseFloat(style.fontSize);

                        if (!isNaN(fontSize) && fontSize > 0) {
                            const sizeKey = Math.round(fontSize) + 'px';
                            sizes[sizeKey] = (sizes[sizeKey] || 0) + 1;

                            if (fontSize < minimum) {
                                minimum = fontSize;
                            }
                        }
                    }

                    return {
                        sizes: sizes,
                        minimum: minimum === Infinity ? null : minimum
                    };
                }
            """)
            return cast(Dict[Any, Any], result)
        except Exception:
            return {"sizes": {}, "minimum": None}
