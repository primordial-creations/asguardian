"""
Error Budget Policy Engine

Maps remaining error-budget percentage to a policy tier (RESEARCH_13):

    NORMAL    remaining > 50%   -- ship freely
    CAUTION   25% <= remaining <= 50% -- extra review, slow down risky changes
    FREEZE    0% < remaining < 25% -- feature freeze, reliability work only
    EXHAUSTED remaining <= 0%  -- hard halt, mandatory post-mortem

Also flags any single contiguous incident that consumed >= 20% of the total
error budget (post-mortem trigger regardless of overall remaining budget),
and reports the meta-SLO buffer between an internal SLO and its external
SLA target.
"""

from enum import Enum
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field

from Asgard.Verdandi.SLO.models.slo_models import ErrorBudget, SLODefinition


class BudgetPolicyTier(str, Enum):
    """Error budget policy tier (RESEARCH_13)."""

    NORMAL = "normal"
    CAUTION = "caution"
    FREEZE = "freeze"
    EXHAUSTED = "exhausted"


#: (remaining_budget_pct lower-bound exclusive, tier, action) in descending order.
_TIER_TABLE = (
    (50.0, BudgetPolicyTier.NORMAL, "Ship freely; normal release cadence."),
    (25.0, BudgetPolicyTier.CAUTION, "Extra review on risky changes; watch burn rate."),
    (0.0, BudgetPolicyTier.FREEZE, "Feature freeze; reliability work only."),
)


class IncidentBudgetImpact(BaseModel):
    """A single contiguous incident's share of the total error budget."""

    started_at: Optional[str] = Field(default=None, description="Incident start (ISO or label)")
    ended_at: Optional[str] = Field(default=None, description="Incident end (ISO or label)")
    bad_events: int = Field(..., description="Bad events attributed to this incident")
    budget_consumed_pct: float = Field(
        ..., description="Percent of the TOTAL allowed-failures budget this incident consumed"
    )
    post_mortem_required: bool = Field(
        default=False, description="True when this single incident consumed >= 20% of budget"
    )


class BudgetPolicyState(BaseModel):
    """Result of evaluating the error budget policy for an SLO."""

    slo_name: str = Field(..., description="Name of the associated SLO")
    remaining_budget_pct: float = Field(..., description="Remaining budget as a percentage")
    tier: BudgetPolicyTier = Field(..., description="Policy tier")
    action: str = Field(..., description="Recommended action for this tier")
    post_mortem_required: bool = Field(
        default=False,
        description="True if overall EXHAUSTED or any single incident consumed >= 20%",
    )
    incidents: List[IncidentBudgetImpact] = Field(
        default_factory=list, description="Incidents flagged for the 20% single-incident rule"
    )
    meta_slo_buffer_minutes: Optional[float] = Field(
        default=None,
        description=(
            "Allowed-downtime minutes of headroom between the internal SLO "
            "target and SLODefinition.external_sla_target over the SLO "
            "window; None when no external_sla_target is set"
        ),
    )
    meta_slo_buffer_valid: Optional[bool] = Field(
        default=None,
        description="True when the internal target is strictly tighter than the external SLA",
    )
    recommendations: List[str] = Field(default_factory=list)


#: Fraction of the TOTAL error budget a single incident must consume to
#: mandate a post-mortem, independent of overall remaining budget.
SINGLE_INCIDENT_POST_MORTEM_THRESHOLD_PCT = 20.0


