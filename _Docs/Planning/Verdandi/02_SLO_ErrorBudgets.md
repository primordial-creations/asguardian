# 02 — SLO & Error Budgets: Multi-Window Burn Rates, Threshold-Fraction SLIs, Budget Policy

## Research-Backed Rationale

- **DEEPTHINK_05** derives the burn-rate math: `BR = target_budget_fraction / (alert_window / slo_window)`. 14.4x is *only* correct for a 30-day window ("page if 2% of budget burns in 1h": `0.02 / (1/720) = 14.4`). For 28d the equivalent is 13.44x, 14d → 6.72x, 7d → 3.36x — but rescaling destroys the absolute noise floor (a 7-day 99.9% SLO would page on ~12s of downtime), so the default should stay 14.4x with the trade-off surfaced to the user.
- **DEEPTHINK_05 / RESEARCH_13** both specify the **multi-window AND pair**: page iff `BR(1h) > 14.4 AND BR(5m) > 14.4` (the "1/12 rule": short window = long/12), warning at `BR(6h) > 6 AND BR(30m) > 6`, ticket at `BR(3d) > 1 AND BR(6h) > 1`. Current code pairs 1h with **6h** — wrong direction: the long window smooths, the short window is the reset-guard; the code has no 5m/30m guard windows at all.
- **DEEPTHINK_04**: latency SLOs must be **threshold-fractions** (good events / total events), not percentile point targets — fractions aggregate across time/hosts and weight by traffic. Also gives the minimum-traffic validity rule: `min_events_per_window = 10 / (1 - slo_target)`.
- **DEEPTHINK_09**: static thresholds break on multimodal workloads → **Dynamic Latency Budgets** (`budget = base + complexity × cost_per_unit`) evaluated per-request into a boolean `sli_passed`.
- **DEEPTHINK_11**: portfolio rollup: never multiply internal SLOs bottom-up; use dual-axis (edge CXI + burn-rate-normalized SRI) and flag sandbagged/uncalibrated SLOs.
- **RESEARCH_13**: error budget policy tiers (>50% ship freely / 25-50% caution / <25% freeze / 0% hard halt + post-mortem when one incident consumes >20% of budget); the meta-SLO buffer (internal SLO strictly tighter than external SLA); 28-day windows preferred (constant weekend/weekday ratio).
- **DEEPTHINK_01**: distinguish infrastructure failures (burn budget) from valid rejections like `INSUFFICIENT_DATA` (burn nothing); Analytical Yield SLI = `(scored + valid_rejections) / submitted`.

## Current State (`Asgard/Verdandi/SLO/`)

- `burn_rate_analyzer.py`: single- and multi-window analysis; thresholds 14.4/6.0/1.0 hard-coded regardless of `slo.window_days`; multi-window uses 1h+6h with same threshold on both — no short guard window, no tiered severity pairs, no minimum-traffic validity check.
- `error_budget_calculator.py`: budget consumption, daily budgets, projection — good foundation; no policy-tier output, no meta-SLO buffer, no 20%-single-incident flag.
- `sli_tracker.py`: in-memory good/total event tracking (already threshold-fraction shaped — good).
- `Analysis/services/sla_checker.py`: percentile point targets (`P99 < 200ms`) — exactly the anti-pattern DEEPTHINK_04 argues against; keep but add fraction mode.

## Target State

1. **Canonical multi-window multi-burn-rate alert policy** in `burn_rate_analyzer.py`:
   ```
   PAGE_FAST:   BR(1h)  >= 14.4  AND  BR(5m)  >= 14.4   # 2% of 30d budget in 1h
   PAGE_SLOW:   BR(6h)  >= 6.0   AND  BR(30m) >= 6.0    # 5% of 30d budget in 6h
   TICKET:      BR(72h) >= 1.0   AND  BR(6h)  >= 1.0    # sustained overspend
   ```
   Implemented as `evaluate_alert_policy(slo, metrics) -> list[BurnRateAlert]` with each pair produced by the existing `analyze()`.
