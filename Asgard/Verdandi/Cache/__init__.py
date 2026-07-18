"""
Verdandi Cache - Cache Performance Metrics

This module provides cache performance metric calculations including:
- Hit/miss ratio calculations
- Eviction rate tracking
- Fill rate analysis
- Cache efficiency metrics

Usage:
    from Asgard.Verdandi.Cache import CacheMetricsCalculator

    calc = CacheMetricsCalculator()
    result = calc.analyze(hits=950, misses=50, evictions=100)
    print(f"Hit Rate: {result.hit_rate_percent}%")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.Cache.models.cache_models import (
    CacheMetrics,
    CacheEfficiency,
    EvictionMetrics,
    KeyAnalysisResult,
    KeyStats,
    SegmentedCacheSLO,
    StampedeKeyReport,
    StampedeReport,
    TTLAnalysis,
    WarmupState,
    WarmupTrajectory,
)
from Asgard.Verdandi.Cache.services.cache_calculator import CacheMetricsCalculator
from Asgard.Verdandi.Cache.services.eviction_analyzer import EvictionAnalyzer
from Asgard.Verdandi.Cache.services.warmup_analyzer import WarmupAnalyzer
from Asgard.Verdandi.Cache.services.segmented_slo import SegmentedSloAnalyzer
from Asgard.Verdandi.Cache.services.stampede_analyzer import StampedeAnalyzer

__all__ = [
    "CacheEfficiency",
    "CacheMetricsCalculator",
    "CacheMetrics",
    "EvictionAnalyzer",
    "EvictionMetrics",
    "KeyAnalysisResult",
    "KeyStats",
    "SegmentedCacheSLO",
    "SegmentedSloAnalyzer",
    "StampedeAnalyzer",
    "StampedeKeyReport",
    "StampedeReport",
    "TTLAnalysis",
    "WarmupAnalyzer",
    "WarmupState",
    "WarmupTrajectory",
]
