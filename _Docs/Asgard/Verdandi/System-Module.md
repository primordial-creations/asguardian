# Verdandi System Module

## Overview

The System module provides analysis for system resource metrics: memory usage and saturation, CPU utilization (virtualization-aware), and device-class-correct I/O performance.

Semantics follow modern systems-performance practice (RESEARCH_12):

- **CPU steal** is a first-class signal with bands (< 2% ok, 2–5% warning, > 5% critical) — steal masks itself as *low* guest CPU, so it can dominate the verdict.
- **%iowait is demoted**: it is a CPU-state artifact, unreliable on multicore, and never sets health status by itself. Disk concerns route to device `await`/`aqu-sz`.
- **%util is meaningless on SSD/NVMe** (parallel devices): health there is rated on `r_await`/`w_await` and `aqu-sz` ballooning, and results carry `utilization_misleading_for_parallel_devices=True`.
- **Memory saturation is evidenced**, not inferred from utilization: major page faults, swap churn, and OOM kills; utilization is derived from `MemAvailable` when supplied.

## Services

### 1. Memory Calculator (`MemoryMetricsCalculator`)

**Purpose**: Analyzes memory utilization and saturation.

**Key semantics**:
| Concern | Signal |
|---------|--------|
| Utilization | `1 - available/total` when `available_bytes` given (preferred); else `used/total` |
| Saturation | `major_faults_ps` (> 10/s warning, > 100/s critical), swap churn, `oom_kills` (any → critical) |
| Thrashing stall | CPU < 30% **and** majflt > 100/s → `thrashing_stall=True`, critical ("idle but slow") |

**Usage**:
```python
from Asgard.Verdandi.System import MemoryMetricsCalculator

calc = MemoryMetricsCalculator()
result = calc.analyze(
    used_bytes=10_000_000_000,
    total_bytes=16_000_000_000,
    available_bytes=6_000_000_000,   # MemAvailable — preferred utilization basis
    swap_total_bytes=8_000_000_000,
    swap_used_bytes=500_000_000,
    major_faults_ps=5.0,
    oom_kills=0,
    cpu_usage_percent=45.0,          # enables the thrashing-stall detector
)

print(f"Usage: {result.usage_percent:.1f}% (available-based={result.available_based_usage})")
print(f"Status: {result.status}")
print(f"Saturation: {result.saturation_signals}")
print(f"Thrashing stall: {result.thrashing_stall}")
```

Notes:
- `swappiness=0` does **not** disable swap; recommendations call this out for latency-sensitive managed runtimes.
- Status bands on utilization: warning ≥ 80%, critical ≥ 95%; saturation evidence outranks utilization.

---

### 2. CPU Calculator (`CpuMetricsCalculator`)

**Purpose**: Analyzes CPU utilization with steal bands and a queueing projection.

**Health rules**:
| Signal | Band |
|--------|------|
| Steal | < 2% ok · 2–5% warning · > 5% critical (migrate/resize; software tuning futile) |
| Utilization | warning ≥ 80%, critical ≥ 95% |
| Load ratio | > 1.0 warning, > 2.0 critical |
| %iowait | **annotation only** — never sets status; `iowait_unreliable_on_multicore=True` |

**Queueing projection** (M/M/1): `latency_multiplier = 1 / (1 - rho)`; utilization ρ > 0.8 is flagged as the hockey-stick zone where residence time degrades non-linearly.

**Usage**:
```python
from Asgard.Verdandi.System import CpuMetricsCalculator

calc = CpuMetricsCalculator()
result = calc.analyze(
    user_percent=45.0,
    system_percent=15.0,
    idle_percent=40.0,
    core_count=8,
    iowait_percent=5.0,
    steal_percent=3.0,
    load_average_1m=4.5,
)

print(f"Usage: {result.usage_percent:.1f}%  Status: {result.status}")
print(f"Steal: {result.steal_percent}% ({result.steal_status})")
print(f"rho={result.utilization_rho}  latency x{result.latency_multiplier}")

# Helper: projected residence-time multiplier at a given utilization
print(calc.queueing_latency_multiplier(0.9))   # 10.0
print(calc.calculate_load_ratio(4.0, 4))       # 1.0
```

---

### 3. I/O Calculator (`IoMetricsCalculator`)

**Purpose**: Analyzes disk I/O with device-class-correct iostat semantics.

