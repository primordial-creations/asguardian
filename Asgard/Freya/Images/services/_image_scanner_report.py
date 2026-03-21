"""
Freya Image Optimization Scanner report builder.

Report building and suggestions extracted from image_optimization_scanner.py.
"""

from typing import Dict, List, cast

from Asgard.Freya.Images.models.image_models import (
    ImageConfig,
    ImageFormat,
    ImageInfo,
    ImageIssue,
    ImageIssueSeverity,
    ImageIssueType,
    ImageReport,
)


def calculate_score(report: ImageReport, total_images: int) -> float:
    """Calculate optimization score (0-100)."""
    if total_images == 0:
        return 100.0

    score = 100.0

    critical_penalty = min(40, report.critical_count * 10)
    score -= critical_penalty

    warning_penalty = min(30, report.warning_count * 3)
    score -= warning_penalty

    info_penalty = min(10, report.info_count * 1)
    score -= info_penalty

    if total_images > 0:
        lazy_ratio = report.images_with_lazy_loading / total_images
        score += lazy_ratio * 5

        modern_ratio = report.optimized_format_count / total_images
        score += modern_ratio * 5

    return cast(float, max(0, min(100, score)))


def generate_suggestions(report: ImageReport) -> List[str]:
    """Generate actionable suggestions."""
    suggestions = []

    if report.missing_alt_count > 0:
        suggestions.append(
            f"Add alt text to {report.missing_alt_count} image(s) for accessibility"
        )

    if report.missing_lazy_loading_count > 0:
        suggestions.append(
            f"Add lazy loading to {report.missing_lazy_loading_count} below-fold image(s)"
        )

    if report.non_optimized_format_count > 0:
        suggestions.append(
            f"Convert {report.non_optimized_format_count} image(s) to WebP/AVIF format"
        )

    if report.missing_dimensions_count > 0:
        suggestions.append(
            f"Add width/height to {report.missing_dimensions_count} image(s) to prevent CLS"
        )

    if report.oversized_count > 0:
        suggestions.append(
            f"Resize {report.oversized_count} oversized image(s) to match display size"
        )

    if report.missing_srcset_count > 0:
        suggestions.append(
            f"Add srcset to {report.missing_srcset_count} large image(s) for responsive loading"
        )

    if not suggestions:
        suggestions.append("Images are well optimized")

    return suggestions


def build_report(
    url: str,
    images: List[ImageInfo],
    issues: List[ImageIssue],
    config: ImageConfig,
) -> ImageReport:
    """Build the final report."""
    report = ImageReport(
        url=url,
        images=images if config.include_all_images else [],
        total_images=len(images),
        issues=issues,
        total_issues=len(issues),
    )

    for issue in issues:
        if issue.issue_type == ImageIssueType.MISSING_ALT:
            report.missing_alt_count += 1
        elif issue.issue_type == ImageIssueType.EMPTY_ALT:
            report.empty_alt_count += 1
        elif issue.issue_type == ImageIssueType.MISSING_LAZY_LOADING:
            report.missing_lazy_loading_count += 1
        elif issue.issue_type == ImageIssueType.NON_OPTIMIZED_FORMAT:
            report.non_optimized_format_count += 1
        elif issue.issue_type == ImageIssueType.MISSING_DIMENSIONS:
            report.missing_dimensions_count += 1
        elif issue.issue_type == ImageIssueType.OVERSIZED_IMAGE:
            report.oversized_count += 1
        elif issue.issue_type == ImageIssueType.MISSING_SRCSET:
            report.missing_srcset_count += 1

    for issue in issues:
        if issue.severity == ImageIssueSeverity.CRITICAL:
            report.critical_count += 1
        elif issue.severity == ImageIssueSeverity.WARNING:
            report.warning_count += 1
        elif issue.severity == ImageIssueSeverity.INFO:
            report.info_count += 1

    for image in images:
        if image.is_above_fold:
            report.images_above_fold += 1
        if image.has_lazy_loading:
            report.images_with_lazy_loading += 1
        if image.has_srcset:
            report.images_with_srcset += 1
        if image.format in [ImageFormat.WEBP, ImageFormat.AVIF]:
            report.optimized_format_count += 1
        if image.file_size_bytes:
            report.total_image_bytes += image.file_size_bytes

    format_counts: Dict[str, int] = {}
    for image in images:
        fmt = image.format.value
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    report.format_breakdown = format_counts

    report.optimization_score = calculate_score(report, len(images))

    report.suggestions = generate_suggestions(report)

    return report
