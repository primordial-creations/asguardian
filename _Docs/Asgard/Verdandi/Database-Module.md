# Verdandi Database Module

## Overview

The Database module provides performance analysis for database operations including query execution metrics, throughput calculations, and connection pool analysis.

## Services

### 1. Query Metrics Analyzer

**Purpose**: Analyzes query execution times and identifies performance issues.

**Key Metrics**:
- Execution time percentiles (P50, P95, P99)
- Slow query identification
- Query type breakdown (SELECT, INSERT, UPDATE, DELETE)
- Table/index usage analysis

**Slow Query Thresholds**:
| Category | Duration |
|----------|----------|
| Fast | < 10ms |
| Normal | 10-100ms |
| Slow | 100-1000ms |
| Very Slow | > 1000ms |

**Usage**:
```python
from Verdandi.Database import QueryMetricsAnalyzer

analyzer = QueryMetricsAnalyzer()

query_data = [
    {"query": "SELECT * FROM users WHERE id = ?", "duration_ms": 5, "type": "SELECT"},
    {"query": "SELECT * FROM orders WHERE user_id = ?", "duration_ms": 150, "type": "SELECT"},
    {"query": "INSERT INTO logs VALUES (?)", "duration_ms": 20, "type": "INSERT"},
    {"query": "UPDATE users SET last_login = ?", "duration_ms": 30, "type": "UPDATE"},
]

result = analyzer.analyze(query_data)

print(f"Total Queries: {result.total_count}")
print(f"P50 Duration: {result.p50_ms}ms")
print(f"P99 Duration: {result.p99_ms}ms")
print(f"Slow Queries: {result.slow_query_count}")

# By query type
for query_type, stats in result.by_type.items():
    print(f"{query_type}: {stats.count} queries, avg {stats.avg_ms:.1f}ms")

# Slow query details
for slow in result.slow_queries:
    print(f"SLOW: {slow.query} ({slow.duration_ms}ms)")
```

---

### 2. Throughput Calculator

**Purpose**: Calculates database throughput metrics including QPS, TPS, and IOPS.

**Throughput Metrics**:
| Metric | Description |
|--------|-------------|
| QPS | Queries Per Second |
| TPS | Transactions Per Second |
| IOPS | I/O Operations Per Second |
| Read QPS | Read queries per second |
| Write QPS | Write queries per second |

**Usage**:
```python
from Verdandi.Database import ThroughputCalculator

calculator = ThroughputCalculator()

# From time-series data
data = [
    {"timestamp": 1000, "queries": 150, "reads": 120, "writes": 30},
    {"timestamp": 2000, "queries": 180, "reads": 140, "writes": 40},
    {"timestamp": 3000, "queries": 160, "reads": 130, "writes": 30},
]

result = calculator.calculate(data)

print(f"Average QPS: {result.avg_qps:.1f}")
print(f"Peak QPS: {result.peak_qps:.1f}")
print(f"Read QPS: {result.read_qps:.1f}")
print(f"Write QPS: {result.write_qps:.1f}")
print(f"Read/Write Ratio: {result.read_write_ratio:.1f}")

# From raw counts
result = calculator.calculate_from_counts(
    total_queries=10000,
    duration_seconds=60,
    read_count=8000,
    write_count=2000
)
```

---

### 3. Connection Pool Analyzer

**Purpose**: Analyzes database connection pool utilization and efficiency.

**Pool Metrics**:
- Active connections
- Idle connections
- Total pool size
- Wait queue length
- Connection acquisition time
- Pool utilization percentage

**Health Status**:
| Status | Utilization |
|--------|-------------|
| HEALTHY | < 70% |
| WARNING | 70-85% |
| CRITICAL | > 85% |

**Queue-wait vs service-time separation** (RESEARCH_14): in-process query timers measure service time only. Pass per-request `acquisition_wait_samples` (the `wait_for_connection` child-span pattern) to get wait p50/p95/p99 and `queue_share = wait_p95 / (wait_p95 + service_p95)` — otherwise the database looks healthy while requests queue for connections.

**Little's-law sizing** (RESEARCH_12): with `qps` and `avg_query_ms`, `required_connections = qps × avg_query_s`; `headroom = pool_size − required`; `recommended_pool_size = ceil(required / 0.7)` (70% target utilization).

**Leak heuristic**: timeouts at < 70% utilization set `leak_suspected=True` — connections are held, not busy.

**Usage**:
```python
from Asgard.Verdandi.Database import ConnectionAnalyzer

analyzer = ConnectionAnalyzer()

metrics = analyzer.analyze(
    pool_size=25,
    active_connections=20,
    waiting_requests=3,
    acquisition_wait_samples=[1.2, 0.8, 95.0, 1.1],  # ms
    qps=200,
    avg_query_ms=100,
    service_p95_ms=30.0,
    timeout_count=0,
)

print(f"Utilization: {metrics.utilization_percent:.1f}%")
print(f"Wait p95: {metrics.wait_p95_ms}ms  queue_share: {metrics.queue_share}")
print(f"Required: {metrics.required_connections}  Recommended: {metrics.recommended_pool_size}")

for rec in analyzer.get_recommendations(metrics):
    print(f"  - {rec}")
```

