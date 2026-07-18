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
    NOISY = "noisy"
    UNKNOWN = "unknown"
    INSUFFICIENT_DATA = "insufficient_data"


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
    stage2: Optional["Stage2ValidityReport"] = Field(
        None, description="Full-SZZ statistical validity report, when available (Plan 05 Phase D)"
    )

    class Config:
        use_enum_values = True


class BugFixCommit(BaseModel):
    """A commit identified by message heuristics as a bug fix (SZZ input)."""
    sha: str
    parent_sha: str
    timestamp: int = Field(..., description="Commit time, unix epoch seconds")
    subject: str


class SZZStatus(str, Enum):
    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"


class SZZResult(BaseModel):
    """
    Output of the SZZ bug-inducing-commit trace (Plan 05 Sec.3.3 Stage 2).

    `induced_commit_counts` maps a file path (as it existed at the time a
    fix touched it) to the number of *distinct* commits that SZZ traced as
    having introduced lines subsequently removed/modified by a bug-fix -
    the per-file defect-inducement count consumed as the outcome variable
    by the Stage 2 count model.
    """
    status: SZZStatus = Field(SZZStatus.INSUFFICIENT_DATA)
    fix_commit_count: int = Field(0, ge=0)
    min_fix_commits: int = Field(0, ge=0)
    induced_commit_counts: Dict[str, int] = Field(default_factory=dict)
    note: str = Field("")

    class Config:
        use_enum_values = True


class NBModelFit(BaseModel):
    """
    Fitted Negative-Binomial count-regression model (Plan 05 Sec.3.3 Stage 2).

    Log-link GLM `mu = exp(X @ beta)` fit via IRLS; `alpha` is the
    method-of-moments overdispersion parameter (alpha == 0 degenerates to a
    quasi-Poisson fit - documented simplification in lieu of a full NB MLE,
    which is out of scope for pure-stdlib arithmetic).
    """
    feature_names: List[str] = Field(default_factory=list, description="Order matches `coefficients` after intercept")
    coefficients: Dict[str, float] = Field(default_factory=dict, description="'intercept' + one entry per feature")
    alpha: float = Field(0.0, ge=0.0, description="Method-of-moments overdispersion parameter")
    converged: bool = Field(False)
    n: int = Field(0, ge=0)
    iterations: int = Field(0, ge=0)


class FeatureAttribution(BaseModel):
    """
    SHAP-lite (exact, for an additive log-link linear predictor) per-feature
    contribution to one observation's predicted defect count, on the link
    (log-eta) scale: `beta_j * (x_j - baseline_j)`. Because the linear
    predictor is additive across features by construction, this equals the
    exact Shapley value for each feature - no coalition sampling is needed
    (see module docstring in `nb_model.py`).
    """
    rule_id: str
    mean_abs_rule_attribution: float = Field(0.0, description="Mean |attribution| of the rule-firing feature")
    mean_abs_control_attribution: float = Field(
        0.0, description="Mean |attribution| summed over LOC+churn control features"
    )
    per_feature_mean_attribution: Dict[str, float] = Field(default_factory=dict)


class Stage2ValidityReport(BaseModel):
    """Full-SZZ, NB-regression validity report for one rule (Plan 05 Stage 2)."""
    rule_id: str
    verdict: ValidityVerdict = Field(ValidityVerdict.INSUFFICIENT_DATA)
    n: int = Field(0, ge=0, description="Observations (files) used to fit the model")
    fix_commit_count: int = Field(0, ge=0)
    rate_ratio: Optional[float] = Field(
        None, description="exp(beta_rule): multiplicative effect of one more rule-firing on expected defect count, controlling for LOC+churn"
    )
    attribution: Optional[FeatureAttribution] = None
    small_sample_warning: bool = Field(
        False, description="True when n is technically above the gate but still low enough that the fit is underpowered"
    )
    note: str = Field("")

    class Config:
        use_enum_values = True


ValidityReport.model_rebuild()


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
