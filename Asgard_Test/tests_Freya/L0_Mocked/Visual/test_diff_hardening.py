"""L0 tests: AA tolerance, region clustering/merging, tripwire framing (Plan 04)."""

from Asgard.Freya.Visual.models.visual_models import (
    ComparisonConfig,
    DifferenceRegion,
    DifferenceType,
)
from Asgard.Freya.Visual.services.image_ops import Image
from Asgard.Freya.Visual.services._visual_regression_compare import (
    apply_antialiasing_filter,
    merge_overlapping_regions,
    pixel_comparison,
)


def _image(width, height, color=(255, 255, 255)):
    return Image(width, height, [color] * (width * height))


def _region(x, y, w, h, pixels=100):
    return DifferenceRegion(
        x=x, y=y, width=w, height=h,
        difference_type=DifferenceType.MODIFICATION,
        confidence=0.8, description="d", pixel_count=pixels,
    )


class TestAntialiasingFilter:
    def test_edge_shift_pixel_filtered(self):
        # Baseline: black left half, white right half; comparison: the
        # boundary column flips — its new color exists in the baseline
        # 8-neighborhood, so it is anti-aliasing, not a change.
        baseline = _image(5, 5)
        comparison = _image(5, 5)
        for y in range(5):
            for x in range(3):
                baseline.set_pixel(x, y, (0, 0, 0))
            for x in range(2):
                comparison.set_pixel(x, y, (0, 0, 0))
        binary = [0] * 25
        for y in range(5):
            binary[y * 5 + 2] = 1  # boundary column differs
        filtered = apply_antialiasing_filter(baseline, comparison, binary, 10)
        assert sum(filtered) == 0

    def test_true_change_not_filtered(self):
        # Isolated red block on white: red exists nowhere in baseline.
        baseline = _image(5, 5)
        comparison = _image(5, 5)
        comparison.set_pixel(2, 2, (255, 0, 0))
        binary = [0] * 25
        binary[2 * 5 + 2] = 1
        filtered = apply_antialiasing_filter(baseline, comparison, binary, 10)
        assert sum(filtered) == 1

    def test_pixel_comparison_respects_flag(self):
        baseline = _image(5, 5)
        comparison = _image(5, 5)
        for y in range(5):
            for x in range(3):
                baseline.set_pixel(x, y, (0, 0, 0))
            for x in range(2):
                comparison.set_pixel(x, y, (0, 0, 0))
        score_aa, _ = pixel_comparison(
            baseline, comparison, ComparisonConfig(ignore_antialiasing=True))
        score_raw, _ = pixel_comparison(
            baseline, comparison, ComparisonConfig(ignore_antialiasing=False))
        assert score_aa == 1.0
        assert score_raw < 1.0


class TestMergeRegions:
    def test_two_separate_blobs_stay_separate(self):
        merged = merge_overlapping_regions(
            [_region(0, 0, 10, 10), _region(50, 50, 10, 10)])
        assert len(merged) == 2

    def test_overlapping_blobs_merge(self):
        merged = merge_overlapping_regions(
            [_region(0, 0, 10, 10, 100), _region(5, 5, 10, 10, 50)])
        assert len(merged) == 1
        assert merged[0].width == 15 and merged[0].height == 15
        assert merged[0].pixel_count == 150

    def test_cap_folds_overflow(self):
        regions = [_region(i * 20, 0, 5, 5, 10) for i in range(60)]
        merged = merge_overlapping_regions(regions, max_regions=50)
        assert len(merged) == 50
        assert "folded in" in merged[-1].description
        assert sum(r.pixel_count for r in merged) == 600


class TestFraming:
    def test_comparison_result_framing_optional(self):
        from Asgard.Freya.Visual.models.visual_models import VisualComparisonResult
        result = VisualComparisonResult(
            baseline_path="a", comparison_path="b",
            similarity_score=1.0, is_similar=True)
        assert result.framing is None

    def test_tester_populates_tripwire_framing(self, tmp_path):
        from Asgard.Freya.Visual.services.image_ops import save_image
        from Asgard.Freya.Visual.services.visual_regression import VisualRegressionTester
        img = _image(10, 10)
        base_path = str(tmp_path / "base.png")
        curr_path = str(tmp_path / "curr.png")
        save_image(img, base_path)
        save_image(img, curr_path)
        tester = VisualRegressionTester(output_directory=str(tmp_path / "out"))
        result = tester.compare(base_path, curr_path)
        assert result.framing is not None
        assert "Structural tripwire" in result.framing
        assert "aesthetic judgment" in result.framing
