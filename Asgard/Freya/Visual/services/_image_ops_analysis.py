"""
Asgard image analysis operations.

Analysis helpers extracted from image_ops.py:
connected component labeling, SSIM, and helper utilities.
"""

from typing import Dict, List, Tuple

from Asgard.Freya.Visual.services.image_ops import Image, difference


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
            ssim_val = numerator / denominator if denominator > 0 else 1.0
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
