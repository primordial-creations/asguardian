"""L3 Contract tests for additional Verdandi (observability) models.

Covers: APM, Cache, Database, Network, System, Tracing, Trend, Web.
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# APM
# ---------------------------------------------------------------------------
from Asgard.Verdandi.APM.models.apm_models import (
    Span,
    SpanAnalysis,
    Trace,
    ServiceMetrics,
    ServiceDependency,
    ServiceMap,
    APMReport,
)


class TestSpanContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            Span()

    def test_accepts_valid_data(self):
        span = Span(
            trace_id="trace-001",
            span_id="span-001",
            operation_name="http.get",
            service_name="api",
            start_time=1000.0,
            end_time=1050.0,
            duration_ms=50.0,
        )
        assert span.trace_id == "trace-001"
        assert hasattr(span, "duration_ms")


class TestTraceContract:
    def test_requires_trace_id(self):
        with pytest.raises((ValidationError, TypeError)):
            Trace()

    def test_accepts_valid_data(self):
        trace = Trace(trace_id="trace-001")
        assert trace.trace_id == "trace-001"
        assert hasattr(trace, "spans") or hasattr(Trace, "model_fields")


class TestServiceMetricsContract:
    def test_requires_service_name(self):
        with pytest.raises((ValidationError, TypeError)):
            ServiceMetrics()

    def test_accepts_valid_data(self):
        sm = ServiceMetrics(service_name="api")
        assert sm.service_name == "api"


class TestServiceDependencyContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ServiceDependency()

    def test_accepts_valid_data(self):
        sd = ServiceDependency(source_service="api", target_service="db")
        assert sd.source_service == "api"
        assert hasattr(sd, "target_service")


class TestAPMReportContract:
    def test_instantiates_with_defaults(self):
        report = APMReport()
        assert report is not None
        assert hasattr(APMReport, "model_fields")


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
from Asgard.Verdandi.Cache.models.cache_models import (
    CacheMetrics,
    EvictionMetrics,
    CacheEfficiency,
)


class TestCacheMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CacheMetrics()

    def test_accepts_valid_data(self):
        cm = CacheMetrics(
            total_requests=1000,
            hits=800,
            misses=200,
            hit_rate_percent=80.0,
            miss_rate_percent=20.0,
            status="healthy",
        )
        assert cm.hits == 800
        assert hasattr(cm, "hit_rate_percent")


class TestEvictionMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            EvictionMetrics()

    def test_accepts_valid_data(self):
        em = EvictionMetrics(
            total_evictions=100,
            eviction_rate_per_sec=5.0,
            eviction_percent=10.0,
            status="warning",
        )
        assert em.total_evictions == 100


class TestCacheEfficiencyContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CacheEfficiency()

    def test_accepts_valid_data(self):
        ce = CacheEfficiency(
            efficiency_score=85.0,
            hit_rate_percent=80.0,
            memory_efficiency_percent=90.0,
            status="healthy",
        )
        assert ce.efficiency_score == 85.0


# ---------------------------------------------------------------------------
# Database (Verdandi)
# ---------------------------------------------------------------------------
from Asgard.Verdandi.Database.models.database_models import (
    QueryMetricsInput,
    QueryMetricsResult,
    ConnectionPoolMetrics,
    TransactionMetrics,
    DatabaseHealthResult,
)


class TestQueryMetricsInputContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            QueryMetricsInput()

    def test_accepts_valid_data(self):
        qmi = QueryMetricsInput(query_type="select", execution_time_ms=150.0)
        assert hasattr(qmi, "query_type")


class TestQueryMetricsResultContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            QueryMetricsResult()

    def test_accepts_valid_data(self):
        qmr = QueryMetricsResult(
            total_queries=1000,
            average_execution_ms=100.0,
            median_execution_ms=80.0,
            p95_execution_ms=300.0,
            p99_execution_ms=500.0,
            max_execution_ms=1000.0,
            min_execution_ms=10.0,
            slow_query_count=5,
            slow_query_threshold_ms=200.0,
            index_usage_rate=0.9,
            scan_rate=0.1,
        )
        assert qmr.total_queries == 1000


class TestConnectionPoolMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ConnectionPoolMetrics()

    def test_accepts_valid_data(self):
        cpm = ConnectionPoolMetrics(
            pool_size=10,
            active_connections=5,
            idle_connections=5,
            waiting_requests=0,
            utilization_percent=50.0,
            average_wait_time_ms=10.0,
            max_wait_time_ms=50.0,
        )
        assert cpm.pool_size == 10


class TestDatabaseHealthResultContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DatabaseHealthResult()

    def test_accepts_valid_data(self):
        dhr = DatabaseHealthResult(
            health_score=95.0,
            status="healthy",
            throughput_qps=500.0,
            error_rate=0.01,
        )
        assert dhr.health_score == 95.0


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
from Asgard.Verdandi.Network.models.network_models import (
    LatencyMetrics,
    BandwidthMetrics,
    DnsMetrics,
    ConnectionMetrics,
)


class TestLatencyMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            LatencyMetrics()

    def test_accepts_valid_data(self):
        lm = LatencyMetrics(
            sample_count=100,
            min_ms=1.0,
            max_ms=200.0,
            mean_ms=50.0,
            median_ms=40.0,
            p90_ms=100.0,
            p95_ms=150.0,
            p99_ms=190.0,
            std_dev_ms=30.0,
            jitter_ms=5.0,
            status="healthy",
        )
        assert lm.mean_ms == 50.0


class TestBandwidthMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            BandwidthMetrics()

    def test_accepts_valid_data(self):
        bm = BandwidthMetrics(
            upload_mbps=10.0,
            download_mbps=100.0,
            total_throughput_mbps=110.0,
            bytes_sent=1000000,
            bytes_received=10000000,
            duration_seconds=60.0,
            status="healthy",
        )
        assert bm.download_mbps == 100.0


class TestDnsMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DnsMetrics()

    def test_accepts_valid_data(self):
        dm = DnsMetrics(
            query_count=500,
            avg_resolution_ms=10.0,
            p95_resolution_ms=50.0,
            max_resolution_ms=200.0,
            cache_hit_rate=0.8,
            failure_rate=0.01,
            status="healthy",
        )
        assert dm.cache_hit_rate == 0.8


class TestConnectionMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ConnectionMetrics()

    def test_accepts_valid_data(self):
        cm = ConnectionMetrics(
            total_connections=1000,
            active_connections=100,
            idle_connections=900,
            avg_connection_time_ms=5.0,
            connection_reuse_rate=0.95,
            error_rate=0.001,
            status="healthy",
        )
        assert cm.total_connections == 1000


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
from Asgard.Verdandi.System.models.system_models import (
    MemoryMetrics,
    CpuMetrics,
    IoMetrics,
    ResourceUtilization,
)


class TestMemoryMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            MemoryMetrics()

    def test_accepts_valid_data(self):
        mm = MemoryMetrics(
            total_bytes=8_000_000_000,
            used_bytes=4_000_000_000,
            available_bytes=4_000_000_000,
            usage_percent=50.0,
            status="healthy",
        )
        assert mm.usage_percent == 50.0


class TestCpuMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CpuMetrics()

    def test_accepts_valid_data(self):
        cm = CpuMetrics(
            usage_percent=30.0,
            user_percent=20.0,
            system_percent=10.0,
            idle_percent=70.0,
            core_count=8,
            status="healthy",
        )
        assert cm.core_count == 8


class TestIoMetricsContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            IoMetrics()

    def test_accepts_valid_data(self):
        im = IoMetrics(
            read_bytes_per_sec=1_000_000,
            write_bytes_per_sec=500_000,
            read_ops_per_sec=100,
            write_ops_per_sec=50,
            total_iops=150,
            total_throughput_mbps=1.5,
            status="healthy",
        )
        assert im.total_iops == 150


class TestResourceUtilizationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ResourceUtilization()

    def test_accepts_valid_data(self):
        mm = MemoryMetrics(
            total_bytes=8000000000, used_bytes=4000000000,
            available_bytes=4000000000, usage_percent=50.0, status="healthy",
        )
        cm = CpuMetrics(
            usage_percent=30.0, user_percent=20.0, system_percent=10.0,
            idle_percent=70.0, core_count=8, status="healthy",
        )
        ru = ResourceUtilization(memory=mm, cpu=cm, overall_health_score=90.0, overall_status="healthy")
        assert ru.overall_health_score == 90.0


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------
from Asgard.Verdandi.Tracing.models.tracing_models import (
    SpanLink,
    TraceSpan,
    DistributedTrace,
    CriticalPathSegment,
    CriticalPathResult,
    TracingReport,
)


class TestSpanLinkContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            SpanLink()

    def test_accepts_valid_data(self):
        sl = SpanLink(trace_id="trace-001", span_id="span-001")
        assert sl.trace_id == "trace-001"


class TestTraceSpanContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TraceSpan()

    def test_accepts_valid_data(self):
        ts = TraceSpan(
            trace_id="trace-001",
            span_id="span-001",
            operation_name="db.query",
            service_name="api",
            start_time_unix_nano=1000000,
            end_time_unix_nano=1050000,
            duration_ms=50.0,
        )
        assert ts.operation_name == "db.query"


class TestDistributedTraceContract:
    def test_requires_trace_id(self):
        with pytest.raises((ValidationError, TypeError)):
            DistributedTrace()

    def test_accepts_valid_data(self):
        dt = DistributedTrace(trace_id="trace-001")
        assert dt.trace_id == "trace-001"
        assert hasattr(dt, "spans") or hasattr(DistributedTrace, "model_fields")


class TestTracingReportContract:
    def test_instantiates_with_defaults(self):
        report = TracingReport()
        assert report is not None
        assert hasattr(TracingReport, "model_fields")


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------
from Asgard.Verdandi.Trend.models.trend_models import (
    TrendData,
    TrendAnalysis,
    ForecastPoint,
    ForecastResult,
    TrendReport,
)


class TestTrendDataContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TrendData()

    def test_accepts_valid_data(self):
        td = TrendData(timestamp="2024-01-01T00:00:00", value=42.0)
        assert td.value == 42.0


class TestTrendAnalysisContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TrendAnalysis()

    def test_accepts_valid_data(self):
        ta = TrendAnalysis(
            metric_name="response_time",
            period_start="2024-01-01",
            period_end="2024-01-31",
        )
        assert ta.metric_name == "response_time"
        assert hasattr(ta, "trend_direction") or hasattr(TrendAnalysis, "model_fields")


class TestForecastPointContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ForecastPoint()

    def test_accepts_valid_data(self):
        fp = ForecastPoint(
            timestamp="2024-02-01T00:00:00",
            predicted_value=55.0,
            lower_bound=40.0,
            upper_bound=70.0,
        )
        assert fp.predicted_value == 55.0


class TestTrendReportContract:
    def test_requires_period_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TrendReport()

    def test_accepts_valid_data(self):
        from datetime import datetime
        report = TrendReport(report_period_start=datetime(2024, 1, 1), report_period_end=datetime(2024, 1, 31))
        assert hasattr(report, "report_period_start")


# ---------------------------------------------------------------------------
# Web Vitals
# ---------------------------------------------------------------------------
from Asgard.Verdandi.Web.models.web_models import (
    CoreWebVitalsInput,
    WebVitalsResult,
    NavigationTimingInput,
    NavigationTimingResult,
    ResourceTimingInput,
    ResourceTimingResult,
)


class TestCoreWebVitalsInputContract:
    def test_instantiates_with_defaults(self):
        cwvi = CoreWebVitalsInput()
        assert cwvi is not None
        assert hasattr(CoreWebVitalsInput, "model_fields")


class TestWebVitalsResultContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            WebVitalsResult()

    def test_accepts_valid_data(self):
        wvr = WebVitalsResult(overall_rating="good", score=90.0)
        assert wvr.overall_rating == "good"
        assert hasattr(wvr, "score")


class TestNavigationTimingInputContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            NavigationTimingInput()

    def test_accepts_valid_data(self):
        nti = NavigationTimingInput(
            dns_start_ms=0.0,
            dns_end_ms=5.0,
            connect_start_ms=5.0,
            connect_end_ms=20.0,
            request_start_ms=20.0,
            response_start_ms=100.0,
            response_end_ms=150.0,
            dom_interactive_ms=300.0,
            dom_complete_ms=500.0,
            load_event_start_ms=500.0,
            load_event_end_ms=505.0,
        )
        assert nti.dns_end_ms == 5.0
