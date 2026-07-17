"""
Tests for cache warm-up trajectory analysis, segmented SLOs, and the
documented-but-previously-missing doc-parity methods (Plan 04.1-04.3).

Encodes DEEPTHINK_08's plunge-and-flatline case and DEEPTHINK_04's
hit-mode-shift masking case as regression tests.
"""

import math

import pytest

from Asgard.Verdandi.Cache import (
    CacheMetricsCalculator,
    EvictionAnalyzer,
    SegmentedSloAnalyzer,
    WarmupAnalyzer,
    WarmupState,
)


def _bucket(rate_pct, total=1000):
    hits = int(round(total * rate_pct / 100))
    return {"hits": hits, "misses": total - hits}


class TestWarmupTrajectory:
    def setup_method(self):
        self.analyzer = WarmupAnalyzer()

    def test_exponential_recovery_is_warming_with_eta(self):
        # Plan 04 L0: h(t) = 0.9 - 0.4*e^(-t/5) after the deploy at t=0
        series = [_bucket(90.0)] + [
            _bucket((0.9 - 0.4 * math.exp(-t / 5)) * 100) for t in range(10)
        ]

        result = self.analyzer.analyze(series)

        assert result.state == WarmupState.WARMING
        assert result.suppress_alert is True
        assert result.tau_buckets == pytest.approx(5.0, rel=0.3)
        assert result.eta_buckets is not None and result.eta_buckets > 0

    def test_plunge_and_flatline_is_critical_and_bypasses_suppression(self):
        series = [_bucket(90.0), _bucket(50.0), _bucket(50.5), _bucket(49.8), _bucket(50.2)]

        result = self.analyzer.analyze(series)

        assert result.state == WarmupState.FLATLINED
        assert result.severity == "critical"
        assert result.suppress_alert is False

    def test_collapse_is_immediately_critical_no_grace(self):
        series = [_bucket(90.0), _bucket(0.0), _bucket(0.0)]

        result = self.analyzer.analyze(series)

        assert result.state == WarmupState.COLLAPSED
        assert result.severity == "critical"

    def test_stable_series(self):
        series = [_bucket(90.0) for _ in range(6)]

        result = self.analyzer.analyze(series)

        assert result.state == WarmupState.STABLE

    def test_insufficient_data(self):
        result = self.analyzer.analyze([_bucket(90.0)])

        assert result.state == WarmupState.INSUFFICIENT_DATA
        assert result.severity == "info"

    def test_db_correlation_strengthens_severity(self):
        # Miss rate and DB load move together
        series = [_bucket(90.0), _bucket(50.0), _bucket(60.0), _bucket(70.0), _bucket(80.0)]
        db_load = [10.0, 50.0, 40.0, 30.0, 20.0]

        result = self.analyzer.analyze(series, db_load_series=db_load)

        assert result.db_correlation is not None and result.db_correlation > 0.8
        assert result.suppress_alert is False


