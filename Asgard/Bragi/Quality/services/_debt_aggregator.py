"""
Bragi Debt Aggregator (Plan 02 Phase C)

Replaces `count x constant` linear sums with the DEEPTHINK_05 aggregation law:

    Total_Effort = Cost_Context + sum(Cost_Marginal x d^(i-1))

- One context cost per FILE batch (checkout, mental model, PR ceremony).
- Geometric batching discount d per rule (mechanical debt batches to ~0).
- Exposure multiplier (1 + beta x centrality percentile) on design/
  architectural items - CISQ Exposure Factor. The centrality feed comes from
  Plan 03 Phase B (DependencyGraphService); until it is wired, callers pass
  None and the multiplier stays 1.0. See CentralityProvider.
- Rewrite cap per file: when remediation approaches rewrite-from-scratch
  cost, cap the debt and recommend REWRITE.
- Output is an EffortInterval, never a point estimate.
"""

from typing import Callable, Dict, List, Optional, Tuple

from Asgard.Bragi.Quality.models.debt_models import (
    DebtItem,
    DebtRecommendation,
    DebtType,
    EffortInterval,
)
from Asgard.Bragi.Quality.services._remediation_model import RemediationModel

# Interface stub for Plan 03 Phase B: maps a file/module path to its
# afferent-coupling percentile in [0, 1]. Returns None when unknown.
CentralityProvider = Callable[[str], Optional[float]]

CONTEXT_COST_MINUTES = 30.0

# Green-field development-cost anchor (RESEARCH_01/04).
DEVELOPMENT_MINUTES_PER_LOC = 30.0


def compute_tdr_percent(total_debt_minutes: float, total_loc: int) -> Optional[float]:
    """
    Standard Technical Debt Ratio %: debt minutes / (LOC x 30 min/LOC) x 100.

    This is THE production formula (used by TechnicalDebtAnalyzer); golden
    tests anchor on it directly. Returns None when LOC is unknown.
    """
    if total_loc <= 0:
        return None
    return total_debt_minutes / (total_loc * DEVELOPMENT_MINUTES_PER_LOC) * 100.0
EXPOSURE_BETA = 2.0            # percentile 1.0 -> x3 multiplier (CISQ max)
REWRITE_MINUTES_PER_LOC = 0.5  # configurable fraction of the 30 min/LOC anchor
INTERVAL_LOW_FACTOR = 0.75
INTERVAL_HIGH_BASE = 1.30
INTERVAL_HIGH_COGNITIVE = 0.60  # extra width per unit share of cognitive debt


class AggregatedDebt:
    """Result of batched debt aggregation."""

    def __init__(
        self,
        total_minutes: float,
        per_file_minutes: Dict[str, float],
        recommendations: Dict[str, str],
        effort_interval: EffortInterval,
    ):
        self.total_minutes = total_minutes
        self.per_file_minutes = per_file_minutes
        self.recommendations = recommendations
        self.effort_interval = effort_interval

    @property
    def total_hours(self) -> float:
        """Aggregated debt total in hours."""
        return self.total_minutes / 60.0


class DebtAggregator:
    """Aggregates debt items with batching, context cost, exposure, and rewrite caps."""

    def __init__(
        self,
        remediation_model: Optional[RemediationModel] = None,
        centrality_provider: Optional[CentralityProvider] = None,
    ):
        self.model = remediation_model or RemediationModel()
        # Deferred feed: Plan 03 Phase B's DependencyGraphService supplies
        # afferent-coupling percentiles. None -> exposure multiplier 1.0.
        self.centrality_provider = centrality_provider

    def aggregate(
        self,
        items: List[DebtItem],
        file_loc: Optional[Dict[str, int]] = None,
    ) -> AggregatedDebt:
        """
        Aggregate debt items into a batched, pessimism-corrected total.

        Args:
            items: All detected debt items.
            file_loc: Optional LOC per file for the rewrite cap.

        Returns:
            AggregatedDebt with per-file totals, recommendations, and interval.
        """
        groups: Dict[Tuple[str, str], List[DebtItem]] = {}
        for item in items:
            debt_type = item.debt_type if isinstance(item.debt_type, str) else item.debt_type.value
            groups.setdefault((item.file_path, debt_type), []).append(item)

        per_file: Dict[str, float] = {}
        cognitive_minutes = 0.0
        for (file_path, debt_type), group in sorted(groups.items()):
            function = self.model.function_for(group[0])
            d = function.batchability
            floor = function.discount_floor
            # Deterministic order: costliest first, so the geometric discount
            # applies to the cheaper repetitions. The per-type floor keeps
            # cognitive debt near-additive: concentrating 100 smells in one
            # file can never cost less than 25% of the additive sum.
            minutes = sorted((self.model.minutes_for(i) for i in group), reverse=True)
            batched = sum(m * max(d ** idx, floor) for idx, m in enumerate(minutes))

            if debt_type == DebtType.DESIGN.value:
                batched *= self._exposure_multiplier(file_path)
            if d >= 0.5:
                cognitive_minutes += batched
            per_file[file_path] = per_file.get(file_path, 0.0) + batched

        recommendations: Dict[str, str] = {}
        total = 0.0
        for file_path, minutes in per_file.items():
            minutes += CONTEXT_COST_MINUTES  # one context cost per file batch
            loc = (file_loc or {}).get(file_path, 0)
            # Rewrite cap: LOC x 0.5 min (configurable fraction of the
            # 30 min/LOC green-field anchor, per Plan 02 section 3.2).
            rewrite_minutes = loc * REWRITE_MINUTES_PER_LOC
            # Guard: for very small files the context cost alone would
            # exceed the rewrite estimate; only recommend REWRITE when the
            # rewrite estimate is at least one context cost.
            if loc > 0 and rewrite_minutes >= CONTEXT_COST_MINUTES and minutes > rewrite_minutes:
                minutes = rewrite_minutes
                recommendations[file_path] = DebtRecommendation.REWRITE.value
            else:
                recommendations[file_path] = DebtRecommendation.FIX.value
            per_file[file_path] = minutes
            total += minutes

        interval = self._build_interval(total, cognitive_minutes)
        return AggregatedDebt(
            total_minutes=total,
            per_file_minutes=per_file,
            recommendations=recommendations,
            effort_interval=interval,
        )

    def _exposure_multiplier(self, file_path: str) -> float:
        """CISQ Exposure Factor: 1 + beta x afferent-coupling percentile."""
        if self.centrality_provider is None:
            return 1.0
        percentile = self.centrality_provider(file_path)
        if percentile is None:
            return 1.0
        return 1.0 + EXPOSURE_BETA * min(max(percentile, 0.0), 1.0)

    @staticmethod
    def _build_interval(total_minutes: float, cognitive_minutes: float) -> EffortInterval:
        """Interval width driven by the cognitive share of the debt."""
        if total_minutes <= 0:
            return EffortInterval(
                low_minutes=0.0, high_minutes=0.0, confidence="high",
                width_reason="no debt detected",
            )
        cognitive_share = min(cognitive_minutes / total_minutes, 1.0)
        high_factor = INTERVAL_HIGH_BASE + INTERVAL_HIGH_COGNITIVE * cognitive_share
        confidence = "high" if cognitive_share < 0.2 else ("medium" if cognitive_share < 0.6 else "low")
        return EffortInterval(
            low_minutes=total_minutes * INTERVAL_LOW_FACTOR,
            high_minutes=total_minutes * high_factor,
            confidence=confidence,
            width_reason=(
                f"{cognitive_share:.0%} of debt is cognitive (low batchability); "
                "no per-file test-coverage signal supplied"
            ),
        )
