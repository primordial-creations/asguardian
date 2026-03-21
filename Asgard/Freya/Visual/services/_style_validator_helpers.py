"""
Freya Style Validator helper functions and ThemeLoader.

Helper functions and ThemeLoader extracted from style_validator.py.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, cast


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


def normalize_color(color: str) -> Optional[str]:
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


def extract_colors(colors_obj: dict, theme_colors: Set[str], prefix: str = "") -> None:
    """Extract colors from nested theme object into the set."""
    for key, value in colors_obj.items():
        if isinstance(value, str):
            normalized = normalize_color(value)
            if normalized:
                theme_colors.add(normalized)
        elif isinstance(value, dict):
            extract_colors(value, theme_colors, f"{prefix}{key}.")


def extract_fonts(fonts_obj: dict, theme_fonts: Set[str]) -> None:
    """Extract font families from theme object into the set."""
    for key, value in fonts_obj.items():
        if isinstance(value, str):
            theme_fonts.add(value.lower())
        elif isinstance(value, dict):
            if "family" in value:
                theme_fonts.add(value["family"].lower())
            extract_fonts(value, theme_fonts)


def load_theme(theme_file: str, theme_colors: Set[str], theme_fonts: Set[str]) -> None:
    """Load theme/design tokens from file into the provided sets."""
    try:
        with open(theme_file, "r") as f:
            theme = json.load(f)

        if "colors" in theme:
            extract_colors(theme["colors"], theme_colors)

        if "fonts" in theme or "typography" in theme:
            fonts = theme.get("fonts", theme.get("typography", {}))
            extract_fonts(fonts, theme_fonts)

    except Exception:
        pass
