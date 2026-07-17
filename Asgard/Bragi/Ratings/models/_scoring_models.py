"""
Bragi Composite Scoring Models

Pydantic models backing the hierarchical gated geometric scoring engine
(Plan 01 - Composite Scoring Engine):

- Utility mapping (u in [0, 1] per metric)
- Weighted Arithmetic Mean within categories
- Weighted Geometric Mean across categories
- Non-compensatory caps (blocker issues, extreme complexity, licenses)
- Tri-state measurement confidence (never reward a missing input)
- SIG-style risk-profile project aggregation
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MeasurementConfidence(str, Enum):
    """Tri-state confidence for whether an input was actually measured."""
    MEASURED = "measured"
    PARTIAL = "partial"
    NOT_MEASURED = "not_measured"


class ScoreCategory(str, Enum):
    """Top-level scoring categories (pillars of the composite score)."""
    RELIABILITY = "reliability"
    MAINTAINABILITY = "maintainability"
    COMPREHENSIBILITY = "comprehensibility"


class MetricUtility(BaseModel):
    """A single raw metric mapped onto a utility u in [0, 1]."""
    metric_id: str = Field(..., description="Stable metric identifier, e.g. 'bug_density'")
    category: ScoreCategory = Field(..., description="Category this metric belongs to")
    utility: float = Field(..., ge=0.0, le=1.0, description="Mapped utility value")
    weight: float = Field(1.0, ge=0.0, description="Intra-category weight")
    confidence: MeasurementConfidence = Field(
        MeasurementConfidence.MEASURED, description="Whether the underlying input was measured"
    )
    detail: str = Field("", description="Human-readable derivation note")

    class Config:
        use_enum_values = True


class CategoryScore(BaseModel):
    """Weighted-arithmetic-mean score for one category."""
    category: ScoreCategory = Field(..., description="Category scored")
    score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="WAM of member utilities; None when the category was not measured"
    )
    weight: float = Field(..., ge=0.0, description="Inter-category weight (pre-renormalization)")
    confidence: MeasurementConfidence = Field(
        MeasurementConfidence.MEASURED, description="Category-level measurement confidence"
    )
    utilities: List[MetricUtility] = Field(default_factory=list, description="Member metric utilities")

    class Config:
        use_enum_values = True


class ScoreCap(BaseModel):
    """A non-compensatory gate applied to the base score."""
    applied: bool = Field(False, description="Whether any cap was triggered")
    ceiling: float = Field(1.0, ge=0.0, le=1.0, description="Maximum final score allowed")
    reason: str = Field("", description="Why the cap was applied")


class ScoreConfidence(BaseModel):
    """Which inputs were present when the score was computed."""
    overall: MeasurementConfidence = Field(
        MeasurementConfidence.MEASURED, description="Aggregate confidence"
    )
    by_category: Dict[str, MeasurementConfidence] = Field(
        default_factory=dict, description="Confidence per category"
    )
    measured_sources: List[str] = Field(default_factory=list, description="Report sources supplied")
    missing_sources: List[str] = Field(default_factory=list, description="Report sources absent")
    notes: List[str] = Field(
        default_factory=list,
        description="Honest annotations, e.g. 'Security: not assessed (no scan supplied)'"
    )

    class Config:
        use_enum_values = True


class ROIAction(BaseModel):
    """One ranked improvement action from the marginal-ROI calculator."""
    metric_id: str = Field(..., description="Metric whose improvement drives the gain")
    description: str = Field(..., description="Human-readable action")
    score_delta: float = Field(..., description="Estimated final-score gain from a standard step")
    lifts_cap: bool = Field(False, description="Whether the action removes a non-compensatory cap")


class FileQualityScore(BaseModel):
    """Composite score for a single file."""
    file_path: str = Field(..., description="File scored")
    loc: int = Field(0, ge=0, description="Lines of code in the file (0 when unknown)")
    utilities: Dict[str, float] = Field(default_factory=dict, description="Utility per metric id")
    category_scores: List[CategoryScore] = Field(default_factory=list, description="Per-category WAM scores")
    base_score: float = Field(0.0, ge=0.0, le=1.0, description="WGM across measured categories")
    cap: ScoreCap = Field(default_factory=ScoreCap, description="Non-compensatory cap applied")
    final_score: float = Field(0.0, ge=0.0, le=1.0, description="min(base_score, cap.ceiling)")
    grade: str = Field("E", description="Letter grade derived from final_score")
    confidence: ScoreConfidence = Field(default_factory=ScoreConfidence, description="Input coverage")
    roi_actions: List[ROIAction] = Field(default_factory=list, description="Ranked improvement actions")
    rationale: str = Field("", description="Explanation, incl. cap narrative when applied")


class RiskProfile(BaseModel):
    """SIG-style risk-profile footprint: distribution of LOC across grade bands.

    The footprint spans the WHOLE measured codebase: LOC in files without
    findings counts in the A band, so one tiny E file cannot sink a large
    clean project, and spreading issues across files cannot hide them
    (project density is reconciled separately).
    """
    total_loc: int = Field(0, ge=0, description="Total LOC across the measured codebase")
    loc_by_grade: Dict[str, int] = Field(default_factory=dict, description="LOC per letter grade")
    pct_by_grade: Dict[str, float] = Field(default_factory=dict, description="% of LOC per letter grade")
    estimated: bool = Field(
        False,
        description="True when per-file LOC was unavailable and a conservative proxy was used (PARTIAL confidence)"
    )

    @property
    def pct_in(self) -> Dict[str, float]:
        """Alias for pct_by_grade."""
        return self.pct_by_grade


class FileMetricBundle(BaseModel):
    """
    Typed per-file metric inputs for the composite engine.

    Optional fields set to None mean NOT MEASURED (excluded with weight
    renormalization) - never silently treated as perfect.
    """
    file_path: str = Field("", description="File path ('' for project-level bundles)")
    loc: int = Field(0, ge=0, description="Lines of code (0 when unknown)")

    # Reliability inputs
    bug_counts_by_severity: Optional[Dict[str, int]] = Field(
        None, description="Bug/smell counts keyed by severity (blocker/critical/high/medium/low/info)"
    )
    # Maintainability inputs
    debt_ratio_percent: Optional[float] = Field(None, description="Technical debt ratio % (TDR)")
    max_cognitive_complexity: Optional[float] = Field(None, description="Max cognitive/cyclomatic complexity")
    mean_cognitive_complexity: Optional[float] = Field(None, description="Mean complexity")
    duplication_percent: Optional[float] = Field(None, description="Duplicated-code percentage")
    cycle_count: Optional[int] = Field(None, description="Dependency cycles touching this scope")
    # Comprehensibility inputs
    doc_coverage_percent: Optional[float] = Field(None, description="Documentation coverage %")
    type_coverage_percent: Optional[float] = Field(None, description="Type-annotation coverage %")

    # Gate inputs
    has_blocker_issue: bool = Field(False, description="Any blocker/critical bug or vulnerability present")
    blocker_description: str = Field("", description="Description of the blocking issue")
    prohibited_license_count: int = Field(0, ge=0, description="Prohibited licenses in dependencies")

    # Provenance
    sources_present: List[str] = Field(default_factory=list, description="Report sources that fed this bundle")
    sources_missing: List[str] = Field(default_factory=list, description="Report sources not supplied")

    # Context (Plan 04 Phase A/B): resolved via Bragi.common.context_classifier.
    # "production" (default) | "test" | "generated" | "suspected_generated" | "script".
    context: str = Field("production", description="Code context this bundle was scored under")
