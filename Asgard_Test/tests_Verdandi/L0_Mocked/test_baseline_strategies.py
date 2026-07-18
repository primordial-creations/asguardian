"""
Tests for the baseline strategy framework (Plan 03E, DEEPTHINK_07).

Strategy taxonomy with confound warnings, Difference-in-Differences,
canary sizing formula, MDES tiers, and cold-start exclusion.
"""

from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.Anomaly import (
    BaselineComparator,
    BaselineStrategy,
    DetectionOutcome,
)


@pytest.fixture
def comparator():
    return BaselineComparator()


class TestStrategyAssessment:
    def test_every_strategy_has_confound_warnings(self, comparator):
        for strategy in BaselineStrategy:
            assessment = comparator.assess_strategy(strategy)
            assert assessment.strategy == strategy
            assert len(assessment.confound_warnings) >= 2
            assert assessment.mdes_percent_range

    def test_pre_post_warns_about_cold_start(self, comparator):
        assessment = comparator.assess_strategy(BaselineStrategy.PRE_POST)

        assert any("old-start" in w for w in assessment.confound_warnings)

    def test_canary_warns_about_sutva(self, comparator):
        assessment = comparator.assess_strategy(BaselineStrategy.CANARY_CONCURRENT)

        assert any("SUTVA" in w for w in assessment.confound_warnings)

    def test_mdes_tiers_ordered_canary_finest_did_coarsest(self, comparator):
        canary = comparator.assess_strategy(BaselineStrategy.CANARY_CONCURRENT)
        did = comparator.assess_strategy(BaselineStrategy.DIFF_IN_DIFF)

        assert canary.mdes_percent_range == "1-5%"
        assert did.mdes_percent_range == "15-25%"


class TestDiffInDiff:
    def test_removes_shared_seasonal_movement(self, comparator):
        # Both weeks got 20ms slower in the afternoon; the deploy added 30ms more.
        pre_now = [100.0] * 10
        post_now = [150.0] * 10  # +50 observed
        pre_lastweek = [100.0] * 10
        post_lastweek = [120.0] * 10  # +20 is seasonal

        result = comparator.diff_in_diff(pre_now, post_now, pre_lastweek, post_lastweek)

        assert result.effect == pytest.approx(30.0)
        assert result.effect_percent == pytest.approx(30.0)
        assert any("arallel-trends" in w for w in result.warnings)

    def test_zero_effect_when_movement_is_all_seasonal(self, comparator):
        result = comparator.diff_in_diff(
            [100.0] * 5, [120.0] * 5, [100.0] * 5, [120.0] * 5
        )

        assert result.effect == pytest.approx(0.0)

    def test_insufficient_data(self, comparator):
        result = comparator.diff_in_diff([], [1.0], [1.0], [1.0])

        assert result.outcome == DetectionOutcome.INSUFFICIENT_DATA


class TestCanarySizing:
    def test_formula_worked_example(self, comparator):
        # T = 8 / (R p (1-p)) * (CV/r)^2
        # R=100 rps, p=0.1, CV=0.5, r=0.05 -> 8/(100*0.09) * 100 = 88.9 s
        duration = comparator.canary_duration_seconds(
            requests_per_second=100, canary_fraction=0.1,
            coefficient_of_variation=0.5, relative_effect=0.05,
        )

        assert duration == pytest.approx(88.8888, rel=1e-3)

    def test_smaller_effects_need_quadratically_longer_windows(self, comparator):
        t_5pct = comparator.canary_duration_seconds(100, 0.1, 0.5, 0.05)
        t_1pct = comparator.canary_duration_seconds(100, 0.1, 0.5, 0.01)

        assert t_1pct == pytest.approx(t_5pct * 25, rel=1e-6)

    def test_invalid_parameters_raise(self, comparator):
        with pytest.raises(ValueError):
            comparator.canary_duration_seconds(100, 1.5, 0.5, 0.05)
        with pytest.raises(ValueError):
            comparator.canary_duration_seconds(0, 0.1, 0.5, 0.05)


class TestColdStartExclusion:
    def test_drops_first_three_minutes_post_deploy(self, comparator):
        deploy = datetime(2026, 1, 1, 12, 0, 0)
        timestamps = [deploy + timedelta(seconds=30 * i) for i in range(10)]
        values = [float(i) for i in range(10)]

        kept, excluded = comparator.exclude_cold_start(values, timestamps, deploy)

        # Samples at 0..150s are inside the 180s window (6 samples)
        assert excluded == 6
        assert kept == [6.0, 7.0, 8.0, 9.0]

    def test_pre_deploy_samples_are_kept(self, comparator):
        deploy = datetime(2026, 1, 1, 12, 0, 0)
        timestamps = [deploy - timedelta(seconds=60), deploy + timedelta(seconds=60)]

        kept, excluded = comparator.exclude_cold_start([1.0, 2.0], timestamps, deploy)

        assert kept == [1.0]
        assert excluded == 1
