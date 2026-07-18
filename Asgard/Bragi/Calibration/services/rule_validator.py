"""
Rule Validity Scoring (Plan 05 Phase C+D, opt-in).

DEEPTHINK_10's Heimdall-Quality framework, phased honestly:

    Stage 1 (this module, `compute_rule_validity`): reuse the bugfix-commit
    heuristic (Plan 02's `_git_friction.py` provides the commit
    classification; this module only does the statistics) - compare
    violation density in files subsequently touched by bugfix commits vs
    not, CONTROLLING FOR LOC by comparing within size deciles. This is
    deliberately the test that matters most in this plan: a rule that is
    merely a file-size proxy must not score PREDICTIVE.

    Stage 2 (this module, `compute_rule_validity_stage2`): full SZZ
    (`szz.py`) traces bug-inducing commits from the repo's own history;
    `nb_model.py` fits a Negative-Binomial count regression of per-file
    defect-inducement count on rule-firing + LOC + churn, so a rule's
    association with defects is measured *net of* size/activity, and
    SHAP-lite attribution (exact for this additive log-link model) turns
    the fitted coefficient into a per-rule, per-file contribution. Needs
    a practical minimum of bug-fix commits (`szz.MIN_FIX_COMMITS`) to even
    attempt a trace, and a full DEEPTHINK_10 burn-in (200-300 traceable
    fixes) before its verdict should be trusted at full strength - below
    that this module still emits a verdict but flags
    `small_sample_warning`. Below the practical minimum entirely, it
    returns a typed `INSUFFICIENT_DATA` result and Stage 1 (or the shipped
    priors) remain authoritative.

Everything here is git-based and offline - no network, no external
services, no tracker integration.
"""

from collections import defaultdict
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence

from Asgard.Bragi.Calibration.models.calibration_models import (
    FeatureAttribution,
    Stage2ValidityReport,
    ValidityReport,
    ValidityVerdict,
)
from Asgard.Bragi.Calibration.services import nb_model, szz

BURN_IN_THRESHOLD = 15
DECILE_COUNT = 10

# Stage 2 gates (Plan 05 Sec.3.3).
STAGE2_MIN_OBSERVATIONS = 20          # files needed to even attempt an NB fit
STAGE2_FULL_BURN_IN = 200             # DEEPTHINK_10's "trust this at full strength" bar
# A rule's own attribution must clear the controls by this ratio to count as
# incremental signal rather than noise riding on the LOC/churn controls.
STAGE2_INCREMENTAL_RATIO = 1.10
STAGE2_NOISY_RATIO = 0.90


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


class RuleFileMetrics(NamedTuple):
    """One file's Stage 2 input row: rule-firing count plus size/churn controls."""
    file_path: str
    rule_firing_count: int
    loc: int
    churn: int


_RULE_FEATURE = "rule_firing"
_CONTROL_FEATURES = ("loc", "churn")
_STAGE2_FEATURES = (_RULE_FEATURE,) + _CONTROL_FEATURES


