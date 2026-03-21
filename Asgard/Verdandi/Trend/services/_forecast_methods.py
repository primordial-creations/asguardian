"""
Forecast method implementations for ForecastCalculator.

Contains the private forecasting algorithms extracted from the forecast calculator.
"""

import math
from datetime import datetime, timedelta
from typing import List, Sequence, Tuple, cast

from Asgard.Verdandi.Trend.models.trend_models import (
    ForecastPoint,
    TrendData,
)


def linear_regression(
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

    mean_y = sum_y / n
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))

    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return slope, intercept, max(0, min(1, r_squared))


def detect_interval(data: List[TrendData]) -> float:
    """Detect interval between data points."""
    if len(data) < 2:
        return 86400

    intervals = []
    for i in range(1, len(data)):
        delta = (data[i].timestamp - data[i - 1].timestamp).total_seconds()
        if delta > 0:
            intervals.append(delta)

    if not intervals:
        return 86400

    sorted_intervals = sorted(intervals)
    mid = len(sorted_intervals) // 2
    if len(sorted_intervals) % 2 == 0:
        return cast(float, (sorted_intervals[mid - 1] + sorted_intervals[mid]) / 2)
    return cast(float, sorted_intervals[mid])


def generate_forecast_warnings(
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

    values = [d.value for d in data]
    mean = sum(values) / len(values)
    std_dev = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    volatility = std_dev / mean if mean != 0 else 0

    if volatility > 0.5:
        warnings.append(
            f"High volatility (CV={volatility:.2f}). "
            f"Forecast confidence intervals may be wider than expected."
        )

    for point in forecast_points:
        if point.lower_bound < 0:
            warnings.append(
                "Some forecast intervals include negative values. "
                "Consider using a different forecasting method."
            )
            break

    return warnings


def linear_forecast(
    data: List[TrendData],
    periods: int,
    interval_seconds: float,
    confidence_level: float,
) -> Tuple[List[ForecastPoint], float]:
    """Forecast using linear regression."""
    values = [d.value for d in data]
    timestamps = [d.timestamp for d in data]

    t0 = timestamps[0].timestamp()
    x_values = [(t.timestamp() - t0) for t in timestamps]

    slope, intercept, r_squared = linear_regression(x_values, values)

    n = len(values)
    mean_x = sum(x_values) / n
    ss_x = sum((x - mean_x) ** 2 for x in x_values)
    residuals = [
        y - (slope * x + intercept)
        for x, y in zip(x_values, values)
    ]
    mse = sum(r ** 2 for r in residuals) / (n - 2) if n > 2 else 0
    std_error = math.sqrt(mse) if mse > 0 else 0

    t_value = 1.96 if confidence_level == 0.95 else 2.576

    forecast_points = []
    last_time = timestamps[-1]
    last_x = x_values[-1]

    for i in range(1, periods + 1):
        x_forecast = last_x + i * interval_seconds
        predicted = slope * x_forecast + intercept

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
                confidence_level=confidence_level,
            )
        )

    return forecast_points, r_squared


def exponential_forecast(
    data: List[TrendData],
    periods: int,
    interval_seconds: float,
    confidence_level: float,
) -> Tuple[List[ForecastPoint], float]:
    """Forecast using exponential smoothing."""
    values = [d.value for d in data]
    timestamps = [d.timestamp for d in data]

    alpha = 0.3
    beta = 0.1

    level = values[0]
    trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0

    fitted_values = [level]
    for i in range(1, len(values)):
        prev_level = level
        level = alpha * values[i] + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
        fitted_values.append(level + trend)

    residuals = [a - f for a, f in zip(values, fitted_values)]
    mse = sum(r ** 2 for r in residuals) / len(residuals)
    std_error = math.sqrt(mse) if mse > 0 else 0

    mean_y = sum(values) / len(values)
    ss_tot = sum((y - mean_y) ** 2 for y in values)
    ss_res = sum(r ** 2 for r in residuals)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    t_value = 1.96 if confidence_level == 0.95 else 2.576
    forecast_points = []
    last_time = timestamps[-1]

    for i in range(1, periods + 1):
        predicted = level + i * trend
        interval_width = t_value * std_error * math.sqrt(1 + i * 0.1)

        forecast_points.append(
            ForecastPoint(
                timestamp=last_time + timedelta(seconds=i * interval_seconds),
                predicted_value=predicted,
                lower_bound=predicted - interval_width,
                upper_bound=predicted + interval_width,
                confidence_level=confidence_level,
            )
        )

    return forecast_points, max(0, r_squared)


def moving_average_forecast(
    data: List[TrendData],
    periods: int,
    interval_seconds: float,
    confidence_level: float,
) -> Tuple[List[ForecastPoint], float]:
    """Forecast using simple moving average."""
    values = [d.value for d in data]
    timestamps = [d.timestamp for d in data]

    window = min(7, len(values))
    recent_values = values[-window:]
    avg = sum(recent_values) / len(recent_values)
    std_dev = math.sqrt(
        sum((v - avg) ** 2 for v in recent_values) / len(recent_values)
    )

    total_var = sum((v - avg) ** 2 for v in values) / len(values)
    r_squared = 1 - (std_dev ** 2 / total_var) if total_var > 0 else 0

    t_value = 1.96 if confidence_level == 0.95 else 2.576
    forecast_points = []
    last_time = timestamps[-1]

    for i in range(1, periods + 1):
        interval_width = t_value * std_dev * math.sqrt(1 + i * 0.05)

        forecast_points.append(
            ForecastPoint(
                timestamp=last_time + timedelta(seconds=i * interval_seconds),
                predicted_value=avg,
                lower_bound=avg - interval_width,
                upper_bound=avg + interval_width,
                confidence_level=confidence_level,
            )
        )

    return forecast_points, max(0, r_squared)
