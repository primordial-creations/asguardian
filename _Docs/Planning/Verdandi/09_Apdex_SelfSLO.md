# 09 — Apdex Governance & Verdandi Self-SLOs

## Research-Backed Rationale

- **DEEPTHINK_03**: Apdex masks bimodal disasters (80% @ 50 ms + 20% @ 5 s scores 0.80, same as a uniformly sluggish service). Correct usage: per-endpooint T, epoch-versioned recalibration, non-human traffic excluded, aggregation as "% of endpoints meeting Apdex target" (SLO compliance rollup), errors dumped into Frustrated. Apdex remains right for RUM smoothing, error-unification, and exec communication — keep it, govern it.
- **DEEPTHINK_09**: per-endpoint Apdex does *not* fix multimodality — surface a warning when the underlying distribution is bimodal.
- **DEEPTHINK_01**: Verdandi itself is a batch analysis tool and should ship with its own SLO framework: **Analytical Yield** (≥ 99.5%/28d, valid rejections count as good), **Freshness/Time-to-Insight** (95% of reports within target of data close), **Retrospective Incident Recall** (85%/90d lagged 14d — needs external incident data; provide the calculator, not the pipeline), **Actionability Rate** (> 30%/28d). Insufficient-data outcomes are successes and burn nothing.

## Current State

- `Analysis/services/apdex_calculator.py`: single-T score, weighted variant, recommended-threshold helper, rating bands. No error integration, no per-endpoint governance, no versioning, no bimodality warning.
- Nothing measures Verdandi's own run quality.

## Target State

### A. Apdex governance (`Analysis/services/apdex_calculator.py` + models)
1. `calculate_with_errors(response_times, error_flags, config)`: any errored request → Frustrated regardless of speed (DEEPTHINK_03 §4.3 — unified SLI).
2. `MultiEndpointApdex.rollup(endpoint_results, targets) -> {pct_endpoints_meeting_target, failing_endpoints}` — replaces volume-weighted pooling (Simpson's-paradox guard); refuse (with explanation) to compute a single pooled Apdex across endpoints unless `force=True`.
3. `ApdexConfig` gains `version: str` and `endpoint: str`; results echo them so downstream storage can keep `Apdex_v1_T500` and `Apdex_v2_T1500` in parallel during a shadow period; recalibration helper emits the epoch-overlap checklist (shadow ≥ 30 days, annotation text, quarter-boundary cutover).
4. Bimodality warning: run Plan 03 guard on inputs; if bimodal, set `distribution_warning="BIMODAL — Apdex masks mode structure; use segmented SLOs (Plan 04/02)"`.
5. Traffic hygiene: optional `is_human: list[bool]`; machine traffic excluded from Apdex, reported separately.

### B. Verdandi self-SLOs (`SLO/services/tool_slo.py`, new)
Run-report shaped input — every Verdandi CLI/batch invocation can emit `RunRecord {entities_submitted, entities_scored, valid_rejections, run_started, data_closed_at, report_ready_at, findings: [{id, severity, acknowledged?}]}`.
- `analytical_yield = (scored + valid_rejections) / submitted`; target 0.995/28d.
- `freshness_sli = frac(report_ready_at - data_closed_at <= threshold)`; target 0.95 @ 15 min default.
- `incident_recall(incidents, findings, overlap_window)`: fraction of Sev1/2 incidents with an overlapping high-severity finding; evaluate over 90d lagged 14d; output explicitly marked `governance="data_science_freeze"` not paging (DEEPTHINK_01 §2).
- `actionability = acknowledged_high_sev / total_high_sev`; target > 0.30/28d.
These reuse `SLITracker`/`ErrorBudgetCalculator` — the tool eats its own SLO machinery.

## Concrete File/Module Changes

| File | Change |
|---|---|
| `Analysis/models/analysis_models.py` | `ApdexConfig {version, endpoint}`, `ApdexResult {distribution_warning, machine_traffic_excluded}`, `MultiEndpointApdexResult`. |
| `Analysis/services/apdex_calculator.py` | §A methods. |
| `SLO/services/tool_slo.py` (new) | Four SLI calculators + `RunRecord` model. |
| `cli/` | `verdandi analysis apdex --errors errors.json --endpoint /checkout`; `verdandi self-slo report runs.jsonl`. |

## Phased Steps

1. Error-unified Apdex + bimodality warning.
2. Multi-endpoint rollup + versioning.
3. Self-SLO calculators (yield + freshness first; recall/actionability once run-record emission exists in CLI).

## Testing Notes

- L0: DEEPTHINK_03 worked examples reproduce exactly — Service A (80% 50 ms / 20% 5000 ms, T=500) = 0.80 **with** `distribution_warning`; Service B (60% 450 / 40% 1500) = 0.80 without.
- L0: errored 20 ms request counts Frustrated.
- L0: rollup — 19 green endpoints + 1 failing checkout → 95% compliance and checkout named; pooled call without `force` raises.
- L0: yield — 80% scored + 15% valid rejections = 0.95 yield; silent drop (submitted > scored+rejected+failed) flags integrity error.
