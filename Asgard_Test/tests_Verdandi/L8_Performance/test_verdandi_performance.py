"""
Verdandi L8 Performance Benchmarks

Benchmarks for Verdandi performance analysis services including
percentile calculation, anomaly detection, error budget computation,
APM, cache, database, network, SLO, system, tracing, and trend services.
"""

import random
from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.Analysis.services.percentile_calculator import PercentileCalculator
from Asgard.Verdandi.Anomaly.services.statistical_detector import StatisticalDetector
from Asgard.Verdandi.SLO.services.error_budget_calculator import ErrorBudgetCalculator
from Asgard.Verdandi.SLO.models.slo_models import SLODefinition, SLIMetric, SLOType


# --- Shared test data -----------------------------------------------------------

def _make_latency_samples(n: int, seed: int = 42) -> list[float]:
    """Generate n realistic latency values (ms) with a log-normal distribution."""
    rng = random.Random(seed)
    return [rng.lognormvariate(4.5, 0.6) for _ in range(n)]


SMALL_DATASET = _make_latency_samples(100)
MEDIUM_DATASET = _make_latency_samples(1_000)
LARGE_DATASET = _make_latency_samples(10_000)

_now = datetime(2026, 5, 18, 12, 0, 0)
_window_start = _now - timedelta(days=30)

SLO_DEFINITION = SLODefinition(
    name="API Availability",
    target=99.9,
    slo_type=SLOType.AVAILABILITY,
    service_name="api-gateway",
    window_days=30,
)

# 720 SLI metrics (30 days * 24 hours), ~80% good events
_SLI_METRICS = [
    SLIMetric(
        timestamp=_window_start + timedelta(hours=i),
        service_name="api-gateway",
        slo_type=SLOType.AVAILABILITY,
        good_events=1 if i % 5 != 0 else 0,
        total_events=1,
    )
    for i in range(720)
]


class TestVerdandiPerformance:
    """L8 performance benchmarks for Verdandi analysis services."""

    def test_percentile_calculation_small_dataset(self, benchmark):
        """Benchmark standard percentile calculation on 100 values."""
        calc = PercentileCalculator()

        result = benchmark(calc.calculate, SMALL_DATASET)

        assert result is not None
        assert result.sample_count == 100
        assert result.p99 >= result.p95 >= result.p50

    def test_percentile_calculation_large_dataset(self, benchmark):
        """Benchmark percentile calculation on 10,000 values (scalability check)."""
        calc = PercentileCalculator()

        result = benchmark(calc.calculate, LARGE_DATASET)

        assert result is not None
        assert result.sample_count == 10_000
        assert result.p99 >= result.p95 >= result.p50

    def test_statistical_anomaly_detection(self, benchmark):
        """Benchmark z-score based anomaly detection on a medium dataset (1k samples)."""
        detector = StatisticalDetector(z_threshold=3.0)

        result = benchmark(detector.detect_zscore, MEDIUM_DATASET, "latency_ms")

        assert result is not None
        assert isinstance(result, list)

    def test_error_budget_calculation(self, benchmark):
        """Benchmark error budget consumption for a 30-day SLO window with 720 metrics."""
        calc = ErrorBudgetCalculator()

        result = benchmark(calc.calculate, SLO_DEFINITION, _SLI_METRICS, _now)

        assert result is not None
        assert result.total_events > 0
        assert result.good_events + result.bad_events == result.total_events


# --- APM benchmarks -------------------------------------------------------------

