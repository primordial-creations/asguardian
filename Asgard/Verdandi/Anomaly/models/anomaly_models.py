"""
Anomaly Models

Pydantic models for anomaly detection including statistical anomalies,
baseline comparisons, and regression detection.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    """Type of anomaly detected."""

    SPIKE = "spike"
    DROP = "drop"
    TREND_CHANGE = "trend_change"
    OUTLIER = "outlier"
    PATTERN_BREAK = "pattern_break"
    REGRESSION = "regression"


class AnomalySeverity(str, Enum):
    """Severity of detected anomaly."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AnomalyDetection(BaseModel):
    """
    Result of anomaly detection for a single data point or period.
    """

    detected_at: datetime = Field(..., description="When the anomaly was detected")
    data_timestamp: datetime = Field(
        ..., description="Timestamp of the anomalous data"
    )
    anomaly_type: AnomalyType = Field(..., description="Type of anomaly")
    severity: AnomalySeverity = Field(..., description="Severity of the anomaly")
    metric_name: str = Field(..., description="Name of the metric")
    actual_value: float = Field(..., description="Actual observed value")
    expected_value: float = Field(..., description="Expected/baseline value")
    deviation: float = Field(
        ..., description="Deviation from expected (absolute)"
    )
    deviation_percent: float = Field(
        ..., description="Deviation as percentage of expected"
    )
    z_score: Optional[float] = Field(
        default=None, description="Z-score of the anomaly"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the anomaly detection (0-1)",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )
    description: str = Field(default="", description="Human-readable description")


class BaselineMetrics(BaseModel):
    """
    Baseline metrics for comparison.

    Captures statistical properties of normal behavior.
    """

    metric_name: str = Field(..., description="Name of the metric")
    calculated_at: datetime = Field(
        default_factory=datetime.now, description="When baseline was calculated"
    )
    sample_count: int = Field(default=0, description="Number of samples in baseline")
    baseline_period_days: int = Field(
        default=7, description="Period used for baseline calculation"
    )
    mean: float = Field(default=0.0, description="Mean value")
    median: float = Field(default=0.0, description="Median value")
    std_dev: float = Field(default=0.0, description="Standard deviation")
    min_value: float = Field(default=0.0, description="Minimum value")
    max_value: float = Field(default=0.0, description="Maximum value")
    p5: float = Field(default=0.0, description="5th percentile")
    p25: float = Field(default=0.0, description="25th percentile (Q1)")
    p75: float = Field(default=0.0, description="75th percentile (Q3)")
    p95: float = Field(default=0.0, description="95th percentile")
    p99: float = Field(default=0.0, description="99th percentile")
    iqr: float = Field(default=0.0, description="Interquartile range (Q3 - Q1)")
    lower_fence: float = Field(
        default=0.0, description="Lower fence for outlier detection (Q1 - 1.5*IQR)"
    )
    upper_fence: float = Field(
        default=0.0, description="Upper fence for outlier detection (Q3 + 1.5*IQR)"
    )

    @property
    def is_valid(self) -> bool:
        """Check if baseline has enough data."""
        return self.sample_count >= 10 and self.std_dev > 0


class BaselineComparison(BaseModel):
    """
    Result of comparing current data against a baseline.
    """

    compared_at: datetime = Field(
        default_factory=datetime.now, description="Comparison timestamp"
    )
    metric_name: str = Field(..., description="Name of the metric")
    baseline: BaselineMetrics = Field(..., description="Baseline used for comparison")
    current_mean: float = Field(default=0.0, description="Current mean value")
    current_median: float = Field(default=0.0, description="Current median value")
    current_p99: float = Field(default=0.0, description="Current P99 value")
    sample_count: int = Field(default=0, description="Current sample count")
    mean_change_percent: float = Field(
        default=0.0, description="Percentage change in mean"
    )
    median_change_percent: float = Field(
        default=0.0, description="Percentage change in median"
    )
    p99_change_percent: float = Field(
        default=0.0, description="Percentage change in P99"
    )
    is_significant: bool = Field(
        default=False, description="Whether change is statistically significant"
    )
    anomalies_detected: List[AnomalyDetection] = Field(
        default_factory=list, description="Anomalies found in comparison"
    )
    overall_status: str = Field(
        default="normal", description="Overall comparison status"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations based on comparison"
    )


class RegressionResult(BaseModel):
    """
    Result of performance regression detection.
    """

    detected_at: datetime = Field(
        default_factory=datetime.now, description="Detection timestamp"
    )
    metric_name: str = Field(..., description="Name of the metric")
    before_mean: float = Field(default=0.0, description="Mean before change point")
    after_mean: float = Field(default=0.0, description="Mean after change point")
    before_p99: float = Field(default=0.0, description="P99 before change point")
    after_p99: float = Field(default=0.0, description="P99 after change point")
    before_sample_count: int = Field(
        default=0, description="Sample count before change"
    )
    after_sample_count: int = Field(default=0, description="Sample count after change")
    mean_change_percent: float = Field(
        default=0.0, description="Percentage change in mean"
    )
    p99_change_percent: float = Field(
        default=0.0, description="Percentage change in P99"
    )
    is_regression: bool = Field(
        default=False, description="Whether a regression was detected"
    )
    regression_severity: AnomalySeverity = Field(
        default=AnomalySeverity.INFO, description="Severity of regression"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in regression detection",
    )
    t_statistic: Optional[float] = Field(
        default=None, description="T-statistic from statistical test"
    )
    p_value: Optional[float] = Field(
        default=None, description="P-value from statistical test"
    )
    effect_size: Optional[float] = Field(
        default=None, description="Cohen's d effect size"
    )
    hl_shift: Optional[float] = Field(
        default=None,
        description="Hodges-Lehmann location shift (median of pairwise diffs)",
    )
    hl_shift_relative: Optional[float] = Field(
        default=None,
        description="HL shift relative to the baseline pseudo-median",
    )
    glass_delta: Optional[float] = Field(
        default=None,
        description="Glass's delta effect size (baseline-sigma standardized)",
    )
    verdict_basis: Optional[str] = Field(
        default=None,
        description="Which gates (statistical/practical/magnitude) drove the verdict",
    )
    description: str = Field(default="", description="Human-readable description")
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations"
    )


