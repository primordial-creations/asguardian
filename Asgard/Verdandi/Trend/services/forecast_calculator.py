"""
Forecast Calculator Service

Forecasts future performance based on historical trends.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple, cast

from Asgard.Verdandi.Trend.models.trend_models import (
    ForecastPoint,
    ForecastResult,
    TrendData,
    TrendDirection,
)


class ForecastCalculator:
    """
    Calculator for performance forecasting.

    Uses historical data to forecast future performance metrics
    with confidence intervals.

    Example:
        forecaster = ForecastCalculator()

        # Forecast 7 days ahead
        forecast = forecaster.forecast(historical_data, periods=7)

        for point in forecast.forecast_points:
            print(f"{point.timestamp}: {point.predicted_value} "
                  f"[{point.lower_bound}, {point.upper_bound}]")
    """

    def __init__(
        self,
        confidence_level: float = 0.95,
        min_training_points: int = 10,
    ):
        """
        Initialize the forecast calculator.

        Args:
            confidence_level: Confidence level for prediction intervals
            min_training_points: Minimum data points required for forecasting
        """
        self.confidence_level = confidence_level
        self.min_training_points = min_training_points

    def forecast(
        self,
        data: Sequence[TrendData],
        periods: int = 7,
        interval_seconds: Optional[float] = None,
        metric_name: str = "metric",
        method: str = "linear",
    ) -> ForecastResult:
        """
        Forecast future values based on historical data.

        Args:
            data: Historical data points
            periods: Number of periods to forecast
            interval_seconds: Interval between points (auto-detected if None)
            metric_name: Name of the metric
            method: Forecasting method ("linear", "exponential", "moving_average")

        Returns:
            ForecastResult with predictions and confidence intervals
        """
        if len(data) < self.min_training_points:
            return ForecastResult(
                metric_name=metric_name,
                forecast_start=datetime.now(),
                forecast_end=datetime.now(),
                method=method,
                training_data_points=len(data),
                warnings=["Insufficient data for reliable forecasting"],
            )

        # Sort by timestamp
        sorted_data = sorted(data, key=lambda d: d.timestamp)

        # Auto-detect interval if not provided
        if interval_seconds is None:
            interval_seconds = self._detect_interval(sorted_data)

        # Choose forecasting method
        if method == "exponential":
            forecast_points, model_fit = self._exponential_forecast(
                sorted_data, periods, interval_seconds
            )
        elif method == "moving_average":
            forecast_points, model_fit = self._moving_average_forecast(
                sorted_data, periods, interval_seconds
            )
        else:
            forecast_points, model_fit = self._linear_forecast(
                sorted_data, periods, interval_seconds
            )

        # Determine trend direction from slope
        if len(forecast_points) >= 2:
            slope = (
                forecast_points[-1].predicted_value - forecast_points[0].predicted_value
            ) / periods
            if slope > 0:
                direction = TrendDirection.DEGRADING  # Higher latency = degrading
            elif slope < 0:
                direction = TrendDirection.IMPROVING
            else:
                direction = TrendDirection.STABLE
        else:
            direction = TrendDirection.UNKNOWN

        # Calculate expected change
        if sorted_data and forecast_points:
            start_value = sorted_data[-1].value
            end_value = forecast_points[-1].predicted_value
            expected_change = (
                (end_value - start_value) / abs(start_value) * 100
                if start_value != 0
                else 0
            )
        else:
            expected_change = 0

        # Generate warnings
        warnings = self._generate_warnings(
            sorted_data, forecast_points, model_fit, method
        )

        return ForecastResult(
            metric_name=metric_name,
            generated_at=datetime.now(),
            forecast_start=(
                forecast_points[0].timestamp if forecast_points else datetime.now()
            ),
            forecast_end=(
                forecast_points[-1].timestamp if forecast_points else datetime.now()
            ),
            forecast_points=forecast_points,
            method=method,
            training_data_points=len(data),
            trend_direction=direction,
            expected_value_at_end=(
                forecast_points[-1].predicted_value if forecast_points else 0
            ),
            expected_change_percent=expected_change,
            model_fit_score=model_fit,
            warnings=warnings,
        )

    def forecast_values(
        self,
        values: Sequence[float],
        periods: int = 7,
        interval_seconds: float = 86400,
        metric_name: str = "metric",
        method: str = "linear",
    ) -> ForecastResult:
        """
        Forecast from raw values (assuming uniform intervals).

        Args:
            values: Historical values
            periods: Number of periods to forecast
            interval_seconds: Interval between data points
            metric_name: Name of the metric
            method: Forecasting method

        Returns:
            ForecastResult with predictions
        """
        if not values:
            return ForecastResult(
                metric_name=metric_name,
                forecast_start=datetime.now(),
                forecast_end=datetime.now(),
                warnings=["No historical data provided"],
            )

        start_time = datetime.now() - timedelta(seconds=interval_seconds * len(values))
        data = [
            TrendData(
                timestamp=start_time + timedelta(seconds=i * interval_seconds),
                value=v,
            )
            for i, v in enumerate(values)
        ]

        return self.forecast(data, periods, interval_seconds, metric_name, method)

    def forecast_multiple(
        self,
        metrics: Dict[str, Sequence[TrendData]],
        periods: int = 7,
    ) -> Dict[str, ForecastResult]:
        """
        Forecast multiple metrics.

        Args:
            metrics: Dictionary of metric_name to data sequence
            periods: Number of periods to forecast

        Returns:
            Dictionary of metric_name to ForecastResult
        """
        return {
            name: self.forecast(data, periods, metric_name=name)
            for name, data in metrics.items()
        }

    def _linear_forecast(
        self,
        data: List[TrendData],
        periods: int,
        interval_seconds: float,
    ) -> Tuple[List[ForecastPoint], float]:
        """
        Forecast using linear regression.
        """
        values = [d.value for d in data]
        timestamps = [d.timestamp for d in data]

        # Convert to numeric x values
        t0 = timestamps[0].timestamp()
        x_values = [(t.timestamp() - t0) for t in timestamps]

        # Linear regression
        slope, intercept, r_squared = self._linear_regression(x_values, values)

        # Calculate prediction interval parameters
        n = len(values)
        mean_x = sum(x_values) / n
        ss_x = sum((x - mean_x) ** 2 for x in x_values)
        residuals = [
            y - (slope * x + intercept)
            for x, y in zip(x_values, values)
        ]
        mse = sum(r ** 2 for r in residuals) / (n - 2) if n > 2 else 0
        std_error = math.sqrt(mse) if mse > 0 else 0

        # t-value for confidence level (approximate for large n)
        t_value = 1.96 if self.confidence_level == 0.95 else 2.576

        # Generate forecast points
        forecast_points = []
        last_time = timestamps[-1]
        last_x = x_values[-1]

        for i in range(1, periods + 1):
            x_forecast = last_x + i * interval_seconds
            predicted = slope * x_forecast + intercept

            # Prediction interval
            if ss_x > 0:
                interval_width = t_value * std_error * math.sqrt(
                    1 + 1 / n + (x_forecast - mean_x) ** 2 / ss_x
                )
            else:
                interval_width = t_value * std_error

            forecast_points.append(
                ForecastPoint(
                    timestamp=last_time + timedelta(seconds=i * interval_seconds),
                    predicted_value=predicted,
                    lower_bound=predicted - interval_width,
                    upper_bound=predicted + interval_width,
                    confidence_level=self.confidence_level,
                )
            )

        return forecast_points, r_squared

    def _exponential_forecast(
        self,
        data: List[TrendData],
        periods: int,
        interval_seconds: float,
    ) -> Tuple[List[ForecastPoint], float]:
        """
        Forecast using exponential smoothing.
        """
        values = [d.value for d in data]
        timestamps = [d.timestamp for d in data]

        # Simple exponential smoothing with trend (Holt's method)
        alpha = 0.3  # Level smoothing
        beta = 0.1  # Trend smoothing

        # Initialize
        level = values[0]
        trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0

        # Smooth through data
        fitted_values = [level]
        for i in range(1, len(values)):
            prev_level = level
            level = alpha * values[i] + (1 - alpha) * (level + trend)
            trend = beta * (level - prev_level) + (1 - beta) * trend
            fitted_values.append(level + trend)

        # Calculate fit
        residuals = [a - f for a, f in zip(values, fitted_values)]
        mse = sum(r ** 2 for r in residuals) / len(residuals)
        std_error = math.sqrt(mse) if mse > 0 else 0

        # R-squared approximation
        mean_y = sum(values) / len(values)
        ss_tot = sum((y - mean_y) ** 2 for y in values)
        ss_res = sum(r ** 2 for r in residuals)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Generate forecasts
        t_value = 1.96 if self.confidence_level == 0.95 else 2.576
        forecast_points = []
        last_time = timestamps[-1]

        for i in range(1, periods + 1):
            predicted = level + i * trend
            # Confidence interval grows with forecast horizon
            interval_width = t_value * std_error * math.sqrt(1 + i * 0.1)

            forecast_points.append(
                ForecastPoint(
                    timestamp=last_time + timedelta(seconds=i * interval_seconds),
                    predicted_value=predicted,
                    lower_bound=predicted - interval_width,
                    upper_bound=predicted + interval_width,
                    confidence_level=self.confidence_level,
                )
            )

        return forecast_points, max(0, r_squared)

    def _moving_average_forecast(
        self,
        data: List[TrendData],
        periods: int,
        interval_seconds: float,
    ) -> Tuple[List[ForecastPoint], float]:
        """
        Forecast using simple moving average.
        """
        values = [d.value for d in data]
        timestamps = [d.timestamp for d in data]

        # Use last N values for average
        window = min(7, len(values))
        recent_values = values[-window:]
        avg = sum(recent_values) / len(recent_values)
        std_dev = math.sqrt(
            sum((v - avg) ** 2 for v in recent_values) / len(recent_values)
        )

        # R-squared is not well-defined for constant forecast
        # Use a rough approximation based on variance
        total_var = sum((v - avg) ** 2 for v in values) / len(values)
        r_squared = 1 - (std_dev ** 2 / total_var) if total_var > 0 else 0

        # Generate forecasts
        t_value = 1.96 if self.confidence_level == 0.95 else 2.576
        forecast_points = []
        last_time = timestamps[-1]

        for i in range(1, periods + 1):
            # Confidence interval grows with horizon
            interval_width = t_value * std_dev * math.sqrt(1 + i * 0.05)

            forecast_points.append(
                ForecastPoint(
                    timestamp=last_time + timedelta(seconds=i * interval_seconds),
                    predicted_value=avg,
                    lower_bound=avg - interval_width,
                    upper_bound=avg + interval_width,
                    confidence_level=self.confidence_level,
                )
            )

        return forecast_points, max(0, r_squared)

    def _linear_regression(
        self,
        x: Sequence[float],
        y: Sequence[float],
    ) -> Tuple[float, float, float]:
        """Calculate linear regression (slope, intercept, r_squared)."""
        n = len(x)
        if n < 2:
            return 0.0, y[0] if y else 0.0, 0.0

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)

        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return 0.0, sum_y / n, 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        # R-squared
        mean_y = sum_y / n
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        return slope, intercept, max(0, min(1, r_squared))

    def _detect_interval(self, data: List[TrendData]) -> float:
        """Detect interval between data points."""
        if len(data) < 2:
            return 86400  # Default to daily

        intervals = []
        for i in range(1, len(data)):
            delta = (data[i].timestamp - data[i - 1].timestamp).total_seconds()
            if delta > 0:
                intervals.append(delta)

        if not intervals:
            return 86400

        # Use median interval
        sorted_intervals = sorted(intervals)
        mid = len(sorted_intervals) // 2
        if len(sorted_intervals) % 2 == 0:
            return cast(float, (sorted_intervals[mid - 1] + sorted_intervals[mid]) / 2)
        return cast(float, sorted_intervals[mid])

    def _generate_warnings(
        self,
        data: List[TrendData],
        forecast_points: List[ForecastPoint],
        model_fit: float,
        method: str,
    ) -> List[str]:
        """Generate warnings about forecast quality."""
        warnings = []

        if model_fit < 0.3:
            warnings.append(
                f"Low model fit (R2={model_fit:.2f}). Forecast may be unreliable."
            )

        if len(data) < 30:
            warnings.append(
                f"Limited historical data ({len(data)} points). "
                f"Consider collecting more data for better forecasts."
            )

        # Check for high volatility
        values = [d.value for d in data]
        mean = sum(values) / len(values)
        std_dev = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        volatility = std_dev / mean if mean != 0 else 0

        if volatility > 0.5:
            warnings.append(
                f"High volatility (CV={volatility:.2f}). "
                f"Forecast confidence intervals may be wider than expected."
            )

        # Check for negative forecasts in metrics that should be positive
        for point in forecast_points:
            if point.lower_bound < 0:
                warnings.append(
                    "Some forecast intervals include negative values. "
                    "Consider using a different forecasting method."
                )
                break

        return warnings
