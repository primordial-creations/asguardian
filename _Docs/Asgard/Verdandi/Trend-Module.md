# Trend Module

## Overview

`Asgard/Verdandi/Trend/` provides trend detection (linear regression,
change-point detection, per-metric reporting) and, as of Plan 03F, a pure
stdlib robust seasonal decomposer. This is a distinct module from
`Verdandi.Analysis`'s own `TrendAnalyzer` documented in
`Analysis-Module.md` -- the two are not the same class.

All new capabilities in this doc are additive: no existing public method
signature in `Trend/` changed. Every new analyzer returns a typed
`DecompositionOutcome` (`OK` / `INSUFFICIENT_DATA`) instead of raising or
returning a degenerate result when it cannot answer.

## Components

### 1. Trend Analyzer (`services/trend_analyzer.py`)

**Purpose**: Detects trend direction (`IMPROVING` / `STABLE` / `DEGRADING` /
`VOLATILE`) via linear regression, with change-point detection and
multi-metric reporting.

```python
from Asgard.Verdandi.Trend import TrendAnalyzer
from Asgard.Verdandi.Trend.models.trend_models import TrendData

analyzer = TrendAnalyzer()
trend = analyzer.analyze(data, metric_name="api_latency")
print(trend.direction, trend.slope, trend.confidence)
```

Other pre-existing methods, unchanged by this work: `analyze_values()`
(raw values at a uniform interval), `analyze_multiple()`,
`detect_change_points()`, `generate_report()`.

### 2. Seasonal Decomposer (`services/seasonal_decomposer.py`, Plan 03F)

**Purpose**: A robust, pure-stdlib STL-lite decomposition -- splits a time
series into trend + seasonal + residual components without numpy/scipy.
Requires at least 3 full seasonal cycles of data; below that it returns
`DecompositionOutcome.INSUFFICIENT_DATA` rather than a misleading fit.

**Algorithm**:
1. Trend: centered moving average over one period (odd/even period both
   handled), with forward/back-filled edges.
2. Seasonal: per-phase median of the detrended series (median, not mean,
   for robustness to spikes).
3. Robustness pass: biweight weights `w = (1 - (r / (6*MAD))^2)^2` applied
   to down-weight outlier residuals before the final seasonal-index pass.
4. Residual: `value - trend - seasonal` (additive) or `value / (trend *
   seasonal)` (multiplicative, via a log-transform; requires all values
   > 0, else `INSUFFICIENT_DATA`).

```python
from Asgard.Verdandi.Trend import SeasonalDecomposer
from Asgard.Verdandi.Trend.models.trend_models import DecompositionMode

decomposer = SeasonalDecomposer()
result = decomposer.decompose(values, period=24, mode=DecompositionMode.ADDITIVE)
print(result.outcome)            # DecompositionOutcome.OK
print(result.cycles_available)   # e.g. 8.0
print(result.trend, result.seasonal, result.residual, result.seasonal_indices)
```

`decompose(values, period=0)` or fewer than 3 cycles both return
`INSUFFICIENT_DATA` with `result.notes` explaining why.

### 3. Deseasonalized Trend Analysis (`TrendAnalyzer.analyze_deseasonalized`)

**Purpose**: Runs `SeasonalDecomposer` first, then feeds the
seasonality-removed series (`trend + residual`, or `trend * residual` in
multiplicative mode) into the existing `analyze_values()` path -- so trend
direction/slope/confidence are computed on the deseasonalized signal
instead of being confounded by a strong daily/weekly cycle.

```python
analyzer = TrendAnalyzer()
result = analyzer.analyze_deseasonalized(values, period=24, metric_name="cpu")
print(result.seasonality_detected)  # True
```

When fewer than 3 cycles are available, it falls back to
`analyze_values()` on the raw series and appends a note to
`result.description` explaining that seasonality was not removed --
it never fails outright.

## Models (`models/trend_models.py`)

- `DecompositionMode` -- `ADDITIVE` / `MULTIPLICATIVE`.
- `DecompositionOutcome` -- `OK` / `INSUFFICIENT_DATA`, the module's local
  typed-outcome enum (per the project-wide convention: each module defines
  its own, not a shared global enum).
- `SeasonalDecomposition` -- `outcome`, `trend`, `seasonal`, `residual`,
  `seasonal_indices`, `cycles_available`, `mode`, `notes`.
- Pre-existing: `TrendData`, `TrendDirection`, `TrendAnalysis`,
  `TrendReport` (unchanged).

## Testing

Regression tests for Plan 03F's worked examples live in
`Asgard_Test/tests_Verdandi/L0_Mocked/test_seasonal_decomposer.py`:
below-3-cycles returns `INSUFFICIENT_DATA`; exactly 3 cycles is sufficient;
a synthetic trend+daily-sine+spike series recovers the injected slope and
routes spikes into the residual; additive seasonal indices sum to ~0;
multiplicative mode reconstructs the original series; multiplicative mode
rejects non-positive values; `TrendAnalyzer.analyze_deseasonalized()` both
succeeds and falls back correctly.