class TestAPMPerformance:
    """Benchmarks for APM services."""

    def test_span_analyzer_analyze(self, benchmark):
        """Benchmark SpanAnalyzer.analyze for a single span with child spans."""
        from Asgard.Verdandi.APM.services.span_analyzer import SpanAnalyzer
        from Asgard.Verdandi.APM.models.apm_models import Span, SpanKind, SpanStatus

        _t0 = datetime(2026, 5, 18, 12, 0, 0)
        root_span = Span(
            trace_id="trace-001",
            span_id="span-root",
            operation_name="http.request",
            service_name="api-gateway",
            kind=SpanKind.SERVER,
            start_time=_t0,
            end_time=_t0 + timedelta(milliseconds=250),
            duration_ms=250.0,
            status=SpanStatus.OK,
        )
        child_spans = [
            Span(
                trace_id="trace-001",
                span_id=f"span-child-{i}",
                parent_span_id="span-root",
                operation_name=f"db.query.{i}",
                service_name="postgres",
                kind=SpanKind.CLIENT,
                start_time=_t0 + timedelta(milliseconds=i * 20),
                end_time=_t0 + timedelta(milliseconds=i * 20 + 15),
                duration_ms=15.0,
                status=SpanStatus.OK,
            )
            for i in range(5)
        ]
        analyzer = SpanAnalyzer(slow_threshold_ms=100.0)

        result = benchmark(analyzer.analyze, root_span, child_spans)

        assert result is not None
        assert result.child_count == 5

    def test_trace_aggregator_aggregate(self, benchmark):
        """Benchmark TraceAggregator.aggregate over 50 traces."""
        from Asgard.Verdandi.APM.services.trace_aggregator import TraceAggregator
        from Asgard.Verdandi.APM.models.apm_models import Span, Trace, SpanKind, SpanStatus

        _t0 = datetime(2026, 5, 18, 12, 0, 0)

        def _make_trace(trace_idx: int) -> Trace:
            root = Span(
                trace_id=f"trace-{trace_idx}",
                span_id=f"root-{trace_idx}",
                operation_name="http.get",
                service_name="frontend",
                kind=SpanKind.SERVER,
                start_time=_t0 + timedelta(seconds=trace_idx),
                end_time=_t0 + timedelta(seconds=trace_idx, milliseconds=120),
                duration_ms=120.0,
                status=SpanStatus.OK,
            )
            child = Span(
                trace_id=f"trace-{trace_idx}",
                span_id=f"child-{trace_idx}",
                parent_span_id=f"root-{trace_idx}",
                operation_name="db.select",
                service_name="postgres",
                kind=SpanKind.CLIENT,
                start_time=_t0 + timedelta(seconds=trace_idx, milliseconds=10),
                end_time=_t0 + timedelta(seconds=trace_idx, milliseconds=50),
                duration_ms=40.0,
                status=SpanStatus.OK,
            )
            return Trace(
                trace_id=f"trace-{trace_idx}",
                root_span=root,
                spans=[root, child],
                service_count=2,
                total_duration_ms=120.0,
                error_count=0,
            )

        traces = [_make_trace(i) for i in range(50)]
        aggregator = TraceAggregator()

        result = benchmark(aggregator.aggregate, traces)

        assert result is not None

    def test_service_map_builder_build_from_spans(self, benchmark):
        """Benchmark ServiceMapBuilder.build_from_spans across 6 services."""
        from Asgard.Verdandi.APM.services.service_map_builder import ServiceMapBuilder
        from Asgard.Verdandi.APM.models.apm_models import Span, SpanKind, SpanStatus

        _t0 = datetime(2026, 5, 18, 12, 0, 0)
        services = ["gateway", "auth", "orders", "inventory", "postgres", "redis"]
        spans = [
            Span(
                trace_id="trace-map",
                span_id=f"sp-{i}",
                parent_span_id=f"sp-{i - 1}" if i > 0 else None,
                operation_name=f"op.{services[i % len(services)]}",
                service_name=services[i % len(services)],
                kind=SpanKind.SERVER if i % 2 == 0 else SpanKind.CLIENT,
                start_time=_t0 + timedelta(milliseconds=i * 10),
                end_time=_t0 + timedelta(milliseconds=i * 10 + 8),
                duration_ms=8.0,
                status=SpanStatus.OK,
            )
            for i in range(100)
        ]
        builder = ServiceMapBuilder()

        result = benchmark(builder.build_from_spans, spans)

        assert result is not None


# --- Cache benchmarks -----------------------------------------------------------

