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


def pixel_comparison(
    img1: Image,
    img2: Image,
    config: ComparisonConfig,
) -> Tuple[float, List[DifferenceRegion]]:
    """Pixel-by-pixel comparison."""
    diff_array = grayscale_difference_array(img1, img2)

    total_pixels = len(diff_array)
    different_pixels = count_above_threshold(diff_array, config.color_tolerance)
    similarity_score = 1.0 - (different_pixels / total_pixels)

    difference_regions = []

    if different_pixels > 0:
        binary = threshold_to_binary(diff_array, config.color_tolerance)
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
