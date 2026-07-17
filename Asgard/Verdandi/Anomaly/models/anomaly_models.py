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


class DetectionOutcome(str, Enum):
    """Typed outcome of a detection attempt.

    INSUFFICIENT_DATA is a *success* outcome (DEEPTHINK_01): the detector is
    reporting honestly that it cannot answer, and it must never trip alerts.
    """

    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"
    BIMODAL_DISTRIBUTION = "bimodal_distribution"


class ModeStats(BaseModel):
    """Per-mode statistics for a multimodal distribution."""

    median: float = Field(..., description="Median of this mode")
    mad: float = Field(..., description="Median absolute deviation of this mode")
    count: int = Field(..., description="Number of samples in this mode")
    weight: float = Field(..., description="Fraction of total samples in this mode")


class BimodalityResult(BaseModel):
    """Result of the bimodality guard (dip-statistic-lite)."""

    outcome: DetectionOutcome = Field(default=DetectionOutcome.OK)
    is_bimodal: bool = Field(default=False, description="Two-peaks-with-valley detected")
    modes: List[ModeStats] = Field(default_factory=list, description="Per-mode stats (low mode first)")
    valley_ratio: Optional[float] = Field(
        default=None, description="Valley height / smaller peak height (< 0.5 => bimodal)"
    )
    split_value: Optional[float] = Field(
        default=None, description="Value at the valley separating the two modes"
    )
    notes: List[str] = Field(default_factory=list)


class StepChangeResult(BaseModel):
    """Result of small-batch step-change detection (split-window MAD / CUSUM)."""

    outcome: DetectionOutcome = Field(default=DetectionOutcome.OK)
    detected: bool = Field(default=False)
    method: str = Field(default="", description="Detecting method: split_window_mad, cusum")
    change_index: Optional[int] = Field(default=None, description="Estimated index of the step")
    magnitude: Optional[float] = Field(default=None, description="Median shift across the step")
    mad_units: Optional[float] = Field(default=None, description="Shift expressed in baseline MADs")
    cusum_alarm_index: Optional[int] = Field(default=None, description="First index where CUSUM crossed h")
    notes: List[str] = Field(default_factory=list)


class DriftResult(BaseModel):
    """Result of gradual-drift detection via global OLS trend (boiling-frog fix)."""

    outcome: DetectionOutcome = Field(default=DetectionOutcome.OK)
    detected: bool = Field(default=False)
    slope: Optional[float] = Field(default=None, description="OLS slope per sample")
    slope_t_statistic: Optional[float] = Field(default=None)
    slope_p_value: Optional[float] = Field(default=None)
    total_drift: Optional[float] = Field(default=None, description="slope x (n-1): drift over the batch")
    relative_drift: Optional[float] = Field(
        default=None, description="Total drift relative to the batch median"
    )
    notes: List[str] = Field(default_factory=list)


class MethodRecommendation(BaseModel):
    """Scenario-routed method recommendation (DEEPTHINK_02 switching thresholds)."""

    recommended_methods: List[str] = Field(default_factory=list)
    avoid_methods: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class MetricClass(str, Enum):
    """Metric class used to select a sensitivity profile."""

    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    CACHE_HIT_RATE = "cache_hit_rate"


class SensitivityProfile(BaseModel):
    """
    Per-metric-class sensitivity preset (DEEPTHINK_08).

    Exposes a sensitivity *dial* instead of raw statistical knobs:
    latency detectors bias to specificity (effect-size gated); error-rate
    detectors bias to sensitivity but gate on absolute event volume.
    """

    metric_class: MetricClass = Field(..., description="Metric class this profile covers")
    z_threshold: float = Field(default=3.0)
    min_sample_size: int = Field(default=10)
    min_absolute_events: int = Field(
        default=0, description="Absolute event-count gate (error-rate profiles)"
    )
    effect_gated: bool = Field(
        default=False, description="Require practical effect gates before flagging"
    )
    trajectory_based: bool = Field(
        default=False, description="Route to trajectory analysis (cache hit rate)"
    )
    bias: str = Field(default="balanced", description="specificity | sensitivity | balanced")
    notes: List[str] = Field(default_factory=list)

    @classmethod
    def latency(cls) -> "SensitivityProfile":
        """Specificity-biased: alert fatigue costs more than a missed slow path."""
        return cls(
            metric_class=MetricClass.LATENCY,
            z_threshold=3.5,
            min_sample_size=20,
            effect_gated=True,
            bias="specificity",
            notes=[
                "Latency anomalies are gated on practical effect size "
                "(Hodges-Lehmann shift > 10ms or > 5% relative, |Glass's delta| > 0.5)."
            ],
        )

    @classmethod
    def error_rate(cls) -> "SensitivityProfile":
        """Sensitivity-biased but gated on absolute volume."""
        return cls(
            metric_class=MetricClass.ERROR_RATE,
            z_threshold=2.5,
            min_sample_size=10,
            min_absolute_events=50,
            bias="sensitivity",
            notes=[
                "Error-rate anomalies require >= 50 absolute error events; "
                "percentage spikes on tiny denominators are noise."
            ],
        )

    @classmethod
    def cache_hit_rate(cls) -> "SensitivityProfile":
        """Trajectory-based: post-deploy dips are expected; flatlines are not."""
        return cls(
            metric_class=MetricClass.CACHE_HIT_RATE,
            z_threshold=3.0,
            min_sample_size=6,
            trajectory_based=True,
            bias="balanced",
            notes=[
                "Cache hit-rate drops are mechanical after deploys; use warm-up "
                "trajectory analysis (Verdandi.Cache.WarmupAnalyzer) rather than "
                "static thresholds."
            ],
        )

    @classmethod
    def for_metric_class(cls, metric_class: MetricClass) -> "SensitivityProfile":
        """Return the preset profile for a metric class."""
        factory = {
            MetricClass.LATENCY: cls.latency,
            MetricClass.ERROR_RATE: cls.error_rate,
            MetricClass.CACHE_HIT_RATE: cls.cache_hit_rate,
        }[metric_class]
        return factory()


class BaselineStrategy(str, Enum):
    """Baseline comparison strategy (DEEPTHINK_07 taxonomy)."""

    PRE_POST = "pre_post"
    HISTORICAL_WEEK = "historical_week"
    CANARY_CONCURRENT = "canary_concurrent"
    DIFF_IN_DIFF = "diff_in_diff"


class BaselineStrategyAssessment(BaseModel):
    """Confound warnings and detectable-effect guidance for a baseline strategy."""

    strategy: BaselineStrategy = Field(...)
    confound_warnings: List[str] = Field(default_factory=list)
    mdes_percent_range: str = Field(
        default="", description="Minimum detectable effect size tier for this strategy"
    )
    notes: List[str] = Field(default_factory=list)


class DiffInDiffResult(BaseModel):
    """Difference-in-Differences estimate for no-split infrastructures."""

    outcome: DetectionOutcome = Field(default=DetectionOutcome.OK)
    effect: float = Field(default=0.0, description="(post_now - pre_now) - (post_base - pre_base)")
    effect_percent: Optional[float] = Field(
        default=None, description="Effect relative to the pre-change current mean"
    )
    pre_now_mean: float = Field(default=0.0)
    post_now_mean: float = Field(default=0.0)
    pre_baseline_mean: float = Field(default=0.0)
    post_baseline_mean: float = Field(default=0.0)
    warnings: List[str] = Field(default_factory=list)


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