class TestCachePerformance:
    """Benchmarks for Cache services."""

    def test_cache_calculator_analyze(self, benchmark):
        """Benchmark CacheCalculator.analyze with realistic hit/miss data."""
        from Asgard.Verdandi.Cache.services.cache_calculator import CacheMetricsCalculator

        calc = CacheMetricsCalculator()

        result = benchmark(
            calc.analyze,
            hits=8500,
            misses=1500,
            avg_hit_latency_ms=0.5,
            avg_miss_latency_ms=15.0,
            size_bytes=512 * 1024 * 1024,
            max_size_bytes=1024 * 1024 * 1024,
        )

        assert result is not None
        assert result.total_requests == 10_000

    def test_eviction_analyzer_analyze(self, benchmark):
        """Benchmark EvictionAnalyzer.analyze with eviction reason breakdown."""
        from Asgard.Verdandi.Cache.services.eviction_analyzer import EvictionAnalyzer

        analyzer = EvictionAnalyzer()

        result = benchmark(
            analyzer.analyze,
            evictions=240,
            duration_seconds=60.0,
            total_operations=10_000,
            by_reason={"ttl": 180, "lru": 50, "size": 10},
            avg_entry_age_seconds=300.0,
            premature_evictions=10,
        )

        assert result is not None
        assert result.total_evictions == 240


# --- Database benchmarks -------------------------------------------------------

class TestDatabasePerformance:
    """Benchmarks for Database services."""

    def test_connection_analyzer_analyze(self, benchmark):
        """Benchmark ConnectionAnalyzer.analyze for a busy connection pool."""
        from Asgard.Verdandi.Database.services.connection_analyzer import ConnectionAnalyzer

        analyzer = ConnectionAnalyzer()

        result = benchmark(
            analyzer.analyze,
            pool_size=20,
            active_connections=15,
            idle_connections=5,
            waiting_requests=2,
            wait_times_ms=[10.0, 12.0, 8.0, 15.0, 9.0],
            connection_errors=0,
            timeout_count=0,
        )

        assert result is not None
        assert result.pool_size == 20

    def test_throughput_calculator_calculate_qps(self, benchmark):
        """Benchmark ThroughputCalculator.calculate_qps."""
        from Asgard.Verdandi.Database.services.throughput_calculator import ThroughputCalculator

        calc = ThroughputCalculator()

        result = benchmark(calc.calculate_qps, query_count=50_000, duration_seconds=60.0)

        assert result is not None
        assert result > 0

    def test_query_metrics_analyze(self, benchmark):
        """Benchmark QueryMetrics.analyze on a batch of 500 queries."""
        from Asgard.Verdandi.Database.services.query_metrics import QueryMetricsCalculator
        from Asgard.Verdandi.Database.models.database_models import QueryMetricsInput, QueryType

        rng = random.Random(7)
        queries = [
            QueryMetricsInput(
                query_id=f"q-{i}",
                query_type=QueryType.SELECT,
                execution_time_ms=rng.lognormvariate(3.5, 0.8),
                rows_examined=rng.randint(1, 1000),
                rows_affected=1,
                used_index=rng.random() > 0.2,
            )
            for i in range(500)
        ]
        metrics = QueryMetricsCalculator()

        result = benchmark(metrics.analyze, queries)

        assert result is not None
        assert result.total_queries == 500


# --- Network benchmarks --------------------------------------------------------

class TestNetworkPerformance:
    """Benchmarks for Network services."""

    def test_bandwidth_calculator_analyze(self, benchmark):
        """Benchmark BandwidthCalculator.analyze for a 1-minute window."""
        from Asgard.Verdandi.Network.services.bandwidth_calculator import BandwidthCalculator

        calc = BandwidthCalculator()

        result = benchmark(
            calc.analyze,
            bytes_sent=500 * 1024 * 1024,
            bytes_received=2 * 1024 * 1024 * 1024,
            duration_seconds=60.0,
            capacity_mbps=1000.0,
        )

        assert result is not None
        assert result.upload_mbps > 0

    def test_dns_calculator_analyze(self, benchmark):
        """Benchmark DnsCalculator.analyze over 200 resolution samples."""
        from Asgard.Verdandi.Network.services.dns_calculator import DnsCalculator

        rng = random.Random(3)
        resolution_times = [rng.uniform(0.5, 50.0) for _ in range(200)]
        calc = DnsCalculator()

        result = benchmark(
            calc.analyze,
            resolution_times_ms=resolution_times,
            cache_hits=80,
            total_queries=280,
            failures=5,
        )

        assert result is not None
        assert result.query_count > 0

    def test_latency_calculator_analyze(self, benchmark):
        """Benchmark LatencyCalculator.analyze over 500 latency samples."""
        from Asgard.Verdandi.Network.services.latency_calculator import LatencyCalculator

        rng = random.Random(11)
        latencies = [rng.lognormvariate(2.5, 0.5) for _ in range(500)]
        calc = LatencyCalculator()

        result = benchmark(calc.analyze, latencies_ms=latencies, packet_loss_percent=0.1)

        assert result is not None
        assert result.sample_count == 500


