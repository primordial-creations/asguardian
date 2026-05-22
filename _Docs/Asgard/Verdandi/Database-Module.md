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

**Usage**:
```python
from Verdandi.Database import ConnectionPoolAnalyzer

analyzer = ConnectionPoolAnalyzer()

pool_data = {
    "max_size": 100,
    "active": 45,
    "idle": 30,
    "waiting": 5,
    "avg_acquisition_ms": 2.5,
    "max_acquisition_ms": 50.0,
    "timeouts": 2
}

result = analyzer.analyze(pool_data)

print(f"Utilization: {result.utilization_percent:.1f}%")
print(f"Status: {result.health_status}")
print(f"Active: {result.active_connections}")
print(f"Idle: {result.idle_connections}")
print(f"Waiting: {result.waiting_count}")

# Recommendations
for rec in result.recommendations:
    print(f"  - {rec}")
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

### ConnectionPoolResult
```python
class ConnectionPoolResult(BaseModel):
    max_size: int
    active_connections: int
    idle_connections: int
    waiting_count: int
    utilization_percent: float
    avg_acquisition_ms: float
    max_acquisition_ms: float
    timeout_count: int
    health_status: str  # HEALTHY, WARNING, CRITICAL
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
