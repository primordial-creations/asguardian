"""
Compat Models - UnifiedChange, ImpactAssessment, CompatReport (plan 01).

The canonical delta model every format adapter projects onto. Scoring
follows DEEPTHINK_04: 100 - sum(base_severity x temporal_penalty x
blast_radius x usage_probability), explained by a Blast Radius Receipt.
"""

from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from Asgard.Forseti.Compatibility.models._compat_base_models import (
    AbstractViolation,
    CompatMode,
    CompatStatus,
    Direction,
    EmpiricalVerdict,
    TierVerdict,
)
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat


class ImpactAssessment(BaseModel):
    """Structural / semantic / empirical tier verdicts for one change."""

    structural: TierVerdict = Field(
        default=TierVerdict.PASS,
        description="Will the parser crash?",
    )
    semantic: TierVerdict = Field(
        default=TierVerdict.PASS,
        description="Will business logic silently corrupt?",
    )
    empirical: Optional[EmpiricalVerdict] = Field(
        default=None,
        description="Telemetry verdict (phase 4); None when no telemetry",
    )


class UnifiedChange(BaseModel):
    """One canonical compatibility change, regardless of source format."""

    rule_id: str = Field(description="Stable rule id, e.g. 'OAS-RES-FIELD-REMOVED'")
    format: SchemaFormat = Field(description="Source schema format")
    direction: Direction = Field(default=Direction.OUTPUT)
    abstract_violation: AbstractViolation = Field(
        default=AbstractViolation.TYPE_CONTRADICTION
    )
    location: str = Field(default="/", description="JSONPath / proto path / channel address")
    message: str = Field(description="Human-readable description")
    old_value: Optional[Any] = Field(default=None)
    new_value: Optional[Any] = Field(default=None)
    impact: ImpactAssessment = Field(default_factory=ImpactAssessment)
    base_severity: int = Field(default=10, ge=0, le=100)
    blast_radius: int = Field(default=1, ge=1, description="Referencing operations count")
    mitigation: Optional[str] = Field(default=None)
    waived: bool = Field(default=False, description="Epoch-waived (governance)")

    @property
    def is_breaking(self) -> bool:
        """Structural FAIL means old clients/parsers break."""
        return self.impact.structural == TierVerdict.FAIL

    @property
    def is_hazard(self) -> bool:
        """Semantic hazard: parses fine but may silently corrupt."""
        return (
            self.impact.structural != TierVerdict.FAIL
            and TierVerdict.HAZARD in (self.impact.structural, self.impact.semantic)
        )


class UsageStats(BaseModel):
    """Usage telemetry for one location (phase 4)."""

    location: str = Field(default="")
    call_count: int = Field(default=0, ge=0)
    window_days: int = Field(default=0, ge=0)

    @property
    def low_confidence(self) -> bool:
        """Telemetry window under 30 days => low confidence (DEEPTHINK_04)."""
        return self.window_days < 30


class TelemetrySource(Protocol):
    """Protocol for usage-telemetry providers."""

    def get_usage(self, location: str) -> Optional[UsageStats]:
        """Return usage stats for a location, or None when unknown."""
        ...


class CompatReport(BaseModel):
    """Result of a unified compatibility check."""

    mode: CompatMode = Field(default=CompatMode.BACKWARD)
    status: CompatStatus = Field(default=CompatStatus.PASSED)
    format: SchemaFormat = Field(default=SchemaFormat.OPENAPI)
    source: Optional[str] = Field(default=None, description="Old version identifier")
    target: Optional[str] = Field(default=None, description="New version identifier")
    score: int = Field(default=100, ge=0, le=100, description="Unified 0-100 score")
    score_receipt: list[str] = Field(
        default_factory=list,
        description="Blast Radius Receipt: one deduction line per change",
    )
    changes: list[UnifiedChange] = Field(default_factory=list)
    structural_breaks: int = Field(default=0)
    semantic_hazards: int = Field(default=0)
    confidence: str = Field(
        default="high",
        description="'high' | 'low' - low when telemetry window < 30 days",
    )
    check_time_ms: float = Field(default=0.0)

    @property
    def is_compatible(self) -> bool:
        """Backward-friendly boolean view of the status."""
        return self.status != CompatStatus.FAILED
