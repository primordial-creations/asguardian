"""
Tests for the Plan 05 Stage-1 rule validity scorer.

The LOC-decile confounder test (the most important test in this plan per
the plan doc) asserts that a rule whose "violations" are purely a function
of file size cannot score PREDICTIVE just because bugfix-touched files
happen to be larger on average.
"""

import random

from Asgard.Bragi.Calibration.models.calibration_models import ValidityVerdict
from Asgard.Bragi.Calibration.services.rule_validator import (
    BURN_IN_THRESHOLD,
    FileObservation,
    compute_rule_validity,
    demoted_channel,
)


def _make_observations(n_touched, n_untouched, violation_fn, loc_fn, seed=0):
    rng = random.Random(seed)
    obs = []
    for i in range(n_touched):
        loc = loc_fn(rng)
        obs.append(FileObservation(f"touched_{i}.py", loc, violation_fn(loc, rng), True))
    for i in range(n_untouched):
        loc = loc_fn(rng)
        obs.append(FileObservation(f"clean_{i}.py", loc, violation_fn(loc, rng), False))
    return obs


class TestBurnIn:
    def test_below_burn_in_is_unknown(self):
        obs = _make_observations(5, 50, lambda loc, r: 1, lambda r: 100)
        report = compute_rule_validity("R1", obs)
        assert report.verdict == ValidityVerdict.UNKNOWN
        assert report.n < BURN_IN_THRESHOLD


class TestPredictiveRule:
    def test_genuinely_predictive_rule_scores_predictive(self):
        # Bugfix-touched files carry 5x the violation density of clean
        # files at every size, independent of LOC - a real signal.
        obs = _make_observations(
            n_touched=40, n_untouched=200,
            violation_fn=lambda loc, r: r.choice([5, 6, 7]),
            loc_fn=lambda r: r.choice([100, 500, 1000]),
        )
        # Give clean files a much lower violation rate at the same sizes.
        obs = [
            FileObservation(o.file_path, o.loc, o.violation_count, o.touched_by_bugfix)
            if o.touched_by_bugfix else
            FileObservation(o.file_path, o.loc, 1, o.touched_by_bugfix)
            for o in obs
        ]
        report = compute_rule_validity("R_PREDICTIVE", obs)
        assert report.verdict == ValidityVerdict.PREDICTIVE
        assert report.lift > 1.0


class TestSizeConfounder:
    """The confounder test: a pure LOC proxy must not score PREDICTIVE."""

    def test_pure_size_proxy_does_not_score_predictive(self):
        rng = random.Random(42)
        obs = []
        # Bugfix-touched files ARE larger on average (a common real-world
        # correlation), and violation_count is purely proportional to LOC
        # (density is therefore IDENTICAL for touched vs untouched at any
        # given size) - the rule carries zero information beyond size.
        for i in range(30):
            loc = rng.choice([800, 900, 1000])  # touched files skew large
            obs.append(FileObservation(f"touched_{i}.py", loc, loc // 50, True))
        for i in range(200):
            loc = rng.choice([100, 200, 300, 800, 900, 1000])
            obs.append(FileObservation(f"clean_{i}.py", loc, loc // 50, False))

        report = compute_rule_validity("R_SIZE_PROXY", obs)
        # Decile-controlled lift must be ~1.0 (NEUTRAL), not > 1 - a naive
        # ungrouped comparison would show elevated density in the
        # (larger, touched) group purely from the size skew.
        assert report.verdict == ValidityVerdict.NEUTRAL
        assert report.lift is not None
        assert 0.8 <= report.lift <= 1.25


class TestChannelDemotion:
    def test_ci_gate_demotes_to_pr_review(self):
        assert demoted_channel("ci_gate") == "pr_review"

    def test_pr_review_demotes_to_dashboard(self):
        assert demoted_channel("pr_review") == "dashboard"

    def test_dashboard_stays_put(self):
        assert demoted_channel("dashboard") == "dashboard"
