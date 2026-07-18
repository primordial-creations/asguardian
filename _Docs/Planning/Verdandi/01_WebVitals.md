# 01 — Web Vitals: p75 Tri-Band Aggregation and Modern CWV Semantics

## Research-Backed Rationale

- **DEEPTHINK_03 (Apdex masking)**: single scalar scores hide bimodal user experiences. The same logic applies to the current `WebVitalsResult.score` (0-100 additive): a page with GOOD LCP and POOR INP averages to a misleading mid-score. Google's own methodology never averages vitals into one number for compliance; it uses per-metric tri-bands evaluated **at the 75th percentile of real-user samples**.
- **DEEPTHINK_04 (threshold-fractions)**: percentile point-estimates aggregate badly; "% of page views under threshold" aggregates perfectly. The Web module should support both p75 evaluation *and* good-fraction evaluation (`% of sessions rated good`), which is the CrUX "% good" framing.
- **RESEARCH_15 (percentile-of-percentiles failure)**: p75s computed per-page/per-device cannot be averaged into an origin p75. Requires mergeable sketches (see Plan 03) or pooled raw samples.

## Current State (`Asgard/Verdandi/Web/`)

- `services/vitals_calculator.py`: rates a **single sample** per metric against tri-band thresholds (LCP 2500/4000, FID 100/300, CLS 0.1/0.25, INP 200/500, TTFB 800/1800, FCP 1800/3000). Thresholds are correct; the evaluation model is not distribution-aware.
- FID is still treated as a first-class Core Web Vital. INP replaced FID as a CWV in March 2024 (noted in `_Docs/Asgard/Verdandi/Web-Module.md` but not enforced in code).
- `score` is an additive 0-100 composite (GOOD=100/3, NI=50/3, POOR=20/3) — a masking metric per DEEPTHINK_03.
- `navigation_timing.py` / `resource_timing.py`: single-record analysis only; no fleet aggregation, no phase attribution against baselines.

## Target State

1. **Distribution-based assessment**: `assess_distribution(samples: list[float], metric: str)` computes the p75 of RUM samples and rates *that* value on the tri-band. A page/origin "passes CWV" iff **all three** of LCP, INP, CLS are GOOD at p75.
2. **Good-fraction SLI**: for each metric emit `good_fraction = count(sample <= good_threshold) / n`, `ni_fraction`, `poor_fraction` — the threshold-fraction form that merges across pages and time windows (DEEPTHINK_04).
3. **INP-first semantics**: `core_passing` computed from {LCP, INP, CLS}; FID retained as `legacy_fid_rating` only, with a deprecation note in output.
4. **Composite score demoted**: keep `score` for backwards compatibility but add `masking_warning: bool` when metric ratings disagree by ≥ 2 bands (e.g., GOOD LCP + POOR INP), per DEEPTHINK_03's bimodal-masking analysis.
5. **Insufficient-data guard** (DEEPTHINK_01, "valid rejection burns no budget"): p75 on fewer than `MIN_SAMPLES = 30` samples returns `rating=INSUFFICIENT_DATA` rather than a junk band. CrUX itself suppresses low-traffic segments.

## Exact Formulas / Thresholds

- p75 via linear-interpolation percentile (existing `PercentileCalculator.calculate_percentile(samples, 75)` — reuse, do not duplicate).
- Tri-bands (unchanged, per Google):
  - LCP: good ≤ 2500 ms, poor > 4000 ms
  - INP: good ≤ 200 ms, poor > 500 ms
  - CLS: good ≤ 0.1, poor > 0.25
  - TTFB (diagnostic): good ≤ 800 ms, poor > 1800 ms
  - FCP (diagnostic): good ≤ 1800 ms, poor > 3000 ms
- Page passes CWV: `rating(p75(LCP)) == GOOD and rating(p75(INP)) == GOOD and rating(p75(CLS)) == GOOD`.
- Origin-level rollup: pool raw samples or merge sketches; NEVER average per-page p75s (RESEARCH_15).

## Concrete File/Module Changes

| File | Change |
|---|---|
| `Web/models/web_models.py` | Add `VitalsDistributionInput {metric: str, samples: list[float], phase?: str}`, `VitalsDistributionResult {p75, rating, good_fraction, ni_fraction, poor_fraction, sample_count, insufficient_data}`, `CWVAssessment {lcp, inp, cls, core_passing, diagnostics: dict, masking_warning}`. Add `INSUFFICIENT_DATA` to `VitalsRating`. |
| `Web/services/vitals_calculator.py` | Add `assess_distribution()` and `assess_page(samples_by_metric) -> CWVAssessment`. Keep `calculate()` (single-sample) delegating to shared banding helper. |
| `Web/services/_vitals_recommendations.py` | Recommendations keyed on which fraction dominates: high `poor_fraction` with good p75 → tail problem ("investigate slow devices/networks segment"), vs shifted p75 → systemic problem. |
| `Web/services/navigation_timing.py` | Add `analyze_batch(list[timing]) -> phase p50/p75/p95 per phase` so TTFB regressions can be attributed to DNS/TCP/TLS/request/response phases (ties into Network plan 05). |
| `cli/_parser_subcommands.py`, `cli/handlers_*` | `verdandi web vitals --samples lcp.json --metric lcp` and `verdandi web assess samples.json` (JSON: `{"lcp": [...], "inp": [...], "cls": [...]}`). |

## Phased Steps

1. Banding helper extraction + `INSUFFICIENT_DATA` enum value (no behavior change to existing API).
2. `assess_distribution` + `assess_page` + models.
3. Batch navigation-timing aggregation.
4. CLI wiring + docs update (`_Docs/Asgard/Verdandi/Web-Module.md`: mark FID legacy, document p75 semantics).

## Testing Notes

- L0: p75 band boundary cases (exactly 2500 ms is GOOD; 2500.01 is NI), n=29 → INSUFFICIENT_DATA, n=30 → rated.
- L0: masking warning fires for {LCP: 1000ms×100, INP: 800ms×100}.
- L0: good_fraction merge property: fraction over concatenated samples == weighted mean of per-window fractions (this is the invariant that justifies the design).
- Regression: existing single-sample `calculate()` outputs unchanged.
