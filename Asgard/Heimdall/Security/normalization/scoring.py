"""
Multiplicative-decay security score (DEEPTHINK_02).

Replaces the linear-subtractive ``100 - 25c - 10h - 5m - 1l`` model, which is
size-blind, gameable (fix cheap LOWs to offset a CRITICAL), and saturates at
zero (score starvation).

    S         = max(1, sqrt(LOC / 1000))                # size factor
    N_crit    = sum_c critical_c                        # absolute, never normalized
    N_high    = sum_c high_c
    N_med_eff = (1/S) * sum_c medium_c ** 0.8           # per-category soft cap + size norm
    N_low_eff = (1/S) * sum_c low_c ** 0.8

    Score = round(100 * 0.40**N_crit * 0.80**N_high
                      * 0.90**N_med_eff * 0.95**N_low_eff)

Golden properties (DEEPTHINK_02 walkthroughs, all unit-tested):
    1 CRITICAL                          -> 40
    50 LOW in one category @ 10k LOC    -> 69
    50 LOW across 10 categories @ 10k   -> 56   (breadth punished over depth)
    50 LOW @ 1M LOC                     -> 96
Score asymptotically approaches, but never reaches, 0 -- every fix moves it.

Rules bound to the formula:
- Never weight by scanner FP rates ("discounted devastation").
- Un-triaged findings count as true positives; false-positive triage
  immediately restores score.
- Test-context and "unlikely"-bucket findings are excluded from the score;
  "possible" findings count at 50% weight in the effective sums. Severity of
  the individual finding is never diluted -- only these aggregate counts.

Deliberately accepted failure modes (documented, DEEPTHINK_02):
- Score shock on first scan of a legacy codebase.
- LOC-inflation exploit (vendoring code inflates S).
- No exploit-chain modeling (two MEDIUMs forming a chain stay two MEDIUMs).
"""

import math
from typing import Dict, Mapping, Optional

_CRIT_DECAY = 0.40
_HIGH_DECAY = 0.80
_MED_DECAY = 0.90
_LOW_DECAY = 0.95
_SOFT_CAP_EXP = 0.8


def size_factor(lines_of_code: int) -> float:
    """S = max(1, sqrt(LOC / 1000)). LOC <= 0 means unknown -> 1."""
    if lines_of_code is None or lines_of_code <= 0:
        return 1.0
    return max(1.0, math.sqrt(lines_of_code / 1000.0))


def score_weight(confidence: Optional[float], is_test_context: bool = False) -> float:
    """
    Aggregate-hygiene weight of a finding in the score sums.

    - test-context findings and bucket "unlikely" (< 0.25): excluded (0.0)
    - bucket "possible" (0.25-0.49): half weight (0.5)
    - "probable"/"certain", or findings without a confidence value: full (1.0)

    This weight affects ONLY the aggregate score; the finding itself keeps
    its full severity and its own confidence bucket.
    """
    if is_test_context:
        return 0.0
    if confidence is None:
        return 1.0
    c = float(confidence)
    if c < 0.25:
        return 0.0
    if c < 0.50:
        return 0.5
    return 1.0


def multiplicative_security_score(
    category_counts: Mapping[str, Mapping[str, float]],
    lines_of_code: int = 0,
) -> float:
    """
    Compute the multiplicative-decay score.

    Args:
        category_counts: category -> {"critical": n, "high": n, "medium": n,
            "low": n}. Counts may be fractional (score-weighted effective
            counts; see :func:`score_weight`).
        lines_of_code: total LOC scanned; <= 0 disables size normalization.

    Returns:
        Integer-valued float in (0, 100]. Rounded half-up (matches the
        DEEPTHINK_02 golden walkthroughs; pure floor would yield 55 on the
        breadth walkthrough instead of the documented 56).
    """
    s = size_factor(lines_of_code)
    n_crit = 0.0
    n_high = 0.0
    med_eff = 0.0
    low_eff = 0.0
    for counts in category_counts.values():
        n_crit += max(0.0, float(counts.get("critical", 0)))
        n_high += max(0.0, float(counts.get("high", 0)))
        med = max(0.0, float(counts.get("medium", 0)))
        low = max(0.0, float(counts.get("low", 0)))
        med_eff += med ** _SOFT_CAP_EXP
        low_eff += low ** _SOFT_CAP_EXP
    med_eff /= s
    low_eff /= s

    raw = (
        100.0
        * _CRIT_DECAY ** n_crit
        * _HIGH_DECAY ** n_high
        * _MED_DECAY ** med_eff
        * _LOW_DECAY ** low_eff
    )
    return float(int(raw + 0.5))


def legacy_security_score(
    critical: int, high: int, medium: int, low: int
) -> float:
    """The deprecated linear-subtractive score (kept one minor version)."""
    score = 100.0 - critical * 25 - high * 10 - medium * 5 - low * 1
    return max(0.0, score)


def counts_dict(critical=0.0, high=0.0, medium=0.0, low=0.0) -> Dict[str, float]:
    """Convenience constructor for a per-category severity-count mapping."""
    return {"critical": critical, "high": high, "medium": medium, "low": low}
