"""
Trend Analyzer Service

Analyzes performance trends over time.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from Asgard.Verdandi.Trend.models.trend_models import (
    TrendAnalysis,
    TrendData,
    TrendDirection,
    TrendReport,
)
from Asgard.Verdandi.Trend.services._trend_helpers import (
    calculate_trend_confidence,
    detect_change_points_in_data,
    determine_direction,
    generate_report_recommendations,
    generate_trend_description,
    linear_regression,
)


class TrendAnalyzer:
    """
    Analyzer for performance trends over time.

    Provides methods to detect and analyze trends in time series data
    using linear regression and statistical analysis.

    Example:
        analyzer = TrendAnalyzer()

        # Analyze trend in latency data
        data = [TrendData(timestamp=ts, value=val) for ts, val in zip(times, values)]
        trend = analyzer.analyze(data, metric_name="api_latency")

        if trend.direction == TrendDirection.DEGRADING:
            print(f"Performance degrading: {trend.change_percent}% over period")
    """

    def __init__(
        self,
        min_data_points: int = 5,
        significance_threshold: float = 5.0,
        r_squared_threshold: float = 0.3,
    ):
        """
        Initialize the trend analyzer.

        Args:
            min_data_points: Minimum points required for analysis
            significance_threshold: Percent change to consider significant
            r_squared_threshold: R-squared threshold for confident trend
        """
        self.min_data_points = min_data_points
        self.significance_threshold = significance_threshold
        self.r_squared_threshold = r_squared_threshold

    def analyze(
        self,
        data: Sequence[TrendData],
        metric_name: str = "metric",
    ) -> TrendAnalysis:
        """
        Analyze trend in time series data.

        Args:
            data: Sequence of TrendData points
            metric_name: Name of the metric

        Returns:
            TrendAnalysis with trend information
        """
        if len(data) < self.min_data_points:
            return TrendAnalysis(
                metric_name=metric_name,
                period_start=data[0].timestamp if data else datetime.now(),
                period_end=data[-1].timestamp if data else datetime.now(),
                description="Insufficient data points for trend analysis",
            )

        sorted_data = sorted(data, key=lambda d: d.timestamp)
        values = [d.value for d in sorted_data]
        timestamps = [d.timestamp for d in sorted_data]

        t0 = timestamps[0].timestamp()
        x_values = [(t.timestamp() - t0) for t in timestamps]

        slope, intercept, r_squared = linear_regression(x_values, values)

        slope_per_day = slope * 86400

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)
        volatility = std_dev / mean if mean != 0 else 0

        start_value = values[0]
        end_value = values[-1]
        change_absolute = end_value - start_value
        change_percent = (
            change_absolute / abs(start_value) * 100 if start_value != 0 else 0
        )

        direction = determine_direction(
            slope, change_percent, r_squared, metric_name,
            self.r_squared_threshold, self.significance_threshold,
        )

        confidence = calculate_trend_confidence(r_squared, len(data), slope)

        is_significant = (
            abs(change_percent) >= self.significance_threshold
            and r_squared >= self.r_squared_threshold
        )

        description = generate_trend_description(
            direction, change_percent, slope_per_day, r_squared
        )

        return TrendAnalysis(
            metric_name=metric_name,
            analyzed_at=datetime.now(),
            period_start=timestamps[0],
            period_end=timestamps[-1],
            data_point_count=len(data),
            direction=direction,
            slope=slope,
            slope_per_day=slope_per_day,
            intercept=intercept,
            r_squared=r_squared,
            confidence=confidence,
            start_value=start_value,
            end_value=end_value,
            change_percent=change_percent,
            change_absolute=change_absolute,
            mean=mean,
            std_dev=std_dev,
            min_value=min(values),
            max_value=max(values),
            volatility=volatility,
            is_significant=is_significant,
            description=description,
        )

    def analyze_values(
        self,
        values: Sequence[float],
        metric_name: str = "metric",
        start_time: Optional[datetime] = None,
        interval_seconds: float = 60,
    ) -> TrendAnalysis:
        """
        Analyze trend from raw values (assuming uniform intervals).

        Args:
            values: Sequence of metric values
            metric_name: Name of the metric
            start_time: Start timestamp (default: now minus duration)
            interval_seconds: Interval between data points

        Returns:
            TrendAnalysis with trend information
        """
        if not values:
            return TrendAnalysis(
                metric_name=metric_name,
                period_start=datetime.now(),
                period_end=datetime.now(),
                description="No data provided",
            )

        start_time = start_time or (
            datetime.now() - timedelta(seconds=interval_seconds * len(values))
        )

        data = [
            TrendData(
                timestamp=start_time + timedelta(seconds=i * interval_seconds),
                value=v,
            )
            for i, v in enumerate(values)
        ]

        return self.analyze(data, metric_name)

    def analyze_multiple(
        self,
        metrics: Dict[str, Sequence[TrendData]],
    ) -> Dict[str, TrendAnalysis]:
        """
        Analyze trends for multiple metrics.

        Args:
            metrics: Dictionary of metric_name to data sequence

        Returns:
            Dictionary of metric_name to TrendAnalysis
        """
        return {name: self.analyze(data, name) for name, data in metrics.items()}

    def detect_change_points(
        self,
        data: Sequence[TrendData],
        window_size: int = 10,
        threshold: float = 2.0,
    ) -> List[Tuple[datetime, float]]:
        """
        Detect points where the trend changes significantly.

        Args:
            data: Sequence of TrendData points
            window_size: Size of comparison windows
            threshold: Z-score threshold for change detection

        Returns:
            List of (timestamp, change_magnitude) tuples
        """
        return detect_change_points_in_data(list(data), window_size, threshold)

    def generate_report(
        self,
        metrics: Dict[str, Sequence[TrendData]],
    ) -> TrendReport:
        """
        Generate a comprehensive trend report.

        Args:
            metrics: Dictionary of metric_name to data sequence

        Returns:
            TrendReport with analysis for all metrics
        """
        analyses = self.analyze_multiple(metrics)

        improving = []
        degrading = []
        stable = []

        for name, analysis in analyses.items():
            if analysis.direction == TrendDirection.IMPROVING:
                improving.append(name)
            elif analysis.direction == TrendDirection.DEGRADING:
                degrading.append(name)
            else:
                stable.append(name)

        if len(degrading) > len(improving):
            overall_health = "degrading"
        elif len(improving) > len(degrading):
            overall_health = "improving"
        else:
            overall_health = "stable"

        recommendations = generate_report_recommendations(analyses)

        first_analysis = list(analyses.values())[0] if analyses else None

        return TrendReport(
            generated_at=datetime.now(),
            report_period_start=(
                first_analysis.period_start if first_analysis else datetime.now()
            ),
            report_period_end=(
                first_analysis.period_end if first_analysis else datetime.now()
            ),
            metrics_analyzed=len(analyses),
            trend_analyses=list(analyses.values()),
            improving_metrics=improving,
            degrading_metrics=degrading,
            stable_metrics=stable,
            overall_health=overall_health,
            recommendations=recommendations,
        )