# --- SLO benchmarks ------------------------------------------------------------

class TestSLOPerformance:
    """Benchmarks for SLO services."""

    def test_burn_rate_analyzer_analyze(self, benchmark):
        """Benchmark BurnRateAnalyzer.analyze for a 1-hour window."""
        from Asgard.Verdandi.SLO.services.burn_rate_analyzer import BurnRateAnalyzer

        analyzer = BurnRateAnalyzer()
        current_time = datetime(2026, 5, 18, 12, 0, 0)

        result = benchmark(
            analyzer.analyze,
            SLO_DEFINITION,
            _SLI_METRICS,
            window_hours=1.0,
            current_time=current_time,
        )

        assert result is not None

    def test_sli_tracker_record_batch(self, benchmark):
        """Benchmark SLITracker.record_batch for 100 metrics."""
        from Asgard.Verdandi.SLO.services.sli_tracker import SLITracker

        batch = [
            SLIMetric(
                timestamp=_window_start + timedelta(hours=i),
                service_name="api-gateway",
                slo_type=SLOType.AVAILABILITY,
                good_events=1,
                total_events=1,
            )
            for i in range(100)
        ]

        def _record_and_count():
            tracker = SLITracker()
            tracker.record_batch(batch)
            return tracker.get_metric_count()

        result = benchmark(_record_and_count)

        assert result == 100


# --- System benchmarks ---------------------------------------------------------

class TestSystemPerformance:
    """Benchmarks for System services."""

    def test_cpu_calculator_analyze(self, benchmark):
        """Benchmark CpuCalculator.analyze with per-core data."""
        from Asgard.Verdandi.System.services.cpu_calculator import CpuMetricsCalculator

        calc = CpuMetricsCalculator()

        result = benchmark(
            calc.analyze,
            user_percent=45.0,
            system_percent=15.0,
            idle_percent=40.0,
            core_count=8,
            iowait_percent=2.0,
            per_core_usage=[50.0, 40.0, 60.0, 45.0, 55.0, 35.0, 48.0, 42.0],
            load_average_1m=3.2,
            load_average_5m=2.8,
            load_average_15m=2.5,
        )

        assert result is not None
        assert result.core_count == 8

    def test_io_calculator_analyze(self, benchmark):
        """Benchmark IoCalculator.analyze for a mixed read/write workload."""
        from Asgard.Verdandi.System.services.io_calculator import IoMetricsCalculator

        calc = IoMetricsCalculator()

        result = benchmark(
            calc.analyze,
            read_bytes=200 * 1024 * 1024,
            write_bytes=50 * 1024 * 1024,
            read_ops=5000,
            write_ops=1200,
            duration_seconds=60.0,
            avg_read_latency_ms=0.5,
            avg_write_latency_ms=1.2,
            queue_depth=2.0,
            utilization_percent=35.0,
        )

        assert result is not None
        assert result.total_iops > 0

    def test_memory_calculator_analyze(self, benchmark):
        """Benchmark MemoryCalculator.analyze with swap data."""
        from Asgard.Verdandi.System.services.memory_calculator import MemoryMetricsCalculator

        calc = MemoryMetricsCalculator()
        total = 16 * 1024 * 1024 * 1024  # 16 GB

        result = benchmark(
            calc.analyze,
            used_bytes=int(total * 0.65),
            total_bytes=total,
            swap_used_bytes=256 * 1024 * 1024,
            swap_total_bytes=4 * 1024 * 1024 * 1024,
        )

        assert result is not None
        assert result.total_bytes == total


# --- Tracing benchmarks -------------------------------------------------------

