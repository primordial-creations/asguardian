"""
Verdandi Trend - Performance Trend Analysis

This module provides trend analysis capabilities including:
- Trend detection and analysis over time
- Performance forecasting
- Robust STL-lite seasonal decomposition (additive/multiplicative)

Usage:
    from Asgard.Verdandi.Trend import TrendAnalyzer, ForecastCalculator

    # Analyze trends
    analyzer = TrendAnalyzer()
    trend = analyzer.analyze(time_series_data)

    # Forecast future performance
    forecaster = ForecastCalculator()
    forecast = forecaster.forecast(historical_data, periods=7)
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.Trend.models.trend_models import (
    TrendDirection,
    TrendData,
    TrendAnalysis,
    ForecastResult,
    TrendReport,
    DecompositionMode,
    DecompositionOutcome,
    SeasonalDecomposition,
)
from Asgard.Verdandi.Trend.services.trend_analyzer import TrendAnalyzer
from Asgard.Verdandi.Trend.services.forecast_calculator import ForecastCalculator
from Asgard.Verdandi.Trend.services.seasonal_decomposer import SeasonalDecomposer

__all__ = [
    # Models
    "TrendDirection",
    "TrendData",
    "TrendAnalysis",
    "ForecastResult",
    "TrendReport",
    "DecompositionMode",
    "DecompositionOutcome",
    "SeasonalDecomposition",
    # Services
    "TrendAnalyzer",
    "ForecastCalculator",
    "SeasonalDecomposer",
]
