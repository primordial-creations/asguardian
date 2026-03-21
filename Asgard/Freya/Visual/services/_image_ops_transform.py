"""
Freya image transformation functions.

Gaussian blur and contrast enhancement extracted from image_ops.py.
"""

import math

from Asgard.Freya.Visual.services.image_ops import Image


def enhance_contrast(image: Image, factor: float) -> Image:
    """Enhance contrast by the given factor (1.0 = no change)."""
    result = image.copy()
    for i in range(len(result.pixels)):
        r, g, b = result.pixels[i]
        result.pixels[i] = (
            max(0, min(255, int(128 + (r - 128) * factor))),
            max(0, min(255, int(128 + (g - 128) * factor))),
            max(0, min(255, int(128 + (b - 128) * factor))),
        )
    return result


def gaussian_blur(image: Image, radius: int) -> Image:
    """Apply a Gaussian blur with the given pixel radius."""
    if radius <= 0:
        return image.copy()
    sigma = radius / 2.0 if radius > 1 else 1.0
    size = radius * 2 + 1
    kernel = []
    total = 0.0
    for i in range(size):
        x = i - radius
        val = math.exp(-(x * x) / (2 * sigma * sigma))
        kernel.append(val)
        total += val
    kernel = [k / total for k in kernel]
    w, h = image.width, image.height
    temp = Image(w, h)
    for y in range(h):
        for x in range(w):
            r_acc, g_acc, b_acc = 0.0, 0.0, 0.0
            for k in range(size):
                sx = min(max(x + k - radius, 0), w - 1)
                pr, pg, pb = image.get_pixel(sx, y)
                r_acc += pr * kernel[k]
                g_acc += pg * kernel[k]
                b_acc += pb * kernel[k]
            temp.set_pixel(x, y, (
                max(0, min(255, int(r_acc + 0.5))),
                max(0, min(255, int(g_acc + 0.5))),
                max(0, min(255, int(b_acc + 0.5))),
            ))
    result = Image(w, h)
    for y in range(h):
        for x in range(w):
            r_acc, g_acc, b_acc = 0.0, 0.0, 0.0
            for k in range(size):
                sy = min(max(y + k - radius, 0), h - 1)
                pr, pg, pb = temp.get_pixel(x, sy)
                r_acc += pr * kernel[k]
                g_acc += pg * kernel[k]
                b_acc += pb * kernel[k]
            result.set_pixel(x, y, (
                max(0, min(255, int(r_acc + 0.5))),
                max(0, min(255, int(g_acc + 0.5))),
                max(0, min(255, int(b_acc + 0.5))),
            ))
    return result
