"""
Comprehensive L0 Unit Tests for Verdandi Analysis Models

Tests all Pydantic models in the Analysis module including:
- PercentileResult
- ApdexConfig and ApdexResult
- SLAConfig and SLAResult
- AggregationConfig and AggregationResult
- TrendResult
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from Asgard.Verdandi.Analysis.models.analysis_models import (
    PercentileResult,
    ApdexConfig,
    ApdexResult,
    SLAConfig,
    SLAResult,
    SLAStatus,
    AggregationConfig,
    AggregationResult,
    TrendResult,
    TrendDirection,
)


class TestPercentileResult:
    """Tests for PercentileResult model."""

    def test_percentile_result_creation_valid(self):
        """Test creating a valid PercentileResult."""
        result = PercentileResult(
            sample_count=100,
            min_value=10.0,
            max_value=500.0,
            mean=150.0,
            median=140.0,
            std_dev=50.0,
            p50=140.0,
            p75=180.0,
            p90=220.0,
            p95=250.0,
            p99=300.0,
            p999=450.0,
        )

        assert result.sample_count == 100
        assert result.min_value == 10.0
        assert result.max_value == 500.0
        assert result.mean == 150.0
        assert result.p99 == 300.0

    def test_percentile_result_range_property(self):
        """Test the range property calculation."""
        result = PercentileResult(
            sample_count=10,
            min_value=50.0,
            max_value=200.0,
            mean=125.0,
            median=120.0,
            std_dev=40.0,
            p50=120.0,
            p75=150.0,
            p90=180.0,
            p95=190.0,
            p99=195.0,
            p999=198.0,
        )

        assert result.range == 150.0  # 200 - 50

    def test_percentile_result_negative_values(self):
        """Test PercentileResult with negative values (valid for some metrics)."""
        result = PercentileResult(
            sample_count=10,
            min_value=-100.0,
            max_value=100.0,
            mean=0.0,
            median=5.0,
            std_dev=60.0,
            p50=5.0,
            p75=50.0,
            p90=80.0,
            p95=90.0,
            p99=95.0,
            p999=98.0,
        )

        assert result.min_value == -100.0
        assert result.range == 200.0

    def test_percentile_result_zero_values(self):
        """Test PercentileResult with all zero values."""
        result = PercentileResult(
            sample_count=10,
            min_value=0.0,
            max_value=0.0,
            mean=0.0,
            median=0.0,
            std_dev=0.0,
            p50=0.0,
            p75=0.0,
            p90=0.0,
            p95=0.0,
            p99=0.0,
            p999=0.0,
        )

        assert result.range == 0.0
        assert result.std_dev == 0.0


class TestApdexConfig:
    """Tests for ApdexConfig model."""

    def test_apdex_config_defaults(self):
        """Test ApdexConfig with default values."""
        config = ApdexConfig()

        assert config.threshold_ms == 500.0
        assert config.frustration_multiplier == 4.0
        assert config.frustration_threshold_ms == 2000.0

    def test_apdex_config_custom_values(self):
        """Test ApdexConfig with custom values."""
        config = ApdexConfig(
            threshold_ms=300.0,
            frustration_multiplier=3.0,
        )

        assert config.threshold_ms == 300.0
        assert config.frustration_multiplier == 3.0
        assert config.frustration_threshold_ms == 900.0

    def test_apdex_config_frustration_threshold_calculation(self):
        """Test frustration threshold property calculation."""
        config = ApdexConfig(threshold_ms=1000.0, frustration_multiplier=5.0)

        assert config.frustration_threshold_ms == 5000.0

    def test_apdex_config_zero_threshold(self):
        """Test ApdexConfig with zero threshold (edge case)."""
        config = ApdexConfig(threshold_ms=0.0)

        assert config.frustration_threshold_ms == 0.0


class TestApdexResult:
    """Tests for ApdexResult model."""

    def test_apdex_result_creation_valid(self):
        """Test creating a valid ApdexResult."""
        result = ApdexResult(
            score=0.92,
            satisfied_count=85,
            tolerating_count=10,
            frustrated_count=5,
            total_count=100,
            threshold_ms=500.0,
            rating="Excellent",
        )

        assert result.score == 0.92
        assert result.satisfied_count == 85
        assert result.total_count == 100
        assert result.rating == "Excellent"

    def test_apdex_result_score_validation_upper_bound(self):
        """Test that score must be <= 1.0."""
        with pytest.raises(ValidationError):
            ApdexResult(
                score=1.5,  # Invalid: > 1.0
                satisfied_count=100,
                tolerating_count=0,
                frustrated_count=0,
                total_count=100,
                threshold_ms=500.0,
                rating="Excellent",
            )

    def test_apdex_result_score_validation_lower_bound(self):
        """Test that score must be >= 0.0."""
        with pytest.raises(ValidationError):
            ApdexResult(
                score=-0.1,  # Invalid: < 0.0
                satisfied_count=0,
                tolerating_count=0,
                frustrated_count=100,
                total_count=100,
                threshold_ms=500.0,
                rating="Unacceptable",
            )

    def test_apdex_result_get_rating_excellent(self):
        """Test rating classification for excellent score."""
        rating = ApdexResult.get_rating(0.95)
        assert rating == "Excellent"

    def test_apdex_result_get_rating_good(self):
        """Test rating classification for good score."""
        rating = ApdexResult.get_rating(0.88)
        assert rating == "Good"

    def test_apdex_result_get_rating_fair(self):
        """Test rating classification for fair score."""
        rating = ApdexResult.get_rating(0.75)
        assert rating == "Fair"

    def test_apdex_result_get_rating_poor(self):
        """Test rating classification for poor score."""
        rating = ApdexResult.get_rating(0.55)
        assert rating == "Poor"

    def test_apdex_result_get_rating_unacceptable(self):
        """Test rating classification for unacceptable score."""
        rating = ApdexResult.get_rating(0.40)
        assert rating == "Unacceptable"

    def test_apdex_result_get_rating_boundary_excellent(self):
        """Test rating boundary at 0.94."""
        assert ApdexResult.get_rating(0.94) == "Excellent"
        assert ApdexResult.get_rating(0.93) == "Good"

    def test_apdex_result_perfect_score(self):
        """Test ApdexResult with perfect score."""
        result = ApdexResult(
            score=1.0,
            satisfied_count=100,
            tolerating_count=0,
            frustrated_count=0,
            total_count=100,
            threshold_ms=500.0,
            rating="Excellent",
        )

        assert result.score == 1.0
        assert result.frustrated_count == 0


class TestSLAConfig:
    """Tests for SLAConfig model."""

    def test_sla_config_minimal(self):
        """Test SLAConfig with minimal required fields."""
        config = SLAConfig(threshold_ms=1000.0)

        assert config.threshold_ms == 1000.0
        assert config.target_percentile == 95.0
        assert config.warning_threshold_percent == 90.0
        assert config.availability_target == 99.9
        assert config.error_rate_threshold == 1.0

    def test_sla_config_custom_values(self):
        """Test SLAConfig with all custom values."""
        config = SLAConfig(
            target_percentile=99.0,
            threshold_ms=500.0,
            warning_threshold_percent=85.0,
            availability_target=99.95,
            error_rate_threshold=0.5,
        )

        assert config.target_percentile == 99.0
        assert config.threshold_ms == 500.0
        assert config.warning_threshold_percent == 85.0
        assert config.availability_target == 99.95
        assert config.error_rate_threshold == 0.5


class TestSLAResult:
    """Tests for SLAResult model."""

    def test_sla_result_compliant(self):
        """Test SLAResult for compliant status."""
        result = SLAResult(
            status=SLAStatus.COMPLIANT,
            percentile_value=450.0,
            percentile_target=95.0,
            threshold_ms=500.0,
            margin_percent=10.0,
        )

        assert result.status == SLAStatus.COMPLIANT
        assert result.percentile_value == 450.0
        assert result.margin_percent == 10.0

    def test_sla_result_warning(self):
        """Test SLAResult for warning status."""
        result = SLAResult(
            status=SLAStatus.WARNING,
            percentile_value=480.0,
            percentile_target=95.0,
            threshold_ms=500.0,
            margin_percent=4.0,
            violations=["Approaching SLA threshold"],
        )

        assert result.status == SLAStatus.WARNING
        assert len(result.violations) == 1

    def test_sla_result_breached(self):
        """Test SLAResult for breached status."""
        result = SLAResult(
            status=SLAStatus.BREACHED,
            percentile_value=550.0,
            percentile_target=95.0,
            threshold_ms=500.0,
            margin_percent=-10.0,
            violations=["P95 exceeds threshold by 50ms"],
        )

        assert result.status == SLAStatus.BREACHED
        assert result.margin_percent < 0
        assert len(result.violations) > 0

    def test_sla_result_with_availability_and_error_rate(self):
        """Test SLAResult with optional availability and error rate."""
        result = SLAResult(
            status=SLAStatus.COMPLIANT,
            percentile_value=400.0,
            percentile_target=95.0,
            threshold_ms=500.0,
            margin_percent=20.0,
            availability_actual=99.95,
            error_rate_actual=0.05,
        )

        assert result.availability_actual == 99.95
        assert result.error_rate_actual == 0.05


class TestAggregationConfig:
    """Tests for AggregationConfig model."""

    def test_aggregation_config_defaults(self):
        """Test AggregationConfig with default values."""
        config = AggregationConfig()

        assert config.window_size_seconds == 60
        assert config.include_percentiles is True
        assert config.include_histograms is False
        assert len(config.histogram_buckets) == 10

    def test_aggregation_config_custom_window(self):
        """Test AggregationConfig with custom window size."""
        config = AggregationConfig(window_size_seconds=300)

        assert config.window_size_seconds == 300

    def test_aggregation_config_custom_buckets(self):
        """Test AggregationConfig with custom histogram buckets."""
        custom_buckets = [50, 100, 200, 500, 1000]
        config = AggregationConfig(
            include_histograms=True,
            histogram_buckets=custom_buckets,
        )

        assert config.include_histograms is True
        assert config.histogram_buckets == custom_buckets


class TestAggregationResult:
    """Tests for AggregationResult model."""

    def test_aggregation_result_basic(self):
        """Test creating a basic AggregationResult."""
        result = AggregationResult(
            window_start="2024-01-01T00:00:00Z",
            window_end="2024-01-01T00:01:00Z",
            sample_count=100,
            sum_value=15000.0,
            mean=150.0,
            min_value=50.0,
            max_value=500.0,
            throughput=1.67,
        )

        assert result.sample_count == 100
        assert result.mean == 150.0
        assert result.throughput == 1.67

    def test_aggregation_result_with_percentiles(self):
        """Test AggregationResult with percentiles."""
        percentiles = PercentileResult(
            sample_count=100,
            min_value=50.0,
            max_value=500.0,
            mean=150.0,
            median=140.0,
            std_dev=50.0,
            p50=140.0,
            p75=180.0,
            p90=220.0,
            p95=250.0,
            p99=300.0,
            p999=450.0,
        )

        result = AggregationResult(
            window_start="2024-01-01T00:00:00Z",
            window_end="2024-01-01T00:01:00Z",
            sample_count=100,
            sum_value=15000.0,
            mean=150.0,
            min_value=50.0,
            max_value=500.0,
            throughput=1.67,
            percentiles=percentiles,
        )

        assert result.percentiles is not None
        assert result.percentiles.p99 == 300.0

    def test_aggregation_result_with_histogram(self):
        """Test AggregationResult with histogram data."""
        histogram = {
            "<=50": 10,
            "50-100": 20,
            "100-250": 40,
            "250-500": 25,
            ">500": 5,
        }

        result = AggregationResult(
            window_start="2024-01-01T00:00:00Z",
            window_end="2024-01-01T00:01:00Z",
            sample_count=100,
            sum_value=15000.0,
            mean=150.0,
            min_value=50.0,
            max_value=500.0,
            throughput=1.67,
            histogram=histogram,
        )

        assert result.histogram is not None
        assert result.histogram["100-250"] == 40


class TestTrendResult:
    """Tests for TrendResult model."""

    def test_trend_result_improving(self):
        """Test TrendResult for improving trend."""
        result = TrendResult(
            direction=TrendDirection.IMPROVING,
            slope=-0.5,
            change_percent=-10.0,
            confidence=0.85,
            data_points=100,
            period_seconds=86400,
            baseline_value=200.0,
            current_value=180.0,
        )

        assert result.direction == TrendDirection.IMPROVING
        assert result.slope == -0.5
        assert result.change_percent == -10.0
        assert result.confidence == 0.85

    def test_trend_result_degrading(self):
        """Test TrendResult for degrading trend."""
        result = TrendResult(
            direction=TrendDirection.DEGRADING,
            slope=1.2,
            change_percent=25.0,
            confidence=0.92,
            data_points=200,
            period_seconds=604800,
            baseline_value=150.0,
            current_value=187.5,
            anomalies_detected=3,
        )

        assert result.direction == TrendDirection.DEGRADING
        assert result.slope > 0
        assert result.anomalies_detected == 3

    def test_trend_result_stable(self):
        """Test TrendResult for stable trend."""
        result = TrendResult(
            direction=TrendDirection.STABLE,
            slope=0.05,
            change_percent=1.0,
            confidence=0.65,
            data_points=50,
            period_seconds=3600,
            baseline_value=100.0,
            current_value=101.0,
        )

        assert result.direction == TrendDirection.STABLE
        assert abs(result.slope) < 0.1

    def test_trend_result_confidence_bounds(self):
        """Test TrendResult confidence validation."""
        # Valid confidence values
        result = TrendResult(
            direction=TrendDirection.STABLE,
            slope=0.0,
            change_percent=0.0,
            confidence=0.0,
            data_points=10,
            period_seconds=60,
            baseline_value=100.0,
            current_value=100.0,
        )
        assert result.confidence == 0.0

        result = TrendResult(
            direction=TrendDirection.STABLE,
            slope=0.0,
            change_percent=0.0,
            confidence=1.0,
            data_points=10,
            period_seconds=60,
            baseline_value=100.0,
            current_value=100.0,
        )
        assert result.confidence == 1.0

        # Invalid confidence
        with pytest.raises(ValidationError):
            TrendResult(
                direction=TrendDirection.STABLE,
                slope=0.0,
                change_percent=0.0,
                confidence=1.5,  # Invalid: > 1.0
                data_points=10,
                period_seconds=60,
                baseline_value=100.0,
                current_value=100.0,
            )


class TestEnumValues:
    """Tests for enum types."""

    def test_sla_status_enum(self):
        """Test SLAStatus enum values."""
        assert SLAStatus.COMPLIANT.value == "compliant"
        assert SLAStatus.WARNING.value == "warning"
        assert SLAStatus.BREACHED.value == "breached"

    def test_trend_direction_enum(self):
        """Test TrendDirection enum values."""
        assert TrendDirection.IMPROVING.value == "improving"
        assert TrendDirection.STABLE.value == "stable"
        assert TrendDirection.DEGRADING.value == "degrading"
