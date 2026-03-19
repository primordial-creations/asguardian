"""
Freya Style Validator

Validates style consistency against design tokens and theme files.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, cast

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Visual.models.visual_models import (
    StyleReport,
    StyleIssue,
    StyleIssueType,
)


class StyleValidator:
    """
    Style validation service.

    Validates style consistency against design tokens
    and detects unknown colors/fonts.
    """

    def __init__(self, theme_file: Optional[str] = None):
        """
        Initialize the Style Validator.

        Args:
            theme_file: Path to theme/design tokens file (JSON)
        """
        self.theme_colors: Set[str] = set()
        self.theme_fonts: Set[str] = set()

        if theme_file:
            self._load_theme(theme_file)

    def _load_theme(self, theme_file: str) -> None:
        """Load theme/design tokens from file."""
        try:
            with open(theme_file, "r") as f:
                theme = json.load(f)

            if "colors" in theme:
                self._extract_colors(theme["colors"])

            if "fonts" in theme or "typography" in theme:
                fonts = theme.get("fonts", theme.get("typography", {}))
                self._extract_fonts(fonts)

        except Exception:
            pass

    def _extract_colors(self, colors_obj: dict, prefix: str = "") -> None:
        """Extract colors from nested theme object."""
        for key, value in colors_obj.items():
            if isinstance(value, str):
                normalized = self._normalize_color(value)
                if normalized:
                    self.theme_colors.add(normalized)
            elif isinstance(value, dict):
                self._extract_colors(value, f"{prefix}{key}.")

    def _extract_fonts(self, fonts_obj: dict) -> None:
        """Extract font families from theme object."""
        for key, value in fonts_obj.items():
            if isinstance(value, str):
                self.theme_fonts.add(value.lower())
            elif isinstance(value, dict):
                if "family" in value:
                    self.theme_fonts.add(value["family"].lower())
                self._extract_fonts(value)

    def _normalize_color(self, color: str) -> Optional[str]:
        """Normalize color to lowercase hex."""
        color = color.strip().lower()

        if color.startswith("#"):
            if len(color) == 4:
                color = f"#{color[1]}{color[1]}{color[2]}{color[2]}{color[3]}{color[3]}"
            return color

        rgb_match = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f"#{r:02x}{g:02x}{b:02x}"

        rgba_match = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+)", color)
        if rgba_match:
            r, g, b = map(int, rgba_match.groups())
            return f"#{r:02x}{g:02x}{b:02x}"

        return None

    async def validate(self, url: str) -> StyleReport:
        """
        Validate styles on a page.

        Args:
            url: URL to validate

        Returns:
            StyleReport with findings
        """
        issues = []
        colors_found: Dict[str, int] = {}
        fonts_found: Dict[str, int] = {}
        unknown_colors: List[str] = []
        unknown_fonts: List[str] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                style_data = await page.evaluate("""
                    () => {
                        const results = {
                            colors: {},
                            fonts: {},
                            elements: []
                        };

                        const elements = document.querySelectorAll('*');

                        for (const el of elements) {
                            const style = getComputedStyle(el);

                            // Collect colors
                            const colors = [
                                style.color,
                                style.backgroundColor,
                                style.borderColor,
                            ];

                            for (const color of colors) {
                                if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') {
                                    results.colors[color] = (results.colors[color] || 0) + 1;
                                }
                            }

                            // Collect fonts
                            const fontFamily = style.fontFamily.split(',')[0].trim().replace(/["']/g, '').toLowerCase();
                            if (fontFamily) {
                                results.fonts[fontFamily] = (results.fonts[fontFamily] || 0) + 1;
                            }

                            // Sample some elements for detailed analysis
                            if (results.elements.length < 50) {
                                const selector = el.id ? '#' + el.id :
                                                  el.className && typeof el.className === 'string' ?
                                                  el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] :
                                                  el.tagName.toLowerCase();

                                results.elements.push({
                                    selector: selector,
                                    color: style.color,
                                    backgroundColor: style.backgroundColor,
                                    fontFamily: fontFamily,
                                    fontSize: style.fontSize,
                                    fontWeight: style.fontWeight,
                                    lineHeight: style.lineHeight,
                                    padding: style.padding,
                                    margin: style.margin,
                                    borderRadius: style.borderRadius
                                });
                            }
                        }

                        return results;
                    }
                """)

                for color, count in style_data["colors"].items():
                    normalized = self._normalize_color(color)
                    if normalized:
                        colors_found[normalized] = colors_found.get(normalized, 0) + count

                        if self.theme_colors and normalized not in self.theme_colors:
                            if normalized not in unknown_colors:
                                unknown_colors.append(normalized)

                for font, count in style_data["fonts"].items():
                    fonts_found[font] = fonts_found.get(font, 0) + count

                    if self.theme_fonts and font not in self.theme_fonts:
                        if font not in unknown_fonts and font not in ["system-ui", "serif", "sans-serif", "monospace"]:
                            unknown_fonts.append(font)

                for elem in style_data["elements"]:
                    normalized_color = self._normalize_color(elem["color"])
                    normalized_bg = self._normalize_color(elem["backgroundColor"])

                    if self.theme_colors:
                        if normalized_color and normalized_color not in self.theme_colors:
                            issues.append(StyleIssue(
                                issue_type=StyleIssueType.UNKNOWN_COLOR,
                                element_selector=elem["selector"],
                                property_name="color",
                                actual_value=normalized_color,
                                description=f"Text color {normalized_color} not in theme",
                                severity="minor",
                            ))

                        if normalized_bg and normalized_bg not in self.theme_colors:
                            if normalized_bg != "#ffffff" and normalized_bg != "#000000":
                                issues.append(StyleIssue(
                                    issue_type=StyleIssueType.UNKNOWN_COLOR,
                                    element_selector=elem["selector"],
                                    property_name="backgroundColor",
                                    actual_value=normalized_bg,
                                    description=f"Background color {normalized_bg} not in theme",
                                    severity="minor",
                                ))

                    if self.theme_fonts:
                        if elem["fontFamily"] and elem["fontFamily"] not in self.theme_fonts:
                            if elem["fontFamily"] not in ["system-ui", "serif", "sans-serif", "monospace"]:
                                issues.append(StyleIssue(
                                    issue_type=StyleIssueType.UNKNOWN_FONT,
                                    element_selector=elem["selector"],
                                    property_name="fontFamily",
                                    actual_value=elem["fontFamily"],
                                    description=f"Font {elem['fontFamily']} not in theme",
                                    severity="minor",
                                ))

                consistency_issues = self._check_consistency(style_data["elements"])
                issues.extend(consistency_issues)

                total_elements = await page.evaluate("() => document.querySelectorAll('*').length")

            finally:
                await browser.close()

        return StyleReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            theme_file=None,
            total_elements=total_elements,
            issues=issues[:50],
            colors_found=colors_found,
            fonts_found=fonts_found,
            unknown_colors=unknown_colors,
            unknown_fonts=unknown_fonts,
        )

    def _check_consistency(self, elements: List[dict]) -> List[StyleIssue]:
        """Check for style consistency issues."""
        issues = []

        font_sizes: Dict[Any, int] = {}
        for elem in elements:
            size = elem.get("fontSize")
            if size:
                font_sizes[size] = font_sizes.get(size, 0) + 1

        if len(font_sizes) > 10:
            issues.append(StyleIssue(
                issue_type=StyleIssueType.FONT_MISMATCH,
                element_selector="body",
                property_name="fontSize",
                actual_value=f"{len(font_sizes)} different sizes",
                description=f"Too many font sizes ({len(font_sizes)}). Consider using a type scale.",
                severity="minor",
            ))

        spacing_values = set()
        for elem in elements:
            padding = elem.get("padding")
            margin = elem.get("margin")
            if padding:
                spacing_values.add(padding)
            if margin:
                spacing_values.add(margin)

        if len(spacing_values) > 20:
            issues.append(StyleIssue(
                issue_type=StyleIssueType.SPACING_MISMATCH,
                element_selector="body",
                property_name="spacing",
                actual_value=f"{len(spacing_values)} values",
                description=f"Too many spacing values ({len(spacing_values)}). Consider using a spacing scale.",
                severity="minor",
            ))

        return issues


class ThemeLoader:
    """Utility class to load various theme file formats."""

    @staticmethod
    def load_from_file(file_path: str) -> Dict:
        """Load theme from various file formats."""
        path = Path(file_path)

        if path.suffix == ".json":
            with open(path, "r") as f:
                return cast(Dict[Any, Any], json.load(f))

        elif path.suffix in [".ts", ".tsx", ".js"]:
            return ThemeLoader._parse_js_theme(path)

        elif path.suffix == ".css":
            return ThemeLoader._parse_css_variables(path)

        return {}

    @staticmethod
    def _parse_js_theme(path: Path) -> Dict:
        """Parse JavaScript/TypeScript theme file."""
        content = path.read_text()

        colors = {}
        color_pattern = r'["\']?([\w-]+)["\']?\s*:\s*["\']?(#[0-9a-fA-F]{3,8}|rgb\([^)]+\))["\']?'
        for match in re.finditer(color_pattern, content):
            colors[match.group(1)] = match.group(2)

        return {"colors": colors}

    @staticmethod
    def _parse_css_variables(path: Path) -> Dict:
        """Parse CSS custom properties."""
        content = path.read_text()

        colors = {}
        var_pattern = r'--([\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgb\([^)]+\)|rgba\([^)]+\))'
        for match in re.finditer(var_pattern, content):
            colors[match.group(1)] = match.group(2)

        return {"colors": colors}
