"""
Completeness Models - 4-vector completeness matrix and gated maturity
tiers (plan 03, DEEPTHINK_08 / RESEARCH_09).

Completeness is a capability vector, never a single composite number.
Tiers are lowest-common-denominator gates: one failed gate demotes the
whole document.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MaturityTier(str, Enum):
    """Gated maturity tiers (DEEPTHINK_08 §3)."""

    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"

    @property
    def rank(self) -> int:
        """Numeric rank, higher = more mature."""
        return {"none": 0, "basic": 1, "standard": 2, "comprehensive": 3}[self.value]


class CompletenessVector(BaseModel):
    """The four completeness vectors, each 0.0-1.0."""

    experiential: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Non-trivial descriptions on operations/params/leaf "
                    "properties; schemas with valid examples",
    )
    precision: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Strings with format/pattern/length; numbers with bounds; "
                    "arrays with maxItems; objects with explicit "
                    "additionalProperties",
    )
    operational: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="4xx/5xx coverage, unified error schema, auth documented, "
                    "pagination on list operations",
    )
    structural: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Parse success, zero broken refs, required OAS fields",
    )


class GateResult(BaseModel):
    """One tier-gate evaluation (explainability payload)."""

    tier: MaturityTier = Field(description="Tier this gate belongs to")
    name: str = Field(description="Gate name, e.g. 'experiential > 60%'")
    passed: bool = Field(default=False)
    detail: str = Field(default="", description="Measured value vs threshold")


class CompletenessSignals(BaseModel):
    """Raw boolean/ratio signals feeding the vectors and gates."""

    operation_count: int = 0
    described_units: int = 0
    total_units: int = 0
    schemas_with_examples: int = 0
    schemas_with_valid_examples: int = 0
    total_component_schemas: int = 0
    all_examples_valid: bool = True
    error_coverage: float = Field(default=0.0, description="Ops with >=1 4xx and >=1 5xx")
    unified_error_schema: bool = False
    auth_documented: bool = False
    pagination_coverage: float = Field(
        default=1.0, description="List-like GET ops with pagination params",
    )
    rate_limits_documented: bool = False
    broken_refs: int = 0
    structural_errors: int = 0


class CompletenessReport(BaseModel):
    """Result of a completeness assessment."""

    spec_path: Optional[str] = Field(default=None)
    profile: str = Field(default="dx", description="'dx' | 'secops'")
    vector: CompletenessVector = Field(default_factory=CompletenessVector)
    tier: MaturityTier = Field(default=MaturityTier.NONE)
    gates: list[GateResult] = Field(default_factory=list)
    signals: CompletenessSignals = Field(default_factory=CompletenessSignals)
    missing_for_next_tier: list[str] = Field(
        default_factory=list,
        description="Failed gates of the next tier up (actionable path)",
    )
