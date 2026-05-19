"""
Comprehensive L0 Unit Tests for Verdandi Anomaly Models

Tests all Pydantic models in the Anomaly module including:
- AnomalyDetection
- BaselineMetrics
- BaselineComparison
- RegressionResult
- AnomalyReport
- Enums (AnomalyType, AnomalySeverity)
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from Asgard.Verdandi.Anomaly.models.anomaly_models import (
    AnomalyDetection,
    AnomalyType,
    AnomalySeverity,
    BaselineMetrics,
    BaselineComparison,
    RegressionResult,
    AnomalyReport,
)


class TestAnomalyType:
    """Tests for AnomalyType enum."""

    def test_anomaly_type_values(self):
        """Test all AnomalyType enum values."""
        assert AnomalyType.SPIKE.value == "spike"
        assert AnomalyType.DROP.value == "drop"
        assert AnomalyType.TREND_CHANGE.value == "trend_change"
        assert AnomalyType.OUTLIER.value == "outlier"
        assert AnomalyType.PATTERN_BREAK.value == "pattern_break"
        assert AnomalyType.REGRESSION.value == "regression"


class TestAnomalySeverity:
    """Tests for AnomalySeverity enum."""

    def test_anomaly_severity_values(self):
        """Test all AnomalySeverity enum values."""
        assert AnomalySeverity.CRITICAL.value == "critical"
        assert AnomalySeverity.HIGH.value == "high"
        assert AnomalySeverity.MEDIUM.value == "medium"
        assert AnomalySeverity.LOW.value == "low"
        assert AnomalySeverity.INFO.value == "info"


class TestAnomalyDetection:
    """Tests for AnomalyDetection model."""

    def test_anomaly_detection_creation_minimal(self):
        """Test creating AnomalyDetection with minimal required fields."""
        now = datetime.now()
        anomaly = AnomalyDetection(
            detected_at=now,
            data_timestamp=now,
            anomaly_type=AnomalyType.SPIKE,
            severity=AnomalySeverity.HIGH,
            metric_name="cpu_usage",
            actual_value=95.0,
            expected_value=50.0,
            deviation=45.0,
            deviation_percent=90.0,
        )

        assert anomaly.metric_name == "cpu_usage"
        assert anomaly.actual_value == 95.0
        assert anomaly.expected_value == 50.0
        assert anomaly.severity == AnomalySeverity.HIGH

    def test_anomaly_detection_with_optional_fields(self):
        """Test AnomalyDetection with all optional fields."""
        now = datetime.now()
        anomaly = AnomalyDetection(
            detected_at=now,
            data_timestamp=now,
            anomaly_type=AnomalyType.OUTLIER,
            severity=AnomalySeverity.CRITICAL,
            metric_name="latency",
            actual_value=5000.0,
            expected_value=200.0,
            deviation=4800.0,
            deviation_percent=2400.0,
            z_score=5.5,
            confidence=0.99,
            context={"method": "zscore", "threshold": 3.0},
            description="Extreme latency spike detected",
        )

        assert anomaly.z_score == 5.5
        assert anomaly.confidence == 0.99
        assert anomaly.context["method"] == "zscore"
        assert anomaly.description == "Extreme latency spike detected"

    def test_anomaly_detection_confidence_validation_upper(self):
        """Test that confidence must be <= 1.0."""
        now = datetime.now()
        with pytest.raises(ValidationError):
            AnomalyDetection(
                detected_at=now,
                data_timestamp=now,
                anomaly_type=AnomalyType.SPIKE,
                severity=AnomalySeverity.HIGH,
                metric_name="test",
                actual_value=100.0,
                expected_value=50.0,
                deviation=50.0,
                deviation_percent=100.0,
                confidence=1.5,  # Invalid: > 1.0
            )

    def test_anomaly_detection_confidence_validation_lower(self):
        """Test that confidence must be >= 0.0."""
        now = datetime.now()
        with pytest.raises(ValidationError):
            AnomalyDetection(
                detected_at=now,
                data_timestamp=now,
                anomaly_type=AnomalyType.DROP,
                severity=AnomalySeverity.LOW,
                metric_name="test",
                actual_value=10.0,
                expected_value=50.0,
                deviation=40.0,
                deviation_percent=80.0,
                confidence=-0.1,  # Invalid: < 0.0
            )

    def test_anomaly_detection_negative_deviation(self):
        """Test AnomalyDetection with negative deviation (valid for drops)."""
        now = datetime.now()
        anomaly = AnomalyDetection(
            detected_at=now,
            data_timestamp=now,
            anomaly_type=AnomalyType.DROP,
            severity=AnomalySeverity.MEDIUM,
            metric_name="throughput",
            actual_value=100.0,
            expected_value=200.0,
            deviation=-100.0,
            deviation_percent=-50.0,
        )

        assert anomaly.deviation == -100.0
        assert anomaly.deviation_percent == -50.0


class TestBaselineMetrics:
    """Tests for BaselineMetrics model."""

    def test_baseline_metrics_creation_minimal(self):
        """Test creating BaselineMetrics with minimal fields."""
        baseline = BaselineMetrics(
            metric_name="response_time",
        )

        assert baseline.metric_name == "response_time"
        assert baseline.sample_count == 0
        assert baseline.baseline_period_days == 7
        assert not baseline.is_valid  # Not enough samples

    def test_baseline_metrics_creation_complete(self):
        """Test creating BaselineMetrics with all fields."""
        baseline = BaselineMetrics(
            metric_name="latency",
            sample_count=1000,
            baseline_period_days=14,
            mean=150.0,
            median=140.0,
            std_dev=30.0,
            min_value=50.0,
            max_value=500.0,
            p5=80.0,
            p25=120.0,
            p75=170.0,
            p95=220.0,
            p99=280.0,
            iqr=50.0,
            lower_fence=45.0,
            upper_fence=245.0,
        )

        assert baseline.sample_count == 1000
        assert baseline.mean == 150.0
        assert baseline.iqr == 50.0
        assert baseline.is_valid  # Enough samples and std_dev > 0

    def test_baseline_metrics_is_valid_property(self):
        """Test the is_valid property logic."""
        # Invalid: too few samples
        baseline = BaselineMetrics(
            metric_name="test",
            sample_count=5,
            std_dev=10.0,
        )
        assert not baseline.is_valid

        # Invalid: std_dev is 0
        baseline = BaselineMetrics(
            metric_name="test",
            sample_count=100,
            std_dev=0.0,
        )
        assert not baseline.is_valid

        # Valid: enough samples and std_dev > 0
        baseline = BaselineMetrics(
            metric_name="test",
            sample_count=100,
            std_dev=10.0,
        )
        assert baseline.is_valid

    def test_baseline_metrics_calculated_at_default(self):
        """Test that calculated_at has a default value."""
        baseline = BaselineMetrics(metric_name="test")

        assert baseline.calculated_at is not None
        assert isinstance(baseline.calculated_at, datetime)


class TestBaselineComparison:
    """Tests for BaselineComparison model."""

    def test_baseline_comparison_creation(self):
        """Test creating a BaselineComparison."""
        baseline = BaselineMetrics(
            metric_name="latency",
            sample_count=100,
            mean=150.0,
            median=140.0,
            std_dev=30.0,
            p99=280.0,
        )

        comparison = BaselineComparison(
            metric_name="latency",
            baseline=baseline,
            current_mean=180.0,
            current_median=170.0,
            current_p99=320.0,
            sample_count=50,
            mean_change_percent=20.0,
            median_change_percent=21.4,
            p99_change_percent=14.3,
            is_significant=True,
            overall_status="degraded",
        )

        assert comparison.current_mean == 180.0
        assert comparison.mean_change_percent == 20.0
        assert comparison.is_significant is True

    def test_baseline_comparison_with_anomalies(self):
        """Test BaselineComparison with detected anomalies."""
        baseline = BaselineMetrics(metric_name="test", sample_count=10)
        now = datetime.now()

        anomaly = AnomalyDetection(
            detected_at=now,
            data_timestamp=now,
            anomaly_type=AnomalyType.SPIKE,
            severity=AnomalySeverity.HIGH,
            metric_name="test",
            actual_value=200.0,
            expected_value=100.0,
            deviation=100.0,
            deviation_percent=100.0,
        )

        comparison = BaselineComparison(
            metric_name="test",
            baseline=baseline,
            anomalies_detected=[anomaly],
        )

        assert len(comparison.anomalies_detected) == 1
        assert comparison.anomalies_detected[0].severity == AnomalySeverity.HIGH

    def test_baseline_comparison_with_recommendations(self):
        """Test BaselineComparison with recommendations."""
        baseline = BaselineMetrics(metric_name="test", sample_count=10)

        comparison = BaselineComparison(
            metric_name="test",
            baseline=baseline,
            recommendations=[
                "Investigate recent deployments",
                "Check for external dependencies",
            ],
        )

        assert len(comparison.recommendations) == 2


class TestRegressionResult:
    """Tests for RegressionResult model."""

    def test_regression_result_creation_minimal(self):
        """Test creating RegressionResult with minimal fields."""
        result = RegressionResult(
            metric_name="api_latency",
        )

        assert result.metric_name == "api_latency"
        assert result.is_regression is False
        assert result.regression_severity == AnomalySeverity.INFO

    def test_regression_result_creation_complete(self):
        """Test creating RegressionResult with all fields."""
        result = RegressionResult(
            metric_name="response_time",
            before_mean=100.0,
            after_mean=150.0,
            before_p99=200.0,
            after_p99=300.0,
            before_sample_count=500,
            after_sample_count=500,
            mean_change_percent=50.0,
            p99_change_percent=50.0,
            is_regression=True,
            regression_severity=AnomalySeverity.HIGH,
            confidence=0.95,
            t_statistic=5.2,
            p_value=0.001,
            effect_size=0.8,
            description="Significant performance regression detected",
            recommendations=[
                "Rollback recent deployment",
                "Review code changes",
            ],
        )

        assert result.is_regression is True
        assert result.regression_severity == AnomalySeverity.HIGH
        assert result.t_statistic == 5.2
        assert result.p_value == 0.001
        assert len(result.recommendations) == 2

    def test_regression_result_confidence_validation(self):
        """Test that confidence is properly validated."""
        # Valid confidence
        result = RegressionResult(
            metric_name="test",
            confidence=0.95,
        )
        assert result.confidence == 0.95

        # Invalid confidence > 1.0
        with pytest.raises(ValidationError):
            RegressionResult(
                metric_name="test",
                confidence=1.5,
            )

        # Invalid confidence < 0.0
        with pytest.raises(ValidationError):
            RegressionResult(
                metric_name="test",
                confidence=-0.1,
            )

    def test_regression_result_negative_change(self):
        """Test RegressionResult with improvement (negative change)."""
        result = RegressionResult(
            metric_name="latency",
            before_mean=200.0,
            after_mean=150.0,
            mean_change_percent=-25.0,
            is_regression=False,
        )

        assert result.mean_change_percent == -25.0
        assert result.is_regression is False


class TestAnomalyReport:
    """Tests for AnomalyReport model."""

    def test_anomaly_report_creation_minimal(self):
        """Test creating AnomalyReport with minimal fields."""
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now()

        report = AnomalyReport(
            analysis_period_start=start,
            analysis_period_end=end,
        )

        assert report.metrics_analyzed == 0
        assert report.total_anomalies == 0
        assert report.health_status == "healthy"

    def test_anomaly_report_creation_complete(self):
        """Test creating AnomalyReport with all fields."""
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now()
        now = datetime.now()

        anomaly = AnomalyDetection(
            detected_at=now,
            data_timestamp=now,
            anomaly_type=AnomalyType.SPIKE,
            severity=AnomalySeverity.CRITICAL,
            metric_name="cpu",
            actual_value=100.0,
            expected_value=50.0,
            deviation=50.0,
            deviation_percent=100.0,
        )

        baseline = BaselineMetrics(metric_name="cpu", sample_count=100)
        comparison = BaselineComparison(
            metric_name="cpu",
            baseline=baseline,
        )

        regression = RegressionResult(
            metric_name="latency",
            is_regression=True,
        )

        report = AnomalyReport(
            analysis_period_start=start,
            analysis_period_end=end,
            metrics_analyzed=5,
            data_points_analyzed=10000,
            anomalies=[anomaly],
            baseline_comparisons=[comparison],
            regressions=[regression],
            total_anomalies=1,
            critical_anomalies=1,
            high_anomalies=0,
            medium_anomalies=0,
            low_anomalies=0,
            anomaly_rate=0.0001,
            health_status="critical",
            recommendations=["Investigate CPU spike"],
        )

        assert report.total_anomalies == 1
        assert report.critical_anomalies == 1
        assert len(report.anomalies) == 1
        assert report.health_status == "critical"

    def test_anomaly_report_has_critical_issues_property(self):
        """Test the has_critical_issues property."""
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now()
        now = datetime.now()

        # No critical issues
        report = AnomalyReport(
            analysis_period_start=start,
            analysis_period_end=end,
        )
        assert not report.has_critical_issues

        # Critical anomaly
        anomaly = AnomalyDetection(
            detected_at=now,
            data_timestamp=now,
            anomaly_type=AnomalyType.SPIKE,
            severity=AnomalySeverity.CRITICAL,
            metric_name="test",
            actual_value=100.0,
            expected_value=50.0,
            deviation=50.0,
            deviation_percent=100.0,
        )

        report = AnomalyReport(
            analysis_period_start=start,
            analysis_period_end=end,
            anomalies=[anomaly],
            critical_anomalies=1,
        )
        assert report.has_critical_issues

        # Critical regression
        regression = RegressionResult(
            metric_name="test",
            is_regression=True,
            regression_severity=AnomalySeverity.CRITICAL,
        )

        report = AnomalyReport(
            analysis_period_start=start,
            analysis_period_end=end,
            regressions=[regression],
        )
        assert report.has_critical_issues

    def test_anomaly_report_severity_breakdown(self):
        """Test anomaly severity breakdown in report."""
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now()

        report = AnomalyReport(
            analysis_period_start=start,
            analysis_period_end=end,
            total_anomalies=10,
            critical_anomalies=2,
            high_anomalies=3,
            medium_anomalies=3,
            low_anomalies=2,
        )

        assert report.total_anomalies == 10
        assert report.critical_anomalies == 2
        assert report.high_anomalies == 3
        assert report.medium_anomalies == 3
        assert report.low_anomalies == 2
