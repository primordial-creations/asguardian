"""
Tests for scenario-routed small-batch detectors (Plan 03D).

Encodes the DEEPTHINK_02 worked scenarios: step changes via split-window
MAD/CUSUM, gradual drift via global OLS (boiling-frog fix), the bimodality
guard, method routing, and sensitivity profiles.
"""

import random

import pytest

from Asgard.Verdandi.Anomaly import (
    DetectionOutcome,
    MetricClass,
    SensitivityProfile,
    StatisticalDetector,
)


@pytest.fixture
def detector():
    return StatisticalDetector()


class TestSplitWindowMad:
    def test_detects_step_at_correct_index_in_500_point_batch(self, detector):
        random.seed(7)
        values = [50 + random.gauss(0, 2) for _ in range(400)]
        values += [200 + random.gauss(0, 2) for _ in range(100)]

        result = detector.detect_step_change(values)

        assert result.detected is True
        assert result.method == "split_window_mad"
        assert 395 <= result.change_index <= 405
        assert 140 <= result.magnitude <= 160
        assert result.mad_units > 3

    def test_no_detection_on_flat_noise(self, detector):
        random.seed(3)
        values = [50 + random.gauss(0, 2) for _ in range(200)]

        result = detector.detect_step_change(values)

        assert result.detected is False

    def test_insufficient_data_outcome(self, detector):
        result = detector.detect_step_change([1.0, 2.0, 3.0])

        assert result.outcome == DetectionOutcome.INSUFFICIENT_DATA
        assert result.detected is False


class TestCusum:
    def test_detects_step_change(self, detector):
        random.seed(11)
        values = [50 + random.gauss(0, 1) for _ in range(100)]
        values += [80 + random.gauss(0, 1) for _ in range(50)]

        result = detector.detect_step_change(values, method="cusum")

        assert result.detected is True
        assert result.method == "cusum"
        # CUSUM alarms shortly after the true change at index 100
        assert 100 <= result.cusum_alarm_index <= 110

    def test_no_alarm_on_stable_series(self, detector):
        random.seed(5)
        values = [50 + random.gauss(0, 1) for _ in range(120)]

        result = detector.detect_step_change(values, method="cusum")

        assert result.detected is False

    def test_insufficient_data(self, detector):
        result = detector.detect_step_change([1.0] * 5, method="cusum")

        assert result.outcome == DetectionOutcome.INSUFFICIENT_DATA


class TestOlsDrift:
    def test_detects_slow_drift_that_rolling_zscore_misses(self, detector):
        # +0.1 ms/pt boiling-frog ramp: never a spike, always a trend.
        random.seed(2)
        values = [100 + 0.1 * i + random.gauss(0, 1) for i in range(200)]

        drift = detector.detect_drift(values)
        zscore_anomalies = detector.detect_zscore(values)

        assert drift.detected is True
        assert drift.slope == pytest.approx(0.1, abs=0.02)
        assert drift.slope_p_value < 0.05
        # The global z-score sees at most tail points, not the ramp itself
        assert len(zscore_anomalies) < len(values) * 0.05

    def test_no_drift_on_flat_series(self, detector):
        random.seed(9)
        values = [100 + random.gauss(0, 1) for _ in range(100)]

        result = detector.detect_drift(values)

        assert result.detected is False

    def test_insufficient_data(self, detector):
        assert (
            detector.detect_drift([1.0] * 5).outcome
            == DetectionOutcome.INSUFFICIENT_DATA
        )

    def test_practical_gate_blocks_tiny_relative_drift(self, detector):
        # Statistically real but practically negligible drift
        values = [1000 + 0.001 * i for i in range(100)]

        result = detector.detect_drift(values, min_relative_drift=0.05)

        assert result.detected is False
        assert result.slope_p_value < 0.05  # significance alone was there


class TestBimodalityGuard:
    def test_flags_bimodal_mixture_with_per_mode_stats(self, detector):
        random.seed(4)
        low = [20 + random.gauss(0, 3) for _ in range(120)]
        high = [120 + random.gauss(0, 3.5) for _ in range(80)]

        result = detector.check_bimodality(low + high)

        assert result.is_bimodal is True
        assert result.outcome == DetectionOutcome.BIMODAL_DISTRIBUTION
        assert len(result.modes) == 2
        assert result.modes[0].median < result.modes[1].median
        assert result.modes[0].median == pytest.approx(20, abs=3)
        assert result.modes[1].median == pytest.approx(120, abs=4)
        assert result.valley_ratio < 0.5

    def test_unimodal_passes(self, detector):
        random.seed(6)
        values = [50 + random.gauss(0, 5) for _ in range(200)]

        result = detector.check_bimodality(values)

        assert result.is_bimodal is False

    def test_insufficient_data(self, detector):
        result = detector.check_bimodality([1.0] * 10)

        assert result.outcome == DetectionOutcome.INSUFFICIENT_DATA


class TestMethodRouter:
    def test_small_n_avoids_distributional_ml(self, detector):
        rec = detector.recommend_method(n=80)

        assert "distributional_ml" in rec.avoid_methods
        assert "bimodality_guard" in rec.recommended_methods

    def test_seasonal_needs_three_cycles(self, detector):
        starved = detector.recommend_method(n=300, cycles_observed=1.5)
        ready = detector.recommend_method(n=300, cycles_observed=4)

        assert "seasonal_decomposition" in starved.avoid_methods
        assert "seasonal_decomposition" in ready.recommended_methods

    def test_deployment_marker_suspends_historical_baseline(self, detector):
        rec = detector.recommend_method(n=200, deployment_marker=True)

        assert "historical_baseline" in rec.avoid_methods

    def test_scenario_routing(self, detector):
        step = detector.recommend_method(n=100, suspected_scenario="step_change")
        drift = detector.recommend_method(n=100, suspected_scenario="gradual_drift")

        assert "cusum" in step.recommended_methods
        assert "ols_drift" in drift.recommended_methods
        assert "rolling_zscore" in drift.avoid_methods


class TestSensitivityProfiles:
    def test_latency_profile_is_specificity_biased(self):
        profile = SensitivityProfile.latency()

        assert profile.bias == "specificity"
        assert profile.effect_gated is True
        assert profile.z_threshold > 3.0

    def test_error_rate_profile_gates_on_absolute_volume(self):
        profile = SensitivityProfile.error_rate()

        assert profile.bias == "sensitivity"
        assert profile.min_absolute_events == 50

    def test_cache_profile_routes_to_trajectory(self):
        profile = SensitivityProfile.cache_hit_rate()

        assert profile.trajectory_based is True

    def test_detector_accepts_profile(self):
        profile = SensitivityProfile.for_metric_class(MetricClass.LATENCY)
        detector = StatisticalDetector(profile=profile)

        assert detector.z_threshold == profile.z_threshold
        assert detector.min_sample_size == profile.min_sample_size
