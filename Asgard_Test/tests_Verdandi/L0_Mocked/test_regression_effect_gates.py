"""
L0 tests for effect-size gated regression verdicts (RESEARCH_15).

Welch's t alone saturates at production sample sizes; the three-gate
verdict requires statistical (p), practical (Hodges-Lehmann shift), and
magnitude (Glass's delta) significance simultaneously.
"""

import math

import pytest

from Asgard.Verdandi.Anomaly.services._regression_statistics import (
    glass_delta,
    hodges_lehmann,
    mann_whitney_u,
    pseudo_median,
)
from Asgard.Verdandi.Anomaly.services.regression_detector import RegressionDetector


class TestHodgesLehmann:
    def test_exact_shift(self):
        """Worked example from the plan: shift of exactly 10."""
        assert hodges_lehmann([1, 2, 3], [11, 12, 13]) == 10

    def test_robust_to_extreme_outlier(self):
        """A 10^6 outlier in the candidate barely moves the estimate."""
        shifted = hodges_lehmann([1, 2, 3], [11, 12, 13, 1_000_000])
        assert 9 <= shifted <= 13

    def test_no_shift_is_zero(self):
        assert hodges_lehmann([5, 6, 7], [5, 6, 7]) == 0

    def test_negative_shift(self):
        assert hodges_lehmann([11, 12, 13], [1, 2, 3]) == -10

    def test_empty_inputs(self):
        assert hodges_lehmann([], [1, 2]) == 0.0
        assert hodges_lehmann([1, 2], []) == 0.0

    def test_identical_large_inputs_give_exactly_zero(self):
        """Regression: paired subsampling (same seed both sides) must make
        HL(x, x) exactly 0 above the subsample cap, not ~1.6 on lognormal."""
        import random

        rng = random.Random(7)
        samples = [rng.lognormvariate(3, 1) for _ in range(5000)]
        assert hodges_lehmann(samples, list(samples)) == 0.0

    def test_large_inputs_are_subsampled_deterministically(self):
        base = [float(i % 50) for i in range(10_000)]
        cand = [v + 20 for v in base]
        first = hodges_lehmann(base, cand)
        second = hodges_lehmann(base, cand)
        assert first == second
        assert first == pytest.approx(20, abs=1.0)


class TestGlassDelta:
    def test_baseline_sigma_standardization(self):
        # mean shift 10, baseline std 2 -> delta = 5
        assert glass_delta(100.0, 2.0, 110.0) == pytest.approx(5.0)

    def test_zero_baseline_std(self):
        assert glass_delta(100.0, 0.0, 100.0) == 0.0
        assert glass_delta(100.0, 0.0, 110.0) == math.inf
        assert glass_delta(100.0, 0.0, 90.0) == -math.inf

    def test_variance_inflating_canary_does_not_dilute_effect(self):
        """Glass's delta ignores candidate variance entirely (its purpose)."""
        assert glass_delta(100.0, 5.0, 120.0) == pytest.approx(4.0)


class TestPseudoMedian:
    def test_symmetric_data(self):
        assert pseudo_median([1, 2, 3]) == 2

    def test_empty(self):
        assert pseudo_median([]) == 0.0


class TestMannWhitney:
    def test_clear_separation_is_significant(self):
        base = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
        cand = [11.0, 12.0, 13.0, 14.0, 15.0] * 10
        _, p = mann_whitney_u(base, cand)
        assert p < 0.001

    def test_identical_distributions_not_significant(self):
        vals = [float(i % 10) for i in range(100)]
        _, p = mann_whitney_u(vals, list(vals))
        assert p > 0.5


