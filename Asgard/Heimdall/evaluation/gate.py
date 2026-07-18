"""
CI acceptance gate for the analyzer itself (plan 10 s3): fails a rule
change if it doesn't clear the profile thresholds, regresses recall on
the temporal holdout ("overfit rejection"), or worsens the Brier score
on the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from Asgard.Heimdall.evaluation.runner import CorpusMetrics


@dataclass(frozen=True)
class AcceptanceProfile:
    name: str
    min_precision: float
    min_recall: float
    min_f_beta: float
    f_beta_attr: str  # "f_half" or "f_two"
    max_alert_density: float


ACCEPTANCE_PROFILES = {
    # Profile A: blocking dev PRs (plan 10 s3).
    "A": AcceptanceProfile(
        name="A (blocking dev PRs)",
        min_precision=0.60,
        min_recall=0.35,
        min_f_beta=0.52,
        f_beta_attr="f_half",
        max_alert_density=2.0,
    ),
    # Profile B: async audit.
    "B": AcceptanceProfile(
        name="B (async audit)",
        min_precision=0.20,
        min_recall=0.75,
        min_f_beta=0.50,
        f_beta_attr="f_two",
        max_alert_density=15.0,
    ),
}

# Overfit rejection: recall drop vs. fixture benchmark that disqualifies a
# rule regardless of headline score (plan 10 s3).
MAX_RECALL_DROP_RATIO = 0.20


@dataclass
class GateResult:
    passed: bool
    reasons: List[str]


def evaluate_gate(
    metrics: CorpusMetrics,
    profile: str = "A",
    fixture_recall: Optional[float] = None,
    holdout_recall: Optional[float] = None,
    baseline_brier: Optional[float] = None,
    new_brier: Optional[float] = None,
) -> GateResult:
    """Evaluate one corpus run against an acceptance profile plus the
    overfit-rejection and Brier non-regression checks.

    ``fixture_recall``/``holdout_recall`` and ``baseline_brier``/
    ``new_brier`` are optional: when omitted, that specific check is
    skipped (callers that only have headline metrics still get the
    profile thresholds enforced).
    """
    if profile not in ACCEPTANCE_PROFILES:
        raise ValueError(f"unknown acceptance profile: {profile!r}")
    spec = ACCEPTANCE_PROFILES[profile]
    reasons: List[str] = []

    if metrics.precision < spec.min_precision:
        reasons.append(
            f"precision {metrics.precision:.3f} < profile {profile} minimum {spec.min_precision:.3f}"
        )
    if metrics.recall < spec.min_recall:
        reasons.append(
            f"recall {metrics.recall:.3f} < profile {profile} minimum {spec.min_recall:.3f}"
        )
    f_value = getattr(metrics, spec.f_beta_attr)
    if f_value < spec.min_f_beta:
        reasons.append(
            f"{spec.f_beta_attr} {f_value:.3f} < profile {profile} minimum {spec.min_f_beta:.3f}"
        )
    if metrics.alert_density > spec.max_alert_density:
        reasons.append(
            f"alert density {metrics.alert_density:.2f}/10k LOC > profile {profile} "
            f"maximum {spec.max_alert_density:.2f}/10k LOC"
        )

    if fixture_recall is not None and holdout_recall is not None and fixture_recall > 0:
        drop_ratio = (fixture_recall - holdout_recall) / fixture_recall
        if drop_ratio > MAX_RECALL_DROP_RATIO:
            reasons.append(
                f"overfit rejection: temporal-holdout recall {holdout_recall:.3f} is "
                f"{drop_ratio:.1%} below fixture recall {fixture_recall:.3f} "
                f"(max allowed drop {MAX_RECALL_DROP_RATIO:.0%})"
            )

    if baseline_brier is not None and new_brier is not None:
        if new_brier > baseline_brier:
            reasons.append(
                f"Brier score regressed: {new_brier:.4f} > baseline {baseline_brier:.4f}"
            )

    return GateResult(passed=not reasons, reasons=reasons)
