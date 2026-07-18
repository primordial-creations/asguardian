"""Tests for the Plan 05 local percentile calibrator."""

from Asgard.Bragi.Calibration.models.calibration_models import LanguageProfile, ThresholdSpec
from Asgard.Bragi.Calibration.services.local_calibrator import (
    MIN_SAMPLE_SIZE,
    calibrate,
    percentile,
    write_local_profile,
)


class TestPercentile:
    def test_p95_of_known_distribution(self):
        samples = list(range(1, 101))  # 1..100
        assert percentile(samples, 95) == 95

    def test_p50_median(self):
        samples = [1, 2, 3, 4, 5]
        assert percentile(samples, 50) == 3

    def test_empty_samples(self):
        assert percentile([], 95) == 0.0


class TestCalibrate:
    ANCHOR = LanguageProfile(
        language="python",
        thresholds={"cyclomatic_complexity": ThresholdSpec(warn=10, fail=20)},
    )

    def test_refuses_below_minimum_sample(self):
        samples = {"cyclomatic_complexity": [float(i) for i in range(10)]}
        profile, run = calibrate("python", samples, self.ANCHOR)
        assert profile is None
        assert run.refused is True
        assert "insufficient sample" in run.refusal_reason

    def test_accepts_sufficient_sample_and_derives_p95(self):
        samples = {"cyclomatic_complexity": [float(i) for i in range(1, MIN_SAMPLE_SIZE + 1)]}
        profile, run = calibrate("python", samples, self.ANCHOR)
        assert profile is not None
        assert run.refused is False
        assert run.sample_size == MIN_SAMPLE_SIZE
        assert "local P95" in profile.provenance

    def test_clamp_engages_for_pathological_codebase(self):
        # Every function has CC=40, far beyond anchor fail=20; clamp must
        # cap the local threshold at 20 * 1.5 = 30 (not let it normalize
        # to 40 and silently declare the codebase clean).
        samples = {"cyclomatic_complexity": [40.0] * MIN_SAMPLE_SIZE}
        profile, run = calibrate("python", samples, self.ANCHOR)
        assert profile is not None
        assert "cyclomatic_complexity" in run.clamped_metrics
        assert profile.thresholds["cyclomatic_complexity"].fail <= 20 * 1.5 + 1e-9

    def test_determinism_same_input_same_output(self):
        samples = {"cyclomatic_complexity": [float(i % 30) for i in range(MIN_SAMPLE_SIZE)]}
        p1, _ = calibrate("python", samples, self.ANCHOR)
        p2, _ = calibrate("python", samples, self.ANCHOR)
        assert p1.model_dump() == p2.model_dump()


class TestWriteLocalProfile:
    def test_writes_to_asgard_cache(self, tmp_path):
        samples = {"cyclomatic_complexity": [float(i) for i in range(1, MIN_SAMPLE_SIZE + 1)]}
        profile, _ = calibrate("python", samples, TestCalibrate.ANCHOR)
        out_path = write_local_profile(profile, project_path=tmp_path)
        assert out_path.exists()
        assert out_path.name == "bragi_local_profile.yaml"
        assert out_path.parent.name == ".asgard_cache"
