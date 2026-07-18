"""
Trend Models

Pydantic models for performance trend analysis and forecasting.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TrendDirection(str, Enum):
    """Direction of a performance trend."""

    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    UNKNOWN = "unknown"


class TrendData(BaseModel):
    """A single data point in a time series."""

    timestamp: datetime = Field(..., description="Data point timestamp")
    value: float = Field(..., description="Metric value")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class TrendAnalysis(BaseModel):
    """Result of trend analysis for a metric."""

    metric_name: str = Field(..., description="Name of the metric")
    analyzed_at: datetime = Field(
        default_factory=datetime.now, description="Analysis timestamp"
    )
    period_start: datetime = Field(..., description="Start of analysis period")
    period_end: datetime = Field(..., description="End of analysis period")
    data_point_count: int = Field(default=0, description="Number of data points")
    direction: TrendDirection = Field(
        default=TrendDirection.UNKNOWN, description="Trend direction"
    )
    slope: float = Field(default=0.0, description="Linear regression slope")
    slope_per_day: float = Field(
        default=0.0, description="Slope normalized to per-day change"
    )
    intercept: float = Field(default=0.0, description="Linear regression intercept")
    r_squared: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="R-squared (coefficient of determination)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in trend direction",
    )
    start_value: float = Field(default=0.0, description="Value at period start")
    end_value: float = Field(default=0.0, description="Value at period end")
    change_percent: float = Field(
        default=0.0, description="Percentage change over period"
    )
    change_absolute: float = Field(
        default=0.0, description="Absolute change over period"
    )
    mean: float = Field(default=0.0, description="Mean value")
    std_dev: float = Field(default=0.0, description="Standard deviation")
    min_value: float = Field(default=0.0, description="Minimum value")
    max_value: float = Field(default=0.0, description="Maximum value")
    volatility: float = Field(
        default=0.0, description="Coefficient of variation (std/mean)"
    )
    is_significant: bool = Field(
        default=False, description="Whether trend is statistically significant"
    )
    seasonality_detected: bool = Field(
        default=False, description="Whether seasonal pattern was detected"
    )
    anomaly_count: int = Field(
        default=0, description="Number of anomalies in period"
    )
    description: str = Field(default="", description="Human-readable description")


class ForecastPoint(BaseModel):
    """A single forecasted data point."""

    timestamp: datetime = Field(..., description="Forecast timestamp")
    predicted_value: float = Field(..., description="Predicted value")
    lower_bound: float = Field(..., description="Lower confidence interval")
    upper_bound: float = Field(..., description="Upper confidence interval")
    confidence_level: float = Field(
        default=0.95, description="Confidence level for bounds"
    )


class ForecastResult(BaseModel):
    """Result of performance forecasting."""

    metric_name: str = Field(..., description="Name of the metric")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="Forecast generation timestamp"
    )
    forecast_start: datetime = Field(..., description="Start of forecast period")
    forecast_end: datetime = Field(..., description="End of forecast period")
    forecast_points: List[ForecastPoint] = Field(
        default_factory=list, description="Forecasted data points"
    )
    method: str = Field(default="linear", description="Forecasting method used")
    training_data_points: int = Field(
        default=0, description="Number of historical points used"
    )
    trend_direction: TrendDirection = Field(
        default=TrendDirection.UNKNOWN, description="Underlying trend direction"
    )
    expected_value_at_end: float = Field(
        default=0.0, description="Expected value at forecast end"
    )
    expected_change_percent: float = Field(
        default=0.0, description="Expected percentage change"
    )
    model_fit_score: float = Field(
        default=0.0, description="How well the model fits historical data"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Warnings about forecast quality"
    )


class TrendReport(BaseModel):
    """Comprehensive trend analysis report."""

    generated_at: datetime = Field(
        default_factory=datetime.now, description="Report generation timestamp"
    )
    report_period_start: datetime = Field(..., description="Start of report period")
    report_period_end: datetime = Field(..., description="End of report period")
    metrics_analyzed: int = Field(default=0, description="Number of metrics analyzed")
    trend_analyses: List[TrendAnalysis] = Field(
        default_factory=list, description="Trend analyses for each metric"
    )
    forecasts: List[ForecastResult] = Field(
        default_factory=list, description="Forecasts for each metric"
    )
    improving_metrics: List[str] = Field(
        default_factory=list, description="Metrics with improving trends"
    )
    degrading_metrics: List[str] = Field(
        default_factory=list, description="Metrics with degrading trends"
    )
    stable_metrics: List[str] = Field(
        default_factory=list, description="Metrics with stable trends"
    )
    overall_health: str = Field(
        default="unknown", description="Overall system health based on trends"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations based on trends"
    )

    @property
    def degrading_count(self) -> int:
        """Count of degrading metrics."""
        return len(self.degrading_metrics)

    @property
    def improving_count(self) -> int:
        """Count of improving metrics."""
        return len(self.improving_metrics)


class DecompositionMode(str, Enum):
    """Additive vs multiplicative seasonal decomposition."""

    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"


class DecompositionOutcome(str, Enum):
    """Typed outcome of a seasonal-decomposition attempt.

    INSUFFICIENT_DATA is a *success* outcome (DEEPTHINK_01): fired when
    fewer than 3 full seasonal cycles are available, per Plan 03F.
    """

    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"


class SeasonalDecomposition(BaseModel):
    """
    Result of a robust STL-lite seasonal decomposition:
    value[i] = trend[i] + seasonal[i] + residual[i]  (additive), or
    value[i] = trend[i] * seasonal[i] * residual[i]  (multiplicative).
    """

    outcome: DecompositionOutcome = Field(default=DecompositionOutcome.OK)
    mode: DecompositionMode = Field(default=DecompositionMode.ADDITIVE)
    period: int = Field(default=0, description="Seasonal period length in points")
    cycles_available: float = Field(
        default=0.0, description="Number of full periods present in the input"
    )
    trend: List[float] = Field(default_factory=list)
    seasonal: List[float] = Field(default_factory=list)
    residual: List[float] = Field(default_factory=list)
    seasonal_indices: List[float] = Field(
        default_factory=list,
        description="One seasonal factor per phase (length == period)",
    )
    robust_weights: List[float] = Field(
        default_factory=list,
        description="Biweight robustness weights from the outlier-resistant pass",
    )
    outlier_indices: List[int] = Field(
        default_factory=list,
        description="Indices zeroed out by the robust biweight pass",
    )
    notes: List[str] = Field(default_factory=list)
