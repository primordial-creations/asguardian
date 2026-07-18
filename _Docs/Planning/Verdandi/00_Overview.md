# 00 — Verdandi Upgrade Plan: Overview

## Executive Summary

Verdandi (`Asgard/Verdandi/`, ~13.1k LOC across 10 sub-modules) has outgrown its intended docs: beyond the documented Analysis/Web/Database/System/Network/Cache modules, it already ships SLO (error budgets, 14.4x/6x burn rates), Anomaly (z-score/IQR, Welch's t + Cohen's d regression detection), Trend (linear/exponential/MA forecasts), APM (service maps), and Tracing (critical path). The foundations are sound and the constants are largely correct.

The gap, per the 16 relevant research documents (DEEPTHINK_01–11, RESEARCH_11–15), is that Verdandi's math is **point-estimate and Gaussian-assumption based**, while production telemetry is skewed, multimodal, seasonal, and measured through lossy instruments. The research prescribes specific, well-bounded upgrades:

1. **Distribution-correct evaluation** — CWV rated at p75 with tri-bands and good-fractions; threshold-fraction SLIs instead of percentile point targets; mergeable t-digest/DDSketch sketches so cross-host percentiles stop being percentile-of-percentiles lies.
2. **Honest measurement** — coordinated-omission detection/correction (HDR expected-interval backfill, Tene heuristic, Little's-law sanity checks); queue-time vs service-time separation for DBs and traces.
3. **Statistically-gated regression verdicts** — Welch's t (present) gated by Hodges-Lehmann shift and Glass's Δ effect sizes so saturated-power p-values stop generating alerts; scenario-routed small-batch detectors (split-window MAD, CUSUM, OLS drift, bimodality guard).
4. **Correct alerting mechanics** — multi-window burn-rate pairs per the 1/12 rule (1h/5m, 6h/30m, 72h/6h), window-scaling math, minimum-traffic validity gates, error-budget policy tiers, dynamic (work-normalized) latency budgets.
5. **Modern systems semantics** — PSI, CFS throttling, steal-time bands, NVMe-correct iostat interpretation, USE↔RED causal correlation; USE applied to cloud NICs/DNS quotas; TTFB phase decomposition.
6. **Robust trace analytics** — causal normalization (clock skew, async truncation, orphan adoption) + sweep-line critical path with confidence flags; hardened service maps (identity resolution, messaging virtual nodes, pruning, centrality for portfolio weighting).

Note on research corpus: RESEARCH_01–10 in `_Docs/Research/Verdandi/Completed/` cover IaC scanners, drift detection, K8s hardening, container scanning, GitOps, SLSA, Helm, policy-as-code, Kustomize, and Dockerfile validation — they belong to Volundr/Heimdall scopes and contribute nothing Verdandi-specific; they are intentionally not cited below.

## Gap Analysis

| Domain | Current code | Research target | Gap severity | Plan |
|---|---|---|---|---|
| Web vitals | Single-sample tri-band rating; FID still core; additive 0-100 score masks | p75-of-RUM tri-bands, good-fractions, INP-first, masking warnings, min-sample guard | High | 01 |
| SLO alerting | 14.4/6.0 fixed; multi-window pairs 1h+6h (no short guard); no traffic validity | 1h/5m + 6h/30m + 72h/6h pairs; window-derived thresholds w/ noise-floor caveat; `10/(1-target)` validity; detection-limit metadata | High | 02 |
| Budget policy | Consumption/projection only | NORMAL/CAUTION/FREEZE/EXHAUSTED tiers, 20%-incident post-mortem flag, meta-SLO buffer, portfolio CXI/SRI, sandbagging detector | Medium | 02 |
| SLI design | Percentile point SLAs (`P99<200ms`); good/total tracker exists | Threshold-fractions everywhere; dynamic work-normalized budgets; rejected-events semantics | High | 02, 07 |
| Regression stats | Welch's t + Cohen's d, %-change severity | + Hodges-Lehmann (>10 ms or >5%), Glass's Δ (>0.5) three-gate verdict; Mann-Whitney offered w/ caveats | High | 03 |
| Percentiles | Exact sort; no merging | t-digest/DDSketch mergeable sketches; forbid percentile averaging | High | 03 |
| Measurement integrity | None | CO backfill correction, Tene heuristic, Little's-law check, quality flags | High | 03 |
| Anomaly detection | Global z-score/IQR (bimodal-blind), naive change points | Split-window MAD, CUSUM, OLS drift (boiling-frog fix), bimodality guard, method router, sensitivity profiles | High | 03 |
| Baselines | Mean/σ bands | Strategy taxonomy w/ confound warnings, DiD, canary sizing formula/MDES tiers, cold-start exclusion | Medium | 03 |
| Trend | Linear/exp/MA forecasts | Robust STL-lite seasonal decomposition (additive/multiplicative), 3-cycle minimum | Medium | 03 |
| Cache | Hit-rate bands, eviction reasons; documented `analyze_trend`/`analyze_keys`/`analyze_ttl_patterns` missing | Warm-up trajectory (derivative) analysis, segmented hit/miss SLOs, stampede/XFetch advisor, TTL & working-set economics | High | 04 |
| Network | RTT/jitter/loss/DNS stats, absolute bands | TTFB phase decomposition + protocol expectations, topology baseline profiles, USE for cloud NICs/quotas, BGP/DNS-hijack signatures, clock-skew guard | High | 05 |
| System | Static CPU/mem/IO bands; iowait as health signal; steal ignored; `%util` on NVMe | PSI, CFS throttle analysis, steal bands (2/5%), queueing projection 1/(1-ρ), majflt/OOM saturation, thrashing detector, device-class iostat, USE↔RED correlator | High | 06 |
| Database | Static slow buckets, pool utilization bands | Pool-exhaustion bimodal signature (equal-variance peaks ⇒ queue wait), Little's-law sizing, query fingerprint classes, work-normalized budgets | High | 07 |
| Tracing | Naive longest-path + self-time subtraction | Causal normalization (skew/truncation/orphans) + sweep-line latest-finisher path + confidence flags | High | 08 |
| APM map | Raw name nodes, all edges | Identity resolution/alias registry, messaging virtual nodes, pruning/ghost/ego views, centrality export | Medium | 08 |
| Apdex | Single-T calculator | Error-unified, per-endpoint rollup (% endpoints meeting target), versioned recalibration, bimodality warning | Medium | 09 |
| Self-measurement | None | Analytical Yield / Freshness / Incident Recall / Actionability self-SLOs | Low | 09 |

## Indexed Priority List

Ordering balances user-facing correctness risk, dependency order, and effort:

1. **P0 — 03A/03B/03C**: HL + Glass's Δ gated verdicts; t-digest; CO toolkit. (Everything else consumes these primitives; current outputs can be actively wrong at scale.)
2. **P0 — 02.1–02.4**: burn-rate alert-policy pairs, threshold derivation, traffic-validity gate, detection limits. (Current 1h+6h pairing is a mis-implementation of the reference design.)
3. **P0 — 01**: p75 CWV assessment + INP-first + good-fractions. (Public-facing semantics; small surface.)
4. **P1 — 06.1–06.3**: steal bands, NVMe iostat semantics, memory saturation/thrashing. (Current NVMe `%util` and iowait verdicts are misleading today.)
5. **P1 — 04.1–04.3**: cache doc-parity methods, warm-up trajectory, segmented SLOs.
6. **P1 — 07.1–07.2**: pool wait separation + Little's-law sizing; bimodal exhaustion signature.
7. **P1 — 03D/03E**: small-batch detector routing; baseline strategies/DiD/canary sizing.
8. **P2 — 08.1–08.2**: causal normalizer + sweep-line critical path.
9. **P2 — 05**: network phases, topology profiles, USE, signatures.
10. **P2 — 02.5–02.8**: budget policy tiers, meta-SLO, dynamic budgets, portfolio scorer (needs 08.5 centrality).
11. **P3 — 06.4–06.6**: PSI, CFS throttling, USE↔RED correlator.
12. **P3 — 03F, 04.4–04.5, 08.3–08.5, 09**: seasonal decomposition, stampede/XFetch + eviction economics, service-map hardening, Apdex governance + self-SLOs.

## Plan Index

| File | Scope | Primary research |
|---|---|---|
| `01_WebVitals.md` | p75 tri-bands, good-fractions, INP-first, masking guard | DEEPTHINK_03/04, RESEARCH_15 |
| `02_SLO_ErrorBudgets.md` | Multi-window burn rates, validity gates, budget policy, dynamic budgets, portfolio | DEEPTHINK_04/05/09/11, RESEARCH_13, DEEPTHINK_01 |
| `03_Statistics_Regression.md` | Effect-size gating, sketches, coordinated omission, small-batch routing, baselines, STL | RESEARCH_14/15, DEEPTHINK_02/07/08 |
| `04_Cache.md` | Warm-up trajectory, segmented SLOs, stampede/XFetch, eviction economics | DEEPTHINK_08/04/02 |
| `05_Network.md` | Phase decomposition, topology baselines, USE, anomaly signatures | RESEARCH_11 |
| `06_System.md` | PSI, CFS, steal, iostat modernity, USE↔RED | RESEARCH_12 |
| `07_Database.md` | Pool signatures, Little's law, query classes, work-normalized budgets | RESEARCH_11/12/14, DEEPTHINK_09 |
| `08_Tracing_APM.md` | Sweep-line critical path, causal normalization, service-map hardening | DEEPTHINK_06/10 |
| `09_Apdex_SelfSLO.md` | Apdex governance, Verdandi self-SLOs | DEEPTHINK_03/09/01 |

## Cross-Cutting Engineering Rules

- **No new hard dependencies**: t-digest, STL-lite, CUSUM, HL estimator implemented in pure Python (stdlib `math`/`statistics`), consistent with the current dependency-light codebase.
- **Additive APIs**: every existing public method keeps its signature; new behavior behind new methods/params; legacy strategies retained one release where semantics change (critical path, multi-window pairing).
- **Doc parity**: `_Docs/Asgard/Verdandi/*.md` must be updated in the same phase as each shipped feature; Cache module currently documents methods that do not exist — fix first (Plan 04 phase 1).
- **Insufficient data is a success** (DEEPTHINK_01): all analyzers return typed `INSUFFICIENT_DATA` outcomes rather than junk numbers, and these never trip alerts.
- **Anomalies ≠ alerts** (DEEPTHINK_08): detectors emit annotations; only SLO-burn integration produces alert-severity output.
- **Testing**: every plan encodes its research's worked numeric examples as regression tests (burn-rate scenarios, Apdex masking pairs, YCSB CO discrepancy, DEEPTHINK_09 budget examples), so the math stays anchored to sources.
