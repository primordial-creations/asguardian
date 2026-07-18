"""
Verdandi Analysis - Statistical Analysis and Metrics Calculation

This module provides core statistical analysis tools including:
- Percentile calculations (P50, P75, P90, P95, P99, P99.9)
- Apdex score calculation
- SLA compliance checking
- Metric aggregation and trending
- Throughput calculations

Usage:
    from Asgard.Verdandi.Analysis import PercentileCalculator, ApdexCalculator

    # Calculate percentiles
    calc = PercentileCalculator()
    result = calc.calculate([100, 150, 200, 250, 300, 350, 400])
    print(f"P95: {result.p95}ms")

    # Calculate Apdex score
    apdex = ApdexCalculator(threshold_ms=500)
    score = apdex.calculate([100, 200, 300, 600, 800, 2500])
    print(f"Apdex: {score.score}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.Analysis.models.analysis_models import (
    ApdexConfig,
    ApdexRecalibrationRecord,
    ApdexResult,
    AggregationConfig,
    AggregationResult,
    MultiEndpointApdexResult,
    PercentileResult,
    SLAConfig,
    SLAResult,
    SLAStatus,
    TrendDirection,
    TrendResult,
)
from Asgard.Verdandi.Analysis.services.percentile_calculator import PercentileCalculator
from Asgard.Verdandi.Analysis.services.apdex_calculator import ApdexCalculator
from Asgard.Verdandi.Analysis.services.sla_checker import SLAChecker
from Asgard.Verdandi.Analysis.services.aggregation_service import AggregationService
from Asgard.Verdandi.Analysis.services.trend_analyzer import TrendAnalyzer

__all__ = [
    "ApdexCalculator",
    "ApdexConfig",
    "ApdexRecalibrationRecord",
    "ApdexResult",
    "MultiEndpointApdexResult",
    "AggregationConfig",
    "AggregationResult",
    "AggregationService",
    "PercentileCalculator",
    "PercentileResult",
    "SLAChecker",
    "SLAConfig",
    "SLAResult",
    "SLAStatus",
    "TrendAnalyzer",
    "TrendDirection",
    "TrendResult",
]
