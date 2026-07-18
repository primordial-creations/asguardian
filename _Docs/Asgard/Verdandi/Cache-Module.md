# Verdandi Cache Module

## Overview

The Cache module provides analysis for cache performance metrics: hit rates and efficiency, eviction patterns and TTL economics, trajectory-aware warm-up classification, and segmented (hit/miss) latency SLOs.

Key semantics:

- **Warm-up drops are expected; flatlines are not** (DEEPTHINK_08): post-deploy hit-rate dips with a positive recovery slope are classified `WARMING` and suppressed; plunge-and-flatline is the broken-connection signature and is `CRITICAL` immediately.
- **Blended latency percentiles mask cache regressions** (DEEPTHINK_04): hit and miss paths carry independent threshold-fraction SLIs, and a hit-mode median shift > 3× baseline MAD raises a fast-path-regression alarm even when blended p99 stays green.
- **Cache stampedes are a concurrency signature, not a rate signature**: many concurrent misses on the same expiring key cluster within one recompute window; XFetch's probabilistic early recomputation spreads that cluster out before it happens.

## Services

### 1. Cache Calculator (`CacheMetricsCalculator`)

**Purpose**: Analyzes cache hit rates, efficiency, per-key value, and hit-rate trends.

**Health status** (hit rate): excellent ≥ 95%, good ≥ 85%, fair ≥ 70%, else poor.

**Usage**:
```python
from Asgard.Verdandi.Cache import CacheMetricsCalculator

calc = CacheMetricsCalculator()

result = calc.analyze(
    hits=9500,
    misses=500,
    avg_hit_latency_ms=2.0,
    avg_miss_latency_ms=45.0,
    size_bytes=800_000_000,
    max_size_bytes=1_000_000_000,
)
print(f"Hit Rate: {result.hit_rate_percent}%  Status: {result.status}")

efficiency = calc.calculate_efficiency(result)
print(f"Efficiency: {efficiency.efficiency_score}/100")

# Time-series trend (delegates to WarmupAnalyzer)
history = [
    {"timestamp": 1, "hits": 900, "misses": 100},
    {"timestamp": 2, "hits": 500, "misses": 500},   # post-deploy drop
    {"timestamp": 3, "hits": 700, "misses": 300},   # recovering
]
trend = calc.analyze_trend(history)
print(trend.state)            # WarmupState.WARMING / FLATLINED / COLLAPSED / STABLE
print(trend.suppress_alert)   # True while recovering

# Per-key analysis
key_stats = [
    {"key": "user:123", "hits": 500, "misses": 10},
    {"key": "product:456", "hits": 100, "misses": 500},
]
keys = calc.analyze_keys(key_stats)
for k in keys.low_hit_rate_keys:
    print(f"Low hit rate: {k.key} ({k.hit_rate:.1%})")
print(keys.do_not_cache_candidates)  # low-hit, high-churn keys
```

---

### 2. Warm-up Trajectory Analyzer (`WarmupAnalyzer`)

**Purpose**: Derivative-based classification of hit-rate trajectories after a drop.

| State | Meaning | Alerting |
|-------|---------|----------|
| `WARMING` | Drop with positive recovery slope; exponential fit gives `tau_buckets` and `eta_buckets` | Suppressed |
| `FLATLINED` | Drop that is not recovering (plunge-and-flatline) | CRITICAL, bypasses suppression |
| `COLLAPSED` | Hit rate < 5% at any point | CRITICAL immediately, no grace |
| `STABLE` | No drop ≥ 15 points | — |
| `INSUFFICIENT_DATA` | < 3 buckets with traffic | Never alerts |

An optional aligned downstream DB-load series is correlated with the miss rate; Pearson r > 0.8 removes suppression even while warming (the misses are landing on the database).

```python
from Asgard.Verdandi.Cache import WarmupAnalyzer

analyzer = WarmupAnalyzer(drop_threshold=15.0, grace_buckets=3)
result = analyzer.analyze(history, db_load_series=[10.0, 55.0, 30.0])
print(result.state, result.recovery_slope, result.eta_buckets, result.db_correlation)
```

---

### 3. Segmented SLO Analyzer (`SegmentedSloAnalyzer`)

**Purpose**: Independent hit-path and miss-path threshold-fraction SLIs.

