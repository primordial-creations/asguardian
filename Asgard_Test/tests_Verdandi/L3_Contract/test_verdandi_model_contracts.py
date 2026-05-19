"""L3 Contract tests for Verdandi (performance monitoring) models.

Covers SLO, Anomaly, and Analysis public models.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from Asgard.Verdandi.SLO.models.slo_models import (
    SLODefinition,
    SLIMetric,
    ErrorBudget,
    BurnRate,
    SLOReport,
    SLOType,
    SLOComplianceStatus,
)
from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalyType,
    AnomalySeverity,
    BaselineMetrics,
    BaselineComparison,
    RegressionResult,
    AnomalyReport,
)
from Asgard.Verdandi.Analysis.models.analysis_models import (
    ApdexConfig,
    ApdexResult,
    SLAConfig,
    SLAResult,
    PercentileResult,
    AggregationConfig,
    AggregationResult,
    TrendResult,
    TrendDirection,
    SLAStatus,
)


# ---------------------------------------------------------------------------
# SLO Models
# ---------------------------------------------------------------------------
class TestSLODefinitionContract:
    def test_requires_name_slo_type_target_service_name(self):
        with pytest.raises((ValidationError, TypeError)):
            SLODefinition()

    def test_instantiates_with_required_fields(self):
        slo = SLODefinition(
            name="availability",
            slo_type=SLOType.AVAILABILITY,
            target=99.9,
            service_name="api",
        )
        assert slo.name == "availability"
        assert slo.target == 99.9

    def test_has_model_fields(self):
        fields = set(SLODefinition.model_fields.keys())
        assert "name" in fields
        assert "target" in fields
        assert "service_name" in fields


class TestSLIMetricContract:
    def test_requires_timestamp_service_name_slo_type(self):
        with pytest.raises((ValidationError, TypeError)):
            SLIMetric()

    def test_instantiates_with_required_fields(self):
        metric = SLIMetric(
            timestamp=datetime.now(timezone.utc).isoformat(),
            service_name="api",
            slo_type=SLOType.LATENCY,
        )
        assert metric.service_name == "api"

    def test_has_model_fields(self):
        fields = set(SLIMetric.model_fields.keys())
        assert "timestamp" in fields
        assert "service_name" in fields


class TestErrorBudgetContract:
    def test_requires_slo_name_target_window_days(self):
        with pytest.raises((ValidationError, TypeError)):
            ErrorBudget()

    def test_instantiates_with_required_fields(self):
        budget = ErrorBudget(slo_name="availability", slo_target=99.9, window_days=30)
        assert budget.slo_name == "availability"
        assert budget.window_days == 30


class TestBurnRateContract:
    def test_requires_slo_name_window_hours_burn_rate(self):
        with pytest.raises((ValidationError, TypeError)):
            BurnRate()

    def test_instantiates_with_required_fields(self):
        br = BurnRate(slo_name="latency", window_hours=1, burn_rate=2.5)
        assert br.burn_rate == 2.5


class TestSLOReportContract:
    def test_requires_period_and_service_name(self):
        with pytest.raises((ValidationError, TypeError)):
            SLOReport()

    def test_instantiates_with_required_fields(self):
        report = SLOReport(
            report_period_start="2026-05-01T00:00:00",
            report_period_end="2026-05-31T23:59:59",
            service_name="api",
        )
        assert report.service_name == "api"

    def test_has_model_fields(self):
        assert "service_name" in SLOReport.model_fields


# ---------------------------------------------------------------------------
# Anomaly Models
# ---------------------------------------------------------------------------
class TestAnomalyDetectionContract:
    def test_requires_multiple_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            AnomalyDetection()

    def test_instantiates_with_required_fields(self):
        anomaly = AnomalyDetection(
            detected_at=datetime.now(timezone.utc).isoformat(),
            data_timestamp=datetime.now(timezone.utc).isoformat(),
            anomaly_type=AnomalyType.SPIKE,
            severity=AnomalySeverity.HIGH,
            metric_name="response_time",
            actual_value=500.0,
            expected_value=100.0,
            deviation=400.0,
            deviation_percent=400.0,
        )
        assert anomaly.metric_name == "response_time"

    def test_has_model_fields(self):
        fields = set(AnomalyDetection.model_fields.keys())
        assert "metric_name" in fields
        assert "severity" in fields


class TestBaselineMetricsContract:
    def test_requires_metric_name(self):
        with pytest.raises((ValidationError, TypeError)):
            BaselineMetrics()

    def test_instantiates_with_required_fields(self):
        bm = BaselineMetrics(metric_name="latency_p99")
        assert bm.metric_name == "latency_p99"

    def test_has_model_fields(self):
        assert "metric_name" in BaselineMetrics.model_fields


class TestBaselineComparisonContract:
    def test_requires_metric_name_and_baseline(self):
        with pytest.raises((ValidationError, TypeError)):
            BaselineComparison()

    def test_instantiates_with_required_fields(self):
        bm = BaselineMetrics(metric_name="latency")
        bc = BaselineComparison(metric_name="latency", baseline=bm)
        assert bc.metric_name == "latency"


class TestRegressionResultContract:
    def test_requires_metric_name(self):
        with pytest.raises((ValidationError, TypeError)):
            RegressionResult()

    def test_instantiates_with_required_fields(self):
        rr = RegressionResult(metric_name="throughput")
        assert rr.metric_name == "throughput"


class TestAnomalyReportContract:
    def test_requires_period_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            AnomalyReport()

    def test_instantiates_with_required_fields(self):
        report = AnomalyReport(
            analysis_period_start="2026-05-01T00:00:00",
            analysis_period_end="2026-05-31T23:59:59",
        )
        assert hasattr(report, "analysis_period_start")

    def test_has_model_fields(self):
        assert "analysis_period_start" in AnomalyReport.model_fields


# ---------------------------------------------------------------------------
# Analysis Models
# ---------------------------------------------------------------------------
class TestApdexConfigContract:
    def test_instantiates_with_defaults(self):
        config = ApdexConfig()
        assert config is not None

    def test_has_threshold_ms_field(self):
        config = ApdexConfig()
        assert hasattr(config, "threshold_ms")

    def test_has_frustration_multiplier_field(self):
        config = ApdexConfig()
        assert hasattr(config, "frustration_multiplier")


class TestApdexResultContract:
    def test_requires_multiple_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ApdexResult()

    def test_instantiates_with_required_fields(self):
        result = ApdexResult(
            score=0.92,
            satisfied_count=900,
            tolerating_count=80,
            frustrated_count=20,
            total_count=1000,
            threshold_ms=500,
            rating="Excellent",
        )
        assert result.score == 0.92

    def test_has_total_count_field(self):
        fields = set(ApdexResult.model_fields.keys())
        assert "total_count" in fields


class TestSLAConfigContract:
    def test_requires_threshold_ms(self):
        with pytest.raises((ValidationError, TypeError)):
            SLAConfig()

    def test_instantiates_with_threshold(self):
        config = SLAConfig(threshold_ms=200)
        assert config.threshold_ms == 200

    def test_has_availability_target_field(self):
        config = SLAConfig(threshold_ms=200)
        assert hasattr(config, "availability_target")


class TestSLAResultContract:
    def test_requires_multiple_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            SLAResult()

    def test_instantiates_with_required_fields(self):
        result = SLAResult(
            status=SLAStatus.COMPLIANT,
            percentile_value=180.0,
            percentile_target=95.0,
            threshold_ms=200,
            margin_percent=10.0,
        )
        assert result.status == SLAStatus.COMPLIANT

    def test_has_violations_field(self):
        result = SLAResult(
            status=SLAStatus.COMPLIANT,
            percentile_value=180.0,
            percentile_target=95.0,
            threshold_ms=200,
            margin_percent=10.0,
        )
        assert hasattr(result, "violations")


class TestPercentileResultContract:
    def test_requires_all_stat_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            PercentileResult()

    def test_instantiates_with_required_fields(self):
        result = PercentileResult(
            sample_count=1000,
            min_value=10.0,
            max_value=2000.0,
            mean=150.0,
            median=120.0,
            std_dev=50.0,
            p50=120.0,
            p75=200.0,
            p90=400.0,
            p95=600.0,
            p99=900.0,
            p999=1800.0,
        )
        assert result.sample_count == 1000
        assert result.p99 == 900.0


class TestAggregationConfigContract:
    def test_instantiates_with_defaults(self):
        config = AggregationConfig()
        assert config is not None

    def test_has_model_fields(self):
        assert hasattr(AggregationConfig, "model_fields")


class TestAggregationResultContract:
    def test_requires_multiple_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            AggregationResult()

    def test_instantiates_with_required_fields(self):
        result = AggregationResult(
            window_start="2026-05-01T00:00:00",
            window_end="2026-05-01T01:00:00",
            sample_count=500,
            sum_value=75000.0,
            mean=150.0,
            min_value=10.0,
            max_value=2000.0,
            throughput=8.33,
        )
        assert result.sample_count == 500


class TestTrendResultContract:
    def test_requires_multiple_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TrendResult()

    def test_instantiates_with_required_fields(self):
        result = TrendResult(
            direction=TrendDirection.IMPROVING,
            slope=-0.5,
            change_percent=-5.0,
            confidence=0.95,
            data_points=100,
            period_seconds=3600,
            baseline_value=200.0,
            current_value=190.0,
        )
        assert result.direction == TrendDirection.IMPROVING

    def test_has_confidence_field(self):
        fields = set(TrendResult.model_fields.keys())
        assert "confidence" in fields