class TestThreeGateVerdict:
    def test_saturated_p_value_without_effect_is_not_a_regression(self):
        """The RESEARCH_15 saturation case: huge n, tiny (0.3 unit / 0.3%)
        shift -> p ~ 0 but the verdict must be False."""
        detector = RegressionDetector()
        base = [100 + ((i * 7) % 13) * 0.1 for i in range(5000)]
        cand = [x + 0.3 for x in base]
        result = detector.detect(base, cand, "latency_ms")
        assert result.p_value < 0.05  # statistically "significant"...
        assert not result.is_regression  # ...but practically irrelevant
        assert "three_gate" in result.verdict_basis

    def test_real_regression_passes_all_three_gates(self):
        detector = RegressionDetector()
        base = [100 + (i % 10) for i in range(200)]
        cand = [150 + (i % 10) for i in range(200)]
        result = detector.detect(base, cand, "latency_ms")
        assert result.is_regression
        assert result.hl_shift == pytest.approx(50.0)
        assert result.glass_delta > 0.5
        assert result.hl_shift_relative > 0.05

    def test_improvement_is_never_a_regression(self):
        detector = RegressionDetector()
        base = [150 + (i % 10) for i in range(200)]
        cand = [100 + (i % 10) for i in range(200)]
        result = detector.detect(base, cand)
        assert not result.is_regression
        assert result.hl_shift == pytest.approx(-50.0)

    def test_result_carries_effect_size_fields(self):
        detector = RegressionDetector()
        base = [100.0, 101.0, 102.0, 103.0] * 20
        cand = [120.0, 121.0, 122.0, 123.0] * 20
        result = detector.detect(base, cand)
        assert result.hl_shift is not None
        assert result.hl_shift_relative is not None
        assert result.glass_delta is not None
        assert result.verdict_basis is not None

    def test_insufficient_data_is_typed_not_junk(self):
        detector = RegressionDetector()
        result = detector.detect([], [1.0, 2.0])
        assert not result.is_regression
        assert result.verdict_basis == "insufficient_data"

    def test_legacy_mode_retains_old_semantics(self):
        detector = RegressionDetector(verdict_mode=RegressionDetector.VERDICT_LEGACY)
        base = [100 + (i % 10) for i in range(200)]
        cand = [150 + (i % 10) for i in range(200)]
        result = detector.detect(base, cand)
        assert result.is_regression
        assert result.verdict_basis.startswith("legacy")

    def test_nonpositive_baseline_relative_shift_is_none_not_zero(self):
        """Regression: with a non-positive baseline pseudo-median the
        relative gate is undefined (None), the absolute gate still applies,
        and the verdict basis says so."""
        detector = RegressionDetector()
        base = [0.0] * 50
        cand = [20.0 + (i % 3) for i in range(50)]
        result = detector.detect(base, cand)
        assert result.hl_shift_relative is None
        assert result.hl_shift > 10
        assert result.is_regression  # absolute gate alone carries it
        assert "undefined" in result.verdict_basis

    def test_cli_threshold_maps_to_relative_shift_gate(self):
        """Regression: the CLI --threshold percent must gate the verdict
        (mapped onto hl_relative_threshold), not be silently ignored."""
        import argparse
        import contextlib
        import io

        from Asgard.Verdandi.cli.handlers_anomaly_trend import run_regression_check

        # ~20% relative shift, well under the 10-unit absolute gate:
        # threshold 50% must suppress the verdict, threshold 10% must flag it.
        # Keep strings short: load_json_or_parse stats them as paths first.
        before = ",".join(str(round(1.0 + (i % 4) * 0.01, 2)) for i in range(40))
        after = ",".join(str(round(1.2 + (i % 4) * 0.01, 2)) for i in range(40))

        def run(threshold):
            args = argparse.Namespace(before=before, after=after, threshold=threshold)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                exit_code = run_regression_check(args, "json")
            return exit_code, out.getvalue()

        _, output_strict = run(50.0)
        assert '"is_regression": false' in output_strict.lower()
        _, output_lenient = run(10.0)
        assert '"is_regression": true' in output_lenient.lower()

    def test_relative_gate_catches_small_absolute_shift_on_fast_metric(self):
        """A 1 -> 1.2 ms shift is < 10 ms absolute but 20% relative."""
        detector = RegressionDetector()
        base = [1.0 + (i % 5) * 0.01 for i in range(200)]
        cand = [1.2 + (i % 5) * 0.01 for i in range(200)]
        result = detector.detect(base, cand)
        assert result.is_regression
        assert result.hl_shift < 10
        assert result.hl_shift_relative > 0.05