class BudgetPolicyEngine:
    """
    Evaluates error-budget policy tiers, the 20%-single-incident post-mortem
    flag, and the meta-SLO buffer between internal and external SLA targets.
    """

    def evaluate(
        self,
        budget: ErrorBudget,
        incidents: Optional[Sequence[IncidentBudgetImpact]] = None,
        slo: Optional[SLODefinition] = None,
    ) -> BudgetPolicyState:
        """
        Evaluate the policy tier for a computed ErrorBudget.

        Args:
            budget: ErrorBudget result from ErrorBudgetCalculator
            incidents: Optional pre-computed per-incident budget impacts;
                each flagged post_mortem_required if it alone consumed
                >= 20% of the total budget
            slo: Optional SLODefinition; when it carries
                external_sla_target, the meta-SLO buffer is reported

        Returns:
            BudgetPolicyState
        """
        remaining_pct = budget.budget_remaining_percent
        tier, action = self._tier_for_remaining(remaining_pct)

        flagged_incidents: List[IncidentBudgetImpact] = []
        any_incident_flag = False
        for incident in incidents or []:
            flagged = incident.budget_consumed_pct >= SINGLE_INCIDENT_POST_MORTEM_THRESHOLD_PCT
            impact = incident.model_copy(update={"post_mortem_required": flagged})
            flagged_incidents.append(impact)
            any_incident_flag = any_incident_flag or flagged

        post_mortem_required = tier == BudgetPolicyTier.EXHAUSTED or any_incident_flag

        recommendations = [action]
        if any_incident_flag:
            recommendations.append(
                "One or more incidents each consumed >= "
                f"{SINGLE_INCIDENT_POST_MORTEM_THRESHOLD_PCT:g}% of the total error "
                "budget; a post-mortem is required regardless of overall remaining budget."
            )

        buffer_minutes: Optional[float] = None
        buffer_valid: Optional[bool] = None
        if slo is not None and slo.external_sla_target is not None:
            buffer_minutes, buffer_valid = self.meta_slo_buffer(slo)
            if not buffer_valid:
                recommendations.append(
                    "WARNING: internal SLO target is not strictly tighter than "
                    "external_sla_target; the meta-SLO buffer is zero or negative "
                    "and budget will exhaust externally before it does internally."
                )

        return BudgetPolicyState(
            slo_name=budget.slo_name,
            remaining_budget_pct=remaining_pct,
            tier=tier,
            action=action,
            post_mortem_required=post_mortem_required,
            incidents=flagged_incidents,
            meta_slo_buffer_minutes=buffer_minutes,
            meta_slo_buffer_valid=buffer_valid,
            recommendations=recommendations,
        )

    @staticmethod
    def _tier_for_remaining(remaining_pct: float) -> "tuple[BudgetPolicyTier, str]":
        if remaining_pct <= 0.0:
            return (
                BudgetPolicyTier.EXHAUSTED,
                "Hard halt: error budget exhausted. Mandatory post-mortem before any "
                "further risky changes.",
            )
        for lower_bound, tier, action in _TIER_TABLE:
            if remaining_pct > lower_bound:
                return tier, action
        # Unreachable given the 0.0 guard above, but keep a safe fallback.
        return BudgetPolicyTier.FREEZE, "Feature freeze; reliability work only."

    @staticmethod
    def meta_slo_buffer(slo: SLODefinition) -> "tuple[Optional[float], Optional[bool]]":
        """
        Compute the meta-SLO buffer: allowed-downtime headroom (minutes)
        between the internal SLO target and the external SLA target over
        the SLO window (RESEARCH_13 -- internal targets must be strictly
        tighter than external commitments).

        Returns:
            (buffer_minutes, is_valid) or (None, None) if no external
            target is configured
        """
        if slo.external_sla_target is None:
            return None, None

        window_minutes = slo.window_days * 24 * 60
        internal_allowed = (100.0 - slo.target) / 100.0 * window_minutes
        external_allowed = (100.0 - slo.external_sla_target) / 100.0 * window_minutes
        buffer_minutes = external_allowed - internal_allowed
        is_valid = slo.target > slo.external_sla_target and buffer_minutes > 0
        return buffer_minutes, is_valid

    @staticmethod
    def incident_budget_impact(
        bad_events: int,
        total_allowed_failures: float,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
    ) -> IncidentBudgetImpact:
        """
        Build an IncidentBudgetImpact from raw counts.

        budget_consumed_pct is this incident's bad_events as a percentage of
        the TOTAL allowed-failures budget for the SLO window (not of the
        remaining budget), matching the "single incident consumes >= 20% of
        budget" rule.
        """
        consumed_pct = (
            (bad_events / total_allowed_failures) * 100.0 if total_allowed_failures > 0 else 0.0
        )
        return IncidentBudgetImpact(
            started_at=started_at,
            ended_at=ended_at,
            bad_events=bad_events,
            budget_consumed_pct=round(consumed_pct, 4),
            post_mortem_required=consumed_pct >= SINGLE_INCIDENT_POST_MORTEM_THRESHOLD_PCT,
        )
