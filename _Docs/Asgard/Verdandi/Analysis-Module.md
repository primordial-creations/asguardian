# Verdandi Analysis Module

## Overview

The Analysis module provides core statistical calculations for performance metrics including percentile calculations, Apdex scoring, SLA compliance checking, time-window aggregation, and trend analysis.

## Services

### 1. Percentile Calculator

**Purpose**: Calculates standard percentiles and statistical summaries for performance data.

**Key Features**:
- Standard percentiles: P50, P75, P90, P95, P99, P99.9
- Custom percentile calculation
- Statistical summary (min, max, mean, median, std_dev)
- Histogram bucket distribution

**Percentile Results**:
```python
PercentileResult(
    sample_count=1000,
    min_value=5.0,
    max_value=500.0,
    mean=45.5,
    median=40.0,
    std_dev=25.3,
    p50=40.0,
    p75=55.0,
    p90=80.0,
    p95=120.0,
    p99=200.0,
    p99_9=350.0
)
```

**Histogram Buckets**:
- <=10ms, <=25ms, <=50ms, <=100ms, <=250ms
- <=500ms, <=1000ms, <=2500ms, <=5000ms, <=10000ms, >10000ms

**Usage**:
```python
from Verdandi.Analysis import PercentileCalculator

calculator = PercentileCalculator()
data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

# Full percentile calculation
result = calculator.calculate(data)
print(f"P50: {result.p50}")
print(f"P99: {result.p99}")

# Single percentile
p95 = calculator.calculate_percentile(data, 95)

# Custom percentiles
custom = calculator.calculate_custom_percentiles(data, [10, 25, 50, 75, 90])

# Histogram distribution
histogram = calculator.calculate_histogram(data)
```

**Cross-host aggregation — mergeable quantile sketches**:

Per-host percentiles must NEVER be averaged: the mean of p99s is not the
p99 of the union. The sanctioned path is one sketch per host, merged:

```python
from Asgard.Verdandi.Analysis.services.quantile_sketch import TDigest, DDSketch

calc = PercentileCalculator()
sketches = [calc.create_sketch(host_samples) for host_samples in hosts]
fleet = calc.merge_sketches(sketches)   # PercentileResult over the union
fleet.p99                                # ~1% accurate
fleet.quality_flags                      # ["SKETCH_APPROXIMATION"]

# Sketches serialize for shipping across hosts:
payload = sketches[0].to_dict()
restored = TDigest.from_dict(payload)
```

- `TDigest` (default): merging t-digest, compression 100 (~1% quantile
  error), high tail resolution.
- `DDSketch`: geometric buckets with a guaranteed relative error
  (`relative_accuracy=0.01` -> 1%).

**Coordinated-omission toolkit** (`Analysis.services.coordinated_omission`):

Closed-loop load generators hide queueing behind slow requests, producing
optimistic percentiles. Detection and correction:

```python
from Asgard.Verdandi.Analysis.services import coordinated_omission as co

# HDR-style expected-interval backfill (100ms sample @ 1ms interval
# backfills 99, 98, ..., 1 ms):
corrected = co.correct_expected_interval(samples_ms, expected_interval_ms=1.0)

# Tene heuristic: suspect CO when avg < max^2 / (2 * duration)
co.tene_heuristic(avg_ms, max_ms, duration_ms)

# Little's law: throughput x latency must not exceed possible concurrency
co.littles_law_check(throughput_rps, avg_latency_s, max_concurrency)

# One call, machine-readable quality flags:
report = co.analyze(samples_ms, duration_ms=60_000,
                    throughput_rps=1000, max_concurrency=100)
report.quality_flags  # e.g. ["SUSPECT_COORDINATED_OMISSION"]
```

Flags attach to `PercentileResult.quality_flags` so downstream consumers
know when a percentile came from a suspect or corrected dataset.

---

### 2. Apdex Calculator

**Purpose**: Calculates Application Performance Index (Apdex) scores for user satisfaction.

**Formula**:
```
Apdex = (Satisfied + Tolerating * 0.5) / Total
```

Where:
- **Satisfied**: Response time <= threshold (T)
- **Tolerating**: Response time <= 4*T (frustration multiplier)
- **Frustrated**: Response time > 4*T

**Rating Thresholds**:
| Score | Rating |
|-------|--------|
| >= 0.94 | Excellent |
| >= 0.85 | Good |
| >= 0.70 | Fair |
| >= 0.50 | Poor |
| < 0.50 | Unacceptable |

**Configuration**:
```python
ApdexConfig(
    threshold_ms=500,           # Target response time
    frustration_multiplier=4.0  # Multiplier for frustrated threshold
)
```

