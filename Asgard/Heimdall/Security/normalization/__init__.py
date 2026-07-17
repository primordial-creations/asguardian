"""
Heimdall Security Severity/Scoring Normalization Engine.

Central authority for:
- Confidence buckets (qualitative display; raw probabilities are internal only).
- Universal CIA-impact severity mapping (mechanism id -> severity).
- Cross-module severity equivalency matrix.
- Actionable priority (Impact x Confidence x Context).
- Multiplicative-decay security score (replaces the linear-subtractive model).

Severity and confidence are orthogonal: severity encodes blast radius (CIA
impact) and is NEVER diluted by detection uncertainty. Confidence routes a
finding to review/triage; it never downgrades severity.
"""

from Asgard.Heimdall.Security.normalization.priority import (
    CONFIDENCE_BUCKETS,
    IMPACT_POINTS,
    confidence_bucket,
    priority,
)
from Asgard.Heimdall.Security.normalization.impact_matrix import (
    MECHANISMS,
    NormalizedFinding,
    normalize_finding,
)
from Asgard.Heimdall.Security.normalization.equivalency import (
    EQUIVALENCY_MATRIX,
    finding_classes_for,
    severity_of_class,
)
from Asgard.Heimdall.Security.normalization.scoring import (
    legacy_security_score,
    multiplicative_security_score,
    score_weight,
    size_factor,
)

__all__ = [
    "CONFIDENCE_BUCKETS",
    "IMPACT_POINTS",
    "confidence_bucket",
    "priority",
    "MECHANISMS",
    "NormalizedFinding",
    "normalize_finding",
    "EQUIVALENCY_MATRIX",
    "finding_classes_for",
    "severity_of_class",
    "legacy_security_score",
    "multiplicative_security_score",
    "score_weight",
    "size_factor",
]
