# Verdandi Anomaly Module

## Overview

Statistical anomaly and performance-regression detection. Detectors emit
annotations, not alerts: only SLO-burn integration produces alert-severity
output.

## Regression Detection — Three-Gate Verdict

At production sample sizes p-values saturate: every trivial difference is
"statistically significant". `RegressionDetector.detect(before, after)`
therefore requires **all three** gates (default `verdict_mode="three_gate"`):

1. **Statistical** — Welch's t-test `p < 0.05` (unequal variances).
2. **Practical** — Hodges-Lehmann shift (median of all pairwise
   candidate-baseline differences; robust to skew and outliers) exceeds
   **10 units absolute** OR **5% relative** to the baseline pseudo-median.
   When the baseline pseudo-median is non-positive the relative shift is
   undefined (`hl_shift_relative=None`) and the gate falls back to the
   absolute threshold alone, noted in `verdict_basis`.
3. **Magnitude** — |Glass's delta| > **0.5**, standardized by the BASELINE
   standard deviation only, so a variance-inflating canary cannot dilute
   its own effect size.

The pairwise HL computation is capped at 250x250 via deterministic
subsampling. Results carry `hl_shift`, `hl_shift_relative`, `glass_delta`,
and a human-readable `verdict_basis` explaining exactly which gates passed.

- Empty input returns a typed non-verdict (`verdict_basis="insufficient_data"`),
  never a junk result.
- `verdict_mode="legacy"` retains the previous Cohen's-d + mean-%-change
  gating for one release (deprecated).
- `RegressionDetector.mann_whitney(before, after)` is offered as an
  alternative judge but is NOT the default: distribution-shape changes cause
  false positives and variance collapse causes false negatives (the
  documented Kayenta failure modes).

```python
from Asgard.Verdandi.Anomaly import RegressionDetector

detector = RegressionDetector()
result = detector.detect(baseline_ms, candidate_ms, "api_latency")
result.is_regression   # True only when all three gates pass
result.verdict_basis   # e.g. "three_gate: statistical p=0.0001 (...); ..."
```

## Other Services

- `StatisticalDetector`: z-score / IQR outlier detection, change points.
- `BaselineComparator`: mean/sigma band comparison against baselines.