class TestTracingPerformance:
    """Benchmarks for Tracing services."""

    def test_critical_path_analyzer_analyze(self, benchmark):
        """Benchmark CriticalPathAnalyzer.analyze on a multi-service trace."""
        from Asgard.Verdandi.Tracing.services.critical_path_analyzer import CriticalPathAnalyzer
        from Asgard.Verdandi.Tracing.models.tracing_models import DistributedTrace, TraceSpan

        _t0_ns = int(datetime(2026, 5, 18, 12, 0, 0).timestamp() * 1e9)

        def _make_span(idx: int, parent_id=None, duration_ms=50.0, service="svc") -> TraceSpan:
            start = _t0_ns + idx * 10_000_000
            end = start + int(duration_ms * 1_000_000)
            return TraceSpan(
                trace_id="trace-cp",
                span_id=f"sp-{idx}",
                parent_span_id=parent_id,
                operation_name=f"op.{service}.{idx}",
                service_name=service,
                start_time_unix_nano=start,
                end_time_unix_nano=end,
                duration_ms=duration_ms,
            )

        root = _make_span(0, duration_ms=300.0, service="gateway")
        children = [
            _make_span(i + 1, parent_id="sp-0", duration_ms=80.0, service=f"svc-{i}")
            for i in range(3)
        ]
        grandchildren = [
            _make_span(10 + ci * 2 + gi, parent_id=children[ci].span_id, duration_ms=30.0, service="db")
            for ci in range(3)
            for gi in range(2)
        ]
        all_spans = [root] + children + grandchildren

        trace = DistributedTrace(
            trace_id="trace-cp",
            spans=all_spans,
            root_span=root,
            service_names=["gateway", "svc-0", "svc-1", "svc-2", "db"],
            total_duration_ms=300.0,
            span_count=len(all_spans),
        )
        analyzer = CriticalPathAnalyzer()

        result = benchmark(analyzer.analyze, trace)

        assert result is not None
        assert result.trace_id == "trace-cp"

    def test_trace_parser_parse_otlp(self, benchmark):
        """Benchmark TraceParser.parse_otlp on a 20-span OTLP payload."""
        from Asgard.Verdandi.Tracing.services.trace_parser import TraceParser

        _t0_ns = int(datetime(2026, 5, 18, 12, 0, 0).timestamp() * 1e9)
        otlp_data = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "api-gateway"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "opentelemetry"},
                            "spans": [
                                {
                                    "traceId": "abcdef1234567890abcdef1234567890",
                                    "spanId": f"span{i:016x}",
                                    "parentSpanId": "span0000000000000000" if i > 0 else "",
                                    "name": f"http.request.{i}",
                                    "kind": 2,
                                    "startTimeUnixNano": str(_t0_ns + i * 1_000_000),
                                    "endTimeUnixNano": str(_t0_ns + i * 1_000_000 + 50_000_000),
                                    "status": {"code": 1},
                                    "attributes": [],
                                }
                                for i in range(20)
                            ],
                        }
                    ],
                }
            ]
        }
        parser = TraceParser()

        result = benchmark(parser.parse_otlp, otlp_data)

        assert result is not None
        assert len(result) > 0


# --- Trend benchmarks ---------------------------------------------------------

class TestTrendPerformance:
    """Benchmarks for Trend services."""

    def test_forecast_calculator_forecast_values(self, benchmark):
        """Benchmark ForecastCalculator.forecast_values over 90 historical points."""
        from Asgard.Verdandi.Trend.services.forecast_calculator import ForecastCalculator

        rng = random.Random(99)
        values = [50.0 + i * 0.3 + rng.gauss(0, 3) for i in range(90)]
        calc = ForecastCalculator()

        result = benchmark(
            calc.forecast_values,
            values=values,
            periods=14,
            interval_seconds=86400,
            metric_name="latency_p99",
        )

        assert result is not None
        assert len(result.forecast_points) == 14

    def test_trend_analyzer_analyze_values(self, benchmark):
        """Benchmark TrendAnalyzer.analyze_values over 60 daily data points."""
        from Asgard.Verdandi.Trend.services.trend_analyzer import TrendAnalyzer

        rng = random.Random(77)
        values = [100.0 + i * 0.5 + rng.gauss(0, 5) for i in range(60)]
        analyzer = TrendAnalyzer()

        result = benchmark(
            analyzer.analyze_values,
            values=values,
            metric_name="error_rate",
            interval_seconds=86400,
        )

        assert result is not None
        assert result.data_point_count == 60
