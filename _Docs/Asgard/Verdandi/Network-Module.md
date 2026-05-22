# Verdandi Network Module

## Overview

The Network module provides analysis for network performance metrics including latency, bandwidth, and DNS resolution performance.

## Services

### 1. Latency Calculator

**Purpose**: Analyzes network latency and jitter metrics.

**Latency Metrics**:
| Metric | Description |
|--------|-------------|
| RTT | Round-trip time |
| Jitter | Variation in latency |
| Packet Loss | Percentage of lost packets |
| Min/Max/Avg | Basic statistics |
| Percentiles | P50, P95, P99 latency |

**Health Status**:
| Status | Condition |
|--------|-----------|
| EXCELLENT | RTT < 20ms, jitter < 5ms, loss < 0.1% |
| GOOD | RTT < 50ms, jitter < 10ms, loss < 1% |
| FAIR | RTT < 100ms, jitter < 20ms, loss < 2% |
| POOR | RTT < 200ms, jitter < 50ms, loss < 5% |
| CRITICAL | RTT > 200ms or jitter > 50ms or loss > 5% |

**Usage**:
```python
from Verdandi.Network import LatencyCalculator

calculator = LatencyCalculator()

# From ping samples
samples = [10, 12, 11, 15, 13, 12, 14, 11, 10, 200]  # ms
result = calculator.analyze(samples)

print(f"Average RTT: {result.avg_ms:.1f}ms")
print(f"Min: {result.min_ms:.1f}ms")
print(f"Max: {result.max_ms:.1f}ms")
print(f"P99: {result.p99_ms:.1f}ms")
print(f"Jitter: {result.jitter_ms:.1f}ms")
print(f"Status: {result.health_status}")

# With packet loss
result = calculator.analyze_with_loss(
    samples=samples,
    sent=100,
    received=98
)
print(f"Packet Loss: {result.packet_loss_percent:.1f}%")

# Multiple endpoints comparison
endpoints = {
    "api-east": [10, 12, 11, 13, 12],
    "api-west": [45, 48, 50, 47, 49],
    "cdn": [5, 6, 5, 7, 6],
}
comparison = calculator.compare_endpoints(endpoints)
for endpoint, stats in comparison.items():
    print(f"{endpoint}: avg={stats.avg_ms:.1f}ms")
```

---

### 2. Bandwidth Calculator

**Purpose**: Analyzes network throughput and bandwidth utilization.

**Bandwidth Metrics**:
| Metric | Description |
|--------|-------------|
| Download | Inbound throughput |
| Upload | Outbound throughput |
| Utilization | Percentage of capacity used |
| Peak | Maximum observed throughput |
| Sustained | Average throughput over time |

**Usage**:
```python
from Verdandi.Network import BandwidthCalculator

calculator = BandwidthCalculator()

bandwidth_data = {
    "download_bytes_per_sec": 100_000_000,  # 100 MB/s
    "upload_bytes_per_sec": 50_000_000,     # 50 MB/s
    "capacity_bytes_per_sec": 125_000_000,  # 1 Gbps
    "duration_seconds": 60
}

result = calculator.analyze(bandwidth_data)

print(f"Download: {result.download_mbps:.1f} Mbps")
print(f"Upload: {result.upload_mbps:.1f} Mbps")
print(f"Utilization: {result.utilization_percent:.1f}%")
print(f"Status: {result.health_status}")

# Time-series throughput analysis
samples = [
    {"timestamp": 1, "bytes": 100_000_000},
    {"timestamp": 2, "bytes": 120_000_000},
    {"timestamp": 3, "bytes": 80_000_000},
]
throughput_result = calculator.analyze_throughput(samples)
print(f"Average: {throughput_result.avg_mbps:.1f} Mbps")
print(f"Peak: {throughput_result.peak_mbps:.1f} Mbps")
```

---

### 3. DNS Calculator

**Purpose**: Analyzes DNS resolution performance.

