"""
Calibration Models (Plan 05 Phase A).

Pydantic models backing the language-profile plane, the local percentile
calibrator, and the (opt-in) rule-validity scorer.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ThresholdSpec(BaseModel):
    """A warn/fail pair for one threshold metric."""
    warn: float = Field(..., description="Value at which the metric starts drawing attention")
    fail: float = Field(..., description="Value at which the metric is a hard violation")


class SeverityConfidence(str, Enum):
    """Confidence-weighted severity for a rule under a given language profile."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LanguageProfile(BaseModel):
    """
    Single source of truth for one language's thresholds (Plan 05 Sec.3.1).

    Loaded from `Bragi/Calibration/profiles/<language>.yaml`; a local
    profile at `.asgard_cache/bragi_local_profile.yaml` (Phase B) can
    override individual thresholds while carrying its own provenance.
    """
    language: str = Field(..., description="Language this profile governs, e.g. 'python'")
    provenance: str = Field(
        "", description="Where the numbers came from and when (time-stamped validity bounds)"
    )
    thresholds: Dict[str, ThresholdSpec] = Field(
        default_factory=dict, description="Metric id -> warn/fail thresholds"
    )
    scalar_thresholds: Dict[str, float] = Field(
        default_factory=dict, description="Metric id -> single threshold (no warn/fail split)"
    )
    severity_confidence: Dict[str, SeverityConfidence] = Field(
        default_factory=dict, description="Rule id -> confidence-weighted severity override"
    )
    category_weights: Optional[Dict[str, float]] = Field(
        None, description="Optional PCA-derived inter-category weights (Plan 05 Sec.3.3)"
    )

    class Config:
        use_enum_values = True


class ValidityVerdict(str, Enum):
    """Rule-validity classification (Plan 05 Sec.3.3)."""
    PREDICTIVE = "predictive"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ValidityReport(BaseModel):
    """Per-rule empirical validity, Stage 1 (friction-based lift)."""
    rule_id: str = Field(..., description="Rule this report covers")
    lift: Optional[float] = Field(
        None, description="Violation-density lift in bugfix-touched files vs not, LOC-decile controlled"
    )
    n: int = Field(0, ge=0, description="Number of bugfix-commit events observed")
    verdict: ValidityVerdict = Field(ValidityVerdict.UNKNOWN, description="Classification")
    burn_in_threshold: int = Field(
        15, description="Minimum events required before a verdict beyond UNKNOWN is issued"
    )
    note: str = Field("", description="Why the verdict was reached")

    class Config:
        use_enum_values = True


class CalibrationRun(BaseModel):
    """Metadata for one local-calibration run (Phase B)."""
    generated_at: datetime = Field(default_factory=datetime.now)
    sample_size: int = Field(0, ge=0, description="Number of functions/files sampled")
    language: str = Field("", description="Language calibrated")
    refused: bool = Field(False, description="True when the sample was below the minimum")
    refusal_reason: str = Field("", description="Why calibration was refused, if it was")
    clamped_metrics: List[str] = Field(
        default_factory=list, description="Metrics whose local threshold hit the +-50% clamp"
    )
