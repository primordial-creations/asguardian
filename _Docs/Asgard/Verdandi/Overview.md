# Verdandi - Runtime Performance Metrics Package

## Overview

Verdandi is GAIA's runtime performance metrics and analysis package. Named after the Norn who measures the present moment in Norse mythology, Verdandi provides comprehensive runtime performance analysis and scoring.

## Why Verdandi?

- **Measures the present** - Analyzes runtime metrics as they happen (vs Heimdall's static analysis)
- **One of the three Norns** - Verdandi specifically deals with the present, perfect for runtime metrics
- **Complements Heimdall** - Heimdall does static code analysis, Verdandi does runtime measurements
- **Single deity name** - Matches existing GAIA patterns (Iris, Athena, Themis, Heimdall, Freya)

## Package Structure

```
Asgard/
└── Verdandi/
    ├── setup.py
    ├── README.md
    └── Verdandi/
        ├── __init__.py
        ├── __main__.py
        ├── cli.py
        │
        ├── Analysis/                      # Core Metric Calculations
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── analysis_models.py     # PercentileResult, ApdexConfig/Result, SLAConfig/Result
        │   └── services/
        │       ├── __init__.py
        │       ├── percentile_calculator.py   # P50, P75, P90, P95, P99, P99.9
        │       ├── apdex_calculator.py        # Application Performance Index
        │       ├── sla_checker.py             # SLA compliance checking
        │       ├── aggregation_service.py     # Time-window aggregation
        │       └── trend_analyzer.py          # Trend detection with linear regression
        │
        ├── Web/                           # Core Web Vitals
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── web_models.py          # CoreWebVitalsInput, WebVitalsResult, VitalsRating
        │   └── services/
        │       ├── __init__.py
        │       ├── vitals_calculator.py   # LCP, FID, CLS, INP, TTFB, FCP ratings
        │       ├── navigation_timing.py   # Page load breakdown
        │       └── resource_timing.py     # Resource loading analysis
        │
        ├── Database/                      # Database Performance
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── database_models.py     # QueryMetricsInput/Result, ConnectionPoolMetrics
        │   └── services/
        │       ├── __init__.py
        │       ├── query_metrics.py       # Query execution analysis
        │       ├── throughput_calculator.py  # QPS, TPS, IOPS
        │       └── connection_analyzer.py    # Connection pool analysis
        │
        ├── System/                        # System Performance
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── system_models.py       # MemoryMetrics, CpuMetrics, IoMetrics
        │   └── services/
        │       ├── __init__.py
        │       ├── memory_calculator.py   # Memory usage analysis
        │       ├── cpu_calculator.py      # CPU utilization
        │       └── io_calculator.py       # I/O throughput
        │
        ├── Network/                       # Network Performance
        │   ├── __init__.py
        │   ├── models/
        │   │   ├── __init__.py
        │   │   └── network_models.py      # LatencyMetrics, BandwidthMetrics, DnsMetrics
        │   └── services/
        │       ├── __init__.py
        │       ├── latency_calculator.py  # Latency and jitter analysis
        │       ├── bandwidth_calculator.py   # Throughput metrics
        │       └── dns_calculator.py         # DNS resolution performance
        │
        └── Cache/                         # Cache Performance
            ├── __init__.py
            ├── models/
            │   ├── __init__.py
            │   └── cache_models.py        # CacheMetrics, EvictionMetrics, CacheEfficiency
            └── services/
                ├── __init__.py
                ├── cache_calculator.py    # Hit rate and efficiency
                └── eviction_analyzer.py   # Eviction pattern analysis
```

## Submodule Overview

| Submodule | Purpose | Services |
|-----------|---------|----------|
| Analysis | Core metric calculations, percentiles, Apdex, SLA | 5 services |
| Web | Core Web Vitals, navigation timing, resource timing | 3 services |
| Database | Query metrics, throughput, connection pools | 3 services |
| System | Memory, CPU, I/O metrics | 3 services |
| Network | Latency, bandwidth, DNS performance | 3 services |
| Cache | Hit rates, efficiency, eviction analysis | 2 services |

---

## Analysis Module

Core statistical calculations for performance metrics:
- **Percentile Calculator** - P50, P75, P90, P95, P99, P99.9 with histogram support
- **Apdex Calculator** - Application Performance Index (Satisfied + Tolerating*0.5) / Total
- **SLA Checker** - Target percentile compliance checking
- **Aggregation Service** - Time-window aggregation (minute, hour, day)
- **Trend Analyzer** - Linear regression trend detection

See [02-Analysis-Module.md](02-Analysis-Module.md) for details.

---

## Web Module

Core Web Vitals analysis using Google's thresholds:
- **Vitals Calculator** - LCP, FID, CLS, INP, TTFB, FCP ratings
- **Navigation Timing** - Page load phase breakdown
- **Resource Timing** - Individual resource loading analysis

**Web Vitals Score**: 0-100 based on individual metric ratings

See [03-Web-Module.md](03-Web-Module.md) for details.

---

## Database Module

Database performance metrics:
- **Query Metrics** - Execution time analysis with percentiles
- **Throughput Calculator** - Queries/Transactions/IOPS per second
- **Connection Analyzer** - Pool utilization and efficiency

See [04-Database-Module.md](04-Database-Module.md) for details.

---

## System Module

System resource metrics:
- **Memory Calculator** - Usage, allocation rates, GC overhead
- **CPU Calculator** - Utilization, saturation, context switches
- **I/O Calculator** - Read/write throughput, IOPS

See [05-System-Module.md](05-System-Module.md) for details.

---

## Network Module

Network performance metrics:
- **Latency Calculator** - RTT, jitter, packet loss
- **Bandwidth Calculator** - Throughput, utilization
- **DNS Calculator** - Resolution time analysis

See [06-Network-Module.md](06-Network-Module.md) for details.

---

## Cache Module

Cache performance metrics:
- **Cache Calculator** - Hit rate, miss rate, efficiency
- **Eviction Analyzer** - Eviction patterns and optimization

See [07-Cache-Module.md](07-Cache-Module.md) for details.

---

## CLI Interface

```bash
# Main entry point
python -m Verdandi <command> [options]

# Analysis commands
python -m Verdandi analysis percentile <data_file>    # Calculate percentiles
python -m Verdandi analysis apdex <data_file>         # Calculate Apdex score
python -m Verdandi analysis sla <data_file>           # Check SLA compliance
python -m Verdandi analysis trend <data_file>         # Analyze trends

# Web Vitals commands
python -m Verdandi web vitals --lcp=2500 --fid=100 --cls=0.1   # Calculate Core Web Vitals
python -m Verdandi web navigation <timing_file>        # Analyze navigation timing
python -m Verdandi web resources <timing_file>         # Analyze resource timing

# Database commands
python -m Verdandi database queries <metrics_file>     # Analyze query metrics
python -m Verdandi database throughput <metrics_file>  # Calculate throughput
python -m Verdandi database connections <pool_file>    # Analyze connection pool

# System commands
python -m Verdandi system memory <metrics_file>        # Analyze memory usage
python -m Verdandi system cpu <metrics_file>           # Analyze CPU utilization
python -m Verdandi system io <metrics_file>            # Analyze I/O performance

# Network commands
python -m Verdandi network latency <samples_file>      # Analyze latency
python -m Verdandi network bandwidth <samples_file>    # Analyze bandwidth
python -m Verdandi network dns <lookup_file>           # Analyze DNS performance

# Cache commands
python -m Verdandi cache analyze <metrics_file>        # Analyze cache performance
python -m Verdandi cache eviction <events_file>        # Analyze eviction patterns

# Output formats
python -m Verdandi <command> --format=text
python -m Verdandi <command> --format=json
python -m Verdandi <command> --format=markdown
```

---

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | COMPLETE | Foundation, package structure, Analysis module |
| Phase 2 | COMPLETE | Web module (Core Web Vitals) |
| Phase 3 | COMPLETE | Database module |
| Phase 4 | COMPLETE | System module |
| Phase 5 | COMPLETE | Network module |
| Phase 6 | COMPLETE | Cache module |
| Phase 7 | COMPLETE | CLI and integration |

---

## Quick Start

### Installation

```bash
# From GAIA root directory
pip install -e ./Asgard/Verdandi
```

### Basic Usage

```bash
# Calculate Core Web Vitals
python -m Verdandi web vitals --lcp=2500 --fid=100 --cls=0.1

# Calculate Apdex score from response times
python -m Verdandi analysis apdex response_times.json --threshold=500

# Check SLA compliance
python -m Verdandi analysis sla latencies.json --target-p99=200
```

### Programmatic Usage

```python
from Verdandi import (
    # Analysis
    PercentileCalculator, ApdexCalculator, SLAChecker,
    # Web
    CoreWebVitalsCalculator, VitalsRating,
    # Database
    QueryMetricsAnalyzer, ThroughputCalculator
)

# Core Web Vitals
vitals_calc = CoreWebVitalsCalculator()
result = vitals_calc.calculate(lcp_ms=2500, fid_ms=100, cls=0.1)
print(f"Overall Rating: {result.overall_rating}")
print(f"Score: {result.score}/100")

# Apdex Score
apdex_calc = ApdexCalculator(threshold_ms=500)
response_times = [100, 200, 600, 800, 2500]
apdex_result = apdex_calc.calculate(response_times)
print(f"Apdex Score: {apdex_result.score:.2f}")
print(f"Rating: {apdex_result.rating}")

# Percentiles
percentile_calc = PercentileCalculator()
latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
percentiles = percentile_calc.calculate(latencies)
print(f"P50: {percentiles.p50}ms")
print(f"P99: {percentiles.p99}ms")
```

---

## Testing

Verdandi is tested through the Hercules Testing Framework.

### Test Location

```
Asgard/Verdandi/Verdandi_Test/
├── __init__.py
├── conftest.py
├── L0_Mocked/
│   ├── __init__.py
│   ├── test_percentile_calculator.py
│   ├── test_apdex_calculator.py
│   └── test_vitals_calculator.py
└── L1_Integration/
    └── __init__.py
```

### Running Verdandi Tests

```bash
# Run all Verdandi tests
python -m pytest Asgard/Verdandi/Verdandi_Test -v

# Run L0 unit tests only
python -m pytest Asgard/Verdandi/Verdandi_Test/L0_Mocked -v

# Run specific test file
python -m pytest Asgard/Verdandi/Verdandi_Test/L0_Mocked/test_vitals_calculator.py -v
```

---

## Related Documentation

- [02-Analysis-Module.md](02-Analysis-Module.md) - Analysis module details
- [03-Web-Module.md](03-Web-Module.md) - Web module details
- [04-Database-Module.md](04-Database-Module.md) - Database module details
- [05-System-Module.md](05-System-Module.md) - System module details
- [06-Network-Module.md](06-Network-Module.md) - Network module details
- [07-Cache-Module.md](07-Cache-Module.md) - Cache module details
