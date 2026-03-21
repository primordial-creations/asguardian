"""
Freya Color Contrast math helpers.

Pure color math functions extracted from color_contrast.py.
"""

import colorsys
import math
import re
from typing import Optional, Tuple


def parse_color(color_str: str) -> Optional[Tuple[int, int, int]]:
    """Parse a color string to RGB tuple."""
    if not color_str:
        return None

    color_str = color_str.strip().lower()

    if color_str.startswith("#"):
        return hex_to_rgb(color_str)

    rgb_match = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str)
    if rgb_match:
        return (
            int(rgb_match.group(1)),
            int(rgb_match.group(2)),
            int(rgb_match.group(3)),
        )

    named_colors = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "green": (0, 128, 0),
        "blue": (0, 0, 255),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "silver": (192, 192, 192),
        "maroon": (128, 0, 0),
        "olive": (128, 128, 0),
        "lime": (0, 255, 0),
        "aqua": (0, 255, 255),
        "teal": (0, 128, 128),
        "navy": (0, 0, 128),
        "fuchsia": (255, 0, 255),
        "purple": (128, 0, 128),
    }

    if color_str in named_colors:
        return named_colors[color_str]

    return None


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")

    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)

    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def calculate_contrast_ratio(
    fg_rgb: Tuple[int, int, int],
    bg_rgb: Tuple[int, int, int]
) -> float:
    """Calculate WCAG contrast ratio between two colors."""
    fg_luminance = calculate_relative_luminance(fg_rgb)
    bg_luminance = calculate_relative_luminance(bg_rgb)

    lighter = max(fg_luminance, bg_luminance)
    darker = min(fg_luminance, bg_luminance)

    return (lighter + 0.05) / (darker + 0.05)


def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate relative luminance per WCAG formula."""
    def gamma_correct(channel: int) -> float:
        c = channel / 255.0
        if c <= 0.03928:
            return c / 12.92
        return math.pow((c + 0.055) / 1.055, 2.4)

    r = gamma_correct(rgb[0])
    g = gamma_correct(rgb[1])
    b = gamma_correct(rgb[2])

    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def parse_font_size(font_size_str: str) -> float:
    """Parse font size string to pixels."""
    match = re.match(r"([\d.]+)(px|pt|em|rem|%)?", font_size_str)
    if match:
        value = float(match.group(1))
        unit = match.group(2) or "px"

        if unit == "pt":
            return value * 1.333
        elif unit == "em" or unit == "rem":
            return value * 16
        elif unit == "%":
            return value * 0.16
        else:
            return value

    return 16.0


def darken_to_ratio(
    rgb: Tuple[int, int, int],
    target_luminance: float,
    ratio: float
) -> Tuple[int, int, int]:
    """Darken a color to achieve target contrast ratio."""
    required_luminance = (target_luminance + 0.05) / ratio - 0.05
    required_luminance = max(0, min(1, required_luminance))

    h, l, s = colorsys.rgb_to_hls(rgb[0]/255, rgb[1]/255, rgb[2]/255)

    step = 0.01
    r, g, b = rgb[0]/255, rgb[1]/255, rgb[2]/255
    while l > 0:
        l -= step
        l = max(0, l)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        test_luminance = calculate_relative_luminance(
            (int(r*255), int(g*255), int(b*255))
        )
        if test_luminance <= required_luminance:
            break

    return (int(r*255), int(g*255), int(b*255))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