**Rating by device class** (`device_type: "hdd" | "ssd" | "nvme"`):
| Class | Valid signals | Notes |
|-------|---------------|-------|
| HDD | `%util` (≥ 80 warning, ≥ 95 critical), queue > 4 heavy, await > 20 ms problem | Serial device: %util is real saturation |
| SSD/NVMe | `r_await`/`w_await` (> 20 ms problem, > 50 ms severe), `aqu_sz` > 3× baseline | `%util` reported but **excluded from health**; `utilization_misleading_for_parallel_devices=True` |
| (omitted) | Legacy %util-based rating | Backwards compatible |

`svctm` is deprecated: it is accepted and discarded with a note.

**Usage**:
```python
from Asgard.Verdandi.System import IoMetricsCalculator

calc = IoMetricsCalculator()
result = calc.analyze(
    read_bytes=1_000_000_000,
    write_bytes=500_000_000,
    read_ops=60_000,
    write_ops=30_000,
    duration_seconds=60,
    device_type="nvme",
    utilization_percent=100.0,   # not a health input on NVMe
    aqu_sz=2.0,
    r_await_ms=0.3,
    w_await_ms=0.4,
)

print(f"Status: {result.status}")   # healthy — %util=100 on NVMe is fine
print(result.utilization_misleading_for_parallel_devices)  # True
```

---

### 4. PSI Analyzer (`PsiAnalyzer`)

**Purpose**: Interpret `/proc/pressure/{cpu,memory,io}`-shaped snapshots —
the unified replacement for the utilization-average edge cases (RESEARCH_12
sec5).

**Severity**: `full_avg10 > 0` → critical (whole-cgroup stall); `some_avg10 >
25` → severe; `some_avg10 > 10` → warning.

**Trajectory**: `avg10 / avg300 > 2` → `fresh_spike`; both elevated →
`sustained_bottleneck`. A large jump in `total_us` between snapshots that
isn't explained by `avg10` flags `micro_burst_detected` (sub-10s stalls
smoothed out of the rolling averages — e.g. CFS throttle bursts).

**Cross-resource diagnosis** (`analyze_cross_resource`): `io.some↑` with
`memory.some≈0` → pure disk bottleneck; `memory.full↑ + io.some↑` →
thrashing; `cpu.some↑` alone → run-queue contention.

```python
from Asgard.Verdandi.System import PsiAnalyzer, PsiSnapshot, PsiResource

analyzer = PsiAnalyzer()
snap = PsiSnapshot(resource=PsiResource.MEMORY, some_avg10=40, full_avg10=3)
report = analyzer.analyze(snap)
print(report.severity)  # "critical"
```

### 5. CFS Throttling Analyzer (`CgroupAnalyzer`)

**Purpose**: Turn `nr_throttled`/`nr_periods`/`throttled_time_ns` cgroup
counters into an effective-quota-starvation verdict (RESEARCH_12 sec2.3).

**Bands**: `throttle_ratio > 25%` → critical; `> 5%` → warning, with an
explicit note that request-clustered bursts mean user-facing impact is
several times the raw ratio. Throttling while the node has idle cores flags
`limit_induced_latency` (raise/remove the limit, or use Guaranteed QoS).
`max_injected_latency_ms = period - quota` estimates the worst-case
per-period stall.

```python
from Asgard.Verdandi.System import CgroupAnalyzer, CgroupCpuStats

analyzer = CgroupAnalyzer()
stats = CgroupCpuStats(
    cpu_quota_us=50_000, cpu_period_us=100_000,
    nr_periods=1000, nr_throttled=300, throttled_time_ns=15_000_000_000,
)
report = analyzer.analyze(stats)
print(report.verdict, report.max_injected_latency_ms)  # "critical" 50.0
```

### 6. USE↔RED Correlator (`UseRedCorrelator`)

**Purpose**: Encode the USE→RED causality chain (Rate↑ → Utilization↑ →
Saturation spike → p99 Duration degrades first → Errors↑ → Rate collapses)
as a correlation/ordering analysis instead of three unrelated health scores.

Cross-correlates a saturation series (run-queue, PSI, `aqu-sz`, throttle
ratio, ...) against p99 duration at small lags; the lag with the strongest
Pearson r identifies whether saturation *leads* the degradation
(`capacity_bound`) or whether saturation stays flat while p99 rises
(`regression_suspected` — not a capacity problem, route to anomaly/
regression analysis).

```python
from Asgard.Verdandi.System import UseRedCorrelator

correlator = UseRedCorrelator()
result = correlator.correlate(saturation=[...], p99_duration_ms=[...])
print(result.best_lag, result.verdict)
```

---

## CLI Usage

```bash
# Memory / CPU / I/O analysis
python -m Asgard.Verdandi system memory stats.json
python -m Asgard.Verdandi system cpu metrics.json
python -m Asgard.Verdandi system io iostat.json
```

---