**DNS Metrics**:
| Metric | Description |
|--------|-------------|
| Resolution Time | Time to resolve hostname |
| Cache Hit Rate | Percentage of cached responses |
| Failure Rate | Percentage of failed lookups |
| Server Response Time | Time per DNS server |

**Health Status**:
| Status | Resolution Time |
|--------|-----------------|
| EXCELLENT | < 20ms |
| GOOD | < 50ms |
| FAIR | < 100ms |
| POOR | < 200ms |
| CRITICAL | > 200ms |

**Usage**:
```python
from Verdandi.Network import DnsCalculator

calculator = DnsCalculator()

dns_data = [
    {"hostname": "api.example.com", "resolution_ms": 15, "cached": False},
    {"hostname": "cdn.example.com", "resolution_ms": 2, "cached": True},
    {"hostname": "api.example.com", "resolution_ms": 3, "cached": True},
    {"hostname": "db.example.com", "resolution_ms": 25, "cached": False},
]

result = calculator.analyze(dns_data)

print(f"Average Resolution: {result.avg_resolution_ms:.1f}ms")
print(f"Cache Hit Rate: {result.cache_hit_rate:.1%}")
print(f"Status: {result.health_status}")

# Per-hostname analysis
for hostname, stats in result.by_hostname.items():
    print(f"{hostname}: avg={stats.avg_ms:.1f}ms, cache_hits={stats.cache_hits}")

# DNS server comparison
servers = {
    "8.8.8.8": [15, 18, 16, 14, 17],
    "1.1.1.1": [12, 14, 13, 11, 12],
    "internal": [5, 6, 5, 7, 6],
}
server_comparison = calculator.compare_servers(servers)
```

---

## CLI Usage

```bash
# Latency analysis
python -m Verdandi network latency ping_results.json
python -m Verdandi network latency data.json --endpoint=api.example.com

# Bandwidth analysis
python -m Verdandi network bandwidth throughput.json
python -m Verdandi network bandwidth data.json --format=json

# DNS analysis
python -m Verdandi network dns lookup_times.json
python -m Verdandi network dns data.json --format=markdown
```

---

## Models Reference

### LatencyMetrics
```python
class LatencyMetrics(BaseModel):
    samples: List[float]  # RTT samples in ms
    sent_count: Optional[int] = None
    received_count: Optional[int] = None
```

### LatencyResult
```python
class LatencyResult(BaseModel):
    min_ms: float
    max_ms: float
    avg_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    jitter_ms: float
    packet_loss_percent: Optional[float]
    sample_count: int
    health_status: str
    recommendations: List[str]
```

### BandwidthMetrics
```python
class BandwidthMetrics(BaseModel):
    download_bytes_per_sec: int
    upload_bytes_per_sec: int
    capacity_bytes_per_sec: Optional[int] = None
    duration_seconds: float
```

### BandwidthResult
```python
class BandwidthResult(BaseModel):
    download_mbps: float
    upload_mbps: float
    total_mbps: float
    utilization_percent: Optional[float]
    health_status: str
    recommendations: List[str]
```

### DnsMetrics
```python
class DnsMetrics(BaseModel):
    hostname: str
    resolution_ms: float
    cached: bool
    server: Optional[str] = None
    success: bool = True
```

### DnsResult
```python
class DnsResult(BaseModel):
    total_lookups: int
    avg_resolution_ms: float
    p95_resolution_ms: float
    cache_hit_rate: float
    failure_rate: float
    by_hostname: Dict[str, DnsHostStats]
    health_status: str
    recommendations: List[str]
```

---

## Best Practices

### Latency
- Monitor P99 latency, not just averages
- Jitter > 20ms indicates unstable connection
- Packet loss > 1% significantly impacts TCP performance

### Bandwidth
- Keep utilization below 80% for headroom
- Monitor for sustained saturation
- Compare peak vs average for burst patterns

### DNS
- DNS should resolve in < 50ms
- High cache hit rate (> 80%) is desirable
- Use local DNS cache for frequently accessed domains
