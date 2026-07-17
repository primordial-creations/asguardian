"""
Unit tests for DynamicLatencyBudget (work-normalized SLI, DEEPTHINK_09).
"""

from datetime import datetime

import pytest

from Asgard.Verdandi.SLO import DynamicLatencyBudget, linear_cost, nlogn_cost
from Asgard.Verdandi.SLO.models.slo_models import SLOType


class TestDynamicLatencyBudget:
    def test_budget_scales_linearly_with_complexity(self):
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        assert budget.budget_for(0) == 50.0
        assert budget.budget_for(50) == 150.0

    def test_evaluate_within_budget_passes(self):
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        assert budget.evaluate(duration_ms=140.0, complexity_units=50) is True

    def test_evaluate_over_budget_fails(self):
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        assert budget.evaluate(duration_ms=180.0, complexity_units=50) is False

    def test_high_complexity_request_gets_more_budget(self):
        """A request doing 10x the work should not be penalized for taking longer."""
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        assert budget.evaluate(duration_ms=900.0, complexity_units=500) is True

    def test_evaluate_batch_matches_individual_calls(self):
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        durations = [140.0, 180.0, 40.0]
        complexities = [50, 50, 0]
        results = budget.evaluate_batch(durations, complexities)
        assert results == [True, False, True]

    def test_evaluate_batch_mismatched_lengths_raises(self):
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        with pytest.raises(ValueError):
            budget.evaluate_batch([100.0], [1, 2])

    def test_nlogn_cost_function(self):
        budget = DynamicLatencyBudget(
            base_ms=10.0, cost_per_unit_ms=1.0, cost_function=nlogn_cost
        )
        # n=8 -> 8*log2(8) = 24 -> budget = 10 + 24 = 34
        assert budget.budget_for(8) == pytest.approx(34.0)

    def test_to_sli_metric_reflects_pass_fail_counts(self):
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        metric = budget.to_sli_metric(
            timestamp=datetime.now(),
            service_name="checkout",
            durations_ms=[140.0, 180.0, 40.0],
            complexity_units=[50, 50, 0],
        )
        assert metric.slo_type == SLOType.LATENCY
        assert metric.total_events == 3
        assert metric.good_events == 2

    def test_negative_base_raises(self):
        with pytest.raises(ValueError):
            DynamicLatencyBudget(base_ms=-1.0, cost_per_unit_ms=1.0)
