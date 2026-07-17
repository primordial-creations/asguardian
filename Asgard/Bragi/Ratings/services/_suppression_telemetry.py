"""
Suppression Telemetry (Plan 04 Sec.3.4).

Thin wrapper turning `QualityGate.suppressions` output into the
`SuppressionStats` "coach vs cop" signal on `ProjectRatings`. Reuses the
QualityGate suppression schema/parser rather than duplicating it - Bragi's
only job here is aggregation.
"""

from typing import Iterable, Set

from Asgard.Bragi.QualityGate.suppressions import (
    SuppressionDirective,
    find_unused_suppressions,
)
from Asgard.Bragi.Ratings.models.ratings_models import SuppressionStats


def build_suppression_stats(
    directives: Iterable[SuppressionDirective],
    active_rule_ids: Set[str] = frozenset(),
) -> SuppressionStats:
    """
    Aggregate parsed suppression directives into telemetry.

    `active_rule_ids` is the set of rule ids that fired anywhere in the
    current scan; directives suppressing a rule outside that set are
    "unused" (Plan 04's stale-suppression finding).
    """
    directives = list(directives)
    by_rule = {}
    invalid = 0
    for d in directives:
        if not d.valid:
            invalid += 1
            continue
        by_rule[d.rule_id] = by_rule.get(d.rule_id, 0) + 1

    unused = find_unused_suppressions(directives, active_rule_ids)

    return SuppressionStats(
        total_suppressions=sum(by_rule.values()),
        by_rule=by_rule,
        invalid_count=invalid,
        unused_count=len(unused),
    )