**Usage**:
```python
from Verdandi.Analysis import ApdexCalculator, ApdexConfig

calculator = ApdexCalculator(threshold_ms=500)
response_times = [100, 200, 300, 600, 800, 2500, 3000]

# Basic calculation
result = calculator.calculate(response_times)
print(f"Apdex Score: {result.score:.2f}")
print(f"Rating: {result.rating}")
print(f"Satisfied: {result.satisfied_count}")
print(f"Tolerating: {result.tolerating_count}")
print(f"Frustrated: {result.frustrated_count}")

# Custom config
config = ApdexConfig(threshold_ms=200, frustration_multiplier=4.0)
result = calculator.calculate(response_times, config=config)

# Weighted Apdex (by request count)
weights = [100, 50, 30, 20, 10, 5, 2]
result = calculator.calculate_with_weights(response_times, weights)

# Recommended threshold for target score
recommended = ApdexCalculator.get_recommended_threshold(response_times, target_score=0.85)
```

**Governance (DEEPTHINK_03)**: a single pooled Apdex score can mask two
serious failure modes — errors being buried inside "fast" latencies, and a
bimodal split (e.g. 80% at 50ms / 20% at 5000ms) scoring identically to a
uniformly mediocre service. The following methods are additive; `calculate()`
and `calculate_with_weights()` keep their original signatures.

**Error-unified Apdex** — any errored request counts Frustrated regardless
of speed:
```python
result = calculator.calculate_with_errors(
    response_times, error_flags,
    is_human=is_human,  # optional; excludes bot/machine traffic
)
print(result.machine_traffic_excluded)
```

**Bimodality warning** — `calculate()` and `calculate_with_errors()` both
run the Plan 03 bimodality guard (`Anomaly.services._batch_detectors.
bimodality_guard`) on the raw response times and set
`ApdexResult.distribution_warning` when the distribution is bimodal. This is
an **annotation, not an alert** — anomalies are not alerts. A worked example
(DEEPTHINK_03): 80% @ 50ms / 20% @ 5000ms and 60% @ ~420ms / 40% spread
across 510-2000ms both score 0.80 at T=500, but only the first is flagged.

**Per-endpoint rollup** — replaces volume-weighted pooling across endpoints
(a Simpson's-paradox guard: one huge fast endpoint can otherwise hide a slow
one):
```python
endpoint_results = {"/search": search_result, "/checkout": checkout_result}
rollup = ApdexCalculator.rollup(endpoint_results, target_score=0.85)
print(rollup.pct_endpoints_meeting_target, rollup.failing_endpoints)

# Pooling across endpoints is refused unless explicitly forced:
calculator.calculate_pooled(endpoint_response_times, force=True)
```

**Versioned recalibration** — `ApdexConfig.version` / `.endpoint` stamp
results so `Apdex_v1_T500` and `Apdex_v2_T1500` can be stored in parallel
during a shadow period:
```python
record = ApdexCalculator.recalibrate(
    old_version="v1", new_version="v2",
    old_threshold_ms=500, new_threshold_ms=1500,
    shadow_period_days=30, endpoint="/checkout",
)
print(record.checklist)  # shadow length, dashboard annotation, cutover timing
```

---

### 3. SLA Checker

**Purpose**: Validates performance metrics against Service Level Agreement targets.

**Key Features**:
- Target percentile checking (e.g., P99 < 200ms)
- Warning and breach thresholds
- Compliance percentage calculation
- Detailed violation reporting

**Configuration**:
```python
SLAConfig(
    target_percentile=99,       # Which percentile to check
    target_value_ms=200,        # Target threshold
    warning_threshold_ms=180,   # Warning level (optional)
    breach_threshold_ms=250     # Breach level (optional)
)
```

**SLA Result**:
```python
SLAResult(
    compliant=True,
    actual_value=185.0,
    target_value=200.0,
    percentile=99,
    compliance_percentage=92.5,
    status="WARNING",  # "COMPLIANT", "WARNING", "BREACH"
    violations=[]
)
```

**Usage**:
```python
from Verdandi.Analysis import SLAChecker, SLAConfig

checker = SLAChecker()
latencies = [50, 60, 70, 80, 90, 100, 150, 180, 200, 250]

# Single SLA check
config = SLAConfig(target_percentile=99, target_value_ms=200)
result = checker.check(latencies, config)
print(f"Compliant: {result.compliant}")
print(f"Status: {result.status}")

# Multiple SLA targets
configs = [
    SLAConfig(target_percentile=50, target_value_ms=100),
    SLAConfig(target_percentile=95, target_value_ms=150),
    SLAConfig(target_percentile=99, target_value_ms=200),
]
results = checker.check_multiple(latencies, configs)
```

---

### 4. Aggregation Service

**Purpose**: Aggregates performance metrics over time windows.

**Aggregation Windows**:
- **Minute**: 60-second windows
- **Hour**: 3600-second windows
- **Day**: 86400-second windows
- **Custom**: User-defined window size

**Key Features**:
- Time-based bucketing
- Per-window statistics (count, sum, avg, min, max)
- Percentiles per window
- Gap detection

