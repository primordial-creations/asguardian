# 04 — Cache: Trajectory-Aware Warm-up, Stampede/XFetch, Segmented SLOs, Eviction Economics

## Research-Backed Rationale

- **DEEPTHINK_08 §3 (cache hit rate)**: post-deploy hit-rate drops are mechanical certainties, but a *static suppression window* is dangerous (a broken Redis connection string melts the DB while alerts sleep). Correct approach: **derivative/trajectory analysis** — expect the drop, monitor recovery slope; plunge-and-flatline or correlation with downstream DB load bypasses suppression.
- **DEEPTHINK_04 §Tier-2 / DEEPTHINK_03**: cache-heavy services are the canonical bimodal distribution. Hit rate collapsing from 85%→0% can keep a loose latency SLO green while median UX degrades 80x. Remedy: **segmented SLOs** — `99% of hits < 20 ms` and `95% of misses < 1000 ms` as independent budgets, plus hit-ratio as its own SLI.
- **DEEPTHINK_02 §4**: cache hit/miss latency mixtures break Gaussian detectors; per-mode statistics required (ties to Plan 03 bimodality guard).
- Standard cache literature required by the task scope: **cache stampede prevention via XFetch (optimal probabilistic early recomputation, Vattani et al.)**: recompute when `now - Δ·β·ln(rand()) ≥ expiry` (Δ = recompute cost, β≈1); miss-ratio analysis and eviction-reason economics extend the existing analyzer.

## Current State (`Asgard/Verdandi/Cache/`)

- `cache_calculator.py`: hit/miss/byte hit rate, efficiency score (40/25/20/15 weighting), static health bands (EXCELLENT ≥ 95% …). No trend/trajectory logic in code (docs promise `analyze_trend`, `analyze_keys` — not present), no latency-mode segmentation, no stampede analysis.
- `eviction_analyzer.py`: eviction rate, by-reason stats, memory-pressure flag, recommendations. No TTL-distribution analysis (docs promise `analyze_ttl_patterns`), no LRU-efficiency estimate, no working-set sizing.

## Target State

### A. Warm-up trajectory analyzer (`Cache/services/warmup_analyzer.py`, new)
Input: time series `{t, hits, misses}` with optional `deploy_marker`. Compute hit-rate series `h(t)` and first derivative `h'(t)` (finite differences over ≥ 3 buckets).
Classification after a drop of ≥ `drop_threshold` (default 15 pts):
- `WARMING`: `h'(t) > 0` within `grace_buckets` (default 3) and fit to logarithmic recovery `h(t) = h_∞ - a·e^(-t/τ)` succeeds → suppress alert, report `eta_to_baseline = τ·ln(a/ε)`.
- `FLATLINED`: `|h'(t)| < 0.5 pt/bucket` for `grace_buckets` at depressed level → `CRITICAL`, bypass suppression (DEEPTHINK_08's broken-connection case).
- `COLLAPSED`: `h(t) < 5%` at any point → immediate `CRITICAL` regardless of grace.
Optional correlation input: downstream DB load series; Pearson r between miss-rate and DB CPU > 0.8 strengthens severity.

### B. Segmented latency SLOs (`Cache/services/segmented_slo.py`, new)
Input: latency samples labeled `hit|miss` (or unlabeled + Plan 03 bimodality split as fallback). Emit two threshold-fraction SLIs (`SLO` module consumes them):
- `hit_sli = frac(hit_latencies <= hit_threshold_ms)` (default 20 ms)
- `miss_sli = frac(miss_latencies <= miss_threshold_ms)` (default 1000 ms)
Plus `mode_shift_alert` when the *hit* mode's median migrates > 3× baseline MAD (the 10 ms→900 ms "fast-path regression" Apdex masks, DEEPTHINK_09 §2).

### C. Stampede risk & XFetch advisor (`Cache/services/stampede_analyzer.py`, new)
Input: per-key access log `{key, t, hit, recompute_ms?, ttl_s?}`.
- **Stampede signature**: for each key, count concurrent misses within a `recompute_ms` window after an expiry; `stampede_factor = concurrent_misses / expected_1`. Factor > 5 → flag.
- **XFetch recommendation**: for flagged hot keys emit the early-recompute rule `fetch_early when: now + Δ·β·ln(1/rand()) ≥ expiry` with Δ = observed p95 recompute time, β = 1.0; report expected stampede probability reduction.
- **TTL-vs-Δ sanity**: if `Δ > 0.1 × TTL`, recommend TTL increase or refresh-ahead.

### D. Eviction economics upgrade (`Cache/services/eviction_analyzer.py`)
- Implement the documented-but-missing `analyze_ttl_patterns`: age-at-eviction histogram; if ≥ 60% of EXPIRED evictions have age ≥ 0.9·TTL *and* the key was re-fetched within `refetch_window` → TTL too short (`suggested_ttl = p75(refetch_interval)`).
- LRU-pressure heuristic: `lru_share = LRU evictions / total`; `lru_share > 40%` with `avg_age < 0.25·median_ttl` → cache undersized; estimate working set: `ws_bytes ≈ bytes_evicted_by_lru_per_s × avg_age_s` and recommend sizing to `ws_bytes / target_headroom (0.9)`.
- Per-key hit-rate analysis (`analyze_keys`, documented but missing): low-hit high-churn keys → "do-not-cache" candidates (negative caching value).

## Concrete File/Module Changes

| File | Change |
|---|---|
| `Cache/models/cache_models.py` | `WarmupTrajectory {state, drop_pct, recovery_slope, tau_s, eta_s, severity}`, `SegmentedCacheSLO`, `StampedeReport {key, factor, delta_ms, xfetch_rule}`, `TTLAnalysis`, `KeyStats`. |
| `Cache/services/warmup_analyzer.py` (new) | Trajectory classification per §A. |
| `Cache/services/segmented_slo.py` (new) | Hit/miss threshold-fraction SLIs per §B. |
| `Cache/services/stampede_analyzer.py` (new) | Stampede detection + XFetch advisor per §C. |
| `Cache/services/cache_calculator.py` | Add documented `analyze_trend` (delegating to warmup analyzer) and `analyze_keys`. |
| `Cache/services/eviction_analyzer.py` | TTL patterns, LRU sizing, working-set estimate. |
| `cli/` | `verdandi cache warmup`, `verdandi cache stampede`, `verdandi cache slo`. |

## Phased Steps

1. Fill doc/code gaps (`analyze_trend`, `analyze_keys`, `analyze_ttl_patterns`) — restores parity with `_Docs/Asgard/Verdandi/Cache-Module.md`.
2. Warm-up trajectory analyzer (replaces any static suppression guidance in recommendations).
3. Segmented SLOs (depends on Plan 03 bimodality split for unlabeled data).
4. Stampede/XFetch advisor.
5. Eviction economics + working-set sizing.

## Testing Notes

- L0 trajectory: synthetic post-deploy series recovering as `0.9 - 0.4·e^(-t/5)` → `WARMING`, eta computed; flat 0.5 after drop → `FLATLINED` CRITICAL; zero series → `COLLAPSED` immediately (no grace).
- L0 stampede: 50 misses of the same key within one recompute window → factor 50, XFetch rule emitted with Δ = p95 recompute.
- L0 segmented: 85% hits @ 10 ms + 15% misses @ 800 ms; hit-mode shift to 200 ms trips `mode_shift_alert` while blended p99 stays under 1000 ms — encodes the DEEPTHINK_04 masking case as a regression test.
- L0 TTL: evictions at age ≈ TTL with quick refetch → suggested TTL ≈ p75 refetch interval.
