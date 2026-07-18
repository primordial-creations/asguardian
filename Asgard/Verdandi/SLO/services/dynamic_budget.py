"""
Dynamic (Work-Normalized) Latency Budget

Static latency thresholds break on multimodal/variable-cost workloads
(DEEPTHINK_09): a request that legitimately does more work should be
allowed more time. This evaluates each request against a budget that
scales with a caller-supplied "complexity" measure:

    sli_passed = duration_ms <= base_ms + f(complexity_units) * cost_per_unit_ms

The output is a boolean pass/fail stream immune to traffic-mix shifts,
designed to feed straight into SLITracker/SLIMetric as good/total events.
"""

import math
from typing import Callable, List, Optional, Sequence

from Asgard.Verdandi.SLO.models.slo_models import SLIMetric, SLOType


def linear_cost(complexity_units: float) -> float:
    """Default cost function: cost scales linearly with complexity."""
    return max(0.0, complexity_units)


def nlogn_cost(complexity_units: float) -> float:
    """Cost function for n*log(n)-scaling work (e.g. sort-shaped endpoints)."""
    n = max(0.0, complexity_units)
    if n <= 1.0:
        return n
    return n * math.log2(n)


class DynamicLatencyBudget:
    """
    Work-normalized per-request SLI evaluator.

    Example:
        budget = DynamicLatencyBudget(base_ms=50.0, cost_per_unit_ms=2.0)
        passed = budget.evaluate(duration_ms=180.0, complexity_units=50)
        # budget = 50 + 50*2 = 150ms; 180ms > 150ms -> False
    """

    def __init__(
        self,
        base_ms: float,
        cost_per_unit_ms: float,
        cost_function: Callable[[float], float] = linear_cost,
    ):
        """
        Args:
            base_ms: Fixed baseline latency budget (network/framework overhead)
            cost_per_unit_ms: Milliseconds of budget granted per complexity unit
            cost_function: Maps raw complexity_units to "billed" units before
                multiplying by cost_per_unit_ms (linear by default; nlogn_cost
                for sort/merge-shaped work)
        """
        if base_ms < 0:
            raise ValueError("base_ms must be non-negative")
        if cost_per_unit_ms < 0:
            raise ValueError("cost_per_unit_ms must be non-negative")
        self.base_ms = base_ms
        self.cost_per_unit_ms = cost_per_unit_ms
        self.cost_function = cost_function

    def budget_for(self, complexity_units: float) -> float:
        """The allowed latency budget (ms) for a given complexity."""
        return self.base_ms + self.cost_function(complexity_units) * self.cost_per_unit_ms

    def evaluate(self, duration_ms: float, complexity_units: float) -> bool:
        """Return True (sli_passed) when duration_ms is within the dynamic budget."""
        return duration_ms <= self.budget_for(complexity_units)

    def evaluate_batch(
        self,
        durations_ms: Sequence[float],
        complexity_units: Sequence[float],
    ) -> List[bool]:
        """
        Evaluate a batch of requests. Feeds directly into SLITracker as a
        good/total boolean stream.

        Raises:
            ValueError: If the sequences have mismatched lengths
        """
        if len(durations_ms) != len(complexity_units):
            raise ValueError("durations_ms and complexity_units must have same length")
        return [
            self.evaluate(duration, complexity)
            for duration, complexity in zip(durations_ms, complexity_units)
        ]

    def to_sli_metric(
        self,
        timestamp,
        service_name: str,
        durations_ms: Sequence[float],
        complexity_units: Sequence[float],
        labels: Optional[dict] = None,
    ) -> SLIMetric:
        """
        Evaluate a batch and package it as an SLIMetric (good = within
        dynamic budget), ready for SLITracker.record().
        """
        results = self.evaluate_batch(durations_ms, complexity_units)
        good = sum(1 for r in results if r)
        return SLIMetric(
            timestamp=timestamp,
            service_name=service_name,
            slo_type=SLOType.LATENCY,
            good_events=good,
            total_events=len(results),
            labels=labels or {},
        )
