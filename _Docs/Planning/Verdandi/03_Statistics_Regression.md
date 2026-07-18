# 03 — Statistics & Regression Detection: Effect-Size Gating, Sketches, Coordinated Omission, Decomposition

## Research-Backed Rationale

- **RESEARCH_15**: at production sample sizes, p-values saturate (every trivial diff is "significant"). Detection must be gated on **practical significance**: Welch's t (already present) for the test, plus **Hodges-Lehmann** (median of all pairwise differences — robust location shift for skewed latency), **Glass's Δ** (baseline-σ-standardized effect when the canary inflates variance), and documented thresholds: HL shift > 10 ms absolute or > 5% relative at p90, Cohen's d / Glass's Δ > 0.5. Also documents Kayenta's Mann-Whitney judge failure modes (shape changes → false positives; variance collapse → false negatives) — justification for defaulting to Welch + HL rather than Mann-Whitney.
- **RESEARCH_15 (percentile-of-percentiles)**: per-host percentiles cannot be averaged; requires **mergeable quantile sketches (t-digest / DDSketch)** with relative-error guarantees.
- **RESEARCH_14**: **coordinated omission** — closed-loop measurement and in-process APM timers hide queueing; corrections: HDR-style *expected-interval backfill* (`recordValueWithExpectedInterval`: a 100 ms sample at 1 ms expected interval backfills 99, 98, …, 1 ms), Little's law sanity check (`L = λW` must be ≤ configured concurrency), and the **Tene heuristic**: suspect CO when `avg < max² / (2 × test_duration)`.
- **DEEPTHINK_02**: method selection by scenario in the 50–500-point regime: step change → split-window MAD / CUSUM; gradual drift → global OLS trend (rolling stats suffer the boiling-frog); seasonality → needs 3–4 full cycles; bimodal → non-parametric spatial methods (z-score/MAD anchored to one mode misfires). Switching thresholds: distributional ML ≥ ~150–250 pts; seasonal modeling ≥ 3–4 cycles; suspend long-memory baselines after known deployments.
- **DEEPTHINK_07**: baseline strategy failure modes (pre/post: time-of-day + cold start; last-week: code/macro drift; canary: SUTVA, cache imbalance) and canary sizing: `T ≈ 8 / (R·p(1-p)) · (CV/r)²`; Difference-in-Differences for no-split infrastructures; MDES tiers (1–5% for canary-vs-baseline-canary … 15–25% for DiD).
- **DEEPTHINK_08**: sensitivity economics — latency detectors must bias to specificity; error-rate detectors bias to sensitivity but gate on absolute volume; expose a per-metric-class sensitivity dial, not raw statistical knobs; separate *anomaly annotation* from *alerting* (alert only when an SLO is burning).
- **RESEARCH_15 (STL/Prophet)**: trend extraction from seasonal noisy telemetry via STL (LOESS, robust outer-loop weights) or Fourier-seasonality models; multiplicative vs additive mode.

## Current State

- `Anomaly/services/_regression_statistics.py`: `welch_t_test`, `cohens_d`, severity by %-change + d. No HL, no Glass's Δ, no Mann-Whitney, no CUSUM/split-window MAD.
- `Anomaly/services/statistical_detector.py`: z-score, IQR, naive change points. Global z-score is exactly the bimodal failure mode of DEEPTHINK_02 §4 — needs MAD variant + bimodality guard.
- `Anomaly/services/baseline_comparator.py`: mean/σ band comparison; no baseline-strategy taxonomy, no DiD.
- `Analysis/services/percentile_calculator.py`: exact sort-based percentiles only; no sketches, no merge, no CO correction.
- `Trend/services/`: linear/exponential/moving-average forecasts; no seasonal decomposition; rolling baselines vulnerable to boiling-frog drift.

## Target State

