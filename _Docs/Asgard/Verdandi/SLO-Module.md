# Verdandi SLO Module

## Overview

Error budgets, SLI tracking, and multi-window burn-rate alerting for
Service Level Objectives. Consumes standard good/total event counts —
no assumptions about any particular infrastructure.

## Burn Rate Semantics

`burn_rate = observed_failure_rate / allowed_failure_rate`

- `1.0` = budget being consumed at exactly the sustainable rate.
- A 100% outage on a 99.9% SLO burns at **1000x** — independent of the
  observation window.
- `budget_consumed_in_window` is the percent of the TOTAL error budget
  consumed within the analysis window (14.4x over 1h of a 30-day SLO
  consumes 2%).

## Multi-Window Alert Policy

`BurnRateAnalyzer.evaluate_alert_policy(slo, metrics)` implements the
reference three-tier design (Google SRE Workbook). Each tier pairs a LONG
alert window with a SHORT guard window at long/12 (the "1/12 rule"); it
fires only when BOTH exceed the tier threshold, so alerts reset quickly
once the burn stops:

| Tier | Long window | Short guard | Threshold | Severity |
|------|-------------|-------------|-----------|----------|
| PAGE_FAST | 1h | 5m | 14.4x | page |
| PAGE_SLOW | 6h | 30m | 6.0x | warning |
| TICKET | 72h | 6h | 1.0x | ticket |

`multi_window_analyze()` now defaults to the 1h/5m pair. The old 1h+6h
pairing was mis-paired (the long window cannot act as a guard); it is still
callable explicitly but deprecated for one release.

### Statistical validity gate

A burn-rate alert is only valid when the long window saw at least
`10 / (1 - target)` events (99.9% -> 10,000). Below that, the alert reports
`severity="insufficient_traffic"` and **never fires** — remediation options
(lower the target, widen the window, add synthetic probes) are attached to
the alert instead. Insufficient data is a typed outcome, not a page.

### Detection limits

Every alert carries its detection floor:
`min_detectable_outage_seconds = threshold x window / (1 / (1 - target))`.
For a 99.9% target: 14.4x over 1h detects nothing shorter than 51.84 s of
full outage; the 5m guard, 4.32 s. Documented blind spot: a sub-critical
bleed (e.g. 14.0x sustained for 55 minutes) evades paging by design — the
TICKET tier is the safety net.

### Threshold derivation for non-30-day windows

`derive_thresholds(window_days, budget_fraction=0.02, alert_window_hours=1)`
returns the rescaled threshold (`BR = budget_fraction / (alert_window /
slo_window)`: 28d -> 13.44x, 14d -> 6.72x, 7d -> 3.36x) AND a recommendation
to keep the 14.4x default, because rescaling destroys the absolute noise
floor (a rescaled 7-day 99.9% SLO would page on ~12 s of downtime).

## Usage

```python
from Asgard.Verdandi.SLO import BurnRateAnalyzer, SLODefinition, SLOType

analyzer = BurnRateAnalyzer()
alerts = analyzer.evaluate_alert_policy(slo, metrics)
for alert in alerts:
    if alert.fired:
        route(alert.severity, alert.recommendations)

derivation = analyzer.derive_thresholds(window_days=7)
```

## Models

- `BurnRateAlert`: tier, severity, both windows' burn rates, `fired`,
  traffic-validity fields, detection-limit metadata, recommendations.
- `ThresholdDerivation`: derived vs recommended thresholds with caveats.
- `BurnRate`, `ErrorBudget`, `SLODefinition`, `SLIMetric`: see
  `SLO/models/slo_models.py`.
- `SLIMetric.rejected_events`: valid rejections (e.g. typed
  `INSUFFICIENT_DATA` outcomes) within `total_events`. These never consume
  error budget — `ErrorBudgetCalculator` and `BurnRateAnalyzer` both
  subtract `rejected_events` from `bad_events` (DEEPTHINK_01).
- `SLODefinition.external_sla_target`: optional contractual external SLA
  percentage, used by the meta-SLO buffer (below).

## Error Budget Policy (`SLO/services/budget_policy.py`)

