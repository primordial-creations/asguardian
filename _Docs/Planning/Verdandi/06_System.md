# 06 — System: USE/RED Correlation, PSI, CFS Throttling, Steal Time, Modern iostat Semantics

## Research-Backed Rationale

All from **RESEARCH_12** unless noted:

- **USE→RED causality chain**: Rate↑ → Utilization↑ → Saturation spike → **p99 Duration degrades first** → Errors → Rate collapses. Verdandi should encode this as a correlation/ordering analysis, not three unrelated health scores.
- **Queueing math**: M/M/1 residence `R = S / (1 - ρ)`; the 70–80% utilization tipping point is the capacity-planning constant. Current code's flat 70/85% CPU bands accidentally match but carry no queueing rationale or latency projection.
- **CPU steal**: < 2% fine, 2–5% moderate, > 5–10% critical (migrate hosts); steal masks itself as *low* guest CPU. Current `CpuMetrics` accepts `steal_percent` but the calculator ignores it.
- **CFS throttling**: quota/period (default 100 ms) causes up-to-90 ms stop-the-world stalls at 20% average utilization; must analyze `nr_throttled / nr_periods` and throttled time, and warn that "0.5% throttled time" can degrade ~40% of requests.
- **Memory**: `available` (not free) is the utilization metric; saturation = major page faults, swap activity, OOM kills; swappiness=0 does **not** disable swap; JVM full-GC + swapped old-gen = multi-second stall with *idle CPU* ("idle but slow": low %CPU, high majflt).
- **iostat modernity**: `%util` and `svctm` are meaningless on SSD/NVMe (parallel devices); authoritative saturation = `aqu-sz` ballooning while throughput plateaus, and `await`/`r_await`/`w_await` (> 20 ms problem, > 50 ms severe). `%iowait` is a CPU-state artifact — discard as a disk indicator.
- **PSI**: `some`/`full` pressure per CPU/memory/IO with avg10/60/300 + total µs; `full > 0` = whole-container stall; `avg10 ≫ avg300` = fresh spike; `memory.full + io.some` rising together = thrashing signature. PSI is the unified replacement for the utilization-average edge cases.

## Current State (`Asgard/Verdandi/System/`)

- `cpu_calculator.py`: utilization bands (70/85), IOWAIT_HIGH status (> 20% — the exact metric RESEARCH_12 says to distrust), load ratio; steal accepted but unused.
- `memory_calculator.py`: usage %, swap %, static bands; no majflt, no PSI, no available-vs-free distinction enforcement.
- `io_calculator.py`: IOPS/throughput/latency/utilization bands — uses `%util`-style utilization as a health input (broken for NVMe).
- No PSI anywhere; no cgroup/CFS awareness; no USE↔RED correlation.

## Target State

### A. PSI analyzer (`System/services/psi_analyzer.py`, new)
Input: `/proc/pressure/*`-shaped records `{resource: cpu|memory|io, some_avg10, some_avg60, some_avg300, full_avg10, full_avg60, full_avg300, total_us}` (+ optional cgroup id).
- Severity: `full_avg10 > 0` → CRITICAL (total stall); `some_avg10 > 10` → WARNING; `some_avg10 > 25` → SEVERE.
- Trajectory: `avg10 / avg300 > 2` → "fresh spike"; both rising across snapshots → "sustained bottleneck".
- Micro-burst detection: Δ`total_us` between snapshots ≫ avg10 implies sub-10s stalls (CFS throttle / page-fault storms) smoothed out of the averages.
- Cross-resource diagnosis table (RESEARCH_12 §5.2): `io.some↑ + memory.some≈0` → pure disk bottleneck; `memory.full↑ + io.some↑` → thrashing; `cpu.some↑ only` → run-queue contention.

### B. CFS throttling analyzer (`System/services/cgroup_analyzer.py`, new)
Input: `{cpu_quota_us, cpu_period_us, nr_periods, nr_throttled, throttled_time_ns, usage_ns, limit_cores?, request_cores?}`.
- `throttle_ratio = nr_throttled / nr_periods`; `avg_stall_ms = throttled_time_ns / nr_throttled / 1e6`.
- Verdict bands: ratio > 25% CRITICAL; > 5% WARNING **with explicit note that request-clustered bursts mean user-facing impact is several × the ratio** (RESEARCH_12 §2.3); any throttling while node has idle cores → "limit-induced latency" recommendation (raise/remove limit or Guaranteed QoS pinning).
- Latency injection estimate: worst-case per-period stall = `period − quota` (e.g., 100 − 50 = 50 ms) reported as `max_injected_latency_ms`.

