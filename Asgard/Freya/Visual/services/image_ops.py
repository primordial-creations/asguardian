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
import struct
import zlib
from pathlib import Path
from typing import List, Optional, Tuple


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
    if color_type == 0:
        bpp = 1
    elif color_type == 2:
        bpp = 3
    elif color_type == 4:
        bpp = 2
    elif color_type == 6:
        bpp = 4
    else:
        raise ValueError(f"Unsupported PNG color type: {color_type}")
    raw = zlib.decompress(b"".join(idat_parts))
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
            if color_type == 0:
                g = unfiltered[base]
                pixels.append((g, g, g))
            elif color_type == 2:
                pixels.append((unfiltered[base], unfiltered[base + 1], unfiltered[base + 2]))
            elif color_type == 4:
                g = unfiltered[base]
                pixels.append((g, g, g))
            elif color_type == 6:
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
    buf.write(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0)
    buf.write(_make_png_chunk("IHDR", ihdr))
    raw_rows = bytearray()
    for y in range(image.height):
        raw_rows.append(0)
        for x in range(image.width):
            r, g, b = image.pixels[y * image.width + x]
            raw_rows.extend((r, g, b))
    compressed = zlib.compress(bytes(raw_rows), 9)
    buf.write(_make_png_chunk("IDAT", compressed))
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


