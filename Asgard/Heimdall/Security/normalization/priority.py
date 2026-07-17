"""
Confidence buckets and actionable priority.

Confidence is displayed ONLY as qualitative buckets (DEEPTHINK_03 s4):
    certain  : > 0.85       (may block CI)
    probable : 0.50 - 0.85  (PR warning)
    possible : 0.25 - 0.49  (informational; never blocks)
    unlikely : < 0.25       (hidden by default; audit dashboards only)

Priority = impact_points(severity) x confidence x context_modifier.
It orders reports/PR comments; it never changes severity.
"""

from typing import Dict

# Bucket name -> (inclusive lower bound, exclusive upper bound); "certain" is
# exclusive-lower per spec (> 0.85).
CONFIDENCE_BUCKETS: Dict[str, tuple] = {
    "certain": (0.85, 1.0000001),
    "probable": (0.50, 0.85),
    "possible": (0.25, 0.50),
    "unlikely": (0.0, 0.25),
}

# Impact points per severity for priority ordering (DEEPTHINK_11).
IMPACT_POINTS: Dict[str, float] = {
    "critical": 100.0,
    "high": 80.0,
    "medium": 50.0,
    "low": 20.0,
    "info": 5.0,
}


def confidence_bucket(confidence: float) -> str:
    """Map a raw confidence probability to its qualitative display bucket."""
    c = max(0.0, min(1.0, float(confidence)))
    if c > 0.85:
        return "certain"
    if c >= 0.50:
        return "probable"
    if c >= 0.25:
        return "possible"
    return "unlikely"


def priority(severity: str, confidence: float, context_modifier: float = 1.0) -> float:
    """
    Actionable priority for report ordering.

    A validated (confidence 1.0) HIGH secret (80) outranks a tentative
    (confidence 0.4) CRITICAL RCE (40) -- the DEEPTHINK_11 worked example.
    """
    impact = IMPACT_POINTS.get(str(severity).lower(), 0.0)
    conf = max(0.0, min(1.0, float(confidence)))
    ctx = max(0.0, min(1.0, float(context_modifier)))
    return impact * conf * ctx