Defaults: hits within **20 ms**, misses within **1000 ms**; hit ratio reported as its own SLI. `hit_good/hit_total` and `miss_good/miss_total` are directly consumable by the SLO module's good/total trackers.

```python
from Asgard.Verdandi.Cache import SegmentedSloAnalyzer

slo = SegmentedSloAnalyzer(hit_threshold_ms=20, miss_threshold_ms=1000)

result = slo.analyze(
    hit_latencies_ms=[8, 12, 11],
    miss_latencies_ms=[700, 900],
    baseline_hit_median_ms=10.0,
    baseline_hit_mad_ms=2.0,
)
print(result.hit_sli, result.miss_sli, result.hit_ratio)
print(result.mode_shift_alert)  # True when hit-mode median moves > 3x baseline MAD

# Unlabeled fallback: splits modes with the Anomaly bimodality guard
approx = slo.analyze_unlabeled(latencies_ms=[...])
print(approx.labeled)  # False — treat SLIs as approximate
```

---

### 4. Eviction Analyzer (`EvictionAnalyzer`)

**Purpose**: Eviction rates, reasons, TTL economics, and working-set sizing.

**Usage**:
```python
from Asgard.Verdandi.Cache import EvictionAnalyzer

analyzer = EvictionAnalyzer()

result = analyzer.analyze(
    evictions=100,
    duration_seconds=3600,
    total_operations=10_000,
    by_reason={"ttl": 60, "lru": 40},
    avg_entry_age_seconds=420.0,
    premature_evictions=10,
)
print(f"Eviction Rate: {result.eviction_rate_per_sec}/s  Status: {result.status}")

# TTL-distribution and eviction economics
events = [
    {"key": "user:100", "reason": "EXPIRED", "age_seconds": 3420,
     "ttl_seconds": 3600, "refetch_interval_seconds": 7200},
    {"key": "product:200", "reason": "LRU", "age_seconds": 300, "ttl_seconds": 3600},
]
ttl = analyzer.analyze_ttl_patterns(events, lru_bytes_per_sec=1_000_000)
print(ttl.ttl_too_short, ttl.suggested_ttl_seconds)   # TTL short -> p75(refetch interval)
print(ttl.cache_undersized, ttl.working_set_bytes)    # LRU pressure -> sizing estimate
```

**Heuristics**:
- **TTL too short**: ≥ 60% of EXPIRED evictions die at age ≥ 0.9×TTL *and* are re-fetched soon after → `suggested_ttl_seconds = p75(refetch_interval)`.
- **Cache undersized**: LRU share > 40% with average LRU age < 0.25×median TTL → working set ≈ `lru_bytes_per_sec × avg_age`, recommended size = working set / 0.9.

---

### 5. Stampede / XFetch Analyzer (`StampedeAnalyzer`)

**Purpose**: Detect cache-stampede / thundering-herd events on expiring hot
keys and recommend XFetch (probabilistic early recomputation).

**Usage**:
```python
from Asgard.Verdandi.Cache import StampedeAnalyzer

analyzer = StampedeAnalyzer()

# Per-key access log: {key, t (ms), hit, recompute_ms?, ttl_s?}
access_log = [
    {"key": "hot:1", "t": i * 0.5, "hit": False, "recompute_ms": 40.0, "ttl_s": 60}
    for i in range(50)
]
report = analyzer.analyze(access_log)
for k in report.flagged_keys:
    print(k.key, k.stampede_factor, k.xfetch_rule)
```

**Heuristics**:
- **Stampede signature**: for each key, cluster misses that fall within one
  observed recompute window (`Delta` = p95 `recompute_ms`) after an expiry.
  `stampede_factor = concurrent_misses`; `factor > 5` → flagged.
- **XFetch rule**: `fetch_early when: now + Delta * beta * ln(1/rand()) >= expiry`
  (`beta = 1.0` by default), reported per flagged key along with a heuristic
  estimate of stampede-probability reduction.
- **TTL-vs-Delta sanity**: `Delta > 0.1 x TTL` → `ttl_too_short_for_delta`,
  recommending a longer TTL or refresh-ahead instead of expire-and-recompute.

---

## CLI Usage

```bash
python -m Asgard.Verdandi cache analyze stats.json
python -m Asgard.Verdandi cache eviction events.json
```

---

## Models Reference

