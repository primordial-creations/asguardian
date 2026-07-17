"""
Freya Visual Regression comparison methods.

Pixel, SSIM, phash, and histogram comparison extracted from visual_regression.py.
"""

from typing import List, Tuple, cast

from Asgard.Freya.Visual.models.visual_models import (
    ComparisonConfig,
    DifferenceRegion,
    DifferenceType,
)
from Asgard.Freya.Visual.services.image_ops import Image, resize
from Asgard.Freya.Visual.services._image_ops_analysis import (
    component_bounding_boxes,
    connected_components,
    count_above_threshold,
    grayscale_difference_array,
    mean_of_indices,
    structural_similarity,
    threshold_to_binary,
)
from Asgard.Freya.Visual.services._image_ops_draw import fill_rectangle


def _is_antialiasing_pixel(
    img1: Image,
    img2: Image,
    x: int,
    y: int,
    tolerance: int,
) -> bool:
    """
    Classic pixelmatch anti-aliasing heuristic: a differing pixel is
    treated as anti-aliasing when the comparison pixel's color already
    exists (within tolerance) somewhere in the baseline's 8-neighborhood
    of the same location — i.e. the edge merely shifted sub-pixel.
    """
    r2, g2, b2 = img2.get_pixel(x, y)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx >= img1.width or ny >= img1.height:
                continue
            r1, g1, b1 = img1.get_pixel(nx, ny)
            luma_delta = abs(
                (0.299 * r1 + 0.587 * g1 + 0.114 * b1)
                - (0.299 * r2 + 0.587 * g2 + 0.114 * b2)
            )
            if luma_delta <= tolerance:
                return True
    return False


def apply_antialiasing_filter(
    img1: Image,
    img2: Image,
    binary: List[int],
    tolerance: int,
) -> List[int]:
    """Zero out diff-mask pixels explainable as anti-aliasing."""
    filtered = list(binary)
    width = img1.width
    for i, flagged in enumerate(binary):
        if not flagged:
            continue
        x, y = i % width, i // width
        if _is_antialiasing_pixel(img1, img2, x, y, tolerance):
            filtered[i] = 0
    return filtered


def merge_overlapping_regions(
    regions: List[DifferenceRegion],
    max_regions: int = 50,
) -> List[DifferenceRegion]:
    """
    Merge overlapping difference regions and cap the count so reports
    say "3 regions: ..." instead of raw pixel noise. When more than
    max_regions remain, the smallest are folded into the largest.
    """
    merged: List[DifferenceRegion] = []
    for region in sorted(regions, key=lambda r: -(r.width * r.height)):
        absorbed = False
        for existing in merged:
            if (region.x < existing.x + existing.width
                    and region.x + region.width > existing.x
                    and region.y < existing.y + existing.height
                    and region.y + region.height > existing.y):
                x_min = min(existing.x, region.x)
                y_min = min(existing.y, region.y)
                x_max = max(existing.x + existing.width, region.x + region.width)
                y_max = max(existing.y + existing.height, region.y + region.height)
                existing.x, existing.y = x_min, y_min
                existing.width, existing.height = x_max - x_min, y_max - y_min
                existing.pixel_count += region.pixel_count
                absorbed = True
                break
        if not absorbed:
            merged.append(region)
    if len(merged) > max_regions:
        overflow = merged[max_regions:]
        merged = merged[:max_regions]
        merged[-1].pixel_count += sum(r.pixel_count for r in overflow)
        merged[-1].description += f" (+{len(overflow)} smaller regions folded in)"
    return merged


def pixel_comparison(
    img1: Image,
    img2: Image,
    config: ComparisonConfig,
) -> Tuple[float, List[DifferenceRegion]]:
    """Pixel-by-pixel comparison (with optional anti-aliasing tolerance)."""
    diff_array = grayscale_difference_array(img1, img2)

    total_pixels = len(diff_array)
    binary = threshold_to_binary(diff_array, config.color_tolerance)
    if config.ignore_antialiasing and any(binary):
        binary = apply_antialiasing_filter(img1, img2, binary, config.color_tolerance)
    different_pixels = sum(binary)
    similarity_score = 1.0 - (different_pixels / total_pixels)

    difference_regions = []

    if different_pixels > 0:
        num_labels, labels = connected_components(binary, img1.width, img1.height)
        boxes = component_bounding_boxes(labels, img1.width, img1.height, num_labels)

        for label, (x_min, y_min, x_max, y_max, pixel_count) in boxes.items():
            if pixel_count > 50:
                difference_regions.append(DifferenceRegion(
                    x=x_min,
                    y=y_min,
                    width=x_max - x_min,
                    height=y_max - y_min,
                    difference_type=DifferenceType.MODIFICATION,
                    confidence=0.8,
                    description="Pixel differences detected",
                    pixel_count=pixel_count,
                ))
        difference_regions = merge_overlapping_regions(
            difference_regions, config.max_difference_regions
        )

    return similarity_score, difference_regions


