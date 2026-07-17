"""
Rule Validity Scoring (Plan 05 Phase C, opt-in; Stage 1 only).

DEEPTHINK_10's Heimdall-Quality framework, phased honestly:

    Stage 1 (this module): reuse the bugfix-commit heuristic (Plan 02's
    `_git_friction.py` provides the commit classification; this module
    only does the statistics) - compare violation density in files
    subsequently touched by bugfix commits vs not, CONTROLLING FOR LOC by
    comparing within size deciles. This is deliberately the test that
    matters most in this plan: a rule that is merely a file-size proxy
    must not score PREDICTIVE.

    Stage 2 (full SZZ + ZINB/SHAP) is out of scope for this module; it
    needs 200-300 traceable bug-fix commits (12-24 months of history) and
    is left as documented future work (`_Docs/Planning/Bragi/05_...md`
    Sec.3.3). Below the Stage 1 burn-in (>= 15 events), rules stay UNKNOWN
    and priors (the shipped language profiles) are kept.

Everything here is git-based and offline - no network, no external
services, no tracker integration.
"""

from collections import defaultdict
from typing import Dict, Iterable, List, NamedTuple

from Asgard.Bragi.Calibration.models.calibration_models import ValidityReport, ValidityVerdict

BURN_IN_THRESHOLD = 15
DECILE_COUNT = 10


class FileObservation(NamedTuple):
    """One file's observation for one rule at one point in time."""
    file_path: str
    loc: int
    violation_count: int
    touched_by_bugfix: bool


def _loc_decile(loc: int, all_locs: List[int]) -> int:
    """Which LOC decile (0-9) a file falls into, over the observed population."""
    if not all_locs:
        return 0
    ordered = sorted(all_locs)
    n = len(ordered)
    rank = sum(1 for v in ordered if v <= loc)
    decile = min(int((rank - 1) * DECILE_COUNT / n), DECILE_COUNT - 1)
    return max(decile, 0)


def _density(observations: Iterable[FileObservation]) -> float:
    observations = list(observations)
    total_loc = sum(o.loc for o in observations) or 1
    total_violations = sum(o.violation_count for o in observations)
    return total_violations / total_loc


def compute_rule_validity(
    rule_id: str,
    observations: List[FileObservation],
    burn_in_threshold: int = BURN_IN_THRESHOLD,
) -> ValidityReport:
    """
    Stage 1 lift: within each LOC decile, compare violation density in
    bugfix-touched files vs untouched files; average the per-decile lift
    ratios (LOC-decile control prevents a pure size proxy from scoring
    PREDICTIVE - the DEEPTHINK_10 confounder test).

    lift > 1 means bugfix-touched files carry more of this rule's
    violations than same-size clean files - evidence the rule predicts
    risk. lift <= 1 or n below burn-in -> NEUTRAL/UNKNOWN, never deleted.
    """
    n = sum(1 for o in observations if o.touched_by_bugfix)
    if n < burn_in_threshold:
        return ValidityReport(
            rule_id=rule_id, lift=None, n=n, verdict=ValidityVerdict.UNKNOWN,
            burn_in_threshold=burn_in_threshold,
            note=f"only {n} bugfix-touched observation(s); burn-in requires {burn_in_threshold}",
        )

    all_locs = [o.loc for o in observations]
    by_decile: Dict[int, List[FileObservation]] = defaultdict(list)
    for obs in observations:
        by_decile[_loc_decile(obs.loc, all_locs)].append(obs)

    decile_lifts: List[float] = []
    for decile, obs_list in by_decile.items():
        touched = [o for o in obs_list if o.touched_by_bugfix]
        untouched = [o for o in obs_list if not o.touched_by_bugfix]
        if not touched or not untouched:
            continue
        touched_density = _density(touched)
        untouched_density = _density(untouched)
        if untouched_density <= 0:
            continue
        decile_lifts.append(touched_density / untouched_density)

    if not decile_lifts:
        return ValidityReport(
            rule_id=rule_id, lift=None, n=n, verdict=ValidityVerdict.UNKNOWN,
            burn_in_threshold=burn_in_threshold,
            note="no LOC decile had both touched and untouched observations",
        )

    lift = sum(decile_lifts) / len(decile_lifts)
    verdict = ValidityVerdict.PREDICTIVE if lift > 1.0 else ValidityVerdict.NEUTRAL
    note = (
        f"mean decile-controlled lift {lift:.2f} over {len(decile_lifts)} decile(s), "
        f"n={n} bugfix-touched observations"
    )
    return ValidityReport(
        rule_id=rule_id, lift=lift, n=n, verdict=verdict,
        burn_in_threshold=burn_in_threshold, note=note,
    )


def demoted_channel(current_channel: str) -> str:
    """
    NEUTRAL-rule consequence (Plan 05 Sec.3.3): demote one channel tier,
    never delete. ci_gate -> pr_review -> dashboard; ide and dashboard
    already carry maximal recall and stay put.
    """
    ladder = {"ci_gate": "pr_review", "pr_review": "dashboard"}
    return ladder.get(current_channel, current_channel)