class AnomalyReport(BaseModel):
    """Comprehensive anomaly detection report."""

    generated_at: datetime = Field(
        default_factory=datetime.now, description="Report generation timestamp"
    )
    analysis_period_start: datetime = Field(..., description="Start of analysis period")
    analysis_period_end: datetime = Field(..., description="End of analysis period")
    metrics_analyzed: int = Field(default=0, description="Number of metrics analyzed")
    data_points_analyzed: int = Field(
        default=0, description="Total data points analyzed"
    )
    anomalies: List[AnomalyDetection] = Field(
        default_factory=list, description="Detected anomalies"
    )
    baseline_comparisons: List[BaselineComparison] = Field(
        default_factory=list, description="Baseline comparison results"
    )
    regressions: List[RegressionResult] = Field(
        default_factory=list, description="Detected regressions"
    )
    total_anomalies: int = Field(default=0, description="Total anomalies detected")
    critical_anomalies: int = Field(
        default=0, description="Number of critical anomalies"
    )
    high_anomalies: int = Field(default=0, description="Number of high severity anomalies")
    medium_anomalies: int = Field(
        default=0, description="Number of medium severity anomalies"
    )
    low_anomalies: int = Field(default=0, description="Number of low severity anomalies")
    anomaly_rate: float = Field(
        default=0.0, description="Rate of anomalies per data point"
    )
    health_status: str = Field(default="healthy", description="Overall health status")
    recommendations: List[str] = Field(
        default_factory=list, description="Overall recommendations"
    )

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are critical issues."""
        return self.critical_anomalies > 0 or any(
            r.regression_severity == AnomalySeverity.CRITICAL for r in self.regressions
        )
