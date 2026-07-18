"""
Work-Normalized Query SLI (thin adapter)

Static slow-query thresholds punish heavy-but-efficient queries and mask
fast-path regressions on continuous complexity distributions (rows scanned
10 vs 10M) (DEEPTHINK_09). The actual budget math lives once in
`Asgard.Verdandi.SLO.services.dynamic_budget.DynamicLatencyBudget`; this
module is a thin Database-shaped adapter plus a calibration helper.
"""

import statistics
from typing import List, Optional, Sequence

from Asgard.Verdandi.Database.models.database_models import QueryBudgetConfig, QueryBudgetResult
from Asgard.Verdandi.SLO.services.dynamic_budget import (
    DynamicLatencyBudget,
    linear_cost,
    nlogn_cost,
)


class QueryBudgetAnalyzer:
    """
    Work-normalized query latency SLI, backed by SLO.DynamicLatencyBudget.

    Example:
        analyzer = QueryBudgetAnalyzer()
        config = QueryBudgetConfig(base_ms=50, cost_per_unit_ms=0.5)
        result = analyzer.evaluate(config, durations_ms=[300, 4900], units=[0, 10_000])
        print(result.sli_passed_fraction)
    """

    def evaluate(
        self,
        config: QueryBudgetConfig,
        durations_ms: Sequence[float],
        units: Sequence[float],
    ) -> QueryBudgetResult:
        """
        Evaluate a batch of queries against a work-normalized budget.

        Args:
            config: Budget configuration (base_ms, cost_per_unit_ms, model)
            durations_ms: Observed query durations in ms
            units: Complexity units per query (rows_scanned/bytes_read/planner_cost)

        Returns:
            QueryBudgetResult
        """
        if len(durations_ms) != len(units):
            raise ValueError("durations_ms and units must have the same length")

        cost_fn = nlogn_cost if config.model == "nlogn" else linear_cost
        budget = DynamicLatencyBudget(
            base_ms=config.base_ms,
            cost_per_unit_ms=config.cost_per_unit_ms,
            cost_function=cost_fn,
        )

        results = budget.evaluate_batch(durations_ms, units)
        good = sum(1 for r in results if r)
        total = len(results)
        violations = [i for i, r in enumerate(results) if not r]

        notes: List[str] = []
        if total > 0 and good / total < 0.9:
            notes.append(
                f"Only {good}/{total} queries passed their work-normalized budget "
                f"({good / total:.1%}); investigate the violating query classes."
            )

        return QueryBudgetResult(
            config=config,
            total=total,
            good=good,
            sli_passed_fraction=round(good / total, 4) if total > 0 else None,
            violations=violations,
            notes=notes,
        )

    def budget_for(self, config: QueryBudgetConfig, units: float) -> float:
        """The allowed latency budget (ms) for a given complexity."""
        cost_fn = nlogn_cost if config.model == "nlogn" else linear_cost
        budget = DynamicLatencyBudget(
            base_ms=config.base_ms, cost_per_unit_ms=config.cost_per_unit_ms, cost_function=cost_fn
        )
        return budget.budget_for(units)

    def calibrate(
        self,
        durations_ms: Sequence[float],
        units: Sequence[float],
        max_pairs: int = 20_000,
    ) -> QueryBudgetConfig:
        """
        Calibrate `base_ms`/`cost_per_unit_ms` from a healthy baseline
        window via a robust (Theil-Sen) slope estimate, targeting p75 of
        duration-vs-units for the intercept (a quantile-regression proxy
        so the budget generously covers the baseline rather than bisecting
        it).

        Fits `duration ~= base + cost * units`:
          1. cost = median of pairwise slopes (duration_j - duration_i) /
             (units_j - units_i) over all i < j with units_j != units_i
             (Theil-Sen: robust to noise/outliers).
          2. base = p75(duration_i - cost * units_i)

        Args:
            durations_ms: Observed durations on a healthy baseline window
            units: Corresponding complexity units
            max_pairs: Cap on the number of pairwise slopes sampled (for
                large inputs, a deterministic stride subsample is used)

        Returns:
            QueryBudgetConfig with fitted base_ms/cost_per_unit_ms (linear model)
        """
        if len(durations_ms) != len(units) or not durations_ms:
            raise ValueError("durations_ms and units must be non-empty and same length")

        n = len(durations_ms)
        pairs = [(units[i], durations_ms[i]) for i in range(n)]

        slopes: List[float] = []
        total_pairs = n * (n - 1) // 2
        stride = max(1, total_pairs // max_pairs) if total_pairs > max_pairs else 1
        seen = 0
        for i in range(n):
            for j in range(i + 1, n):
                seen += 1
                if stride > 1 and seen % stride != 0:
                    continue
                du = pairs[j][0] - pairs[i][0]
                if du == 0:
                    continue
                slopes.append((pairs[j][1] - pairs[i][1]) / du)

        cost = max(0.0, statistics.median(slopes)) if slopes else 0.0

        residuals = sorted(d - cost * u for d, u in zip(durations_ms, units))
        base = max(0.0, self._percentile(residuals, 75))

        return QueryBudgetConfig(base_ms=round(base, 3), cost_per_unit_ms=round(cost, 4))

    @staticmethod
    def _percentile(sorted_values: List[float], pct: float) -> float:
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        if n == 1:
            return float(sorted_values[0])
        rank = (pct / 100) * (n - 1)
        lower = int(rank)
        upper = min(lower + 1, n - 1)
        frac = rank - lower
        return sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower])
