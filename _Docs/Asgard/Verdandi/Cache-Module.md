# Verdandi Cache Module

## Overview

The Cache module provides analysis for cache performance metrics including hit rates, efficiency calculations, and eviction pattern analysis.

## Services

### 1. Cache Calculator

**Purpose**: Analyzes cache hit rates and efficiency metrics.

**Cache Metrics**:
| Metric | Description |
|--------|-------------|
| Hit Rate | Percentage of requests served from cache |
| Miss Rate | Percentage of requests requiring origin fetch |
| Hit Ratio | Hits / (Hits + Misses) |
| Byte Hit Rate | Bytes served from cache vs total |
| Efficiency | Combined effectiveness score |

**Health Status**:
| Status | Hit Rate |
|--------|----------|
| EXCELLENT | >= 95% |
| GOOD | >= 85% |
| FAIR | >= 70% |
| POOR | >= 50% |
| CRITICAL | < 50% |

**Usage**:
```python
from Verdandi.Cache import CacheCalculator

calculator = CacheCalculator()

cache_data = {
    "hits": 9500,
    "misses": 500,
    "bytes_served": 1_000_000_000,
    "bytes_from_cache": 900_000_000,
    "total_requests": 10000
}

result = calculator.analyze(cache_data)

print(f"Hit Rate: {result.hit_rate:.1%}")
print(f"Miss Rate: {result.miss_rate:.1%}")
print(f"Byte Hit Rate: {result.byte_hit_rate:.1%}")
print(f"Efficiency Score: {result.efficiency_score:.1f}/100")
print(f"Status: {result.health_status}")

# Time-series analysis
history = [
    {"timestamp": 1, "hits": 900, "misses": 100},
    {"timestamp": 2, "hits": 920, "misses": 80},
    {"timestamp": 3, "hits": 850, "misses": 150},
]
trend_result = calculator.analyze_trend(history)
print(f"Trend: {trend_result.trend}")

# Per-key analysis
key_stats = [
    {"key": "user:123", "hits": 500, "misses": 10},
    {"key": "product:456", "hits": 100, "misses": 50},
    {"key": "session:789", "hits": 1000, "misses": 5},
]
key_result = calculator.analyze_keys(key_stats)
for key in key_result.low_hit_rate_keys:
    print(f"Low hit rate: {key.key} ({key.hit_rate:.1%})")
```

---

### 2. Eviction Analyzer

**Purpose**: Analyzes cache eviction patterns and provides optimization recommendations.

**Eviction Metrics**:
| Metric | Description |
|--------|-------------|
| Eviction Rate | Evictions per second |
| Eviction Reason | Why items were evicted |
| TTL Distribution | Time-to-live patterns |
| Memory Pressure | Memory-based eviction frequency |
| LRU Efficiency | How well LRU is working |

**Eviction Reasons**:
| Reason | Description |
|--------|-------------|
| EXPIRED | TTL expired |
| LRU | Least recently used |
| LFU | Least frequently used |
| MEMORY | Memory pressure |
| MANUAL | Explicitly deleted |

**Usage**:
```python
from Verdandi.Cache import EvictionAnalyzer

analyzer = EvictionAnalyzer()

eviction_data = [
    {"key": "user:100", "reason": "EXPIRED", "age_seconds": 3600, "size_bytes": 1024},
    {"key": "product:200", "reason": "LRU", "age_seconds": 300, "size_bytes": 2048},
    {"key": "session:300", "reason": "MEMORY", "age_seconds": 60, "size_bytes": 512},
    {"key": "cache:400", "reason": "EXPIRED", "age_seconds": 7200, "size_bytes": 4096},
]

result = analyzer.analyze(eviction_data)

print(f"Total Evictions: {result.total_evictions}")
print(f"Eviction Rate: {result.evictions_per_second:.2f}/s")
print(f"Avg Age at Eviction: {result.avg_age_seconds:.0f}s")

# By reason
for reason, stats in result.by_reason.items():
    print(f"{reason}: {stats.count} ({stats.percentage:.1%})")

# Recommendations
for rec in result.recommendations:
    print(f"  - {rec}")

# TTL optimization suggestions
ttl_analysis = analyzer.analyze_ttl_patterns(eviction_data)
print(f"Suggested TTL: {ttl_analysis.suggested_ttl_seconds}s")
```

---

## CLI Usage

```bash
# Cache performance analysis
python -m Verdandi cache analyze stats.json
python -m Verdandi cache analyze data.json --format=json

# Eviction analysis
python -m Verdandi cache eviction events.json
python -m Verdandi cache eviction data.json --format=markdown
```

---

## Models Reference

### CacheMetrics
```python
class CacheMetrics(BaseModel):
    hits: int
    misses: int
    bytes_served: Optional[int] = None
    bytes_from_cache: Optional[int] = None
    total_requests: int
    memory_used_bytes: Optional[int] = None
    memory_limit_bytes: Optional[int] = None
```

### CacheResult
```python
class CacheResult(BaseModel):
    hit_rate: float
    miss_rate: float
    byte_hit_rate: Optional[float]
    efficiency_score: float  # 0-100
    memory_utilization: Optional[float]
    health_status: str
    recommendations: List[str]
```

### EvictionMetrics
```python
class EvictionMetrics(BaseModel):
    key: str
    reason: str  # EXPIRED, LRU, LFU, MEMORY, MANUAL
    age_seconds: float
    size_bytes: int
    timestamp: Optional[float] = None
```

### EvictionResult
```python
class EvictionResult(BaseModel):
    total_evictions: int
    evictions_per_second: float
    avg_age_seconds: float
    avg_size_bytes: float
    by_reason: Dict[str, EvictionReasonStats]
    memory_pressure_detected: bool
    recommendations: List[str]
```

### CacheEfficiency
```python
class CacheEfficiency(BaseModel):
    overall_score: float  # 0-100
    hit_rate_score: float
    byte_efficiency_score: float
    memory_efficiency_score: float
    eviction_health_score: float
    grade: str  # A, B, C, D, F
```

---

## Best Practices

### Hit Rate Optimization
- Target > 90% hit rate for frequently accessed data
- Identify and pre-warm cold cache entries
- Use appropriate TTLs based on data freshness requirements

### Memory Management
- Keep memory utilization below 90%
- Monitor memory pressure evictions
- Size cache appropriately for working set

### TTL Strategy
- Short TTLs for volatile data (sessions, counters)
- Longer TTLs for stable data (configs, reference data)
- Consider refresh-ahead for critical data

### Eviction Patterns
- High LRU evictions suggest undersized cache
- High memory evictions indicate memory pressure
- Frequent expired evictions may allow longer TTLs

---

## Cache Efficiency Grading

The cache efficiency grade combines multiple factors:

| Grade | Score | Description |
|-------|-------|-------------|
| A | 90-100 | Excellent cache performance |
| B | 80-89 | Good performance, minor improvements possible |
| C | 70-79 | Fair performance, optimization recommended |
| D | 60-69 | Poor performance, significant issues |
| F | < 60 | Critical issues, immediate action needed |

**Score Components**:
- Hit Rate (40%): Based on request hit rate
- Byte Efficiency (25%): Based on byte hit rate
- Memory Efficiency (20%): Based on memory utilization
- Eviction Health (15%): Based on eviction patterns