### CacheMetrics (result)
```python
class CacheMetrics(BaseModel):
    total_requests: int
    hits: int
    misses: int
    hit_rate_percent: float
    miss_rate_percent: float
    avg_hit_latency_ms: Optional[float]
    avg_miss_latency_ms: Optional[float]
    latency_savings_ms: Optional[float]
    size_bytes: Optional[int]
    max_size_bytes: Optional[int]
    fill_percent: Optional[float]
    status: str                    # excellent | good | fair | poor
    recommendations: List[str]
```

### WarmupTrajectory
```python
class WarmupTrajectory(BaseModel):
    state: WarmupState             # stable | warming | flatlined | collapsed | insufficient_data
    severity: str                  # info | warning | critical
    suppress_alert: bool
    baseline_hit_rate: Optional[float]
    drop_pct: Optional[float]
    drop_index: Optional[int]
    recovery_slope: Optional[float]
    tau_buckets: Optional[float]
    eta_buckets: Optional[float]
    db_correlation: Optional[float]
    notes: List[str]
```

### SegmentedCacheSLO
```python
class SegmentedCacheSLO(BaseModel):
    hit_sli: Optional[float]       # frac(hit latencies <= hit_threshold_ms)
    miss_sli: Optional[float]      # frac(miss latencies <= miss_threshold_ms)
    hit_threshold_ms: float
    miss_threshold_ms: float
    hit_good: int; hit_total: int
    miss_good: int; miss_total: int
    hit_ratio: Optional[float]
    hit_median_ms: Optional[float]
    mode_shift_alert: bool
    mode_shift_details: Optional[str]
    labeled: bool
    notes: List[str]
```

### KeyAnalysisResult / KeyStats
```python
class KeyStats(BaseModel):
    key: str
    hits: int
    misses: int
    hit_rate: float                # 0-1
    total: int

class KeyAnalysisResult(BaseModel):
    keys: List[KeyStats]
    low_hit_rate_keys: List[KeyStats]
    do_not_cache_candidates: List[KeyStats]
    overall_hit_rate: float
    recommendations: List[str]
```

### TTLAnalysis
```python
class TTLAnalysis(BaseModel):
    total_evictions: int
    expired_share: Optional[float]
    expired_near_ttl_fraction: Optional[float]
    ttl_too_short: bool
    suggested_ttl_seconds: Optional[float]
    lru_share: Optional[float]
    cache_undersized: bool
    working_set_bytes: Optional[float]
    recommended_size_bytes: Optional[float]
    recommendations: List[str]
    notes: List[str]
```

### StampedeReport / StampedeKeyReport
```python
class StampedeKeyReport(BaseModel):
    key: str
    concurrent_misses: int
    stampede_factor: float          # concurrent_misses / expected_1
    flagged: bool                   # factor > 5
    delta_ms: Optional[float]       # p95 observed recompute time
    ttl_s: Optional[float]
    xfetch_rule: Optional[str]
    expected_stampede_reduction_pct: Optional[float]
    ttl_too_short_for_delta: bool   # Delta > 0.1 x TTL
    notes: List[str]

class StampedeReport(BaseModel):
    keys: List[StampedeKeyReport]
    flagged_keys: List[StampedeKeyReport]
    total_keys_analyzed: int
    beta: float
    status: str                     # healthy | warning | critical
    recommendations: List[str]
    notes: List[str]
```

### EvictionMetrics (result)
```python
class EvictionMetrics(BaseModel):
    total_evictions: int
    eviction_rate_per_sec: float
    eviction_percent: float
    by_reason: Dict[str, int]      # ttl, lru, size, manual
    avg_entry_age_seconds: Optional[float]
    premature_evictions: int
    status: str
    recommendations: List[str]
```

---

## Best Practices

### Hit Rate
- Target > 90% for frequently accessed data, but judge drops by trajectory, not level: a recovering dip is warm-up; a flatlined dip is an outage.
- Never suppress cache alerts on a fixed post-deploy timer — monitor the recovery slope instead.

### Latency SLOs
- Do not put one latency SLO over a hit/miss mixture; give each path its own budget and track the hit ratio as an SLI.
- Watch the hit-mode median: a 10 ms → 200 ms fast-path shift can hide inside a green blended p99.

### TTL & Sizing
- Evictions at age ≈ TTL followed by quick refetches mean the TTL is too short; size TTL to the refetch interval.
- High LRU shares with young evictions mean the working set does not fit; size to working set with ~10% headroom.
