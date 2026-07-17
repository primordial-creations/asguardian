"""
L0 tests for mergeable quantile sketches (t-digest / DDSketch).

The design invariant: per-host percentiles must never be averaged; sketches
merge such that merge(a, b) approximates the sketch of the concatenation
(RESEARCH_15).
"""

import random

import pytest

from Asgard.Verdandi.Analysis.services.quantile_sketch import (
    DDSketch,
    TDigest,
    sketch_from_values,
)
from Asgard.Verdandi.Analysis.services.percentile_calculator import (
    PercentileCalculator,
    SKETCH_APPROXIMATION,
)


def _lognormal_samples(n: int, seed: int = 42):
    rng = random.Random(seed)
    return [rng.lognormvariate(3, 1) for _ in range(n)]


def _exact_quantile(sorted_values, q):
    rank = (len(sorted_values) - 1) * q
    lower = int(rank)
    frac = rank - lower
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])


class TestTDigest:
    def test_quantile_error_under_1pct_on_lognormal(self):
        samples = _lognormal_samples(100_000)
        digest = TDigest(compression=200)
        digest.add_batch(samples)
        ordered = sorted(samples)
        for q in (0.5, 0.75, 0.9, 0.95, 0.99):
            exact = _exact_quantile(ordered, q)
            estimate = digest.quantile(q)
            assert abs(estimate - exact) / exact < 0.01, (
                f"q={q}: exact={exact:.2f}, estimate={estimate:.2f}"
            )

    def test_merge_approximates_concatenation(self):
        samples = _lognormal_samples(100_000)
        half_a = sketch_from_values(samples[:50_000], compression=200)
        half_b = sketch_from_values(samples[50_000:], compression=200)
        half_a.merge(half_b)
        whole = sketch_from_values(samples, compression=200)
        for q in (0.5, 0.9, 0.99):
            assert half_a.quantile(q) == pytest.approx(whole.quantile(q), rel=0.02)
        assert half_a.count == 100_000

    def test_serialization_round_trip(self):
        digest = sketch_from_values(_lognormal_samples(10_000))
        restored = TDigest.from_dict(digest.to_dict())
        for q in (0.5, 0.9, 0.99):
            assert restored.quantile(q) == pytest.approx(digest.quantile(q))
        assert restored.count == digest.count

    def test_min_max_are_exact(self):
        values = [5.0, 1.0, 9.0, 3.0]
        digest = sketch_from_values(values)
        assert digest.quantile(0.0) == pytest.approx(1.0)
        assert digest.quantile(1.0) == pytest.approx(9.0)

    def test_empty_sketch_raises(self):
        with pytest.raises(ValueError):
            TDigest().quantile(0.5)

    def test_invalid_quantile_raises(self):
        digest = sketch_from_values([1.0, 2.0])
        with pytest.raises(ValueError):
            digest.quantile(1.5)


class TestDDSketch:
    def test_relative_error_guarantee(self):
        samples = _lognormal_samples(50_000)
        sketch = DDSketch(relative_accuracy=0.01)
        sketch.add_batch(samples)
        ordered = sorted(samples)
        for q in (0.5, 0.9, 0.99):
            exact = _exact_quantile(ordered, q)
            estimate = sketch.quantile(q)
            assert abs(estimate - exact) / exact < 0.02  # ~alpha + rank noise

    def test_merge(self):
        a = DDSketch(0.01)
        b = DDSketch(0.01)
        a.add_batch([1.0, 2.0, 3.0])
        b.add_batch([100.0, 200.0, 300.0])
        a.merge(b)
        assert a.count == 6

    def test_merge_incompatible_accuracy_raises(self):
        with pytest.raises(ValueError):
            DDSketch(0.01).merge(DDSketch(0.02))

    def test_serialization_round_trip(self):
        sketch = DDSketch(0.01)
        sketch.add_batch([1.0, 50.0, 0.0, 200.0])
        restored = DDSketch.from_dict(sketch.to_dict())
        assert restored.quantile(0.5) == pytest.approx(sketch.quantile(0.5))
        assert restored.count == sketch.count


class TestMergeSketchesPath:
    """PercentileCalculator.merge_sketches is the sanctioned cross-host path."""

    def test_merged_p99_matches_pooled_p99_not_average_of_p99s(self):
        """Two hosts with very different distributions: the average of
        per-host p99s is far from the true pooled p99; the merged sketch
        is close. This is the invariant that forbids percentile averaging."""
        fast_host = [10.0 + (i % 5) for i in range(9_500)]
        slow_host = [1000.0 + (i % 50) for i in range(500)]
        pooled = sorted(fast_host + slow_host)
        true_p99 = _exact_quantile(pooled, 0.99)

        calc = PercentileCalculator()
        sketches = [calc.create_sketch(fast_host), calc.create_sketch(slow_host)]
        merged = calc.merge_sketches(sketches)

        p99_fast = _exact_quantile(sorted(fast_host), 0.99)
        p99_slow = _exact_quantile(sorted(slow_host), 0.99)
        averaged_p99 = (p99_fast + p99_slow) / 2

        assert abs(merged.p99 - true_p99) < abs(averaged_p99 - true_p99)
        assert merged.p99 == pytest.approx(true_p99, rel=0.20)
        # The averaging lie, quantified: averaging halves the true tail.
        assert averaged_p99 < 0.6 * true_p99

    def test_result_is_flagged_as_sketch_approximation(self):
        calc = PercentileCalculator()
        result = calc.merge_sketches([calc.create_sketch(range(1, 101))])
        assert SKETCH_APPROXIMATION in result.quality_flags
        assert result.sample_count == 100

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            PercentileCalculator().merge_sketches([])
