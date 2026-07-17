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

---

## Plan 05 Additions (TTFB Phases, Topology Baselines, USE, Anomaly Signatures)

The sections above predate Plan 05 and describe the module's original
absolute-band design (some of the class/method names above, e.g.
`LatencyResult`, `analyze_with_loss`, `compare_endpoints`, do not exist in
the current codebase and are pending a future doc-accuracy pass). The
sections below document what Plan 05 actually shipped, in
`Asgard/Verdandi/Network/`, additively: every existing method signature is
unchanged, and every new analyzer returns a typed `NetworkOutcome` (`OK` /
`INSUFFICIENT_DATA`) rather than a junk result when it cannot answer.

### 4. Phase Analyzer (`services/phase_analyzer.py`)

**Purpose**: Decomposes TTFB into DNS -> TCP -> TLS -> request -> response
phases and checks the TLS phase against protocol-specific handshake-RTT
expectations (RESEARCH_11).

```python
from Asgard.Verdandi.Network import PhaseAnalyzer

analyzer = PhaseAnalyzer()
result = analyzer.analyze([
    {"dns_ms": 5, "tcp_ms": 50, "tls_ms": 300, "request_ms": 2,
     "response_ms": 40, "tls_version": "1.2"},
])
print(result.ttfb_dominant_phase)   # "tls"
print(result.protocol_flags)        # ["HANDSHAKE_OVERHEAD"]
```

`HANDSHAKE_OVERHEAD` fires when `tls_ms` exceeds `1.5 x expected_rtts x
rtt_est`, where `rtt_est` is estimated from `tcp_ms` and `expected_rtts` is
2 for TLS 1.2, 1 for TLS 1.3, and 0 for a resumed session or QUIC/HTTP-3
(never flagged). Empty input returns `outcome=INSUFFICIENT_DATA`.

### 5. Topology Baseline Profiles (`LatencyCalculator.analyze_against_profile`)

**Purpose**: Rates latency against named cloud topology baselines instead of
one-size absolute health bands.

| Profile | Expected RTT | Rated POOR above |
|---|---|---|
| `INTRA_AZ` | 0.1-0.6 ms | 1.0 ms |
| `INTER_AZ` | 1-2 ms | 5.0 ms (sync-replication warning fires above 3 ms) |
| `SAME_REGION_PUBLIC` | 2-10 ms | 20 ms |
| `CROSS_REGION` | caller-declared (`cross_region_declared_ms`) | 1.3x declared |
| `INTERNET_EDGE` | 20-150 ms | 195 ms |
| `LEGACY_DEFAULT` | reuses the original `GOOD_THRESHOLD`/`ACCEPTABLE_THRESHOLD` bands | -- |

```python
from Asgard.Verdandi.Network import LatencyCalculator, TopologyProfile

calculator = LatencyCalculator()
result = calculator.analyze_against_profile(
    [1.7, 1.8, 1.9], TopologyProfile.INTER_AZ
)
print(result.rating)  # TopologyRating.GOOD
```

Packet-loss baselines are enforced too: backbone profiles expect < 0.01%
loss; `INTERNET_EDGE` tolerates up to 1%. `CROSS_REGION` without a declared
baseline, and empty input, both return `INSUFFICIENT_DATA`.

### 6. USE Analyzer (`services/use_analyzer.py`)

**Purpose**: Applies the USE method (Utilization/Saturation/Errors) to a
cloud NIC, the TCP stack, and the DNS resolver's link-local rate limit.
Errors trump utilization: any non-zero allowance-exceeded counter is
CRITICAL regardless of reported utilization.

```python
from Asgard.Verdandi.Network import UseAnalyzer
from Asgard.Verdandi.Network.models.network_models import UseCounterSnapshot

analyzer = UseAnalyzer()
report = analyzer.analyze(UseCounterSnapshot(linklocal_allowance_exceeded=3))
print(report.dns_resolver.severity)  # "critical"
```

`nic.errors` covers `pps_allowance_exceeded`, `bw_in_allowance_exceeded`,
`conntrack_allowance_exceeded`; `dns_resolver` flags the 1,024-PPS AWS
link-local DNS quota. Retransmit spikes are correlated (Pearson r) against
an optional utilization series to distinguish link saturation (r > 0.7)
from uncorrelated path loss. `analyze(None)` returns `INSUFFICIENT_DATA`.

### 7. Signature Classifier (`services/signature_classifier.py`)

**Purpose**: Classifies RTT/ASN/TLS-failure series into named anomaly
signatures. These are annotations, not alerts (anomalies != alerts).

| Signature | Trigger |
|---|---|
| `ROUTE_CHANGE` | A CUSUM step in RTT sustained >= 15 minutes (optionally corroborated by a hop-count delta) |
| `DNS_HIJACK_SUSPECT` | Resolved-ASN change coincident with a TLS-failure spike |
| `CONGESTION` | Retransmit spike + growing RTT variance with no genuine location step |
| `CLOCK_SKEW` | Any negative one-way latency -- a data-quality flag, never a network anomaly; takes priority over every other signature |

```python
from Asgard.Verdandi.Network import SignatureClassifier

classifier = SignatureClassifier()
sig = classifier.classify(rtt_series=[20.0] * 20 + [45.0] * 20)
print(sig.signature)  # NetworkSignatureType.ROUTE_CHANGE
```

The standalone `detect_clock_skew()` function is also exported from
`services/signature_classifier.py` for reuse by other analyzers.

### 8. DNS Quota / Environment Bands (`DnsCalculator.analyze_quota`)

**Purpose**: USE-style utilization/error columns for the DNS resolver, plus
in-VPC (< 2 ms) vs public (< 100 ms) expectation bands.

```python
from Asgard.Verdandi.Network import DnsCalculator

calculator = DnsCalculator()
result = calculator.analyze_quota(queries_ps=2000)
print(result.quota_exceeded)  # True (over the 1,024 PPS link-local quota)
```

`queries_ps=None` returns `INSUFFICIENT_DATA`.

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
