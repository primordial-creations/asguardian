"""
Freya Color Contrast Checker

Validates color contrast ratios against WCAG 2.1 requirements.
Supports AA (4.5:1 normal, 3:1 large) and AAA (7:1 normal, 4.5:1 large) levels.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    ContrastReport,
    ContrastResult,
    ContrastIssue,
    TextSize,
    WCAGLevel,
)
from Asgard.Freya.Accessibility.services._color_contrast_math import (
    parse_color,
    hex_to_rgb,
    calculate_contrast_ratio,
    calculate_relative_luminance,
    parse_font_size,
    darken_to_ratio,
    rgb_to_hex,
)


CONTRAST_REQUIREMENTS = {
    WCAGLevel.A: {
        TextSize.NORMAL: 3.0,
        TextSize.LARGE: 3.0,
    },
    WCAGLevel.AA: {
        TextSize.NORMAL: 4.5,
        TextSize.LARGE: 3.0,
    },
    WCAGLevel.AAA: {
        TextSize.NORMAL: 7.0,
        TextSize.LARGE: 4.5,
    },
}


class ColorContrastChecker:
    """
    Color contrast ratio checker for WCAG compliance.

    Analyzes text elements and their backgrounds to verify
    contrast ratios meet WCAG 2.1 requirements.
    """

    def __init__(self, config: AccessibilityConfig):
        """
        Initialize the Color Contrast Checker.

        Args:
            config: Accessibility configuration
        """
        self.config = config

    async def check(self, url: str) -> ContrastReport:
        """
        Check color contrast on a page.

        Args:
            url: URL to check

        Returns:
            ContrastReport with all findings
        """
        results = []
        issues = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                text_elements = await self._get_text_elements(page)

                for element_data in text_elements:
                    result = await self._analyze_element_contrast(page, element_data)
                    if result:
                        results.append(result)
                        if not result.is_passing:
                            issues.append(self._create_issue(result))

            finally:
                await browser.close()

        passing_count = sum(1 for r in results if r.is_passing)
        failing_count = len(results) - passing_count
        avg_contrast = sum(r.contrast_ratio for r in results) / len(results) if results else 0.0

        return ContrastReport(
            url=url,
            wcag_level=self.config.wcag_level.value,
            tested_at=datetime.now().isoformat(),
            total_elements=len(results),
            passing_count=passing_count,
            failing_count=failing_count,
            results=results,
            issues=issues,
            average_contrast=avg_contrast,
        )

    async def check_colors(
        self,
        foreground: str,
        background: str,
        font_size_px: float = 16.0,
        font_weight: str = "400"
    ) -> ContrastResult:
        """
        Check contrast between two colors directly.

        Args:
            foreground: Foreground color (hex, rgb, or named)
            background: Background color (hex, rgb, or named)
            font_size_px: Font size in pixels
            font_weight: Font weight (400, 700, bold, etc.)

        Returns:
            ContrastResult for the color pair
        """
        fg_rgb = parse_color(foreground)
        bg_rgb = parse_color(background)

        if fg_rgb is None:
            fg_rgb = (0, 0, 0)
        if bg_rgb is None:
            bg_rgb = (255, 255, 255)

        contrast_ratio = calculate_contrast_ratio(fg_rgb, bg_rgb)
        text_size = self._categorize_text_size(font_size_px, font_weight)

        required_aa = CONTRAST_REQUIREMENTS[WCAGLevel.AA][text_size]
        required_aaa = CONTRAST_REQUIREMENTS[WCAGLevel.AAA][text_size]
        required = CONTRAST_REQUIREMENTS[self.config.wcag_level][text_size]

        return ContrastResult(
            element_selector="direct-check",
            foreground_color=foreground,
            background_color=background,
            contrast_ratio=contrast_ratio,
            required_ratio=required,
            text_size=text_size,
            font_size_px=font_size_px,
            font_weight=font_weight,
            is_passing=contrast_ratio >= required,
            wcag_aa_pass=contrast_ratio >= required_aa,
            wcag_aaa_pass=contrast_ratio >= required_aaa,
        )

    async def _get_text_elements(self, page: Page) -> List[dict]:
        """Get all text elements from the page."""
        selectors = [
            "p", "span", "div", "h1", "h2", "h3", "h4", "h5", "h6",
            "a", "button", "label", "li", "td", "th", "caption",
            "figcaption", "blockquote", "cite", "q", "em", "strong",
            "small", "mark", "del", "ins", "sub", "sup", "time",
        ]

        elements = []

        for selector in selectors:
            found = await page.query_selector_all(selector)
            for elem in found[:50]:
                try:
                    has_text = await elem.evaluate("""
                        el => {
                            const text = el.innerText || el.textContent;
                            return text && text.trim().length > 0;
                        }
                    """)

                    if has_text:
                        box = await elem.bounding_box()
                        if box and box["width"] > 0 and box["height"] > 0:
                            styles = await self._get_element_styles(page, elem)
                            elements.append({
                                "element": elem,
                                "selector": selector,
                                "styles": styles,
                            })
                except Exception:
                    continue

        return elements

    async def _get_element_styles(self, page: Page, element) -> dict:
        """Get computed styles for an element."""
        try:
            styles = await page.evaluate("""
                (element) => {
                    const computed = getComputedStyle(element);
                    return {
                        color: computed.color,
                        backgroundColor: computed.backgroundColor,
                        fontSize: computed.fontSize,
                        fontWeight: computed.fontWeight,
                        lineHeight: computed.lineHeight,
                    };
                }
            """, element)
            return cast(Dict[Any, Any], styles)
        except Exception:
            return {
                "color": "rgb(0, 0, 0)",
                "backgroundColor": "rgb(255, 255, 255)",
                "fontSize": "16px",
                "fontWeight": "400",
            }

    async def _get_effective_background(self, page: Page, element) -> str:
        """Get effective background color including parent elements."""
        try:
            bg_color = await page.evaluate("""
                (element) => {
                    let current = element;
                    while (current) {
                        const computed = getComputedStyle(current);
                        const bg = computed.backgroundColor;

                        // Skip transparent backgrounds
                        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
                            return bg;
                        }
                        current = current.parentElement;
                    }
                    return 'rgb(255, 255, 255)';  // Default to white
                }
            """, element)
            return cast(str, bg_color)
        except Exception:
            return "rgb(255, 255, 255)"

    async def _analyze_element_contrast(self, page: Page, element_data: dict) -> Optional[ContrastResult]:
        """Analyze contrast for a single element."""
        try:
            element = element_data["element"]
            styles = element_data["styles"]
            selector = element_data["selector"]

            fg_color = styles.get("color", "rgb(0, 0, 0)")
            bg_color = await self._get_effective_background(page, element)

            fg_rgb = parse_color(fg_color)
            bg_rgb = parse_color(bg_color)

            if fg_rgb is None or bg_rgb is None:
                return None

            contrast_ratio = calculate_contrast_ratio(fg_rgb, bg_rgb)

            font_size_str = styles.get("fontSize", "16px")
            font_size_px = parse_font_size(font_size_str)
            font_weight = styles.get("fontWeight", "400")

            text_size = self._categorize_text_size(font_size_px, font_weight)

            required_aa = CONTRAST_REQUIREMENTS[WCAGLevel.AA][text_size]
            required_aaa = CONTRAST_REQUIREMENTS[WCAGLevel.AAA][text_size]
            required = CONTRAST_REQUIREMENTS[self.config.wcag_level][text_size]

            unique_selector = await self._get_unique_selector(page, element)

            return ContrastResult(
                element_selector=unique_selector or selector,
                foreground_color=fg_color,
                background_color=bg_color,
                contrast_ratio=round(contrast_ratio, 2),
                required_ratio=required,
                text_size=text_size,
                font_size_px=font_size_px,
                font_weight=font_weight,
                is_passing=contrast_ratio >= required,
                wcag_aa_pass=contrast_ratio >= required_aa,
                wcag_aaa_pass=contrast_ratio >= required_aaa,
            )

        except Exception:
            return None

    async def _get_unique_selector(self, page: Page, element) -> Optional[str]:
        """Generate a unique CSS selector for an element."""
        try:
            selector = await page.evaluate("""
                (element) => {
                    if (element.id) {
                        return '#' + element.id;
                    }

                    const path = [];
                    let current = element;

                    while (current && current.nodeType === Node.ELEMENT_NODE) {
                        let selector = current.nodeName.toLowerCase();

                        if (current.id) {
                            selector = '#' + current.id;
                            path.unshift(selector);
                            break;
                        }

                        if (current.className && typeof current.className === 'string') {
                            const classes = current.className.trim().split(/\\s+/).slice(0, 2);
                            if (classes.length > 0 && classes[0]) {
                                selector += '.' + classes.join('.');
                            }
                        }

                        path.unshift(selector);
                        current = current.parentNode;
                    }

                    return path.slice(-3).join(' > ');
                }
            """, element)
            return cast(Optional[str], selector)
        except Exception:
            return None

    def _categorize_text_size(self, font_size_px: float, font_weight: str) -> TextSize:
        """Categorize text as normal or large per WCAG."""
        is_bold = font_weight in ["bold", "700", "800", "900"] or (
            font_weight.isdigit() and int(font_weight) >= 700
        )

        if font_size_px >= 24:
            return TextSize.LARGE
        elif font_size_px >= 18.5 and is_bold:
            return TextSize.LARGE
        else:
            return TextSize.NORMAL

    def _create_issue(self, result: ContrastResult) -> ContrastIssue:
        """Create a ContrastIssue from a failing result."""
        fg_suggested, bg_suggested = self._suggest_fixes(
            result.foreground_color,
            result.background_color,
            result.required_ratio,
        )

        return ContrastIssue(
            element_selector=result.element_selector,
            foreground_color=result.foreground_color,
            background_color=result.background_color,
            contrast_ratio=result.contrast_ratio,
            required_ratio=result.required_ratio,
            suggested_foreground=fg_suggested,
            suggested_background=bg_suggested,
        )

    def _suggest_fixes(
        self,
        foreground: str,
        background: str,
        required_ratio: float
    ) -> Tuple[Optional[str], Optional[str]]:
        """Suggest color fixes to meet contrast requirements."""
        fg_rgb = parse_color(foreground)
        bg_rgb = parse_color(background)

        if fg_rgb is None or bg_rgb is None:
            return None, None

        fg_luminance = calculate_relative_luminance(fg_rgb)
        bg_luminance = calculate_relative_luminance(bg_rgb)

        if fg_luminance < bg_luminance:
            darker_rgb = darken_to_ratio(fg_rgb, bg_luminance, required_ratio)
            return rgb_to_hex(darker_rgb), None
        else:
            darker_rgb = darken_to_ratio(bg_rgb, fg_luminance, required_ratio)
            return None, rgb_to_hex(darker_rgb)

    def _parse_color(self, color_str: str) -> Optional[Tuple[int, int, int]]:
        """Parse a color string to RGB tuple."""
        return parse_color(color_str)

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        return hex_to_rgb(hex_color)

    def _calculate_contrast_ratio(
        self,
        fg_rgb: Tuple[int, int, int],
        bg_rgb: Tuple[int, int, int]
    ) -> float:
        """Calculate WCAG contrast ratio between two colors."""
        return calculate_contrast_ratio(fg_rgb, bg_rgb)

    def _calculate_relative_luminance(self, rgb: Tuple[int, int, int]) -> float:
        """Calculate relative luminance per WCAG formula."""
        return calculate_relative_luminance(rgb)

    def _parse_font_size(self, font_size_str: str) -> float:
        """Parse font size string to pixels."""
        return parse_font_size(font_size_str)

    def _darken_to_ratio(
        self,
        rgb: Tuple[int, int, int],
        target_luminance: float,
        ratio: float
    ) -> Tuple[int, int, int]:
        """Darken a color to achieve target contrast ratio."""
        return darken_to_ratio(rgb, target_luminance, ratio)

    def _rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        """Convert RGB tuple to hex string."""
        return rgb_to_hex(rgb)
