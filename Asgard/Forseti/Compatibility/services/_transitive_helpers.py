"""
Transitive Helpers - N-version (transitive) compatibility checking
(RESEARCH_02 temporal depth).

BACKWARD_TRANSITIVE: the newest schema must be compatible with EVERY
prior version, not just the immediately preceding one; likewise FORWARD
and FULL.
"""

from typing import Callable

from Asgard.Forseti.Compatibility.models._compat_base_models import CompatMode
from Asgard.Forseti.Compatibility.models.compat_models import CompatReport
from Asgard.Forseti.Compatibility.services._scoring_helpers import (
    compute_score,
    compute_status,
)

PairwiseCheck = Callable[[str, str, CompatMode], CompatReport]


def check_transitive(
    history: list[str],
    mode: CompatMode,
    pairwise_check: PairwiseCheck,
) -> CompatReport:
    """
    Fold a pairwise check over an ordered version list (oldest first).

    Non-transitive modes check only the last pair; transitive modes check
    the newest schema against every earlier version.
    """
    if len(history) < 2:
        raise ValueError("Transitive check requires at least two schema versions")
    base = mode.pairwise
    newest = history[-1]
    if mode.is_transitive:
        pairs = [(older, newest) for older in history[:-1]]
    else:
        pairs = [(history[-2], newest)]

    reports = [pairwise_check(old, new, base) for old, new in pairs]
    merged_changes = []
    seen = set()
    for report in reports:
        for change in report.changes:
            key = (change.rule_id, change.location, change.message)
            if key not in seen:
                seen.add(key)
                merged_changes.append(change)

    score, receipt = compute_score(merged_changes)
    status = compute_status(merged_changes)
    return CompatReport(
        mode=mode,
        status=status,
        format=reports[-1].format,
        source=history[0],
        target=newest,
        score=score,
        score_receipt=receipt,
        changes=merged_changes,
        structural_breaks=sum(1 for c in merged_changes if c.is_breaking),
        semantic_hazards=sum(1 for c in merged_changes if c.is_hazard),
        confidence=reports[-1].confidence,
        check_time_ms=sum(r.check_time_ms for r in reports),
    )