def compute_rule_validity_stage2(
    repo_root,
    rule_id: str,
    file_metrics: Sequence[RuleFileMetrics],
    min_fix_commits: int = szz.MIN_FIX_COMMITS,
    min_observations: int = STAGE2_MIN_OBSERVATIONS,
) -> Stage2ValidityReport:
    """
    Full Stage 2: SZZ-trace `repo_root`'s history for bug-inducing commits,
    fit an NB count-regression of per-file defect-inducement count on
    rule-firing + LOC + churn, and classify the rule's *incremental*
    (controls-adjusted) association with defects via SHAP-lite attribution.

    Never fabricates a verdict: any of "too few fix commits to trace",
    "too few files with both rule + SZZ data", or "IRLS did not converge"
    returns `ValidityVerdict.INSUFFICIENT_DATA` with the reason in `note`.
    """
    szz_result = szz.compute_szz(repo_root, min_fix_commits=min_fix_commits)
    if szz_result.status != "ok":
        return Stage2ValidityReport(
            rule_id=rule_id,
            verdict=ValidityVerdict.INSUFFICIENT_DATA,
            fix_commit_count=szz_result.fix_commit_count,
            note=f"SZZ trace unavailable: {szz_result.note}",
        )

    observations: List[nb_model.Observation] = []
    for row in file_metrics:
        defect_count = szz_result.induced_commit_counts.get(row.file_path, 0)
        observations.append(
            nb_model.Observation(
                file_path=row.file_path,
                features={
                    _RULE_FEATURE: float(row.rule_firing_count),
                    "loc": float(row.loc),
                    "churn": float(row.churn),
                },
                defect_count=defect_count,
            )
        )

    if len(observations) < min_observations:
        return Stage2ValidityReport(
            rule_id=rule_id,
            verdict=ValidityVerdict.INSUFFICIENT_DATA,
            fix_commit_count=szz_result.fix_commit_count,
            n=len(observations),
            note=(
                f"only {len(observations)} file(s) with both rule-firing and SZZ "
                f"data; Stage 2 requires >= {min_observations} to fit an NB model"
            ),
        )

    fit = nb_model.fit_negative_binomial(observations, feature_names=list(_STAGE2_FEATURES))
    if not fit.converged:
        return Stage2ValidityReport(
            rule_id=rule_id,
            verdict=ValidityVerdict.INSUFFICIENT_DATA,
            fix_commit_count=szz_result.fix_commit_count,
            n=len(observations),
            note="NB/IRLS fit did not converge - insufficient variation in this sample to trust a verdict",
        )

    attribution = nb_model.feature_attribution(
        fit, observations, rule_feature=_RULE_FEATURE, control_features=list(_CONTROL_FEATURES)
    )
    attribution = FeatureAttribution(
        rule_id=rule_id,
        mean_abs_rule_attribution=attribution.mean_abs_rule_attribution,
        mean_abs_control_attribution=attribution.mean_abs_control_attribution,
        per_feature_mean_attribution=attribution.per_feature_mean_attribution,
    )

    beta_rule = fit.coefficients.get(_RULE_FEATURE, 0.0)
    rate_ratio = None
    try:
        rate_ratio = min(1e6, max(1e-6, 2.718281828459045 ** beta_rule))
    except OverflowError:
        rate_ratio = None

    # Incremental-signal test: the rule's own attribution must not be
    # dwarfed (or merely tied) by the LOC+churn control attribution, and
    # its coefficient sign must point the expected direction.
    control_floor = max(attribution.mean_abs_control_attribution, 1e-9)
    ratio = attribution.mean_abs_rule_attribution / control_floor

    if beta_rule > 0 and ratio >= STAGE2_INCREMENTAL_RATIO:
        verdict = ValidityVerdict.PREDICTIVE
        note = (
            f"rate ratio {rate_ratio:.2f}x per additional firing (beta={beta_rule:.3f}); "
            f"rule attribution exceeds LOC+churn controls by {ratio:.2f}x"
        )
    elif beta_rule < 0 and ratio >= STAGE2_INCREMENTAL_RATIO:
        verdict = ValidityVerdict.NOISY
        note = (
            f"rule-firing is associated with FEWER defect-inducing commits after controls "
            f"(beta={beta_rule:.3f}, rate ratio {rate_ratio:.2f}x) - counterproductive/perverse signal"
        )
    else:
        verdict = ValidityVerdict.NEUTRAL
        note = (
            f"rule attribution ({attribution.mean_abs_rule_attribution:.4f}) is not distinguishable "
            f"from LOC+churn controls ({attribution.mean_abs_control_attribution:.4f}) - "
            "no incremental predictive power beyond size/activity"
        )

    small_sample_warning = szz_result.fix_commit_count < STAGE2_FULL_BURN_IN
    if small_sample_warning:
        note += (
            f" [small-sample warning: only {szz_result.fix_commit_count} traceable fix commit(s), "
            f"below the {STAGE2_FULL_BURN_IN}-fix DEEPTHINK_10 burn-in - treat this verdict as provisional]"
        )

    return Stage2ValidityReport(
        rule_id=rule_id,
        verdict=verdict,
        n=len(observations),
        fix_commit_count=szz_result.fix_commit_count,
        rate_ratio=rate_ratio,
        attribution=attribution,
        small_sample_warning=small_sample_warning,
        note=note,
    )


def combine_stage1_stage2(
    stage1: ValidityReport, stage2: Optional[Stage2ValidityReport]
) -> ValidityReport:
    """
    Wire Stage 2 into the existing rule_validator output. Stage 2, when it
    reaches a real verdict (not INSUFFICIENT_DATA), is the more rigorous
    signal (controls for churn, not just LOC; uses actual bug-inducement
    rather than a density lift) and overrides Stage 1's verdict; Stage 1's
    PREDICTIVE/NEUTRAL/UNKNOWN stands alone whenever Stage 2 could not run.
    The full Stage 2 report always rides along in `.stage2` regardless, so
    nothing is silently dropped.
    """
    if stage2 is None or stage2.verdict == ValidityVerdict.INSUFFICIENT_DATA:
        return stage1.model_copy(update={"stage2": stage2})

    return stage1.model_copy(update={"verdict": stage2.verdict, "stage2": stage2})
