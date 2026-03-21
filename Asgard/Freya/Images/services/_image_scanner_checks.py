"""
Freya Image Optimization Scanner checks.

Individual image check functions extracted from image_optimization_scanner.py.
"""

from typing import List, Optional
from urllib.parse import urlparse

from Asgard.Freya.Images.models.image_models import (
    ImageConfig,
    ImageFormat,
    ImageInfo,
    ImageIssue,
    ImageIssueSeverity,
    ImageIssueType,
    ImageReport,
)


def detect_format(src: str) -> ImageFormat:
    """Detect image format from URL."""
    if not src:
        return ImageFormat.UNKNOWN

    src_lower = src.lower()

    for fmt in ImageFormat:
        if fmt == ImageFormat.UNKNOWN:
            continue
        if f".{fmt.value}" in src_lower:
            return fmt

    if "webp" in src_lower:
        return ImageFormat.WEBP
    if "avif" in src_lower:
        return ImageFormat.AVIF

    return ImageFormat.UNKNOWN


def parse_int(value) -> Optional[int]:
    """Safely parse an integer value."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def build_image_info(data: dict) -> ImageInfo:
    """Build ImageInfo from extracted data."""
    src = data.get("src", "")
    format_type = detect_format(src)

    is_decorative = (
        data.get("role") == "presentation" or
        data.get("ariaHidden") == "true" or
        (data.get("hasAlt") and data.get("alt") == "")
    )

    return ImageInfo(
        src=src,
        alt=data.get("alt"),
        has_alt=data.get("hasAlt", False),
        width=parse_int(data.get("width")),
        height=parse_int(data.get("height")),
        has_dimensions=bool(data.get("width") and data.get("height")),
        loading=data.get("loading"),
        has_lazy_loading=data.get("loading") == "lazy",
        srcset=data.get("srcset"),
        has_srcset=bool(data.get("srcset")),
        sizes=data.get("sizes"),
        format=format_type,
        natural_width=data.get("naturalWidth"),
        natural_height=data.get("naturalHeight"),
        display_width=data.get("displayWidth"),
        display_height=data.get("displayHeight"),
        is_above_fold=data.get("isAboveFold", False),
        element_html=data.get("html"),
        css_selector=data.get("cssSelector"),
        is_decorative=is_decorative,
        is_background_image=data.get("type") == "background",
    )


def appears_decorative(image: ImageInfo) -> bool:
    """Heuristic to detect if image appears decorative."""
    src_lower = image.src.lower()

    decorative_patterns = [
        "icon", "logo", "spacer", "dot", "bullet",
        "divider", "separator", "border", "shadow",
        "gradient", "pattern", "texture", "background",
        "arrow", "chevron", "caret",
    ]

    for pattern in decorative_patterns:
        if pattern in src_lower:
            return True

    if image.display_width and image.display_height:
        if image.display_width < 24 and image.display_height < 24:
            return True

    return False


def check_alt_text(image: ImageInfo) -> Optional[ImageIssue]:
    """Check for alt text issues."""
    if image.is_decorative and image.has_alt and image.alt == "":
        return None

    if not image.has_alt:
        return ImageIssue(
            issue_type=ImageIssueType.MISSING_ALT,
            severity=ImageIssueSeverity.CRITICAL,
            image_src=image.src,
            description="Image is missing alt attribute",
            suggested_fix=(
                "Add an alt attribute describing the image content. "
                "For decorative images, use alt=\"\""
            ),
            wcag_reference="WCAG 1.1.1 (Non-text Content)",
            impact="Screen reader users will not know what the image contains",
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    if image.alt == "" and not image.is_decorative:
        if appears_decorative(image):
            return None

        return ImageIssue(
            issue_type=ImageIssueType.EMPTY_ALT,
            severity=ImageIssueSeverity.WARNING,
            image_src=image.src,
            description="Image has empty alt text but may contain meaningful content",
            suggested_fix=(
                "If the image conveys information, add descriptive alt text. "
                "If purely decorative, empty alt is correct."
            ),
            wcag_reference="WCAG 1.1.1 (Non-text Content)",
            impact="Screen reader users may miss important information",
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    return None


def check_lazy_loading(image: ImageInfo) -> Optional[ImageIssue]:
    """Check for lazy loading issues."""
    if image.is_above_fold and image.has_lazy_loading:
        return ImageIssue(
            issue_type=ImageIssueType.MISSING_LAZY_LOADING,
            severity=ImageIssueSeverity.INFO,
            image_src=image.src,
            description="Above-fold image has lazy loading which may delay LCP",
            suggested_fix=(
                "Remove loading=\"lazy\" from above-fold images "
                "to improve Largest Contentful Paint"
            ),
            wcag_reference=None,
            impact="May negatively impact Core Web Vitals (LCP)",
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    if not image.is_above_fold and not image.has_lazy_loading:
        return ImageIssue(
            issue_type=ImageIssueType.MISSING_LAZY_LOADING,
            severity=ImageIssueSeverity.WARNING,
            image_src=image.src,
            description="Below-fold image does not have lazy loading",
            suggested_fix="Add loading=\"lazy\" to defer loading until needed",
            wcag_reference=None,
            impact=(
                "Images load immediately, increasing initial page weight "
                "and slowing page load"
            ),
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    return None


def check_format(image: ImageInfo, skip_svg: bool) -> Optional[ImageIssue]:
    """Check for non-optimized format."""
    if skip_svg and image.format == ImageFormat.SVG:
        return None

    modern_formats = [ImageFormat.WEBP, ImageFormat.AVIF, ImageFormat.SVG]

    if image.format not in modern_formats and image.format != ImageFormat.UNKNOWN:
        return ImageIssue(
            issue_type=ImageIssueType.NON_OPTIMIZED_FORMAT,
            severity=ImageIssueSeverity.WARNING,
            image_src=image.src,
            description=(
                f"Image uses {image.format.value.upper()} format "
                f"instead of modern WebP/AVIF"
            ),
            suggested_fix=(
                "Convert to WebP or AVIF format for better compression. "
                "Use <picture> element for fallback support."
            ),
            wcag_reference=None,
            impact="Modern formats can reduce file size by 25-50% without quality loss",
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    return None


def check_dimensions(image: ImageInfo) -> Optional[ImageIssue]:
    """Check for missing width/height attributes."""
    if not image.has_dimensions:
        return ImageIssue(
            issue_type=ImageIssueType.MISSING_DIMENSIONS,
            severity=ImageIssueSeverity.WARNING,
            image_src=image.src,
            description="Image is missing width and/or height attributes",
            suggested_fix=(
                "Add explicit width and height attributes to prevent "
                "Cumulative Layout Shift (CLS)"
            ),
            wcag_reference=None,
            impact="Browser cannot reserve space, causing layout shifts when image loads",
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    return None


def estimate_size_savings(
    natural_width: int,
    natural_height: int,
    display_width: int,
    display_height: int,
) -> int:
    """Estimate bytes saved by resizing."""
    if not natural_height or not display_height:
        return 0

    natural_pixels = natural_width * natural_height
    display_pixels = display_width * display_height

    bytes_per_pixel = 0.5

    natural_bytes = natural_pixels * bytes_per_pixel
    display_bytes = display_pixels * bytes_per_pixel

    return int(natural_bytes - display_bytes)


def check_oversized(image: ImageInfo, oversized_threshold: float) -> Optional[ImageIssue]:
    """Check for oversized images."""
    if not image.natural_width or not image.display_width:
        return None

    if image.display_width == 0:
        return None

    ratio = image.natural_width / image.display_width

    if ratio > oversized_threshold:
        wasted_pixels = image.natural_width - image.display_width
        estimated_savings = estimate_size_savings(
            image.natural_width,
            image.natural_height or 0,
            image.display_width,
            image.display_height or 0,
        )

        return ImageIssue(
            issue_type=ImageIssueType.OVERSIZED_IMAGE,
            severity=ImageIssueSeverity.WARNING,
            image_src=image.src,
            description=(
                f"Image is {ratio:.1f}x larger than displayed size "
                f"({image.natural_width}x{image.natural_height} displayed at "
                f"{image.display_width}x{image.display_height})"
            ),
            suggested_fix=(
                f"Resize image to match display size or use srcset. "
                f"Could save ~{estimated_savings // 1024}KB"
            ),
            wcag_reference=None,
            impact=f"~{wasted_pixels}px of unnecessary width being downloaded",
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    return None


def check_srcset(image: ImageInfo, min_srcset_width: int) -> Optional[ImageIssue]:
    """Check for missing srcset on responsive images."""
    if (image.display_width or 0) < min_srcset_width:
        return None

    if not image.has_srcset:
        return ImageIssue(
            issue_type=ImageIssueType.MISSING_SRCSET,
            severity=ImageIssueSeverity.INFO,
            image_src=image.src,
            description="Large image missing srcset for responsive images",
            suggested_fix=(
                "Add srcset attribute with multiple image sizes "
                "for different screen resolutions"
            ),
            wcag_reference=None,
            impact="Mobile users may download unnecessarily large images",
            element_html=image.element_html,
            css_selector=image.css_selector,
        )

    return None


def check_image(image: ImageInfo, config: ImageConfig) -> List[ImageIssue]:
    """Check a single image for issues."""
    issues: List[ImageIssue] = []

    if image.is_background_image:
        if config.check_formats:
            format_issue = check_format(image, config.skip_svg)
            if format_issue:
                issues.append(format_issue)
        return issues

    if config.check_alt_text:
        alt_issue = check_alt_text(image)
        if alt_issue:
            issues.append(alt_issue)

    if config.check_lazy_loading:
        lazy_issue = check_lazy_loading(image)
        if lazy_issue:
            issues.append(lazy_issue)

    if config.check_formats:
        format_issue = check_format(image, config.skip_svg)
        if format_issue:
            issues.append(format_issue)

    if config.check_dimensions:
        dim_issue = check_dimensions(image)
        if dim_issue:
            issues.append(dim_issue)

    if config.check_oversized:
        oversized_issue = check_oversized(image, config.oversized_threshold)
        if oversized_issue:
            issues.append(oversized_issue)

    if config.check_srcset:
        srcset_issue = check_srcset(image, config.min_srcset_width)
        if srcset_issue:
            issues.append(srcset_issue)

    return issues
