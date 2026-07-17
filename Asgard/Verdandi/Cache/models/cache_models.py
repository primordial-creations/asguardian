"""
Cache Performance Models

Pydantic models for cache performance metrics.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WarmupState(str, Enum):
    """Classification of a post-drop hit-rate trajectory (DEEPTHINK_08)."""

    STABLE = "stable"
    WARMING = "warming"
    FLATLINED = "flatlined"
    COLLAPSED = "collapsed"
    INSUFFICIENT_DATA = "insufficient_data"


class WarmupTrajectory(BaseModel):
    """Warm-up trajectory analysis of a hit-rate time series."""

    state: WarmupState = Field(..., description="Trajectory classification")
    severity: str = Field(
        default="info", description="info | warning | critical"
    )
    suppress_alert: bool = Field(
        default=False,
        description="True while the drop is a recovering (WARMING) trajectory",
    )
    baseline_hit_rate: Optional[float] = Field(
        default=None, description="Pre-drop hit rate (percent)"
    )
    drop_pct: Optional[float] = Field(
        default=None, description="Points of hit rate lost at the trough"
    )
    drop_index: Optional[int] = Field(default=None, description="Bucket index of the drop")
    recovery_slope: Optional[float] = Field(
        default=None, description="Mean hit-rate derivative after the drop (pts/bucket)"
    )
    tau_buckets: Optional[float] = Field(
        default=None, description="Fitted exponential-recovery time constant (buckets)"
    )
    eta_buckets: Optional[float] = Field(
        default=None, description="Estimated buckets until back within 1pt of baseline"
    )
    db_correlation: Optional[float] = Field(
        default=None,
        description="Pearson r between miss rate and downstream DB load",
    )
    notes: List[str] = Field(default_factory=list)


class SegmentedCacheSLO(BaseModel):
    """Independent hit-path and miss-path threshold-fraction SLIs (DEEPTHINK_04)."""

    hit_sli: Optional[float] = Field(
        default=None, description="Fraction of hits within hit_threshold_ms"
    )
    miss_sli: Optional[float] = Field(
        default=None, description="Fraction of misses within miss_threshold_ms"
    )
    hit_threshold_ms: float = Field(default=20.0)
    miss_threshold_ms: float = Field(default=1000.0)
    hit_good: int = Field(default=0)
    hit_total: int = Field(default=0)
    miss_good: int = Field(default=0)
    miss_total: int = Field(default=0)
    hit_ratio: Optional[float] = Field(
        default=None, description="hits / (hits + misses) — its own SLI"
    )
    hit_median_ms: Optional[float] = Field(default=None)
    mode_shift_alert: bool = Field(
        default=False,
        description="Hit-mode median migrated > 3x baseline MAD (fast-path regression)",
    )
    mode_shift_details: Optional[str] = Field(default=None)
    labeled: bool = Field(
        default=True, description="False when hit/miss split came from bimodality fallback"
    )
    notes: List[str] = Field(default_factory=list)


class KeyStats(BaseModel):
    """Per-key cache statistics."""

    key: str = Field(...)
    hits: int = Field(default=0)
    misses: int = Field(default=0)
    hit_rate: float = Field(default=0.0, description="Hit fraction 0-1")
    total: int = Field(default=0)


class KeyAnalysisResult(BaseModel):
    """Per-key hit-rate analysis."""

    keys: List[KeyStats] = Field(default_factory=list)
    low_hit_rate_keys: List[KeyStats] = Field(
        default_factory=list, description="Keys under the low-hit threshold"
    )
    do_not_cache_candidates: List[KeyStats] = Field(
        default_factory=list,
        description="Low-hit high-churn keys with negative caching value",
    )
    overall_hit_rate: float = Field(default=0.0)
    recommendations: List[str] = Field(default_factory=list)


class TTLAnalysis(BaseModel):
    """TTL-distribution and eviction-economics analysis."""

    total_evictions: int = Field(default=0)
    expired_share: Optional[float] = Field(
        default=None, description="Fraction of evictions with reason EXPIRED"
    )
    expired_near_ttl_fraction: Optional[float] = Field(
        default=None,
        description="Fraction of EXPIRED evictions at age >= 0.9 x TTL",
    )
    ttl_too_short: bool = Field(default=False)
    suggested_ttl_seconds: Optional[float] = Field(
        default=None, description="p75 of observed refetch intervals when TTL too short"
    )
    lru_share: Optional[float] = Field(
        default=None, description="Fraction of evictions with reason LRU"
    )
    cache_undersized: bool = Field(default=False)
    working_set_bytes: Optional[float] = Field(
        default=None, description="Estimated working set (bytes)"
    )
    recommended_size_bytes: Optional[float] = Field(
        default=None, description="working_set / 0.9 headroom target"
    )
    recommendations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class CacheMetrics(BaseModel):
    """Cache performance metrics."""

    total_requests: int = Field(..., description="Total cache requests")
    hits: int = Field(..., description="Cache hits")
    misses: int = Field(..., description="Cache misses")
    hit_rate_percent: float = Field(..., description="Hit rate percentage")
    miss_rate_percent: float = Field(..., description="Miss rate percentage")
    avg_hit_latency_ms: Optional[float] = Field(default=None, description="Avg hit latency")
    avg_miss_latency_ms: Optional[float] = Field(default=None, description="Avg miss latency")
    latency_savings_ms: Optional[float] = Field(default=None, description="Latency saved by cache")
    size_bytes: Optional[int] = Field(default=None, description="Current cache size")
    max_size_bytes: Optional[int] = Field(default=None, description="Maximum cache size")
    fill_percent: Optional[float] = Field(default=None, description="Cache fill percentage")
    status: str = Field(..., description="Status (excellent, good, fair, poor)")
    recommendations: List[str] = Field(default_factory=list)


class EvictionMetrics(BaseModel):
    """Cache eviction metrics."""

    total_evictions: int = Field(..., description="Total evictions")
    eviction_rate_per_sec: float = Field(..., description="Evictions per second")
    eviction_percent: float = Field(..., description="Eviction percentage of total ops")
    by_reason: Dict[str, int] = Field(
        default_factory=dict,
        description="Evictions by reason (ttl, lru, size, manual)",
    )
    avg_entry_age_seconds: Optional[float] = Field(
        default=None,
        description="Avg age of evicted entries",
    )
    premature_evictions: int = Field(
        default=0,
        description="Entries evicted before natural expiry",
    )
    status: str = Field(..., description="Status")
    recommendations: List[str] = Field(default_factory=list)


class CacheEfficiency(BaseModel):
    """Overall cache efficiency assessment."""

    efficiency_score: float = Field(..., ge=0, le=100, description="Efficiency score 0-100")
    hit_rate_percent: float = Field(..., description="Hit rate")
    memory_efficiency_percent: float = Field(..., description="Memory utilization efficiency")
    latency_improvement_factor: Optional[float] = Field(
        default=None,
        description="How much faster hits are vs misses",
    )
    cost_savings_percent: Optional[float] = Field(
        default=None,
        description="Estimated cost savings from caching",
    )
    optimal_size_bytes: Optional[int] = Field(
        default=None,
        description="Recommended cache size",
    )
    status: str = Field(..., description="Overall status")
    recommendations: List[str] = Field(default_factory=list)
