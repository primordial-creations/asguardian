"""
Unit tests for Apdex governance: error-unified Apdex, per-endpoint rollup,
versioned recalibration, and the bimodality warning (Plan 09).
"""

import pytest

from Asgard.Verdandi.Analysis import ApdexCalculator, ApdexConfig


class TestErrorUnifiedApdex:
    """DEEPTHINK_03 section 4.3: errors are Frustrated regardless of speed."""

    def setup_method(self):
        self.calculator = ApdexCalculator(threshold_ms=500)

    def test_errored_fast_request_counts_frustrated(self):
        """A 20ms request that errored is Frustrated, not Satisfied."""
        times = [20, 100, 200]
        errors = [True, False, False]
        result = self.calculator.calculate_with_errors(times, errors)

        assert result.frustrated_count == 1
        assert result.satisfied_count == 2
        assert result.tolerating_count == 0
        assert result.score == pytest.approx(2 / 3, abs=0.001)

    def test_no_errors_matches_plain_calculate(self):
        times = [100, 200, 600, 800, 2500]
        errors = [False] * 5
        result = self.calculator.calculate_with_errors(times, errors)
        plain = self.calculator.calculate(times)
        assert result.score == plain.score

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            self.calculator.calculate_with_errors([100, 200], [True])

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            self.calculator.calculate_with_errors([], [])

    def test_machine_traffic_excluded(self):
        times = [100, 100, 5000, 5000]
        errors = [False, False, False, False]
        is_human = [True, True, False, False]
        result = self.calculator.calculate_with_errors(
            times, errors, is_human=is_human
        )
        assert result.machine_traffic_excluded == 2
        assert result.total_count == 2
        assert result.score == 1.0


class TestBimodalityWarning:
    """
    DEEPTHINK_03 worked example: Service A (80% @ 50ms / 20% @ 5000ms) and
    Service B (60% @ ~420ms / 40% spread across 510-2000ms) both score 0.80
    Apdex at T=500, but only Service A's distribution is bimodal.
    """

    def setup_method(self):
        self.calculator = ApdexCalculator(threshold_ms=500)

    def test_service_a_bimodal_masks_disaster(self):
        response_times = [50] * 80 + [5000] * 20
        result = self.calculator.calculate(response_times)

        assert result.score == pytest.approx(0.80, abs=0.001)
        assert result.satisfied_count == 80
        assert result.frustrated_count == 20
        assert result.distribution_warning is not None
        assert "BIMODAL" in result.distribution_warning

    def test_service_b_same_score_no_warning(self):
        # 60 satisfied, tightly clustered just under T=500.
        satisfied = [100 + i * (500 - 100) / 59 for i in range(60)]
        # 40 tolerating, spread broadly across the tolerating band (500, 2000].
        tolerating = [510 + i * (2000 - 510) / 39 for i in range(40)]
        response_times = satisfied + tolerating

        result = self.calculator.calculate(response_times)

        assert result.score == pytest.approx(0.80, abs=0.001)
        assert result.satisfied_count == 60
        assert result.tolerating_count == 40
        assert result.frustrated_count == 0
        assert result.distribution_warning is None

    def test_small_sample_insufficient_for_bimodality_guard(self):
        """Below the guard's min_points, no warning is raised either way."""
        result = self.calculator.calculate([100, 200, 5000])
        assert result.distribution_warning is None


class TestMultiEndpointRollup:
    """DEEPTHINK_03: '% of endpoints meeting target' replaces pooled Apdex."""

    def setup_method(self):
        self.calculator = ApdexCalculator(threshold_ms=500)

    def test_rollup_19_green_1_failing(self):
        good = self.calculator.calculate([100] * 20)
        failing = self.calculator.calculate([5000] * 20)

        endpoint_results = {f"ep{i}": good for i in range(19)}
        endpoint_results["checkout"] = failing

        rollup = self.calculator.rollup(endpoint_results, target_score=0.85)

        assert rollup.total_endpoints == 20
        assert rollup.endpoints_meeting_target == 19
        assert rollup.pct_endpoints_meeting_target == pytest.approx(95.0)
        assert rollup.failing_endpoints == ["checkout"]

    def test_rollup_empty_raises(self):
        with pytest.raises(ValueError):
            self.calculator.rollup({}, target_score=0.85)

    def test_pooled_without_force_raises(self):
        with pytest.raises(ValueError):
            self.calculator.calculate_pooled(
                {"a": [100, 200], "b": [5000, 5000]}
            )

    def test_pooled_with_force_succeeds(self):
        result = self.calculator.calculate_pooled(
            {"a": [100, 200], "b": [5000, 5000]}, force=True
        )
        assert result.total_count == 4


class TestVersionedRecalibration:
    def test_config_stamps_version_and_endpoint(self):
        calculator = ApdexCalculator(threshold_ms=500)
        config = ApdexConfig(threshold_ms=1500, version="v2", endpoint="/checkout")
        result = calculator.calculate([100, 200, 300], config=config)

        assert result.version == "v2"
        assert result.endpoint == "/checkout"

    def test_recalibrate_emits_shadow_checklist(self):
        record = ApdexCalculator.recalibrate(
            old_version="v1",
            new_version="v2",
            old_threshold_ms=500,
            new_threshold_ms=1500,
            shadow_period_days=30,
            endpoint="/checkout",
        )
        assert record.shadow_sufficient is True
        assert any("30" in item for item in record.checklist)
        assert any("quarter" in item.lower() for item in record.checklist)

    def test_recalibrate_short_shadow_warns(self):
        record = ApdexCalculator.recalibrate(
            old_version="v1",
            new_version="v2",
            old_threshold_ms=500,
            new_threshold_ms=600,
            shadow_period_days=5,
        )
        assert record.shadow_sufficient is False
        assert any("WARNING" in item for item in record.checklist)
