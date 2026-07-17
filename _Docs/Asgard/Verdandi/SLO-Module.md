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
