"""
Freya Performance Budget Models

Route archetypes and per-archetype soft/hard budgets (DEEPTHINK_02).
Universal performance thresholds are simultaneously too lenient for
static documents and unrealistic for rich SPAs, so budgets are keyed
by route archetype. Budgets use lab-proxy metrics (TBT, payload
weights, render-blocking counts) rather than field metrics.

All numbers here are Lab Data — synthetic-baseline evidence, strong
for regressions (deltas), weak for real-user experience.
"""

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


#: Mandated header for every performance report surface (DEEPTHINK_03).
LAB_DATA_HEADER = (
    "Lab Data — Synthetic Baseline. These metrics measure code structure "
    "under a controlled environment; they are strong evidence for "
    "regressions (deltas), weak evidence for real-user experience. "
    "Use RUM for field truth."
)


class RouteArchetype(str, Enum):
    """Route archetypes with distinct performance expectations."""
    DOCUMENT = "document"           # static/text-dominant pages
    TRANSACTIONAL = "transactional" # forms, checkout, auth flows
    RICH_APP = "rich_app"           # SPAs / app-like experiences


class BudgetThreshold(BaseModel):
    """A soft (warn) / hard (fail) threshold pair for one metric."""
    metric: str = Field(
        description=(
            'Metric key: "lcp_ms" | "cls" | "tbt_ms" | "js_bytes" | '
            '"image_bytes" | "font_bytes" | "render_blocking_count"'
        )
    )
    soft: Optional[float] = Field(default=None, description="Warn above this value")
    hard: Optional[float] = Field(default=None, description="Fail above this value")


class RouteBudget(BaseModel):
    """Per-archetype budget: thresholds plus formal exemptions."""
    archetype: RouteArchetype = Field(description="Archetype this budget applies to")
    thresholds: List[BudgetThreshold] = Field(default_factory=list)
    exemptions: List[str] = Field(
        default_factory=list,
        description="Metric names formally exempted (business-accepted tradeoffs)"
    )
    exemption_reasons: Dict[str, str] = Field(
        default_factory=dict,
        description="Reason per exempted metric name"
    )


class BudgetEvaluation(BaseModel):
    """Result of evaluating one metric against its budget."""
    metric: str = Field(description="Metric key")
    value: float = Field(description="Measured value (lab data)")
    soft: Optional[float] = Field(default=None, description="Soft (warn) threshold")
    hard: Optional[float] = Field(default=None, description="Hard (fail) threshold")
    status: Literal["pass", "warn", "fail", "exempt"] = Field(description="Evaluation status")
    note: Optional[str] = Field(
        default=None,
        description="Exemption reason or contextual note"
    )


def _payload_thresholds() -> List[BudgetThreshold]:
    """Payload-weight budgets shared by all archetypes (DEEPTHINK_02)."""
    return [
        BudgetThreshold(metric="js_bytes", soft=1_000_000, hard=2_000_000),
        BudgetThreshold(metric="image_bytes", soft=1_500_000, hard=None),
        BudgetThreshold(metric="font_bytes", soft=300_000, hard=None),
        BudgetThreshold(metric="render_blocking_count", soft=3, hard=None),
    ]


#: Default per-archetype budgets (DEEPTHINK_02 Step-1 table).
#: PROVISIONAL pending RESEARCH_02 (CWV 2024-25 / FID->INP transition):
#: only these data tables should change when it lands.
DEFAULT_BUDGETS: Dict[RouteArchetype, RouteBudget] = {
    RouteArchetype.DOCUMENT: RouteBudget(
        archetype=RouteArchetype.DOCUMENT,
        thresholds=[
            BudgetThreshold(metric="lcp_ms", soft=1000, hard=2500),
            BudgetThreshold(metric="cls", soft=0.0, hard=0.1),
            BudgetThreshold(metric="tbt_ms", soft=100, hard=300),
        ] + _payload_thresholds(),
    ),
    RouteArchetype.TRANSACTIONAL: RouteBudget(
        archetype=RouteArchetype.TRANSACTIONAL,
        thresholds=[
            BudgetThreshold(metric="lcp_ms", soft=2500, hard=4000),
            BudgetThreshold(metric="cls", soft=0.05, hard=0.25),
            BudgetThreshold(metric="tbt_ms", soft=150, hard=600),
        ] + _payload_thresholds(),
    ),
    RouteArchetype.RICH_APP: RouteBudget(
        archetype=RouteArchetype.RICH_APP,
        thresholds=[
            BudgetThreshold(metric="lcp_ms", soft=4000, hard=6000),
            BudgetThreshold(metric="cls", soft=0.15, hard=0.25),
            BudgetThreshold(metric="tbt_ms", soft=150, hard=600),
        ] + _payload_thresholds(),
    ),
}


def default_budget_for(archetype: RouteArchetype) -> RouteBudget:
    """Return a copy of the default budget for an archetype."""
    return DEFAULT_BUDGETS[archetype].model_copy(deep=True)
