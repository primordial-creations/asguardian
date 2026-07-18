"""
Bragi Utility Mapper

Pure functions mapping raw metrics onto utilities u in [0, 1]
(Plan 01 section 3.1). Zero I/O; fully unit-testable.

Transforms:
- Count-based metrics: Laplace-smoothed density + exponential decay
- Complexity: exponential decay above a language threshold, max + mean blend
- Bounded percentages: linear (optionally inverted)
- LOC: logistic decay around a critical size
"""

import math
from typing import Dict, Mapping, Optional

# SQALE non-remediation severity weights (RESEARCH_04), normalized so that
# one MEDIUM issue counts as 1.0 weighted unit.
SEVERITY_WEIGHTS: Dict[str, float] = {
    "blocker": 1000.0,
    "critical": 1000.0,
    "high": 100.0,
    "medium": 15.0,
    "low": 10.0,
    "info": 4.0,
}
_MEDIUM_WEIGHT = 15.0

# Laplace smoothing constant for density (protects tiny files from volatility).
LAPLACE_LOC = 200.0

# Default decay rate for count-based densities. Tuned so a single MEDIUM
# issue in a mid-size file barely moves the utility while hundreds crush it,
# and a single CRITICAL (weight 1000/15) is heavily but not totally punished -
# the non-compensatory blocker cap handles the "must not pass" part.
DEFAULT_LAMBDA = 8.0


def weighted_issue_count(counts_by_severity: Mapping[str, int]) -> float:
    """Severity-weighted issue count, normalized to MEDIUM = 1 unit."""
    total = 0.0
    for severity, count in counts_by_severity.items():
        weight = SEVERITY_WEIGHTS.get(str(severity).lower(), _MEDIUM_WEIGHT)
        total += (weight / _MEDIUM_WEIGHT) * max(int(count), 0)
    return total


def count_to_utility(weighted_count: float, loc: int, lam: float = DEFAULT_LAMBDA) -> float:
    """
    Map a severity-weighted issue count to a utility via Laplace density decay.

    rho = weighted_count / (LOC + 200); u = exp(-lam * rho)

    Monotonically decreasing in weighted_count, increasing in LOC.
    """
    if weighted_count <= 0:
        return 1.0
    density = weighted_count / (max(loc, 0) + LAPLACE_LOC)
    return math.exp(-lam * density)


def complexity_to_utility(
    max_cc: float,
    mean_cc: Optional[float] = None,
    threshold: float = 15.0,
    k: float = 0.05,
) -> float:
    """
    Map cognitive complexity to a utility.

    Never sums complexity across a file: uses exponential decay of the max
    above the language threshold, blended with the mean when available.
    """
    u_max = math.exp(-k * max(max_cc - threshold, 0.0))
    if mean_cc is None:
        return u_max
    u_mean = math.exp(-k * max(mean_cc - threshold, 0.0))
    return 0.7 * u_max + 0.3 * u_mean


def bounded_to_utility(pct: float, invert: bool = False) -> float:
    """
    Map a bounded percentage (0-100) linearly to [0, 1].

    invert=True for "bad" percentages such as duplication.
    """
    clamped = min(max(pct, 0.0), 100.0) / 100.0
    return 1.0 - clamped if invert else clamped


def debt_ratio_to_utility(tdr_percent: float) -> float:
    """
    Map a technical debt ratio percentage to a utility.

    Anchored on the industry A-E grid (5/10/20/50): exponential decay tuned so
    TDR 5% ~ 0.90 (A/B boundary) and TDR 50% ~ 0.35.
    """
    return math.exp(-0.021 * max(tdr_percent, 0.0))


def loc_penalty(loc: int, l_c: float = 600.0, k: float = 0.01) -> float:
    """
    Logistic decay penalizing oversized files: u = 1 - 1/(1 + exp(-k*(LOC - L_c))).

    ~1.0 for small files, 0.5 at L_c, approaching 0 for very large files.
    """
    return 1.0 - 1.0 / (1.0 + math.exp(-k * (max(loc, 0) - l_c)))


def cycle_count_to_utility(cycle_count: int, lam: float = 0.15) -> float:
    """Map a dependency-cycle count to a utility via exponential decay."""
    return math.exp(-lam * max(cycle_count, 0))