## Models Reference

### MemoryMetrics (result)
```python
class MemoryMetrics(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    swap_total_bytes: Optional[int]
    swap_used_bytes: Optional[int]
    swap_percent: Optional[float]
    major_faults_ps: Optional[float]
    swap_in_ps: Optional[float]
    swap_out_ps: Optional[float]
    oom_kills: Optional[int]
    available_based_usage: bool
    thrashing_stall: bool
    saturation_signals: List[str]
    status: str                       # healthy | warning | critical
    recommendations: List[str]
```

### CpuMetrics (result)
```python
class CpuMetrics(BaseModel):
    usage_percent: float
    user_percent: float
    system_percent: float
    idle_percent: float
    iowait_percent: Optional[float]
    core_count: int
    per_core_usage: Optional[List[float]]
    load_average_1m: Optional[float]
    load_average_5m: Optional[float]
    load_average_15m: Optional[float]
    steal_percent: Optional[float]
    steal_status: Optional[str]       # ok | warning | critical
    utilization_rho: Optional[float]
    latency_multiplier: Optional[float]
    iowait_unreliable_on_multicore: bool
    status: str
    recommendations: List[str]
```

### IoMetrics (result)
```python
class IoMetrics(BaseModel):
    read_bytes_per_sec: float
    write_bytes_per_sec: float
    read_ops_per_sec: float
    write_ops_per_sec: float
    total_iops: float
    total_throughput_mbps: float
    avg_read_latency_ms: Optional[float]
    avg_write_latency_ms: Optional[float]
    queue_depth: Optional[float]
    utilization_percent: Optional[float]
    device_type: Optional[str]        # hdd | ssd | nvme
    aqu_sz: Optional[float]
    r_await_ms: Optional[float]
    w_await_ms: Optional[float]
    utilization_misleading_for_parallel_devices: bool
    status: str
    recommendations: List[str]
```

### PsiSnapshot / PsiReport
```python
class PsiSnapshot(BaseModel):
    resource: PsiResource             # cpu | memory | io
    some_avg10: float
    some_avg60: float
    some_avg300: float
    full_avg10: float
    full_avg60: float
    full_avg300: float
    total_us: int
    cgroup_id: Optional[str]
    timestamp: Optional[float]

class PsiReport(BaseModel):
    resource: Optional[PsiResource]
    severity: str                     # healthy | warning | severe | critical
    trajectory: Optional[str]         # fresh_spike | sustained_bottleneck
    micro_burst_detected: bool
    cross_resource_diagnosis: Optional[str]
    notes: List[str]
    recommendations: List[str]
```

### CgroupCpuStats / ThrottleReport
```python
class CgroupCpuStats(BaseModel):
    cpu_quota_us: Optional[int]
    cpu_period_us: int
    nr_periods: int
    nr_throttled: int
    throttled_time_ns: int
    usage_ns: Optional[int]
    limit_cores: Optional[float]
    request_cores: Optional[float]
    idle_cores_available: Optional[bool]

class ThrottleReport(BaseModel):
    throttle_ratio: Optional[float]
    avg_stall_ms: Optional[float]
    max_injected_latency_ms: Optional[float]
    verdict: str                      # healthy | warning | critical
    limit_induced_latency: bool
    notes: List[str]
    recommendations: List[str]
```

### UseRedCorrelation
```python
class UseRedCorrelation(BaseModel):
    best_lag: Optional[int]
    best_correlation: Optional[float]
    correlations_by_lag: Dict[int, float]
    verdict: str                      # capacity_bound | regression_suspected | insufficient_data
    ordering_confirmed: bool
    notes: List[str]
```

---

## Best Practices

### Memory
- Rate utilization on `MemAvailable`, not "free" — reclaimable page cache is not pressure.
- Saturation is evidence-based: major faults, swap churn, OOM kills. Any OOM kill is critical.
- "Idle but slow" (low CPU + high majflt) means a runtime is paging its heap: disable swap for latency-sensitive managed runtimes; `swappiness=0` does not disable swap.

### CPU
- Treat steal > 5% as a host problem, not a tuning problem — migrate or resize.
- %iowait is not a disk-health metric; check device `await`/`aqu-sz` or PSI io pressure.
- Past ρ ≈ 0.8, queueing (`1/(1-ρ)`) makes latency degrade non-linearly — plan capacity at 70–80%.

### I/O
- Never rate SSD/NVMe health on `%util` or `svctm`; use `r_await`/`w_await` (> 20 ms problem, > 50 ms severe) and `aqu-sz` ballooning while throughput plateaus.
- `%util` and queue depth remain valid for HDDs.