### C. CPU calculator upgrade (`cpu_calculator.py`)
- **Steal bands**: < 2% OK, 2–5% WARNING, > 5% CRITICAL ("hypervisor contention — software tuning futile; migrate/resize").
- **Queueing projection**: with per-core utilization ρ, report `latency_multiplier = 1 / (1 - ρ)` and flag ρ > 0.8 as the hockey-stick zone; saturation metric preference order: run-queue length / scheduler latency > load-average heuristics.
- Demote `%iowait`: keep reporting it but annotate `unreliable_on_multicore=True`; never let it alone set health status (route disk concerns to `await`/PSI-io).

### D. Memory calculator upgrade (`memory_calculator.py`)
- Enforce available-based utilization: `usage = 1 - available/total` when `available_bytes` present.
- New saturation inputs: `major_faults_ps`, `swap_in_ps/out_ps`, `oom_kills`. Bands: majflt > 10/s WARNING, > 100/s CRITICAL; any OOM kill → CRITICAL.
- **"Idle but slow" detector**: low CPU utilization (< 30%) + majflt > threshold (+ optional GC pause series) → emit `THRASHING_STALL` with the swap-vs-managed-runtime explanation and "disable swap for latency-sensitive managed runtimes" recommendation.
- Swappiness note in recommendations: swappiness=0 ≠ no swap.

### E. I/O calculator upgrade (`io_calculator.py`)
- Split rating by device class (`device_type: hdd|ssd|nvme`):
  - HDD: `%util` valid; queue > 4 heavy; await > 20 ms problem.
  - SSD/NVMe: **ignore `%util` for health** (report with `misleading_for_parallel_devices=True`); saturation = `aqu-sz` ballooning vs baseline while MB/s plateaus; primary metric `r_await`/`w_await` (> 20 ms problem, > 50 ms severe).
- Drop `svctm` if ever supplied (deprecated).

### F. USE↔RED correlator (`System/services/use_red_correlator.py`, new)
Input: aligned time series — RED (`rate, errors, duration_p99`) + USE saturation series (run-queue/PSI/aqu-sz/throttle ratio).
- Cross-correlation at small lags: find the saturation series that leads p99 degradation (Pearson r at lag 0..k, report argmax).
- Ordering check (Rate↑ → Sat↑ → p99↑ → Err↑) to distinguish load-driven degradation from code regression: saturation flat while p99 rises → *not* a capacity problem → route to Anomaly/regression path.

## Concrete File/Module Changes

| File | Change |
|---|---|
| `System/models/system_models.py` | `PsiSnapshot/PsiReport`, `CgroupCpuStats/ThrottleReport`, extend `CpuMetrics` handling of steal, `MemoryMetrics {major_faults_ps, swap_in_ps, swap_out_ps, oom_kills}`, `IoMetrics {device_type, aqu_sz, r_await, w_await}`, `UseRedCorrelation`. |
| `System/services/psi_analyzer.py` (new) | §A. |
| `System/services/cgroup_analyzer.py` (new) | §B. |
| `System/services/use_red_correlator.py` (new) | §F. |
| `System/services/cpu_calculator.py` | Steal bands, queueing projection, iowait demotion. |
| `System/services/memory_calculator.py` | Available-based usage, majflt/OOM saturation, thrashing detector. |
| `System/services/io_calculator.py` | Device-class-aware rating; await-primary semantics. |
| `cli/` | `verdandi system psi`, `verdandi system throttle`, `verdandi system correlate`. |

## Phased Steps

1. CPU steal + iowait demotion + queueing projection (small, immediate value).
2. I/O device-class semantics (fixes actively misleading `%util` health on NVMe).
3. Memory saturation inputs + thrashing detector.
4. PSI analyzer.
5. CFS throttling analyzer.
6. USE↔RED correlator (needs Plans 03 stats helpers).

## Testing Notes

- L0 steal: 6% steal with 40% total util → CRITICAL (steal dominates verdict).
- L0 CFS: quota 50 ms/period 100 ms, nr_throttled/nr_periods=0.3 → CRITICAL, `max_injected_latency_ms=50`.
- L0 iostat: NVMe at %util=100, aqu-sz=2, r_await=0.3 ms → HEALTHY; HDD identical numbers → saturated.
- L0 thrashing: cpu=15%, majflt=500/s → `THRASHING_STALL`.
- L0 PSI: `memory.full_avg10=3, io.some_avg10=20` → thrashing diagnosis string; `io.some` alone → disk bottleneck.
- L0 correlator: synthetic series where run-queue leads p99 by 2 buckets → lag=2, capacity verdict; flat saturation + rising p99 → regression verdict.