2. **Window-aware threshold derivation**: `derive_thresholds(slo.window_days, budget_fraction=0.02, alert_window_hours=1)` returning both the *rescaled* threshold and the *default-14.4* recommendation with the absolute-noise-floor caveat (DEEPTHINK_05 §2) in `recommendations`.
3. **Statistical validity gate**: before any alert, require `total_events >= 10 / (1 - target/100)` in the alert window; otherwise emit `severity="insufficient_traffic"` with remediation options (lower target / widen window / synthetic probes) — DEEPTHINK_04 §5.
4. **Detection-limit metadata**: annotate policy output with minimum detectable outage: full outage burn rate = `1 / (1 - target/100)`; time to breach = `threshold × window / full_outage_BR` (e.g., 99.9% + 14.4x + 1h → 51.8 s; 5m guard → 4.3 s). Also warn about the sub-critical bleed (14.0x for 55 min evades paging) — the TICKET tier is the documented safety net.
5. **Error Budget Policy engine** (`SLO/services/budget_policy.py`, new): maps remaining-budget% → `NORMAL / CAUTION / FREEZE / EXHAUSTED` with the RESEARCH_13 action table; flags any single contiguous incident consuming > 20% of budget (`post_mortem_required=True`).
6. **Meta-SLO buffer**: `SLODefinition` gains optional `external_sla_target`; calculator reports buffer minutes between internal SLO and external SLA (99.95 vs 99.9 → 21.9 min buffer).
7. **Dynamic Latency Budget SLI** (`SLO/services/dynamic_budget.py`, new): `sli_passed = duration_ms <= base_ms + f(complexity_units) × cost_per_unit_ms`, with pluggable `f` (linear default, `n log n` option). Output is a boolean stream feeding `SLITracker` — DEEPTHINK_09's work-normalized SLI, immune to traffic-mix shifts.
8. **Portfolio health** (`SLO/services/portfolio_scorer.py`, new): Dual-axis per DEEPTHINK_11 — CXI (business-weighted critical-journey SLIs, measured at edge) and SRI (Σ centrality-weighted burn rates). Include `detect_uncalibrated_slos()`: 90-day achieved performance vs declared target; flag when achieved ≥ target + 1 order of magnitude of nines (sandbagging).
9. **Uncounted-events semantics** (DEEPTHINK_01): `SLIMetric` gains `rejected_events` (valid rejections); Analytical Yield = `(good + rejected) / total`; rejections never consume budget.

## Concrete File/Module Changes

| File | Change |
|---|---|
| `SLO/models/slo_models.py` | `BurnRateAlert {tier, short_window_h, long_window_h, short_br, long_br, fired, budget_consumed_pct, min_detectable_outage_s}`; `BudgetPolicyState`; `SLODefinition.external_sla_target`; `SLIMetric.rejected_events: int = 0`. |
| `SLO/services/burn_rate_analyzer.py` | Add `evaluate_alert_policy()`, `derive_thresholds()`, validity gate; fix `multi_window_analyze` default pair to (1h, 5m). |
| `SLO/services/_burn_rate_helpers.py` | `minimum_traffic_for_target(target)`, `min_detectable_outage_seconds(target, threshold, window_h)`. |
| `SLO/services/budget_policy.py` (new) | Policy tiers + 20% single-incident post-mortem flag + meta-SLO buffer report. |
| `SLO/services/dynamic_budget.py` (new) | Work-normalized per-request SLI evaluation. |
| `SLO/services/portfolio_scorer.py` (new) | CXI/SRI dual-axis + sandbagging detector (consumes APM service-map centrality, Plan 08). |
| `Analysis/services/sla_checker.py` | Add `check_fraction(latencies, threshold_ms, target_fraction)` (threshold-fraction mode) and deprecate-in-docs the pure percentile mode for SLO use. |
| `cli/` | `verdandi slo policy`, `verdandi slo alerts`, `verdandi slo portfolio` subcommands. |

## Phased Steps

1. Models + validity gate + `derive_thresholds` (pure functions, easy to test).
2. Alert-policy tiers (1h/5m, 6h/30m, 72h/6h) replacing the 1h/6h pairing.
3. Budget policy engine + meta-SLO buffer.
4. Dynamic latency budgets.
5. Portfolio scorer (depends on APM centrality — can ship with degenerate equal weights first).

## Testing Notes

- L0: burn-rate arithmetic reproduces DEEPTHINK_05 worked examples exactly: 99.9% SLO, 100% outage → BR=1000x; 1h window breach at 51.84 s; 5m at 4.32 s; deploy scenario (2 min @ 5% errors, 10/day) → 1h BR ≈ 1.66x, no page; 2 min @ 50% errors → 16.6x, page.
- L0: `minimum_traffic_for_target(0.999) == 10_000` per window; below → `insufficient_traffic`.
- L0: sawtooth pattern (30 s outage every 61 min) never fires PAGE_FAST but fires TICKET within 3 days — encodes the documented blind spot.
- L0: rejected_events excluded from bad-event counts.
- L1: policy state transitions across a synthetic 30-day metric stream.