def ssim_comparison(
    img1: Image,
    img2: Image,
    config: ComparisonConfig,
) -> Tuple[float, List[DifferenceRegion]]:
    """Structural Similarity Index comparison."""
    gray1 = img1.to_grayscale_array()
    gray2 = img2.to_grayscale_array()

    similarity_score, ssim_map = structural_similarity(
        gray1, gray2, img1.width, img1.height
    )

    difference_regions = []

    diff_threshold = 1.0 - config.threshold
    significant_binary = [1 if v < (1.0 - diff_threshold) else 0 for v in ssim_map]

    if any(v == 1 for v in significant_binary):
        num_labels, labels = connected_components(
            significant_binary, img1.width, img1.height
        )
        boxes = component_bounding_boxes(labels, img1.width, img1.height, num_labels)

        for label, (x_min, y_min, x_max, y_max, pixel_count) in boxes.items():
            if pixel_count > 100:
                component_indices = [
                    i for i in range(len(labels)) if labels[i] == label
                ]
                avg_similarity = mean_of_indices(ssim_map, component_indices)

                difference_regions.append(DifferenceRegion(
                    x=x_min,
                    y=y_min,
                    width=x_max - x_min,
                    height=y_max - y_min,
                    difference_type=DifferenceType.MODIFICATION,
                    confidence=float(1.0 - avg_similarity),
                    description=f"Structural difference (SSIM: {avg_similarity:.3f})",
                    pixel_count=pixel_count,
                    average_difference=float(1.0 - avg_similarity),
                ))

    return float(similarity_score), difference_regions


def phash_comparison(
    img1: Image,
    img2: Image,
    config: ComparisonConfig,
) -> Tuple[float, List[DifferenceRegion]]:
    """Perceptual hash comparison."""
    def calc_phash(image: Image) -> str:
        small = resize(image, 8, 8)
        gray = small.to_grayscale_array()
        avg = sum(gray) / len(gray)
        return "".join("1" if p > avg else "0" for p in gray)

    hash1 = calc_phash(img1)
    hash2 = calc_phash(img2)

    hamming_distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    similarity_score = 1.0 - (hamming_distance / len(hash1))

    difference_regions = []
    if similarity_score < config.threshold:
        difference_regions.append(DifferenceRegion(
            x=0,
            y=0,
            width=img1.width,
            height=img1.height,
            difference_type=DifferenceType.MODIFICATION,
            confidence=1.0 - similarity_score,
            description=f"Perceptual difference (Hamming: {hamming_distance})",
        ))

    return similarity_score, difference_regions


def histogram_comparison(
    img1: Image,
    img2: Image,
    config: ComparisonConfig,
) -> Tuple[float, List[DifferenceRegion]]:
    """Histogram comparison."""
    hist1 = img1.histogram()
    hist2 = img2.histogram()

    def correlation(h1: list, h2: list) -> float:
        sum1, sum2 = sum(h1), sum(h2)
        if sum1 == 0 or sum2 == 0:
            return 0.0

        h1_norm = [x / sum1 for x in h1]
        h2_norm = [x / sum2 for x in h2]

        mean1 = sum(h1_norm) / len(h1_norm)
        mean2 = sum(h2_norm) / len(h2_norm)

        numerator = sum((h1_norm[i] - mean1) * (h2_norm[i] - mean2) for i in range(len(h1_norm)))
        sum_sq1 = sum((h1_norm[i] - mean1) ** 2 for i in range(len(h1_norm)))
        sum_sq2 = sum((h2_norm[i] - mean2) ** 2 for i in range(len(h2_norm)))

        if sum_sq1 == 0 or sum_sq2 == 0:
            return 0.0

        return cast(float, numerator / (sum_sq1 * sum_sq2) ** 0.5)

    corr_r = correlation(hist1[0:256], hist2[0:256])
    corr_g = correlation(hist1[256:512], hist2[256:512])
    corr_b = correlation(hist1[512:768], hist2[512:768])

    similarity_score = (abs(corr_r) + abs(corr_g) + abs(corr_b)) / 3

    difference_regions = []
    if similarity_score < config.threshold:
        difference_regions.append(DifferenceRegion(
            x=0,
            y=0,
            width=img1.width,
            height=img1.height,
            difference_type=DifferenceType.COLOR,
            confidence=1.0 - similarity_score,
            description=f"Histogram difference (correlation: {similarity_score:.3f})",
        ))

    return similarity_score, difference_regions


def mask_regions(image: Image, regions: List[dict]) -> Image:
    """Mask specified regions."""
    masked = image.copy()

    for region in regions:
        x = region.get("x", 0)
        y = region.get("y", 0)
        w = region.get("width", 0)
        h = region.get("height", 0)
        fill_rectangle(masked, x, y, w, h, (128, 128, 128))

    return masked
