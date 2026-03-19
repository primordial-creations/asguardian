"""
Freya Visual Regression Tester

Compares screenshots to detect visual differences and regressions.
Supports multiple comparison methods and generates diff images.

Uses Asgard's custom image_ops module (pure Python, no external dependencies)
instead of Pillow, numpy, opencv-python, or scikit-image.
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, cast

from Asgard.Freya.Visual.models.visual_models import (
    ComparisonConfig,
    ComparisonMethod,
    DifferenceRegion,
    DifferenceType,
    RegressionReport,
    RegressionTestSuite,
    VisualComparisonResult,
)
from Asgard.Freya.Visual.services.image_ops import (
    Image,
    component_bounding_boxes,
    connected_components,
    count_above_threshold,
    difference,
    draw_label,
    draw_rectangle,
    enhance_contrast,
    fill_rectangle,
    gaussian_blur,
    grayscale_difference_array,
    load_image,
    mean_of_indices,
    resize,
    save_image,
    structural_similarity,
    threshold_to_binary,
)

# Color name to RGB mapping for annotation drawing
_COLOR_MAP = {
    "green": (0, 180, 0),
    "red": (220, 0, 0),
    "orange": (255, 165, 0),
    "blue": (0, 0, 220),
    "purple": (128, 0, 128),
    "yellow": (255, 255, 0),
    "cyan": (0, 220, 220),
}


class VisualRegressionTester:
    """
    Visual regression testing service.

    Compares images using various methods and identifies
    visual differences.
    """

    def __init__(self, output_directory: str = "./regression_output"):
        """
        Initialize the Visual Regression Tester.

        Args:
            output_directory: Directory for output files
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

        (self.output_directory / "diffs").mkdir(exist_ok=True)
        (self.output_directory / "reports").mkdir(exist_ok=True)

    def compare(
        self,
        baseline_path: str,
        comparison_path: str,
        config: Optional[ComparisonConfig] = None
    ) -> VisualComparisonResult:
        """
        Compare two images.

        Args:
            baseline_path: Path to baseline image
            comparison_path: Path to comparison image
            config: Comparison configuration

        Returns:
            VisualComparisonResult with comparison details
        """
        if config is None:
            config = ComparisonConfig()

        start_time = time.time()

        try:
            baseline_img = load_image(baseline_path)
            comparison_img = load_image(comparison_path)
        except Exception as e:
            return VisualComparisonResult(
                baseline_path=baseline_path,
                comparison_path=comparison_path,
                similarity_score=0.0,
                is_similar=False,
                difference_regions=[],
                metadata={"error": str(e)},
            )

        if baseline_img.size != comparison_img.size:
            min_width = min(baseline_img.width, comparison_img.width)
            min_height = min(baseline_img.height, comparison_img.height)
            baseline_img = resize(baseline_img, min_width, min_height)
            comparison_img = resize(comparison_img, min_width, min_height)

        if config.blur_radius > 0:
            baseline_img = gaussian_blur(baseline_img, config.blur_radius)
            comparison_img = gaussian_blur(comparison_img, config.blur_radius)

        if config.ignore_regions:
            baseline_img = self._mask_regions(baseline_img, config.ignore_regions)
            comparison_img = self._mask_regions(comparison_img, config.ignore_regions)

        if config.method == ComparisonMethod.STRUCTURAL_SIMILARITY:
            similarity_score, difference_regions = self._ssim_comparison(
                baseline_img, comparison_img, config
            )
        elif config.method == ComparisonMethod.PERCEPTUAL_HASH:
            similarity_score, difference_regions = self._phash_comparison(
                baseline_img, comparison_img, config
            )
        elif config.method == ComparisonMethod.HISTOGRAM_COMPARISON:
            similarity_score, difference_regions = self._histogram_comparison(
                baseline_img, comparison_img, config
            )
        else:
            similarity_score, difference_regions = self._pixel_comparison(
                baseline_img, comparison_img, config
            )

        diff_image_path = None
        annotated_image_path = None

        if difference_regions:
            diff_image_path = self._generate_diff_image(baseline_img, comparison_img)
            annotated_image_path = self._generate_annotated_image(comparison_img, difference_regions)

        analysis_time = time.time() - start_time
        is_similar = similarity_score >= config.threshold

        return VisualComparisonResult(
            baseline_path=baseline_path,
            comparison_path=comparison_path,
            similarity_score=round(similarity_score, 4),
            is_similar=is_similar,
            difference_regions=difference_regions,
            diff_image_path=diff_image_path,
            annotated_image_path=annotated_image_path,
            comparison_method=config.method,
            analysis_time=round(analysis_time, 3),
            metadata={
                "baseline_size": baseline_img.size,
                "comparison_size": comparison_img.size,
                "threshold": config.threshold,
            },
        )

    def run_suite(self, suite: RegressionTestSuite) -> RegressionReport:
        """
        Run a regression test suite.

        Args:
            suite: Test suite configuration

        Returns:
            RegressionReport with all results
        """
        results = []
        baseline_dir = Path(suite.baseline_directory)

        config = ComparisonConfig(
            threshold=suite.default_threshold,
            method=suite.comparison_method,
        )

        for test_case in suite.test_cases:
            baseline_path = baseline_dir / f"{test_case.name}.png"
            comparison_path = Path(suite.output_directory) / f"{test_case.name}_current.png"

            if not baseline_path.exists():
                continue

            if comparison_path.exists():
                result = self.compare(
                    str(baseline_path),
                    str(comparison_path),
                    config,
                )
                results.append(result)

        passed = sum(1 for r in results if r.is_similar)
        failed = len(results) - passed
        overall_similarity = sum(r.similarity_score for r in results) / len(results) if results else 0.0
        critical_failures = sum(1 for r in results if not r.is_similar and r.similarity_score < 0.5)

        report = RegressionReport(
            suite_name=suite.name,
            total_comparisons=len(results),
            passed_comparisons=passed,
            failed_comparisons=failed,
            results=results,
            overall_similarity=overall_similarity,
            critical_failures=critical_failures,
        )

        report_path = self._generate_html_report(report)
        report.report_path = str(report_path)

        return report

    def _pixel_comparison(
        self,
        img1: Image,
        img2: Image,
        config: ComparisonConfig
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

    def _ssim_comparison(
        self,
        img1: Image,
        img2: Image,
        config: ComparisonConfig
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
                    # Collect ssim values for pixels in this component
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

    def _phash_comparison(
        self,
        img1: Image,
        img2: Image,
        config: ComparisonConfig
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

    def _histogram_comparison(
        self,
        img1: Image,
        img2: Image,
        config: ComparisonConfig
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

    def _mask_regions(self, image: Image, regions: List[dict]) -> Image:
        """Mask specified regions."""
        masked = image.copy()

        for region in regions:
            x = region.get("x", 0)
            y = region.get("y", 0)
            w = region.get("width", 0)
            h = region.get("height", 0)
            fill_rectangle(masked, x, y, w, h, (128, 128, 128))

        return masked

    def _generate_diff_image(self, img1: Image, img2: Image) -> str:
        """Generate difference visualization."""
        diff = difference(img1, img2)
        diff_enhanced = enhance_contrast(diff, 3.0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        diff_hash = hashlib.md5(f"{timestamp}".encode()).hexdigest()[:8]
        diff_filename = f"diff_{diff_hash}.png"
        diff_path = self.output_directory / "diffs" / diff_filename

        save_image(diff_enhanced, str(diff_path))
        return str(diff_path)

    def _generate_annotated_image(
        self,
        image: Image,
        regions: List[DifferenceRegion]
    ) -> str:
        """Generate annotated image with highlighted regions."""
        annotated = image.copy()

        colors = {
            DifferenceType.ADDITION: "green",
            DifferenceType.REMOVAL: "red",
            DifferenceType.MODIFICATION: "orange",
            DifferenceType.POSITION: "blue",
            DifferenceType.COLOR: "purple",
            DifferenceType.SIZE: "yellow",
            DifferenceType.TEXT: "cyan",
        }

        for region in regions:
            color_name = colors.get(region.difference_type, "red")
            rgb = _COLOR_MAP.get(color_name, (220, 0, 0))

            draw_rectangle(
                annotated,
                region.x, region.y, region.width, region.height,
                rgb,
                line_width=3,
            )
            draw_label(
                annotated,
                region.x, max(0, region.y - 15),
                f"{region.difference_type.value} ({region.confidence:.2f})",
                rgb,
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ann_hash = hashlib.md5(f"{timestamp}".encode()).hexdigest()[:8]
        ann_filename = f"annotated_{ann_hash}.png"
        ann_path = self.output_directory / "diffs" / ann_filename

        save_image(annotated, str(ann_path))
        return str(ann_path)

    def _generate_html_report(self, report: RegressionReport) -> Path:
        """Generate HTML report for regression suite."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Visual Regression Report - {report.suite_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
        .pass {{ color: #4CAF50; }}
        .fail {{ color: #f44336; }}
        .test-case {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .test-pass {{ border-left: 4px solid #4CAF50; }}
        .test-fail {{ border-left: 4px solid #f44336; }}
        .images {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .images img {{ max-width: 300px; height: auto; }}
    </style>
</head>
<body>
    <h1>Visual Regression Report: {report.suite_name}</h1>
    <div class="summary">
        <p><strong>Total:</strong> {report.total_comparisons}</p>
        <p class="pass"><strong>Passed:</strong> {report.passed_comparisons}</p>
        <p class="fail"><strong>Failed:</strong> {report.failed_comparisons}</p>
        <p><strong>Overall Similarity:</strong> {report.overall_similarity:.2%}</p>
        <p><strong>Generated:</strong> {report.report_timestamp}</p>
    </div>
"""

        for result in report.results:
            status_class = "test-pass" if result.is_similar else "test-fail"
            status = "PASS" if result.is_similar else "FAIL"

            html += f"""
    <div class="test-case {status_class}">
        <h3>{Path(result.baseline_path).name} - {status}</h3>
        <p><strong>Similarity:</strong> {result.similarity_score:.2%}</p>
        <p><strong>Method:</strong> {result.comparison_method.value}</p>
        <p><strong>Differences:</strong> {len(result.difference_regions)}</p>
    </div>
"""

        html += """
</body>
</html>
"""

        report_path = self.output_directory / "reports" / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        report_path.write_text(html)

        return report_path
