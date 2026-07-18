# 07 — Database: Pool-Exhaustion Signatures, Work-Normalized Query Budgets, Queue-Time Separation

## Research-Backed Rationale

- **RESEARCH_11 (connection pooling)**: pool exhaustion produces a **bimodal latency distribution with two near-equal-variance peaks**; the X-axis distance between peaks *is* the mean queue wait. This is distinguishable from cache-aside bimodality (narrow fast peak, wide slow peak). Alerting on blended mean/median during exhaustion is meaningless.
- **RESEARCH_14 (coordinated omission)**: in-process query timers measure service time only; the wait-for-connection time must be measured separately (`wait_for_connection` child span pattern) or the DB looks healthy while requests queue.
- **DEEPTHINK_09 (dynamic latency budgets)**: query latency SLOs on continuous complexity distributions (rows scanned 10 vs 10M) must be **work-normalized**: `budget = base_ms + rows_scanned × cost_per_row_ms` (non-linear variants allowed), evaluated per-query into `sli_passed`. Static slow-query thresholds punish heavy-but-efficient queries and mask fast-path regressions.
- **DEEPTHINK_04 (heterogeneous outliers)**: one blended P99 across `GET /user` lookups and export queries hides 80x degradations; segment by query class.
- **RESEARCH_12 (Little's law)**: pool sizing sanity: required connections `L = λ (qps) × W (avg query s)`; wait begins when `L_required > pool_size`.

## Current State (`Asgard/Verdandi/Database/`)

- `query_metrics.py`: percentiles + static slow-query buckets (10/100/1000 ms) + by-type stats.
- `throughput_calculator.py`: QPS/TPS/read-write ratio.
- `connection_analyzer.py`: utilization % bands (70/85), acquisition time, waiting count.
- No bimodality analysis, no queue/service separation, no work-normalized budgets, no Little's-law sizing.

## Target State

### A. Pool-exhaustion signature detector (`Database/services/pool_signature_detector.py`, new)
Input: raw query latencies (blended) + optional acquisition-wait samples.
1. Run Plan 03 bimodality guard; if bimodal, fit two modes (medians m₁ < m₂, MADs s₁, s₂).
2. Classify:
   - `POOL_EXHAUSTION`: `|s₁ - s₂| / max(s₁, s₂) < 0.35` (near-equal variance) → `mean_queue_wait_ms ≈ m₂ - m₁`.
   - `CACHE_ASIDE_PATTERN`: `s₂ > 2·s₁` (wide slow mode) → route to Cache plan 04.
3. If acquisition-wait samples provided, corroborate: `p50(wait) ≈ m₂ - m₁` (± 25%) strengthens confidence to HIGH.
Output includes the RESEARCH_11 explanation and the warning that blended mean/median are invalid during exhaustion.

### B. Queue/service time separation (`Database/services/connection_analyzer.py`)
- Accept `acquisition_wait_samples: list[float]` in addition to the current scalar averages; report wait p50/p95/p99 alongside query service time; `queue_share = wait_p95 / (wait_p95 + service_p95)`.
- **Little's-law sizing**: `required_connections = qps × avg_query_s`; report `headroom = pool_size - required`; recommend pool size `ceil(required / 0.7)` (70% target utilization per RESEARCH_12's tipping point).
- Timeout economics: `timeouts > 0` at `utilization < 70%` → leak suspicion (connections held, not busy).

### C. Work-normalized query SLI (`Database/services/query_budget.py`, new)
- `QueryBudgetConfig {base_ms (default 50), cost_per_unit_ms (default 0.5), unit: rows_scanned|bytes_read|planner_cost, model: linear|nlogn}`.
- Per query: `budget = base + cost × f(units)`; `sli_passed = duration <= budget`; emit good/total counts consumable by `SLO.SLITracker` (Plan 02 §7 shares the same primitive — implement once in SLO and import here, or vice versa; decision: implement in `SLO/services/dynamic_budget.py`, thin adapter here).
- Calibration helper: fit `base`, `cost` by quantile regression (or least-absolute-deviation via iterated median fit) on a healthy baseline week, targeting p75 of duration-vs-units.

### D. Query class segmentation (`Database/services/query_metrics.py`)
- Normalize query fingerprints (existing `query` strings → collapse literals/whitespace) and segment stats per fingerprint; per-class percentiles + per-class HL-shift regression vs baseline (Plan 03).
- Keep static slow buckets as a legacy view; primary verdicts move to budget violations (§C) and per-class shifts — removes the DEEPTHINK_09 cliff-edge problem.

## Concrete File/Module Changes

| File | Change |
|---|---|
| `Database/models/database_models.py` | `PoolSignature {classification, mean_queue_wait_ms, mode_stats, confidence}`, `QueryBudgetConfig/Result`, `QueryClassStats`, extend `ConnectionPoolMetrics {acquisition_wait_samples?, qps?, avg_query_ms?}`. |
| `Database/services/pool_signature_detector.py` (new) | §A. |
| `Database/services/query_budget.py` (new) | §C adapter + calibration. |
| `Database/services/connection_analyzer.py` | Wait percentiles, queue_share, Little's-law sizing, leak heuristic. |
| `Database/services/query_metrics.py` | Fingerprinting + per-class stats/regression. |
| `cli/` | `verdandi database pool-signature`, `verdandi database budget`, `--per-class` flag on `database queries`. |

## Phased Steps

1. Connection analyzer upgrade (wait samples + Little's law) — pure additive.
2. Pool signature detector (needs Plan 03 bimodality guard).
3. Query fingerprint segmentation.
4. Work-normalized budgets + calibration (after Plan 02's `dynamic_budget.py` lands).

## Testing Notes

- L0 signature: synthetic 60% N(20, 3) + 40% N(120, 3.5) → POOL_EXHAUSTION, queue wait ≈ 100 ms; 80% N(5, 1) + 20% N(200, 60) → CACHE_ASIDE_PATTERN.
- L0 Little: qps=200, avg query 100 ms → required=20; pool=25 → headroom 5, recommended ceil(20/0.7)=29.
- L0 budget: rows=0 → budget 50 ms (cache-hit path); rows=10 000 → 5 050 ms; 300 ms zero-row query fails, 4 900 ms 10k-row query passes (DEEPTHINK_09's canonical example as regression test).
- L0 calibration: synthetic duration = 40 + 0.6·rows + noise recovers base≈40, cost≈0.6 within 15%.
