"""
Asgard custom image operations module.

Pure-Python replacement for Pillow, numpy, opencv-python, and scikit-image
used in visual regression testing. Uses only the Python standard library
(struct, zlib, io) to read/write PNG files and perform image analysis.

Supported operations:
- PNG read/write (8-bit RGB)
- Image resizing (bilinear interpolation)
- Pixel-level difference and thresholding
- Grayscale conversion
- Connected component labeling (union-find)
- Structural Similarity Index (SSIM)
- Gaussian blur
- Drawing (rectangles, text placeholders)
- Histogram computation and contrast enhancement
"""

import io
import math
import struct
import zlib
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Image:
    """
    Minimal RGB image backed by a flat list of (r, g, b) tuples.

    Pixel layout is row-major: pixels[y * width + x] = (r, g, b).
    """

    __slots__ = ("width", "height", "pixels")

    def __init__(self, width: int, height: int, pixels: Optional[List[Tuple[int, int, int]]] = None):
        self.width = width
        self.height = height
        if pixels is not None:
            self.pixels = pixels
        else:
            self.pixels = [(0, 0, 0)] * (width * height)

    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)

    def copy(self) -> "Image":
        return Image(self.width, self.height, list(self.pixels))

    def get_pixel(self, x: int, y: int) -> Tuple[int, int, int]:
        return self.pixels[y * self.width + x]

    def set_pixel(self, x: int, y: int, color: Tuple[int, int, int]) -> None:
        self.pixels[y * self.width + x] = color

    def to_grayscale_array(self) -> List[int]:
        """Return a flat list of luminance values (0-255), row-major."""
        return [
            int(0.299 * r + 0.587 * g + 0.114 * b)
            for r, g, b in self.pixels
        ]

    def histogram(self) -> List[int]:
        """Return a 768-element histogram: [R0..R255, G0..G255, B0..B255]."""
        hist = [0] * 768
        for r, g, b in self.pixels:
            hist[r] += 1
            hist[256 + g] += 1
            hist[512 + b] += 1
        return hist


# ---------------------------------------------------------------------------
# PNG reading
# ---------------------------------------------------------------------------