**Usage**:
```python
from Verdandi.Analysis import AggregationService, AggregationWindow

service = AggregationService()

# Data with timestamps
data = [
    {"timestamp": 1000, "value": 50},
    {"timestamp": 1030, "value": 60},
    {"timestamp": 1060, "value": 70},
    {"timestamp": 2000, "value": 80},
]

# Aggregate by minute
result = service.aggregate(data, window=AggregationWindow.MINUTE)
for bucket in result.buckets:
    print(f"Window {bucket.start_time}: avg={bucket.average:.1f}")

# Custom window size
result = service.aggregate(data, window_seconds=300)
```

---

### 5. Trend Analyzer

**Purpose**: Detects performance trends using linear regression and change detection.

**Trend Types**:
| Trend | Description |
|-------|-------------|
| IMPROVING | Metrics getting better (decreasing latency) |
| STABLE | No significant change |
| DEGRADING | Metrics getting worse (increasing latency) |
| VOLATILE | High variance, inconsistent |

**Key Features**:
- Linear regression slope calculation
- R-squared correlation coefficient
- Change point detection
- Trend strength classification

**Trend Result**:
```python
TrendResult(
    trend="DEGRADING",
    slope=0.5,           # Change per unit time
    r_squared=0.85,      # Correlation strength
    confidence=0.92,     # Confidence in trend
    change_points=[150, 300],  # Detected changes
    recommendation="Performance is degrading. Investigate recent changes."
)
```

**Usage**:
```python
from Verdandi.Analysis import TrendAnalyzer

analyzer = TrendAnalyzer()

# Time series data
data = [
    {"timestamp": 1, "value": 50},
    {"timestamp": 2, "value": 55},
    {"timestamp": 3, "value": 60},
    {"timestamp": 4, "value": 65},
    {"timestamp": 5, "value": 70},
]

result = analyzer.analyze(data)
print(f"Trend: {result.trend}")
print(f"Slope: {result.slope:.2f}")
print(f"Confidence: {result.confidence:.1%}")

# With baseline comparison
baseline = [50, 52, 48, 51, 49]
current = [70, 75, 72, 78, 80]
comparison = analyzer.compare_periods(baseline, current)
```

---

## CLI Usage

```bash
# Percentile calculation
python -m Verdandi analysis percentile data.json
python -m Verdandi analysis percentile data.json --percentiles=50,90,95,99

# Apdex calculation
python -m Verdandi analysis apdex response_times.json --threshold=500
python -m Verdandi analysis apdex data.json --threshold=200 --format=json

# SLA checking
python -m Verdandi analysis sla latencies.json --target-p99=200
python -m Verdandi analysis sla data.json --target-p95=150 --warning=140

# Trend analysis
python -m Verdandi analysis trend timeseries.json
python -m Verdandi analysis trend data.json --window=hourly --format=markdown
```

---

## Models Reference

### PercentileResult
```python
class PercentileResult(BaseModel):
    sample_count: int
    min_value: float
    max_value: float
    mean: float
    median: float
    std_dev: float
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    p99_9: float
    quality_flags: list[str]  # e.g. SUSPECT_COORDINATED_OMISSION,
                              # LITTLES_LAW_VIOLATION, CO_CORRECTED,
                              # SKETCH_APPROXIMATION
```

### ApdexConfig / ApdexResult
```python
class ApdexConfig(BaseModel):
    threshold_ms: float = 500
    frustration_multiplier: float = 4.0
    version: Optional[str] = None    # recalibration epoch label
    endpoint: Optional[str] = None

class ApdexResult(BaseModel):
    score: float
    rating: str
    threshold_ms: float
    satisfied_count: int
    tolerating_count: int
    frustrated_count: int
    total_count: int
    version: Optional[str] = None
    endpoint: Optional[str] = None
    distribution_warning: Optional[str] = None  # set when input is bimodal
    machine_traffic_excluded: int = 0
```

### MultiEndpointApdexResult / ApdexRecalibrationRecord
```python
class MultiEndpointApdexResult(BaseModel):
    endpoint_results: Dict[str, ApdexResult]
    target_score: float
    total_endpoints: int
    endpoints_meeting_target: int
    pct_endpoints_meeting_target: float
    failing_endpoints: List[str]

class ApdexRecalibrationRecord(BaseModel):
    old_version: str
    new_version: str
    old_threshold_ms: float
    new_threshold_ms: float
    endpoint: Optional[str]
    shadow_period_days: int
    shadow_sufficient: bool       # True when shadow_period_days >= 30
    recalibrated_at: datetime
    checklist: List[str]
```

### SLAConfig / SLAResult
```python
class SLAConfig(BaseModel):
    target_percentile: int
    target_value_ms: float
    warning_threshold_ms: Optional[float] = None
    breach_threshold_ms: Optional[float] = None

class SLAResult(BaseModel):
    compliant: bool
    actual_value: float
    target_value: float
    percentile: int
    compliance_percentage: float
    status: str
    violations: List[str]
```

### TrendResult
```python
class TrendResult(BaseModel):
    trend: str  # IMPROVING, STABLE, DEGRADING, VOLATILE
    slope: float
    r_squared: float
    confidence: float
    change_points: List[int]
    recommendation: str
```