---

### 4. Pool Signature Detector (`PoolSignatureDetector`)

**Purpose**: Classifies bimodal query-latency distributions (RESEARCH_11).

Pool exhaustion produces **two near-equal-variance peaks** whose separation *is* the mean queue wait; cache-aside bimodality has a narrow fast peak and a wide slow peak. Blended mean/median are meaningless during exhaustion.

| Classification | Rule | Meaning |
|----------------|------|---------|
| `POOL_EXHAUSTION` | `\|s1−s2\|/max(s1,s2) < 0.35` | `mean_queue_wait_ms ≈ m2 − m1` |
| `CACHE_ASIDE_PATTERN` | `s2 > 2×s1` | Route to Cache segmented SLOs |
| `AMBIGUOUS_BIMODAL` | Neither template | Investigate per-mode membership |
| `UNIMODAL` / `INSUFFICIENT_DATA` | — | No signature / starved |

Optional `acquisition_wait_samples` corroborate: p50(wait) within ±25% of the inter-peak distance raises confidence to HIGH.

```python
from Asgard.Verdandi.Database import PoolSignatureDetector, PoolSignatureClass

detector = PoolSignatureDetector()
signature = detector.detect(latencies_ms, acquisition_wait_samples=waits_ms)

if signature.classification == PoolSignatureClass.POOL_EXHAUSTION:
    print(f"Mean queue wait: {signature.mean_queue_wait_ms}ms "
          f"(confidence: {signature.confidence})")
```

---

## CLI Usage

```bash
# Query metrics analysis
python -m Verdandi database queries query_logs.json
python -m Verdandi database queries data.json --slow-threshold=100

# Throughput calculation
python -m Verdandi database throughput metrics.json
python -m Verdandi database throughput data.json --window=60

# Connection pool analysis
python -m Verdandi database connections pool_stats.json
python -m Verdandi database connections data.json --format=json
```

---

## Models Reference

### QueryMetricsInput
```python
class QueryMetricsInput(BaseModel):
    query: str
    duration_ms: float
    type: Optional[str] = None  # SELECT, INSERT, UPDATE, DELETE
    table: Optional[str] = None
    rows_affected: Optional[int] = None
    timestamp: Optional[float] = None
```

### QueryMetricsResult
```python
class QueryMetricsResult(BaseModel):
    total_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    max_ms: float
    slow_query_count: int
    slow_query_threshold_ms: float
    by_type: Dict[str, QueryTypeStats]
    slow_queries: List[SlowQueryInfo]
```

### ThroughputResult
```python
class ThroughputResult(BaseModel):
    avg_qps: float
    peak_qps: float
    min_qps: float
    read_qps: float
    write_qps: float
    read_write_ratio: float
    total_queries: int
    duration_seconds: float
```

### ConnectionPoolMetrics
```python
class ConnectionPoolMetrics(BaseModel):
    pool_size: int
    active_connections: int
    idle_connections: int
    waiting_requests: int
    utilization_percent: float
    average_wait_time_ms: float
    max_wait_time_ms: float
    connection_errors: int
    timeout_count: int
    wait_p50_ms: Optional[float]
    wait_p95_ms: Optional[float]
    wait_p99_ms: Optional[float]
    queue_share: Optional[float]
    required_connections: Optional[float]
    headroom_connections: Optional[float]
    recommended_pool_size: Optional[int]
    leak_suspected: bool
```

### PoolSignature
```python
class PoolSignature(BaseModel):
    classification: PoolSignatureClass  # pool_exhaustion | cache_aside_pattern |
                                        # ambiguous_bimodal | unimodal | insufficient_data
    mean_queue_wait_ms: Optional[float]
    modes: List[PoolModeStats]          # median_ms, mad_ms, count, weight
    mad_disparity: Optional[float]
    confidence: str                     # low | medium | high
    corroborated_by_wait_samples: bool
    warnings: List[str]
    recommendations: List[str]
```

---

## Best Practices

### Query Performance
- P99 latency should be < 100ms for user-facing queries
- Identify and optimize queries with > 1000ms execution time
- Monitor query type distribution (read-heavy vs write-heavy)

### Throughput
- Establish baseline QPS during normal operation
- Alert on significant deviations (> 2x baseline)
- Monitor read/write ratio changes

### Connection Pools
- Keep utilization below 70% for headroom
- Set appropriate timeouts to prevent connection leaks
- Right-size pool based on observed peak usage
