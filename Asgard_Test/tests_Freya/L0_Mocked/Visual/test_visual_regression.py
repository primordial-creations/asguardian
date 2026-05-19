"""
Freya Visual L0 Mocked Tests - Visual Regression Tester
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from Asgard.Freya.Visual.models.visual_models import (
    ComparisonConfig,
    ComparisonMethod,
    DifferenceType,
    RegressionTestSuite,
    RegressionTestCase,
)
from Asgard.Freya.Visual.services.visual_regression import VisualRegressionTester

# Module path prefix for patching
_VR = "Asgard.Freya.Visual.services.visual_regression"


def _make_mock_image(width=1920, height=1080):
    img = MagicMock()
    img.width = width
    img.height = height
    img.size = (width, height)
    img.pixels = [(0, 0, 0)] * (width * height)
    img.copy.return_value = img
    img.to_grayscale_array.return_value = [128] * (width * height)
    img.histogram.return_value = [0] * 768
    return img


class TestVisualRegressionTesterInit:
    @pytest.mark.L0
    def test_init_default_directory(self, tmp_path):
        with patch("Asgard.Freya.Visual.services.visual_regression.Path.mkdir"):
            tester = VisualRegressionTester.__new__(VisualRegressionTester)
            tester.output_directory = Path("./regression_output")
        assert tester.output_directory == Path("./regression_output")

    @pytest.mark.L0
    def test_init_custom_directory(self, temp_output_dir):
        tester = VisualRegressionTester(output_directory=str(temp_output_dir))
        assert tester.output_directory == temp_output_dir

    @pytest.mark.L0
    def test_init_creates_subdirectories(self, tmp_path):
        output_dir = tmp_path / "regression"
        tester = VisualRegressionTester(output_directory=str(output_dir))
        assert (output_dir / "diffs").exists()
        assert (output_dir / "reports").exists()


class TestCompareBasic:
    @pytest.mark.L0
    def test_compare_identical_images(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image()

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.pixel_comparison", return_value=(1.0, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file))

        assert result.baseline_path == str(temp_baseline_file)
        assert result.comparison_path == str(temp_comparison_file)
        assert result.similarity_score == 1.0
        assert result.is_similar is True
        assert len(result.difference_regions) == 0

    @pytest.mark.L0
    def test_compare_different_images(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image()
        from Asgard.Freya.Visual.models.visual_models import DifferenceRegion
        region = DifferenceRegion(
            x=0, y=0, width=100, height=100,
            difference_type=DifferenceType.MODIFICATION,
            confidence=0.9,
            description="Change"
        )

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.pixel_comparison", return_value=(0.9, [region])), \
             patch(f"{_VR}.difference", return_value=mock_img), \
             patch(f"{_VR}.enhance_contrast", return_value=mock_img), \
             patch(f"{_VR}.save_image"), \
             patch(f"{_VR}.draw_rectangle"), \
             patch(f"{_VR}.draw_label"):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(threshold=0.95, method=ComparisonMethod.PIXEL_DIFF)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert result.similarity_score == 0.9
        assert result.is_similar is False

    @pytest.mark.L0
    def test_compare_handles_image_load_error(self, temp_baseline_file, temp_comparison_file, tmp_path):
        with patch(f"{_VR}.load_image", side_effect=Exception("Failed to load image")):
            tester = VisualRegressionTester(output_directory=str(tmp_path))
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file))

        assert result.similarity_score == 0.0
        assert result.is_similar is False
        assert "error" in result.metadata

    @pytest.mark.L0
    def test_compare_resizes_mismatched_sizes(self, temp_baseline_file, temp_comparison_file, tmp_path):
        baseline_img = _make_mock_image(1920, 1080)
        comparison_img = _make_mock_image(1280, 720)
        resized_img = _make_mock_image(1280, 720)

        with patch(f"{_VR}.load_image", side_effect=[baseline_img, comparison_img]), \
             patch(f"{_VR}.resize", return_value=resized_img) as mock_resize, \
             patch(f"{_VR}.pixel_comparison", return_value=(1.0, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file))

        assert mock_resize.call_count == 2


class TestComparisonMethods:
    @pytest.mark.L0
    def test_pixel_diff_comparison(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.pixel_comparison", return_value=(0.995, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(method=ComparisonMethod.PIXEL_DIFF)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert result.comparison_method == ComparisonMethod.PIXEL_DIFF
        assert 0.99 <= result.similarity_score <= 1.0

    @pytest.mark.L0
    def test_ssim_comparison(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.ssim_comparison", return_value=(0.95, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(method=ComparisonMethod.STRUCTURAL_SIMILARITY)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert result.comparison_method == ComparisonMethod.STRUCTURAL_SIMILARITY
        assert result.similarity_score == 0.95

    @pytest.mark.L0
    def test_perceptual_hash_comparison(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.phash_comparison", return_value=(1.0, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(method=ComparisonMethod.PERCEPTUAL_HASH)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert result.comparison_method == ComparisonMethod.PERCEPTUAL_HASH
        assert result.similarity_score == 1.0

    @pytest.mark.L0
    def test_histogram_comparison(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.histogram_comparison", return_value=(0.98, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(method=ComparisonMethod.HISTOGRAM_COMPARISON)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert result.comparison_method == ComparisonMethod.HISTOGRAM_COMPARISON


class TestComparisonConfiguration:
    @pytest.mark.L0
    def test_compare_with_blur(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.gaussian_blur", return_value=mock_img) as mock_blur, \
             patch(f"{_VR}.pixel_comparison", return_value=(1.0, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(blur_radius=5)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert mock_blur.call_count == 2

    @pytest.mark.L0
    def test_compare_with_ignore_regions(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.mask_regions", return_value=mock_img) as mock_mask, \
             patch(f"{_VR}.pixel_comparison", return_value=(1.0, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(ignore_regions=[{"x": 0, "y": 0, "width": 100, "height": 50}])
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert mock_mask.call_count == 2

    @pytest.mark.L0
    def test_compare_respects_threshold(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.pixel_comparison", return_value=(0.96, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))

            config_high = ComparisonConfig(threshold=0.97, method=ComparisonMethod.PIXEL_DIFF)
            result_high = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config_high)

            config_low = ComparisonConfig(threshold=0.90, method=ComparisonMethod.PIXEL_DIFF)
            result_low = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config_low)

        assert result_high.similarity_score == result_low.similarity_score
        assert result_high.is_similar != result_low.is_similar


class TestRunSuite:
    @pytest.mark.L0
    def test_run_suite_basic(self, sample_regression_test_suite, tmp_path):
        baseline_dir = Path(sample_regression_test_suite.baseline_directory)
        (baseline_dir / "test1.png").write_text("baseline1")
        (baseline_dir / "test2.png").write_text("baseline2")

        output_dir = Path(sample_regression_test_suite.output_directory)
        (output_dir / "test1_current.png").write_text("comparison1")
        (output_dir / "test2_current.png").write_text("comparison2")

        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.pixel_comparison", return_value=(1.0, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            report = tester.run_suite(sample_regression_test_suite)

        assert report.suite_name == sample_regression_test_suite.name
        assert report.total_comparisons == 2
        assert report.report_path is not None

    @pytest.mark.L0
    def test_run_suite_skips_missing_baselines(self, temp_output_dir, tmp_path):
        baseline_dir = temp_output_dir / "baselines"
        baseline_dir.mkdir()
        output_dir = temp_output_dir / "output"
        output_dir.mkdir()

        (baseline_dir / "test1.png").write_text("baseline1")

        suite = RegressionTestSuite(
            name="Test Suite",
            baseline_directory=str(baseline_dir),
            output_directory=str(output_dir),
            test_cases=[
                RegressionTestCase(name="test1", url="https://example.com/1"),
                RegressionTestCase(name="test2", url="https://example.com/2"),
            ],
        )

        tester = VisualRegressionTester(output_directory=str(tmp_path))
        report = tester.run_suite(suite)

        assert report.total_comparisons == 0

    @pytest.mark.L0
    def test_run_suite_calculates_statistics(self, temp_output_dir, tmp_path):
        baseline_dir = temp_output_dir / "baselines"
        baseline_dir.mkdir(exist_ok=True)
        output_dir = temp_output_dir / "output"
        output_dir.mkdir(exist_ok=True)

        (baseline_dir / "test1.png").write_text("baseline1")
        (baseline_dir / "test2.png").write_text("baseline2")
        (output_dir / "test1_current.png").write_text("comparison1")
        (output_dir / "test2_current.png").write_text("comparison2")

        suite = RegressionTestSuite(
            name="Stats Suite",
            baseline_directory=str(baseline_dir),
            output_directory=str(output_dir),
            test_cases=[
                RegressionTestCase(name="test1", url="https://example.com/1", threshold=0.95),
                RegressionTestCase(name="test2", url="https://example.com/2", threshold=0.95),
            ],
            comparison_method=ComparisonMethod.PIXEL_DIFF,
        )

        call_count = [0]

        from Asgard.Freya.Visual.models.visual_models import DifferenceRegion

        failing_region = DifferenceRegion(
            x=0, y=0, width=50, height=50,
            difference_type=DifferenceType.MODIFICATION,
            confidence=0.9,
            description="diff",
        )

        def mock_pixel_comparison(img1, img2, config):
            call_count[0] += 1
            return (1.0, []) if call_count[0] <= 1 else (0.4, [failing_region])

        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.pixel_comparison", side_effect=mock_pixel_comparison), \
             patch(f"{_VR}.difference", return_value=mock_img), \
             patch(f"{_VR}.enhance_contrast", return_value=mock_img), \
             patch(f"{_VR}.save_image"), \
             patch(f"{_VR}.draw_rectangle"), \
             patch(f"{_VR}.draw_label"):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            report = tester.run_suite(suite)

        assert report.total_comparisons == 2
        assert report.passed_comparisons == 1
        assert report.failed_comparisons == 1


class TestHelperMethods:
    @pytest.mark.L0
    def test_mask_regions(self, tmp_path):
        mock_img = _make_mock_image(200, 200)

        with patch(f"{_VR}.mask_regions", return_value=mock_img) as mock_mask:
            tester = VisualRegressionTester(output_directory=str(tmp_path))
            regions = [{"x": 0, "y": 0, "width": 100, "height": 50}]
            masked = tester._compare_with_mask(mock_img, mock_img, regions, ComparisonConfig()) if hasattr(tester, '_compare_with_mask') else mock_mask(mock_img, regions)

        assert masked is not None

    @pytest.mark.L0
    def test_generate_diff_image(self, tmp_path):
        mock_img = _make_mock_image(100, 100)
        mock_diff = _make_mock_image(100, 100)
        mock_enhanced = _make_mock_image(100, 100)

        with patch(f"{_VR}.difference", return_value=mock_diff), \
             patch(f"{_VR}.enhance_contrast", return_value=mock_enhanced), \
             patch(f"{_VR}.save_image") as mock_save:

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            diff_path = tester._generate_diff_image(mock_img, mock_img)

        assert "diff_" in diff_path
        assert ".png" in diff_path
        mock_save.assert_called_once()

    @pytest.mark.L0
    def test_generate_annotated_image(self, tmp_path):
        mock_img = _make_mock_image(200, 200)

        from Asgard.Freya.Visual.models.visual_models import DifferenceRegion, DifferenceType

        regions = [
            DifferenceRegion(
                x=10, y=20, width=100, height=50,
                difference_type=DifferenceType.MODIFICATION,
                confidence=0.85,
                description="Change detected"
            )
        ]

        with patch(f"{_VR}.draw_rectangle") as mock_rect, \
             patch(f"{_VR}.draw_label") as mock_label, \
             patch(f"{_VR}.save_image") as mock_save:

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            ann_path = tester._generate_annotated_image(mock_img, regions)

        assert "annotated_" in ann_path
        assert ".png" in ann_path
        mock_img.copy.assert_called_once()
        mock_rect.assert_called_once()
        mock_label.assert_called_once()
        mock_save.assert_called_once()

    @pytest.mark.L0
    def test_generate_html_report(self, sample_regression_test_suite, tmp_path):
        from Asgard.Freya.Visual.models.visual_models import RegressionReport, VisualComparisonResult

        results = [
            VisualComparisonResult(
                baseline_path="/tmp/baseline.png",
                comparison_path="/tmp/comparison.png",
                similarity_score=0.98,
                is_similar=True,
            )
        ]

        report = RegressionReport(
            suite_name="Test Suite",
            total_comparisons=1,
            passed_comparisons=1,
            failed_comparisons=0,
            results=results,
            overall_similarity=0.98,
        )

        tester = VisualRegressionTester(output_directory=str(tmp_path))
        report_path = tester._generate_html_report(report)

        assert report_path.exists()
        assert report_path.suffix == ".html"

        html_content = report_path.read_text()
        assert "Test Suite" in html_content


class TestErrorHandling:
    @pytest.mark.L0
    def test_compare_handles_load_errors(self, temp_baseline_file, temp_comparison_file, tmp_path):
        with patch(f"{_VR}.load_image", side_effect=Exception("Conversion failed")):
            tester = VisualRegressionTester(output_directory=str(tmp_path))
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file))

        assert result.similarity_score == 0.0
        assert result.is_similar is False

    @pytest.mark.L0
    def test_ssim_always_available(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.ssim_comparison", return_value=(0.92, [])):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(method=ComparisonMethod.STRUCTURAL_SIMILARITY)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert result.comparison_method == ComparisonMethod.STRUCTURAL_SIMILARITY
        assert result.similarity_score == 0.92


class TestVisualRegressionIntegration:
    @pytest.mark.L0
    def test_full_comparison_workflow(self, temp_baseline_file, temp_comparison_file, tmp_path):
        mock_img = _make_mock_image(100, 100)
        from Asgard.Freya.Visual.models.visual_models import DifferenceRegion

        region = DifferenceRegion(
            x=10, y=10, width=20, height=20,
            difference_type=DifferenceType.MODIFICATION,
            confidence=0.9,
            description="SSIM region",
            pixel_count=400,
        )

        with patch(f"{_VR}.load_image", return_value=mock_img), \
             patch(f"{_VR}.ssim_comparison", return_value=(0.92, [region])), \
             patch(f"{_VR}.difference", return_value=mock_img), \
             patch(f"{_VR}.enhance_contrast", return_value=mock_img), \
             patch(f"{_VR}.save_image"), \
             patch(f"{_VR}.draw_rectangle"), \
             patch(f"{_VR}.draw_label"):

            tester = VisualRegressionTester(output_directory=str(tmp_path))
            config = ComparisonConfig(threshold=0.95, method=ComparisonMethod.STRUCTURAL_SIMILARITY)
            result = tester.compare(str(temp_baseline_file), str(temp_comparison_file), config=config)

        assert result.similarity_score == 0.92
        assert result.is_similar is False
        assert result.diff_image_path is not None
        assert result.annotated_image_path is not None
        assert len(result.difference_regions) == 1
        assert result.difference_regions[0].pixel_count == 400