`BudgetPolicyEngine.evaluate(budget, incidents=None, slo=None)` maps
remaining error-budget percentage to a policy tier (RESEARCH_13):

| Remaining budget | Tier | Action |
|---|---|---|
| > 50% | `NORMAL` | Ship freely |
| 25% - 50% | `CAUTION` | Extra review on risky changes |
| 0% < remaining < 25% | `FREEZE` | Feature freeze, reliability work only |
| <= 0% | `EXHAUSTED` | Hard halt, mandatory post-mortem |

**20%-single-incident flag**: independent of the overall tier, any single
contiguous incident that consumed >= 20% of the *total* error budget sets
`post_mortem_required=True`. Build an `IncidentBudgetImpact` with
`BudgetPolicyEngine.incident_budget_impact(bad_events, total_allowed_failures)`
and pass a list of them to `evaluate()`.

**Meta-SLO buffer**: when `SLODefinition.external_sla_target` is set,
`evaluate()` (or the static `BudgetPolicyEngine.meta_slo_buffer(slo)`)
reports the allowed-downtime headroom, in minutes, between the internal
target and the external SLA over the SLO window, and whether the internal
target is strictly tighter (it must be, per RESEARCH_13).

## Dynamic (Work-Normalized) Latency Budgets (`SLO/services/dynamic_budget.py`)

`DynamicLatencyBudget(base_ms, cost_per_unit_ms, cost_function=linear_cost)`
evaluates each request against `base_ms + cost_function(complexity_units) *
cost_per_unit_ms` instead of a fixed threshold, so traffic-mix shifts
(e.g. more big requests one day) don't spuriously breach or slack a static
SLO (DEEPTHINK_09). `nlogn_cost` is offered for sort/merge-shaped work.
`evaluate_batch()` / `to_sli_metric()` feed straight into `SLITracker`.

## Portfolio Scoring (`SLO/services/portfolio_scorer.py`)

`PortfolioScorer` never multiplies per-service SLIs bottom-up (that
collapses to ~0 for any large portfolio). It reports two independent axes
(DEEPTHINK_11):

- **CXI** (`compute_cxi`): business-weighted average of critical-journey
  success rates, measured at the edge.
- **SRI** (`compute_sri`): centrality-weighted burn-rate score across the
  service graph. The `centrality: dict[str, float] | None` parameter is a
  **pluggable hook** — pass a service-name -> weight mapping (e.g. from
  APM's service-map centrality export, Plan 08.5) for topology-aware
  weighting; omit it (or pass `None`) and SRI falls back to uniform
  weighting. This module has no import-time dependency on APM and degrades
  gracefully whether or not that export exists yet.
- `detect_uncalibrated_slos(declared_targets, achieved_pct_90d)` flags
  "sandbagged" SLOs whose 90-day achieved performance clears the declared
  target by a full order of magnitude of nines (e.g. declared 99%, achieved
  99.99%+) — a target that's never genuinely tested.

## Verdandi Self-SLOs (`SLO/services/tool_slo.py`)

Verdandi measures its own output quality — "the tool eats its own SLO
machinery." `RunRecord` is the run-report shaped input every CLI/batch
invocation can emit; `ToolSelfSLOCalculator` computes:

| SLI | Formula | Target |
|---|---|---|
| Analytical Yield | `(scored + valid_rejections) / submitted` | >= 99.5% / 28d |
| Freshness | `frac(report_ready_at - data_closed_at <= threshold)` | >= 95% @ 15 min |
| Incident Recall | fraction of Sev1/2 incidents with an overlapping high-severity finding | >= 85% / 90d, lagged 14d |
| Actionability | `acknowledged_high_sev / total_high_sev` | > 30% / 28d |

`RunRecord.silent_drop` / `has_integrity_error` catch entities that vanish
between submission and accounting (`submitted > scored + rejected +
failed`) — `analytical_yield()` surfaces this as `integrity_errors` rather
than silently absorbing it into the yield fraction. Incident recall is
explicitly `governance="data_science_freeze"` — a slow offline quality
metric for Verdandi's own detectors, never a paging signal.
