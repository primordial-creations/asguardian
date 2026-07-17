"""
Tests for pool-exhaustion signatures and queue-wait separation (Plan 07.1-07.2).

Encodes RESEARCH_11's worked example (equal-variance peaks => the inter-peak
distance is the mean queue wait) and RESEARCH_12's Little's-law sizing case.
"""

import random

import pytest

from Asgard.Verdandi.Database import (
    ConnectionAnalyzer,
    PoolSignatureClass,
    PoolSignatureDetector,
)


class TestPoolSignatureDetector:
    def setup_method(self):
        self.detector = PoolSignatureDetector()

    def test_equal_variance_peaks_classified_as_pool_exhaustion(self):
        # Plan 07 L0: 60% N(20, 3) + 40% N(120, 3.5) -> queue wait ~= 100ms
        random.seed(1)
        latencies = [random.gauss(20, 3) for _ in range(600)]
        latencies += [random.gauss(120, 3.5) for _ in range(400)]

        result = self.detector.detect(latencies)

        assert result.classification == PoolSignatureClass.POOL_EXHAUSTION
        assert result.mean_queue_wait_ms == pytest.approx(100, abs=8)
        assert result.mad_disparity < 0.35
        assert len(result.modes) == 2
        assert any("lended mean/median" in w for w in result.warnings)

    def test_wide_slow_mode_classified_as_cache_aside(self):
        # Plan 07 L0: 80% N(5, 1) + 20% N(200, 60)
        random.seed(2)
        latencies = [random.gauss(5, 1) for _ in range(800)]
        latencies += [random.gauss(200, 60) for _ in range(200)]

        result = self.detector.detect(latencies)

        assert result.classification == PoolSignatureClass.CACHE_ASIDE_PATTERN
        assert any("cache" in r.lower() for r in result.recommendations)

    def test_wait_samples_corroboration_raises_confidence(self):
        random.seed(3)
        latencies = [random.gauss(20, 3) for _ in range(600)]
        latencies += [random.gauss(120, 3.5) for _ in range(400)]
        waits = [random.gauss(100, 10) for _ in range(200)]

        result = self.detector.detect(latencies, acquisition_wait_samples=waits)

        assert result.classification == PoolSignatureClass.POOL_EXHAUSTION
        assert result.confidence == "high"
        assert result.corroborated_by_wait_samples is True

    def test_mismatched_wait_samples_keep_medium_confidence(self):
        random.seed(4)
        latencies = [random.gauss(20, 3) for _ in range(600)]
        latencies += [random.gauss(120, 3.5) for _ in range(400)]

        result = self.detector.detect(latencies, acquisition_wait_samples=[5.0] * 100)

        assert result.confidence == "medium"
        assert result.corroborated_by_wait_samples is False

    def test_unimodal_distribution(self):
        random.seed(5)
        latencies = [random.gauss(50, 5) for _ in range(500)]

        result = self.detector.detect(latencies)

        assert result.classification == PoolSignatureClass.UNIMODAL

    def test_insufficient_data(self):
        result = self.detector.detect([10.0] * 5)

        assert result.classification == PoolSignatureClass.INSUFFICIENT_DATA


class TestQueueWaitSeparation:
    def setup_method(self):
        self.analyzer = ConnectionAnalyzer()

    def test_littles_law_sizing_worked_example(self):
        # Plan 07 L0: qps=200, avg query 100ms -> required=20; pool=25 ->
        # headroom 5, recommended ceil(20/0.7)=29
        metrics = self.analyzer.analyze(
            pool_size=25, active_connections=20, qps=200, avg_query_ms=100,
        )

        assert metrics.required_connections == pytest.approx(20.0)
        assert metrics.headroom_connections == pytest.approx(5.0)
        assert metrics.recommended_pool_size == 29

    def test_negative_headroom_recommendation(self):
        metrics = self.analyzer.analyze(
            pool_size=10, active_connections=10, qps=200, avg_query_ms=100,
        )
        recs = self.analyzer.get_recommendations(metrics)

        assert metrics.headroom_connections == pytest.approx(-10.0)
        assert any("Little" in r for r in recs)

    def test_wait_percentiles_and_queue_share(self):
        waits = [1.0] * 90 + [100.0] * 10
        metrics = self.analyzer.analyze(
            pool_size=20, active_connections=10,
            acquisition_wait_samples=waits, service_p95_ms=50.0,
        )

        assert metrics.wait_p50_ms == pytest.approx(1.0)
        assert metrics.wait_p99_ms == pytest.approx(100.0, abs=1)
        assert metrics.queue_share is not None and 0 < metrics.queue_share < 1

    def test_queue_share_dominant_wait_flagged(self):
        metrics = self.analyzer.analyze(
            pool_size=20, active_connections=18,
            acquisition_wait_samples=[200.0] * 50, service_p95_ms=30.0,
        )
        recs = self.analyzer.get_recommendations(metrics)

        assert metrics.queue_share > 0.5
        assert any("pool, not the" in r for r in recs)

    def test_leak_heuristic_timeouts_at_low_utilization(self):
        metrics = self.analyzer.analyze(
            pool_size=20, active_connections=5, timeout_count=3,
        )
        recs = self.analyzer.get_recommendations(metrics)

        assert metrics.leak_suspected is True
        assert any("leak" in r.lower() for r in recs)

    def test_no_leak_flag_at_high_utilization(self):
        metrics = self.analyzer.analyze(
            pool_size=20, active_connections=19, timeout_count=3,
        )

        assert metrics.leak_suspected is False

    def test_legacy_call_unchanged(self):
        metrics = self.analyzer.analyze(
            pool_size=20, active_connections=15, waiting_requests=3,
            wait_times_ms=[10, 20, 15, 25],
        )

        assert metrics.utilization_percent == pytest.approx(75.0)
        assert metrics.average_wait_time_ms == pytest.approx(17.5)
        assert metrics.wait_p95_ms is None
