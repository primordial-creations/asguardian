"""
Composite Score Models (plan 07 — DEEPTHINK_05 / DEEPTHINK_01).

A ``ScoreReport`` is computed ONLY from Validation-engine findings on
rendered output — generators never grade their own intent. It carries:

- four dimension sub-scores (Security is a veto dimension),
- per-logical-resource defect-density scores,
- letter grades (CodeClimate model) + remediation hints,
- suppressed-finding receipts (suppressions score as passed but stay
  visible as posture debt),
- the environment weight profile used.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ScoreDimension(str, Enum):
    """The four composite-score dimensions (DEEPTHINK_05 §3)."""

    SECURITY = "security"
    OPERABILITY = "operability"
    COMPLETENESS = "completeness"
    MAINTAINABILITY = "maintainability"


def letter_grade(score: float) -> str:
    """CodeClimate-style letter grade: A>=90, B>=80, C>=65, D>=50, F<50."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


class DimensionScore(BaseModel):
    """Sub-score for a single dimension."""

    dimension: ScoreDimension
    score: float = Field(ge=0, le=100)
    grade: str = Field(description="Letter grade A-F")
    weight: float = Field(ge=0, description="Weight in the composite (profile-driven)")
    finding_count: int = Field(default=0)


class ResourceScore(BaseModel):
    """Defect-density score for one logical resource (DEEPTHINK_05 §1B)."""

    resource: str
    score: float = Field(ge=0, le=100)
    finding_count: int = Field(default=0)
    aggregate_weight: float = Field(
        default=1.0,
        description=(
            "Weight of this resource in the artifact mean. Clean "
            "(zero-finding) resources get near-zero weight so score "
            "dilution by trivially-passing resources is ineffective "
            "(DEEPTHINK_01 §1B)."
        ),
    )


class RemediationHint(BaseModel):
    """Actionable remediation with a rough effort estimate."""

    rule_id: str
    message: str
    remediation: str = Field(default="")
    severity: str = Field(default="medium")
    effort: str = Field(default="1 edit", description="Rough effort estimate")


class SuppressedReceipt(BaseModel):
    """A suppressed finding, kept visible as accepted posture debt."""

    rule_id: str
    target: str
    reason: str


class ScoreReport(BaseModel):
    """Full composite score report for one rendered artifact."""

    composite: float = Field(ge=0, le=100)
    grade: str = Field(description="Composite letter grade")
    environment: str = Field(default="production")
    dimensions: List[DimensionScore] = Field(default_factory=list)
    resource_scores: List[ResourceScore] = Field(default_factory=list)
    resource_density_score: float = Field(
        default=100.0, ge=0, le=100,
        description="Weighted mean of per-resource defect-density scores",
    )
    veto_applied: Optional[str] = Field(
        default=None,
        description=(
            "Set when the security veto capped the composite "
            "('critical' cap 50, 'high' cap 70) — DEEPTHINK_05 §3"
        ),
    )
    remediation: List[RemediationHint] = Field(default_factory=list)
    suppressed_count: int = Field(default=0)
    suppressed_receipts: List[SuppressedReceipt] = Field(default_factory=list)
    total_findings: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now)

    def dimension(self, dim: ScoreDimension) -> Optional[DimensionScore]:
        for d in self.dimensions:
            if d.dimension == dim:
                return d
        return None

    def delta(self, baseline: "ScoreReport") -> Dict[str, float]:
        """Delta mode (plan 07 §2.2): per-dimension change vs a baseline."""
        deltas: Dict[str, float] = {
            "composite": round(self.composite - baseline.composite, 2)
        }
        for d in self.dimensions:
            base = baseline.dimension(d.dimension)
            if base is not None:
                deltas[d.dimension.value] = round(d.score - base.score, 2)
        return deltas


class PostureIndex(BaseModel):
    """Portfolio-level Graph-Weighted Posture Index (DEEPTHINK_01)."""

    posture: float = Field(ge=0, le=100, description="100 * (1 - rho)")
    system_risk: float = Field(ge=0, le=1, description="L3-norm system risk rho")
    resource_risks: Dict[str, float] = Field(default_factory=dict)
    resource_weights: Dict[str, float] = Field(default_factory=dict)
    epistemic_floor: float = Field(
        default=0.4,
        description=(
            "Minimum residual risk when only Volundr static rules ran; "
            "external tools buy down uncertainty (DEEPTHINK_01 §1C)"
        ),
    )
    assumptions: List[str] = Field(
        default_factory=lambda: [
            "ClickOps divergence: live state may differ from analyzed artifacts",
            "Cross-domain linkage: graph edges only cover declared references",
            "Independence fallacy: finding probabilities are treated as independent",
        ],
        description="Invalidating assumptions (DEEPTHINK_01 §3) — read before trusting",
    )
