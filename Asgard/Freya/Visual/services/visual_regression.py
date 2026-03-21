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
from typing import List, Optional

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
    difference,
    load_image,
    resize,
    save_image,
)
from Asgard.Freya.Visual.services._image_ops_draw import (
    draw_label,
    draw_rectangle,
)
from Asgard.Freya.Visual.services._image_ops_transform import enhance_contrast, gaussian_blur
from Asgard.Freya.Visual.services._visual_regression_compare import (
    histogram_comparison,
    mask_regions,
    phash_comparison,
    pixel_comparison,
    ssim_comparison,
)
from Asgard.Freya.Visual.services._visual_regression_report import generate_html_report

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
            baseline_img = mask_regions(baseline_img, config.ignore_regions)
            comparison_img = mask_regions(comparison_img, config.ignore_regions)

        if config.method == ComparisonMethod.STRUCTURAL_SIMILARITY:
            similarity_score, difference_regions = ssim_comparison(baseline_img, comparison_img, config)
        elif config.method == ComparisonMethod.PERCEPTUAL_HASH:
            similarity_score, difference_regions = phash_comparison(baseline_img, comparison_img, config)
        elif config.method == ComparisonMethod.HISTOGRAM_COMPARISON:
            similarity_score, difference_regions = histogram_comparison(baseline_img, comparison_img, config)
        else:
            similarity_score, difference_regions = pixel_comparison(baseline_img, comparison_img, config)

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
        return generate_html_report(report, self.output_directory)