### A. Effect-size gated regression verdict (upgrade `regression_detector.py`)
Verdict requires **all three**: statistical (Welch p < α), practical (effect gate), and magnitude context:
```
p_value           = welch_t_test(baseline, candidate)
hl_shift_ms       = hodges_lehmann(baseline, candidate)         # median of pairwise diffs
glass_delta       = (mean_c - mean_b) / std_b                    # baseline σ only
rel_shift         = hl_shift_ms / pseudo_median(baseline)
is_regression     = p < 0.05 AND (hl_shift_ms > 10 OR rel_shift > 0.05) AND |glass_delta| > 0.5
```
For n×m pairwise diffs cap computation at 250×250 (random subsample above; DEEPTHINK_02's regime is ≤ 500 points anyway).

### B. Quantile sketches (`Analysis/services/quantile_sketch.py`, new)
Pure-Python **t-digest** (merging variant): centroids `(mean, weight)`, scale function `k(q) = δ/2π · asin(2q-1)`, compression δ=100 default; `add(value)`, `merge(other)`, `quantile(q)`, `to_dict/from_dict`. Optionally a DDSketch alternative (relative-error γ buckets: `bucket = ceil(log(x)/log((1+γ)/(1-γ)))`, γ=0.01 → 1% relative error). `PercentileCalculator.merge_sketches(list) -> PercentileResult` becomes the sanctioned cross-host aggregation path; document that averaging per-host p99s is forbidden (RESEARCH_15).

### C. Coordinated-omission toolkit (`Analysis/services/coordinated_omission.py`, new)
- `correct_expected_interval(samples_ms, expected_interval_ms) -> list[float]`: for each `s > interval`, append `s - i·interval` for i = 1.. while > interval (HDR backfill).
- `tene_heuristic(avg_ms, max_ms, duration_ms) -> bool`: `avg < max² / (2·duration)` → flag `SUSPECT_COORDINATED_OMISSION`.
- `littles_law_check(throughput_rps, avg_latency_s, max_concurrency) -> bool`: `λ·W > L_max` → impossible report, flag invalid.
- Wire flags into `PercentileResult` as optional `quality_flags: list[str]`.

### D. Small-batch detector routing (`Anomaly/services/statistical_detector.py`)
- `detect_step_change`: split-window MAD (compare `median ± k·MAD` of first vs second half; k=3) and CUSUM (`S_i = max(0, S_{i-1} + (x_i - μ0 - κ))`, κ = 0.5σ, alarm at `h = 5σ`).
- `detect_drift`: OLS slope over the full batch with t-test on slope ≠ 0 (fixes boiling-frog; DEEPTHINK_02 §2).
- Bimodality guard before z-score/IQR: dip-statistic-lite — flag when histogram has 2 local maxima separated by a valley < 50% of the smaller peak; if bimodal, skip Gaussian methods and report `BIMODAL_DISTRIBUTION` with per-mode stats (feeds Database plan 07 pool-exhaustion signature).
- `recommend_method(n, cycles_observed)`: encode DEEPTHINK_02 switching thresholds (n < 150 → stats only; ≥ 3–4 seasonal cycles → seasonal model; deployment marker present → suspend historical baseline).

### E. Baseline strategy framework (`Anomaly/services/baseline_comparator.py`)
- `BaselineStrategy` enum: `PRE_POST`, `HISTORICAL_WEEK`, `CANARY_CONCURRENT`, `DIFF_IN_DIFF` with per-strategy confound warnings (cold-start blind spot: drop the first 3 min post-deploy; SUTVA note for canary) — DEEPTHINK_07.
- `diff_in_diff(pre_now, post_now, pre_lastweek, post_lastweek)`: effect = `(post_now - pre_now) - (post_lastweek - pre_lastweek)`; MDES guidance 15–25%.
- `canary_duration_seconds(R, p, cv, r)` = `8 / (R·p·(1-p)) · (cv/r)²`; expose in results so callers know whether their window was statistically starved.

### F. Seasonal decomposition (`Trend/services/seasonal_decomposer.py`, new)
Additive STL-lite: (1) trend = centered moving average over one period; (2) detrend; (3) seasonal = per-phase medians; (4) residual; (5) robust pass: recompute with weights `w = (1 - (r/6·MAD)²)²` (biweight) zeroing gross outliers. Multiplicative mode via log-transform. Require ≥ 3 full periods (else `INSUFFICIENT_CYCLES`). `TrendAnalyzer.analyze(deseasonalized=True)` option.

### G. Sensitivity profiles (DEEPTHINK_08)
`Anomaly/models/anomaly_models.py`: `SensitivityProfile` presets per metric class — `LATENCY` (specificity-biased: effect gates as in §A), `ERROR_RATE` (sensitivity-biased but `min_absolute_errors=50` gate), `CACHE_HIT_RATE` (trajectory-based, see Plan 04). Detectors accept `profile=` instead of exposing raw z-thresholds in CLI.

## Concrete File/Module Changes

| File | Change |
|---|---|
| `Anomaly/services/_regression_statistics.py` | `hodges_lehmann()`, `glass_delta()`, `mann_whitney_u()` (offered but not default), verdict gating rewrite. |
| `Anomaly/services/regression_detector.py` | Three-gate verdict; result model gains `hl_shift_ms`, `glass_delta`, `verdict_basis`. |
| `Anomaly/services/statistical_detector.py` | MAD split-window, CUSUM, OLS drift, bimodality guard, `recommend_method`. |
| `Anomaly/services/baseline_comparator.py` | Strategy enum, DiD, canary sizing, cold-start exclusion window. |
| `Analysis/services/quantile_sketch.py` (new) | t-digest (+ optional DDSketch). |
| `Analysis/services/coordinated_omission.py` (new) | Backfill, Tene heuristic, Little's-law check. |
| `Trend/services/seasonal_decomposer.py` (new) | Robust additive/multiplicative decomposition. |
| `cli/` | `verdandi analysis sketch merge`, `verdandi anomaly regression --profile latency`, `verdandi analysis co-check`. |

## Phased Steps

1. HL + Glass's Δ + gated verdict (highest value, smallest surface).
2. CO toolkit + quality flags.
3. t-digest + merge path in PercentileCalculator.
4. Small-batch routing (MAD/CUSUM/OLS/bimodality).
5. Baseline strategies + DiD + canary sizing.
6. Seasonal decomposition; wire into Trend.

## Testing Notes

- L0 HL: `hodges_lehmann([1,2,3],[11,12,13]) == 10`; robust to a 10⁶ outlier in candidate.
- L0 gating: n=100k with 0.3 ms shift → p≈0 but verdict False (the saturation case RESEARCH_15 describes).
- L0 t-digest: quantile error < 1% vs exact on 10⁵ log-normal samples; `merge(a,b)` ≈ sketch of concatenation; serialization round-trip.
- L0 CO: YCSB-style case — 4 ms samples at 1000 ops/s target on a 250 ops/s server: corrected p99 ≫ uncorrected (directionally reproduces RESEARCH_14's table); Tene heuristic fires on avg=5 ms, max=10 s, duration=60 s.
- L0 CUSUM/MAD: detects 50→200 ms step at the correct index in a 500-pt batch; OLS drift detects +0.1 ms/pt slope that rolling z-score misses.
- L0 STL: synthetic `trend + daily sine + spikes` recovers slope within 10%, spikes land in residual.