class TestDocParityMethods:
    def setup_method(self):
        self.calc = CacheMetricsCalculator()

    def test_analyze_trend_delegates_to_warmup(self):
        history = [
            {"timestamp": 1, "hits": 900, "misses": 100},
            {"timestamp": 2, "hits": 920, "misses": 80},
            {"timestamp": 3, "hits": 850, "misses": 150},
        ]

        result = self.calc.analyze_trend(history)

        assert result.state == WarmupState.STABLE

    def test_analyze_keys_flags_low_hit_and_do_not_cache(self):
        key_stats = [
            {"key": "user:123", "hits": 500, "misses": 10},
            {"key": "product:456", "hits": 100, "misses": 500},
            {"key": "session:789", "hits": 1000, "misses": 5},
        ]

        result = self.calc.analyze_keys(key_stats)

        low = {k.key for k in result.low_hit_rate_keys}
        assert low == {"product:456"}
        assert {k.key for k in result.do_not_cache_candidates} == {"product:456"}
        assert result.overall_hit_rate == pytest.approx(1600 / 2115, abs=0.001)
        assert result.recommendations

    def test_analyze_ttl_patterns_suggests_p75_refetch_interval(self):
        # Plan 04 L0: evictions at age ~= TTL with quick refetch
        evictions = [
            {
                "key": f"k{i}",
                "reason": "EXPIRED",
                "age_seconds": 3600 * 0.95,
                "ttl_seconds": 3600,
                "refetch_interval_seconds": interval,
            }
            for i, interval in enumerate([7000, 7200, 7500, 8000])
        ]

        result = EvictionAnalyzer().analyze_ttl_patterns(evictions)

        assert result.ttl_too_short is True
        # p75 of [7000, 7200, 7500, 8000] = 7625
        assert result.suggested_ttl_seconds == pytest.approx(7625, abs=1)

    def test_analyze_ttl_patterns_lru_undersized_and_working_set(self):
        evictions = [
            {"key": f"k{i}", "reason": "LRU", "age_seconds": 60, "ttl_seconds": 3600}
            for i in range(6)
        ] + [
            {"key": "e1", "reason": "EXPIRED", "age_seconds": 3600, "ttl_seconds": 3600}
        ]

        result = EvictionAnalyzer().analyze_ttl_patterns(
            evictions, lru_bytes_per_sec=1_000_000
        )

        assert result.cache_undersized is True
        assert result.working_set_bytes == pytest.approx(60_000_000)
        assert result.recommended_size_bytes == pytest.approx(60_000_000 / 0.9)

    def test_analyze_ttl_patterns_empty_is_insufficient_data(self):
        result = EvictionAnalyzer().analyze_ttl_patterns([])

        assert result.total_evictions == 0
        assert any("INSUFFICIENT_DATA" in n for n in result.notes)


class TestSegmentedSlo:
    def setup_method(self):
        self.analyzer = SegmentedSloAnalyzer()

    def test_independent_hit_and_miss_slis(self):
        hits = [10.0] * 99 + [30.0]      # 99% within 20ms
        misses = [800.0] * 19 + [1500.0]  # 95% within 1000ms

        result = self.analyzer.analyze(hits, misses)

        assert result.hit_sli == pytest.approx(0.99)
        assert result.miss_sli == pytest.approx(0.95)
        assert result.hit_ratio == pytest.approx(100 / 120)

    def test_deepthink04_masking_case_mode_shift_alert(self):
        # 85% hits @ 10ms + 15% misses @ 800ms; hit mode shifts to 200ms.
        # Blended p99 stays < 1000ms (loose SLO green) but the fast path
        # regressed 20x — the mode-shift alarm must fire.
        shifted_hits = [200.0] * 85
        misses = [800.0] * 15
        blended = sorted(shifted_hits + misses)
        p99 = blended[int(0.99 * len(blended)) - 1]
        assert p99 < 1000  # the masking precondition

        result = self.analyzer.analyze(
            shifted_hits, misses,
            baseline_hit_median_ms=10.0, baseline_hit_mad_ms=2.0,
        )

        assert result.mode_shift_alert is True
        assert result.hit_sli == 0.0  # segmented SLO catches what p99 masked

    def test_no_mode_shift_within_mad_band(self):
        result = self.analyzer.analyze(
            [11.0] * 50, [500.0] * 5,
            baseline_hit_median_ms=10.0, baseline_hit_mad_ms=2.0,
        )

        assert result.mode_shift_alert is False

    def test_unlabeled_fallback_uses_bimodality_split(self):
        import random
        random.seed(8)
        latencies = [10 + random.gauss(0, 2) for _ in range(120)]
        latencies += [800 + random.gauss(0, 50) for _ in range(40)]

        result = self.analyzer.analyze_unlabeled(latencies)

        assert result.labeled is False
        assert result.hit_total == pytest.approx(120, abs=5)
        assert result.miss_total == pytest.approx(40, abs=5)
        assert result.hit_sli > 0.95

    def test_unlabeled_unimodal_noted(self):
        result = self.analyzer.analyze_unlabeled([10.0 + i * 0.01 for i in range(100)])

        assert result.labeled is False
        assert any("not bimodal" in n for n in result.notes)
