"""
Analysis Models

Pydantic models for statistical analysis and metrics calculation.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SLAStatus(str, Enum):
    """SLA compliance status."""

    COMPLIANT = "compliant"
    WARNING = "warning"
    BREACHED = "breached"


class TrendDirection(str, Enum):
    """Trend direction indicator."""

    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


class PercentileResult(BaseModel):
    """Result of percentile calculations."""

    sample_count: int = Field(..., description="Number of samples analyzed")
    min_value: float = Field(..., description="Minimum value")
    max_value: float = Field(..., description="Maximum value")
    mean: float = Field(..., description="Arithmetic mean")
    median: float = Field(..., description="Median (P50)")
    std_dev: float = Field(..., description="Standard deviation")
    p50: float = Field(..., description="50th percentile")
    p75: float = Field(..., description="75th percentile")
    p90: float = Field(..., description="90th percentile")
    p95: float = Field(..., description="95th percentile")
    p99: float = Field(..., description="99th percentile")
    p999: float = Field(..., description="99.9th percentile")
    quality_flags: List[str] = Field(
        default_factory=list,
        description=(
            "Measurement-quality annotations (e.g. SUSPECT_COORDINATED_OMISSION, "
            "LITTLES_LAW_VIOLATION, CO_CORRECTED, SKETCH_APPROXIMATION)"
        ),
    )

    @property
    def range(self) -> float:
        """Calculate range (max - min)."""
        return self.max_value - self.min_value


class ApdexConfig(BaseModel):
    """Configuration for Apdex calculation."""

    threshold_ms: float = Field(
        default=500.0,
        description="Satisfied threshold T in milliseconds",
    )
    frustration_multiplier: float = Field(
        default=4.0,
        description="Multiplier for frustration threshold (default 4T)",
    )
    version: Optional[str] = Field(
        default=None,
        description=(
            "Recalibration epoch label (e.g. 'v1'); results are stamped so "
            "downstream storage can keep Apdex_v1_T500 and Apdex_v2_T1500 in "
            "parallel during a shadow period"
        ),
    )
    endpoint: Optional[str] = Field(
        default=None, description="Endpoint/route this config applies to"
    )

    @property
    def frustration_threshold_ms(self) -> float:
        """Calculate frustration threshold (4T by default)."""
        return self.threshold_ms * self.frustration_multiplier


class ApdexResult(BaseModel):
    """Result of Apdex score calculation."""

    score: float = Field(..., ge=0.0, le=1.0, description="Apdex score (0-1)")
    satisfied_count: int = Field(..., description="Count of satisfied responses")
    tolerating_count: int = Field(..., description="Count of tolerating responses")
    frustrated_count: int = Field(..., description="Count of frustrated responses")
    total_count: int = Field(..., description="Total response count")
    threshold_ms: float = Field(..., description="Threshold T used")
    rating: str = Field(..., description="Human-readable rating")
    version: Optional[str] = Field(
        default=None, description="Config version this result was computed under"
    )
    endpoint: Optional[str] = Field(
        default=None, description="Endpoint/route this result applies to"
    )
    distribution_warning: Optional[str] = Field(
        default=None,
        description=(
            "Set when the underlying response-time distribution is bimodal: "
            "a single Apdex score masks the mode structure (DEEPTHINK_03). "
            "This is an annotation, not an alert."
        ),
    )
    machine_traffic_excluded: int = Field(
        default=0,
        description="Count of non-human requests excluded from this Apdex score",
    )

    @classmethod
    def get_rating(cls, score: float) -> str:
        """Get human-readable rating for Apdex score."""
        if score >= 0.94:
            return "Excellent"
        elif score >= 0.85:
            return "Good"
        elif score >= 0.70:
            return "Fair"
        elif score >= 0.50:
            return "Poor"
        else:
            return "Unacceptable"


class MultiEndpointApdexResult(BaseModel):
    """
    Rollup of per-endpoint Apdex results (DEEPTHINK_03 Simpson's-paradox guard).

    Replaces volume-weighted pooling: the headline number is "% of endpoints
    meeting target", not a single traffic-weighted score that a single huge,
    fast endpoint can mask a slow one behind.
    """

    endpoint_results: Dict[str, ApdexResult] = Field(
        default_factory=dict, description="Apdex result per endpoint"
    )
    target_score: float = Field(..., description="Apdex score target used for compliance")
    total_endpoints: int = Field(..., description="Number of endpoints evaluated")
    endpoints_meeting_target: int = Field(
        ..., description="Number of endpoints at/above target_score"
    )
    pct_endpoints_meeting_target: float = Field(
        ..., description="Percentage of endpoints meeting target_score"
    )
    failing_endpoints: List[str] = Field(
        default_factory=list, description="Endpoints below target_score"
    )


class ApdexRecalibrationRecord(BaseModel):
    """
    Audit trail for a threshold-T recalibration across versions/releases.

    Per DEEPTHINK_03, recalibration must not silently rewrite history: the
    old and new configs run in parallel ("shadow") for >= 30 days before
    cutover, ideally aligned to a quarter boundary.
    """

    old_version: str = Field(..., description="Previous config version label")
    new_version: str = Field(..., description="New config version label")
    old_threshold_ms: float = Field(..., description="Previous threshold T")
    new_threshold_ms: float = Field(..., description="New threshold T")
    endpoint: Optional[str] = Field(default=None, description="Endpoint being recalibrated")
    shadow_period_days: int = Field(
        ..., description="Requested shadow (parallel-run) period in days"
    )
    shadow_sufficient: bool = Field(
        ..., description="True when shadow_period_days >= 30"
    )
    recalibrated_at: datetime = Field(
        default_factory=datetime.now, description="When this recalibration was recorded"
    )
    checklist: List[str] = Field(
        default_factory=list,
        description="Epoch-overlap checklist: shadow length, annotation text, cutover timing",
    )


class SLAConfig(BaseModel):
    """Configuration for SLA checking."""

    target_percentile: float = Field(
        default=95.0,
        description="Target percentile for SLA (e.g., 95 for P95)",
    )
    threshold_ms: float = Field(
        ...,
        description="Maximum allowed value at target percentile",
    )
    warning_threshold_percent: float = Field(
        default=90.0,
        description="Percentage of threshold that triggers warning",
    )
    availability_target: Optional[float] = Field(
        default=99.9,
        description="Target availability percentage",
    )
    error_rate_threshold: Optional[float] = Field(
        default=1.0,
        description="Maximum allowed error rate percentage",
    )


class SLAResult(BaseModel):
    """Result of SLA compliance check."""

    status: SLAStatus = Field(..., description="Overall SLA status")
    percentile_value: float = Field(..., description="Actual value at target percentile")
    percentile_target: float = Field(..., description="Target percentile checked")
    threshold_ms: float = Field(..., description="SLA threshold")
    margin_percent: float = Field(..., description="Margin from threshold (negative if over)")
    availability_actual: Optional[float] = Field(
        default=None,
        description="Actual availability percentage",
    )
    error_rate_actual: Optional[float] = Field(
        default=None,
        description="Actual error rate percentage",
    )
    violations: List[str] = Field(
        default_factory=list,
        description="List of SLA violations",
    )


class AggregationConfig(BaseModel):
    """Configuration for metric aggregation."""

    window_size_seconds: int = Field(
        default=60,
        description="Aggregation window size in seconds",
    )
    include_percentiles: bool = Field(
        default=True,
        description="Whether to include percentile calculations",
    )
    include_histograms: bool = Field(
        default=False,
        description="Whether to include histogram data",
    )
    histogram_buckets: List[float] = Field(
        default_factory=lambda: [10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0],
        description="Histogram bucket boundaries in ms",
    )


class AggregationResult(BaseModel):
    """Result of metric aggregation."""

    window_start: str = Field(..., description="Start of aggregation window (ISO format)")
    window_end: str = Field(..., description="End of aggregation window (ISO format)")
    sample_count: int = Field(..., description="Number of samples in window")
    sum_value: float = Field(..., description="Sum of all values")
    mean: float = Field(..., description="Mean value")
    min_value: float = Field(..., description="Minimum value")
    max_value: float = Field(..., description="Maximum value")
    percentiles: Optional[PercentileResult] = Field(
        default=None,
        description="Percentile breakdown if calculated",
    )
    histogram: Optional[Dict[str, int]] = Field(
        default=None,
        description="Histogram bucket counts if calculated",
    )
    throughput: float = Field(..., description="Samples per second")


class TrendResult(BaseModel):
    """Result of trend analysis."""

    direction: TrendDirection = Field(..., description="Overall trend direction")
    slope: float = Field(..., description="Linear regression slope")
    change_percent: float = Field(..., description="Percentage change over period")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in trend direction (0-1)",
    )
    data_points: int = Field(..., description="Number of data points analyzed")
    period_seconds: int = Field(..., description="Period analyzed in seconds")
    baseline_value: float = Field(..., description="Starting baseline value")
    current_value: float = Field(..., description="Most recent value")
    anomalies_detected: int = Field(
        default=0,
        description="Number of anomalies detected in period",
    )
