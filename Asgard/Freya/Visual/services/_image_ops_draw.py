"""
Asgard image drawing operations.

Drawing helpers extracted from image_ops.py:
rectangles, fills, and text label placeholders.
"""

from typing import Tuple

from Asgard.Freya.Visual.services.image_ops import Image


def draw_rectangle(
    image: Image,
    x: int, y: int, w: int, h: int,
    color: Tuple[int, int, int],
    line_width: int = 3,
) -> None:
    """Draw a rectangle outline on the image (mutates in place)."""
    for lw in range(line_width):
        for dx in range(x, min(x + w, image.width)):
            if 0 <= y + lw < image.height:
                image.set_pixel(dx, y + lw, color)
        by = y + h - 1 - lw
        for dx in range(x, min(x + w, image.width)):
            if 0 <= by < image.height:
                image.set_pixel(dx, by, color)
        for dy in range(y, min(y + h, image.height)):
            if 0 <= x + lw < image.width:
                image.set_pixel(x + lw, dy, color)
        rx = x + w - 1 - lw
        for dy in range(y, min(y + h, image.height)):
            if 0 <= rx < image.width:
                image.set_pixel(rx, dy, color)


def fill_rectangle(
    image: Image,
    x: int, y: int, w: int, h: int,
    color: Tuple[int, int, int],
) -> None:
    """Fill a rectangle on the image (mutates in place)."""
    for dy in range(max(0, y), min(y + h, image.height)):
        for dx in range(max(0, x), min(x + w, image.width)):
            image.set_pixel(dx, dy, color)


def draw_label(
    image: Image,
    x: int, y: int,
    text: str,
    color: Tuple[int, int, int],
) -> None:
    """
    Draw a simple text label as a colored bar with height proportional to text length.

    This is a minimal stand-in: real text rasterization requires a font engine.
    Instead we draw a small colored bar to mark the annotation point, which is
    sufficient for visual regression diff images where the actual text content
    is recorded in the structured report data.
    """
    bar_width = min(len(text) * 6, image.width - x)
    bar_height = 12
    for dy in range(max(0, y), min(y + bar_height, image.height)):
        for dx in range(max(0, x), min(x + bar_width, image.width)):
            image.set_pixel(dx, dy, color)
