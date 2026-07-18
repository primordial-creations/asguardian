# Freya Performance Module

## Overview

The Performance module measures page-load timing and Core Web Vitals via
Playwright browser automation, evaluates measured metrics against
configurable per-route performance budgets, and supports before/after
snapshot diffing for regression tracking. Per DEEPTHINK_03, this is
**lab data**: single-run synthetic measurements in a controlled browser
session, not field/RUM data, and severities are capped below Blocker
because lab data alone cannot prove a journey-failing defect (see
Scoring module).

---

## Package Structure

```
Freya/Performance/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── performance_models.py
│   ├── _budget_models.py
│   ├── _performance_report_models.py
│   └── _performance_timing_models.py
└── services/
    ├── __init__.py
    ├── page_load_analyzer.py
    ├── _page_load_helpers.py
    ├── resource_timing_analyzer.py
    ├── _resource_timing_helpers.py
    ├── budget_evaluator.py
    ├── _archetype_detector.py
    └── performance_delta.py
```

---

## Services

### PageLoadAnalyzer

Analyzes page load timing and Core Web Vitals (LCP, TBT, and related
Navigation Timing metrics) for a URL by evaluating the browser's
`PerformanceNavigationTiming`/`PerformanceObserver` APIs in-page via
Playwright.

### ResourceTimingAnalyzer

Analyzes per-resource loading performance (timing, transfer size, caching
behavior) using the Resource Timing API, surfaced through
`ResourceTimingReport`.

### budget_evaluator

Module functions (`evaluate_budget`, `budget_score`,
`budget_evaluations_to_issues`) that compare measured metrics against a
`RouteBudget`'s thresholds and translate breaches into `PerformanceIssue`s.

### _archetype_detector

`detect_archetype` infers a route archetype (e.g. homepage, listing,
checkout) from a URL so the right default budget can be selected without
configuration.

### performance_delta

Pure-stdlib (`json` + `pathlib`) snapshot persistence and diffing:
`snapshot_from_report`, `save_snapshot`/`load_snapshot`, and
`compute_deltas` compare a current report against a prior snapshot to
flag regressions.

---

## Models

- `PageLoadMetrics`, `NavigationTiming` — raw timing captured from the browser
- `ResourceTiming`, `ResourceTimingReport` — per-resource breakdown
- `PerformanceReport`, `PerformanceIssue`, `PerformanceConfig` — aggregate report and findings
- `PerformanceGrade`, `PerformanceMetricType`, `ResourceType` — enums
- `RouteBudget`, `BudgetThreshold`, `BudgetEvaluation`, `RouteArchetype` — budget-evaluation models
- `DEFAULT_BUDGETS` — built-in budget table keyed by archetype

---

## CLI Commands

```bash
freya performance audit <url>          # full performance audit
freya performance load-time <url>      # page load timing only
freya performance resources <url>      # resource loading analysis

# Options
--format [text|json|github]
--output <file>
```

---

## Technology

Zero heavy dependencies: **Playwright only** — timing data comes from the
browser's Navigation/Resource Timing APIs via JS evaluation
(`page.evaluate`), not a separate metrics library. `performance_delta.py`
persists snapshots with plain `json`/`pathlib`, no database. No `httpx`
usage in this module.

Epistemic note: results are single-run lab measurements from one browser
session; they are directional signals for CI gating, not a substitute for
field Real User Monitoring (RUM) or multi-run statistical sampling.