def _read_png_chunks(data: bytes) -> List[Tuple[str, bytes]]:
    """Parse PNG chunks from raw file bytes."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a valid PNG file")
    pos = 8
    chunks = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8].decode("ascii")
        chunk_data = data[pos + 8:pos + 8 + length]
        # skip CRC (4 bytes)
        pos += 12 + length
        chunks.append((chunk_type, chunk_data))
        if chunk_type == "IEND":
            break
    return chunks


def _paeth_predictor(a: int, b: int, c: int) -> int:
    """PNG Paeth predictor."""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter_row(filter_type: int, current_raw: bytes, previous_row: bytes, bpp: int) -> bytes:
    """Reverse the PNG per-row filter."""
    result = bytearray(len(current_raw))
    for i in range(len(current_raw)):
        raw = current_raw[i]
        a = result[i - bpp] if i >= bpp else 0
        b = previous_row[i] if previous_row else 0
        c = previous_row[i - bpp] if (previous_row and i >= bpp) else 0

        if filter_type == 0:
            result[i] = raw
        elif filter_type == 1:
            result[i] = (raw + a) & 0xFF
        elif filter_type == 2:
            result[i] = (raw + b) & 0xFF
        elif filter_type == 3:
            result[i] = (raw + (a + b) // 2) & 0xFF
        elif filter_type == 4:
            result[i] = (raw + _paeth_predictor(a, b, c)) & 0xFF
        else:
            result[i] = raw
    return bytes(result)


def load_image(path: str) -> Image:
    """Load a PNG file and return an Image (converted to RGB)."""
    data = Path(path).read_bytes()
    chunks = _read_png_chunks(data)

    # Parse IHDR
    ihdr_data = None
    idat_parts = []
    for chunk_type, chunk_data in chunks:
        if chunk_type == "IHDR":
            ihdr_data = chunk_data
        elif chunk_type == "IDAT":
            idat_parts.append(chunk_data)

    if ihdr_data is None:
        raise ValueError("PNG missing IHDR chunk")

    width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr_data[:10])

    if bit_depth != 8:
        raise ValueError(f"Only 8-bit PNGs are supported (got {bit_depth}-bit)")

    # Determine bytes per pixel and whether there's an alpha channel
    if color_type == 0:  # Grayscale
        bpp = 1
        has_alpha = False
    elif color_type == 2:  # RGB
        bpp = 3
        has_alpha = False
    elif color_type == 4:  # Grayscale + Alpha
        bpp = 2
        has_alpha = True
    elif color_type == 6:  # RGBA
        bpp = 4
        has_alpha = True
    else:
        raise ValueError(f"Unsupported PNG color type: {color_type}")

    # Decompress IDAT
    raw = zlib.decompress(b"".join(idat_parts))

    # Unfilter rows
    row_bytes = width * bpp
    pixels = []
    previous_row: Optional[bytes] = None

    for y in range(height):
        offset = y * (1 + row_bytes)
        filter_type = raw[offset]
        current_raw = raw[offset + 1:offset + 1 + row_bytes]
        unfiltered = _unfilter_row(filter_type, current_raw, previous_row or bytes(row_bytes), bpp)
        previous_row = unfiltered

        for x in range(width):
            base = x * bpp
            if color_type == 0:  # Grayscale
                g = unfiltered[base]
                pixels.append((g, g, g))
            elif color_type == 2:  # RGB
                pixels.append((unfiltered[base], unfiltered[base + 1], unfiltered[base + 2]))
            elif color_type == 4:  # Grayscale + Alpha (discard alpha)
                g = unfiltered[base]
                pixels.append((g, g, g))
            elif color_type == 6:  # RGBA (discard alpha)
                pixels.append((unfiltered[base], unfiltered[base + 1], unfiltered[base + 2]))

    return Image(width, height, pixels)


# ---------------------------------------------------------------------------
# PNG writing
# ---------------------------------------------------------------------------

def _make_png_chunk(chunk_type: str, data: bytes) -> bytes:
    """Build a single PNG chunk with CRC."""
    type_bytes = chunk_type.encode("ascii")
    crc = zlib.crc32(type_bytes + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + type_bytes + data + struct.pack(">I", crc)


def save_image(image: Image, path: str) -> None:
    """Save an Image as an 8-bit RGB PNG file."""
    buf = io.BytesIO()
    # PNG signature
    buf.write(b"\x89PNG\r\n\x1a\n")

    # IHDR
    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    buf.write(_make_png_chunk("IHDR", ihdr))

    # IDAT - build raw image data with filter type 0 (None) per row
    raw_rows = bytearray()
    for y in range(image.height):
        raw_rows.append(0)  # filter type None
        for x in range(image.width):
            r, g, b = image.pixels[y * image.width + x]
            raw_rows.extend((r, g, b))

    compressed = zlib.compress(bytes(raw_rows), 9)
    buf.write(_make_png_chunk("IDAT", compressed))

    # IEND
    buf.write(_make_png_chunk("IEND", b""))

    Path(path).write_bytes(buf.getvalue())


# ---------------------------------------------------------------------------
# Image transformations
# ---------------------------------------------------------------------------

def resize(image: Image, new_width: int, new_height: int) -> Image:
    """Resize image using bilinear interpolation."""
    if new_width == image.width and new_height == image.height:
        return image.copy()

    result = Image(new_width, new_height)
    x_ratio = image.width / new_width
    y_ratio = image.height / new_height

    for y in range(new_height):
        src_y = y * y_ratio
        y0 = min(int(src_y), image.height - 1)
        y1 = min(y0 + 1, image.height - 1)
        fy = src_y - y0

        for x in range(new_width):
            src_x = x * x_ratio
            x0 = min(int(src_x), image.width - 1)
            x1 = min(x0 + 1, image.width - 1)
            fx = src_x - x0

            # Bilinear interpolation on each channel
            p00 = image.get_pixel(x0, y0)
            p10 = image.get_pixel(x1, y0)
            p01 = image.get_pixel(x0, y1)
            p11 = image.get_pixel(x1, y1)

            channels = []
            for c in range(3):
                top = p00[c] * (1 - fx) + p10[c] * fx
                bottom = p01[c] * (1 - fx) + p11[c] * fx
                channels.append(int(top * (1 - fy) + bottom * fy + 0.5))

            result.set_pixel(x, y, (
                max(0, min(255, channels[0])),
                max(0, min(255, channels[1])),
                max(0, min(255, channels[2])),
            ))

    return result


def difference(img1: Image, img2: Image) -> Image:
    """Absolute per-channel pixel difference between two same-sized images."""
    if img1.width != img2.width or img1.height != img2.height:
        raise ValueError("Images must have the same dimensions")

    result = Image(img1.width, img1.height)
    for i in range(len(img1.pixels)):
        r1, g1, b1 = img1.pixels[i]
        r2, g2, b2 = img2.pixels[i]
        result.pixels[i] = (abs(r1 - r2), abs(g1 - g2), abs(b1 - b2))
    return result


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

    # Build 1D Gaussian kernel
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

    # Horizontal pass
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

    # Vertical pass
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


# ---------------------------------------------------------------------------
# Analysis operations
# ---------------------------------------------------------------------------

def grayscale_difference_array(img1: Image, img2: Image) -> List[int]:
    """Compute per-pixel grayscale difference as a flat array."""
    diff_img = difference(img1, img2)
    return diff_img.to_grayscale_array()


def count_above_threshold(values: List[int], threshold: int) -> int:
    """Count values strictly above the threshold."""
    return sum(1 for v in values if v > threshold)


def threshold_to_binary(values: List[int], threshold: int) -> List[int]:
    """Convert grayscale array to binary (0 or 1) based on threshold."""
    return [1 if v > threshold else 0 for v in values]


def connected_components(binary: List[int], width: int, height: int) -> Tuple[int, List[int]]:
    """
    Label connected components in a binary image using union-find.

    Returns (num_labels, labels) where labels is a flat array of component IDs.
    Label 0 is background, labels 1..N are the components.
    """
    labels = [0] * len(binary)
    parent: Dict[int, int] = {}
    next_label = 1

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # First pass: assign provisional labels
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if binary[idx] == 0:
                continue

            neighbors = []
            if x > 0 and binary[idx - 1] == 1:
                neighbors.append(labels[idx - 1])
            if y > 0 and binary[idx - width] == 1:
                neighbors.append(labels[idx - width])

            if not neighbors:
                labels[idx] = next_label
                parent[next_label] = next_label
                next_label += 1
            else:
                min_label = min(neighbors)
                labels[idx] = min_label
                for nb in neighbors:
                    union(min_label, nb)

    # Second pass: resolve to root labels
    label_map: Dict[int, int] = {}
    final_label = 0
    for i in range(len(labels)):
        if labels[i] == 0:
            continue
        root = find(labels[i])
        if root not in label_map:
            final_label += 1
            label_map[root] = final_label
        labels[i] = label_map[root]

    return final_label, labels


def component_bounding_boxes(
    labels: List[int], width: int, height: int, num_labels: int
) -> Dict[int, Tuple[int, int, int, int, int]]:
    """
    For each component label, return (x_min, y_min, x_max, y_max, pixel_count).
    """
    boxes: Dict[int, List[int]] = {}
    for y in range(height):
        for x in range(width):
            label = labels[y * width + x]
            if label == 0:
                continue
            if label not in boxes:
                boxes[label] = [x, y, x, y, 0]
            box = boxes[label]
            if x < box[0]:
                box[0] = x
            if y < box[1]:
                box[1] = y
            if x > box[2]:
                box[2] = x
            if y > box[3]:
                box[3] = y
            box[4] += 1

    return {k: (v[0], v[1], v[2], v[3], v[4]) for k, v in boxes.items()}


def structural_similarity(
    gray1: List[int], gray2: List[int], width: int, height: int, window_size: int = 7
) -> Tuple[float, List[float]]:
    """
    Compute the Structural Similarity Index (SSIM) between two grayscale images.

    Returns (overall_ssim, ssim_map) where ssim_map is a per-pixel quality value.
    Uses the standard SSIM formula with constants C1 and C2 derived from dynamic range.

    The window_size parameter controls the local region used for statistics.
    """
    L = 255
    C1 = (0.01 * L) ** 2
    C2 = (0.03 * L) ** 2

    half_w = window_size // 2
    ssim_map = [1.0] * (width * height)
    ssim_sum = 0.0
    count = 0

    for y in range(half_w, height - half_w):
        for x in range(half_w, width - half_w):
            # Collect window values
            sum1, sum2 = 0.0, 0.0
            sum1_sq, sum2_sq = 0.0, 0.0
            sum12 = 0.0
            n = 0

            for wy in range(y - half_w, y + half_w + 1):
                for wx in range(x - half_w, x + half_w + 1):
                    idx = wy * width + wx
                    v1 = gray1[idx]
                    v2 = gray2[idx]
                    sum1 += v1
                    sum2 += v2
                    sum1_sq += v1 * v1
                    sum2_sq += v2 * v2
                    sum12 += v1 * v2
                    n += 1

            mu1 = sum1 / n
            mu2 = sum2 / n
            sigma1_sq = sum1_sq / n - mu1 * mu1
            sigma2_sq = sum2_sq / n - mu2 * mu2
            sigma12 = sum12 / n - mu1 * mu2

            numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
            denominator = (mu1 * mu1 + mu2 * mu2 + C1) * (sigma1_sq + sigma2_sq + C2)

            if denominator > 0:
                ssim_val = numerator / denominator
            else:
                ssim_val = 1.0

            ssim_map[y * width + x] = ssim_val
            ssim_sum += ssim_val
            count += 1

    overall = ssim_sum / count if count > 0 else 1.0
    return overall, ssim_map


def mean_of_indices(values: List[float], indices: List[int]) -> float:
    """Compute the mean of values at the given indices."""
    if not indices:
        return 0.0
    return sum(values[i] for i in indices) / len(indices)


# ---------------------------------------------------------------------------
# Drawing operations
# ---------------------------------------------------------------------------

def draw_rectangle(
    image: Image,
    x: int, y: int, w: int, h: int,
    color: Tuple[int, int, int],
    line_width: int = 3,
) -> None:
    """Draw a rectangle outline on the image (mutates in place)."""
    for lw in range(line_width):
        # Top edge
        for dx in range(x, min(x + w, image.width)):
            if 0 <= y + lw < image.height:
                image.set_pixel(dx, y + lw, color)
        # Bottom edge
        by = y + h - 1 - lw
        for dx in range(x, min(x + w, image.width)):
            if 0 <= by < image.height:
                image.set_pixel(dx, by, color)
        # Left edge
        for dy in range(y, min(y + h, image.height)):
            if 0 <= x + lw < image.width:
                image.set_pixel(x + lw, dy, color)
        # Right edge
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
