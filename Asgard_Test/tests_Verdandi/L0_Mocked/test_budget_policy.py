"""
Unit tests for BudgetPolicyEngine: policy tiers, the 20%-single-incident
post-mortem flag, and the meta-SLO buffer (Plan 02 sections 2.5-2.6).
"""

from datetime import datetime, timedelta

import pytest

from Asgard.Verdandi.SLO import (
    BudgetPolicyEngine,
    BudgetPolicyTier,
    ErrorBudgetCalculator,
    SLIMetric,
    SLODefinition,
    SLOType,
)


def _budget(good, total, target=99.9, window_days=30):
    slo = SLODefinition(
        name="api", slo_type=SLOType.AVAILABILITY, target=target,
        window_days=window_days, service_name="api",
    )
    now = datetime.now()
    metrics = [
        SLIMetric(
            timestamp=now - timedelta(hours=1), service_name="api",
            slo_type=SLOType.AVAILABILITY, good_events=good, total_events=total,
        )
    ]
    return ErrorBudgetCalculator().calculate(slo, metrics, now), slo


class TestPolicyTiers:
    def setup_method(self):
        self.engine = BudgetPolicyEngine()

    def test_normal_tier_above_50_percent_remaining(self):
        # target 99.9%, allowed failures = 0.1% of total; consume 10% of that.
        budget, _ = _budget(good=9999, total=10000)  # 1 bad / 10 allowed = 10% consumed
        state = self.engine.evaluate(budget)
        assert state.tier == BudgetPolicyTier.NORMAL

    def test_caution_tier_25_to_50_percent_remaining(self):
        # consume 60% of budget -> 40% remaining -> CAUTION
        budget, _ = _budget(good=9994, total=10000)  # 6 bad / 10 allowed = 60% consumed
        state = self.engine.evaluate(budget)
        assert state.tier == BudgetPolicyTier.CAUTION

    def test_freeze_tier_below_25_percent_remaining(self):
        # consume 80% -> 20% remaining -> FREEZE
        budget, _ = _budget(good=9992, total=10000)  # 8 bad / 10 allowed = 80% consumed
        state = self.engine.evaluate(budget)
        assert state.tier == BudgetPolicyTier.FREEZE

    def test_exhausted_tier_at_zero_remaining(self):
        budget, _ = _budget(good=9989, total=10000)  # 11 bad / 10 allowed > 100% consumed
        state = self.engine.evaluate(budget)
        assert state.tier == BudgetPolicyTier.EXHAUSTED
        assert state.post_mortem_required is True

    def test_perfect_budget_is_normal(self):
        budget, _ = _budget(good=10000, total=10000)
        state = self.engine.evaluate(budget)
        assert state.tier == BudgetPolicyTier.NORMAL
        assert state.post_mortem_required is False


class TestSingleIncidentPostMortem:
    def setup_method(self):
        self.engine = BudgetPolicyEngine()

    def test_incident_consuming_20_percent_flags_post_mortem(self):
        impact = self.engine.incident_budget_impact(
            bad_events=2, total_allowed_failures=10
        )
        assert impact.budget_consumed_pct == pytest.approx(20.0)
        assert impact.post_mortem_required is True

    def test_incident_below_20_percent_does_not_flag(self):
        impact = self.engine.incident_budget_impact(
            bad_events=1, total_allowed_failures=10
        )
        assert impact.budget_consumed_pct == pytest.approx(10.0)
        assert impact.post_mortem_required is False

    def test_normal_tier_but_single_incident_still_flags(self):
        # Overall budget is healthy (NORMAL) but one incident alone hit 20%.
        budget, _ = _budget(good=9999, total=10000)
        incident = self.engine.incident_budget_impact(
            bad_events=2, total_allowed_failures=10
        )
        state = self.engine.evaluate(budget, incidents=[incident])
        assert state.tier == BudgetPolicyTier.NORMAL
        assert state.post_mortem_required is True
        assert state.incidents[0].post_mortem_required is True


class TestMetaSLOBuffer:
    def setup_method(self):
        self.engine = BudgetPolicyEngine()

    def test_buffer_reported_when_external_target_set(self):
        budget, slo = _budget(good=9999, total=10000, target=99.95)
        slo = slo.model_copy(update={"external_sla_target": 99.9})
        state = self.engine.evaluate(budget, slo=slo)

        assert state.meta_slo_buffer_minutes is not None
        assert state.meta_slo_buffer_minutes > 0
        assert state.meta_slo_buffer_valid is True

    def test_buffer_none_without_external_target(self):
        budget, slo = _budget(good=9999, total=10000)
        state = self.engine.evaluate(budget, slo=slo)
        assert state.meta_slo_buffer_minutes is None
        assert state.meta_slo_buffer_valid is None

    def test_buffer_invalid_when_internal_not_tighter(self):
        budget, slo = _budget(good=9999, total=10000, target=99.9)
        slo = slo.model_copy(update={"external_sla_target": 99.95})
        state = self.engine.evaluate(budget, slo=slo)
        assert state.meta_slo_buffer_valid is False
