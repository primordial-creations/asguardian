"""
Forecast Calculator Service

Forecasts future performance based on historical trends.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from Asgard.Verdandi.Trend.models.trend_models import (
    ForecastPoint,
    ForecastResult,
    TrendData,
    TrendDirection,
)
from Asgard.Verdandi.Trend.services._forecast_methods import (
    detect_interval,
    exponential_forecast,
    generate_forecast_warnings,
    linear_forecast,
    moving_average_forecast,
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

        sorted_data = sorted(data, key=lambda d: d.timestamp)

        if interval_seconds is None:
            interval_seconds = detect_interval(sorted_data)

        if method == "exponential":
            forecast_points, model_fit = exponential_forecast(
                sorted_data, periods, interval_seconds, self.confidence_level
            )
        elif method == "moving_average":
            forecast_points, model_fit = moving_average_forecast(
                sorted_data, periods, interval_seconds, self.confidence_level
            )
        else:
            forecast_points, model_fit = linear_forecast(
                sorted_data, periods, interval_seconds, self.confidence_level
            )

        if len(forecast_points) >= 2:
            slope = (
                forecast_points[-1].predicted_value - forecast_points[0].predicted_value
            ) / periods
            if slope > 0:
                direction = TrendDirection.DEGRADING
            elif slope < 0:
                direction = TrendDirection.IMPROVING
            else:
                direction = TrendDirection.STABLE
        else:
            direction = TrendDirection.UNKNOWN

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

        warnings = generate_forecast_warnings(
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
