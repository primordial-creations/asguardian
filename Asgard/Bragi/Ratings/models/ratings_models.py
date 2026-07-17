"""
Heimdall Ratings Models

Pydantic models for the A-E letter ratings system.

Ratings are calculated across three quality dimensions:

Maintainability (based on technical debt ratio):
  A: <= 5%   B: <= 10%   C: <= 20%   D: <= 50%   E: > 50%

Reliability (based on worst severity bug found):
  A: No bugs   B: LOW only   C: MEDIUM   D: HIGH   E: CRITICAL

Security (based on worst severity vulnerability):
  A: No vulnerabilities   B: LOW   C: MEDIUM   D: HIGH   E: CRITICAL
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Bragi.Ratings.models._scoring_models import (
    FileQualityScore,
    MeasurementConfidence,
    RiskProfile,
    ROIAction,
    ScoreConfidence,
)


class LetterRating(str, Enum):
    """A-E letter rating."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class RatingDimension(str, Enum):
    """Quality dimension being rated."""
    MAINTAINABILITY = "maintainability"
    RELIABILITY = "reliability"
    SECURITY = "security"


class DimensionRating(BaseModel):
    """Rating result for a single quality dimension."""
    dimension: RatingDimension = Field(..., description="The quality dimension being rated")
    rating: LetterRating = Field(..., description="The A-E letter rating")
    score: float = Field(0.0, description="Numeric score used to derive the rating")
    rationale: str = Field("", description="Explanation of how the rating was determined")
    issues_count: int = Field(0, description="Number of issues contributing to this rating")
    confidence: MeasurementConfidence = Field(
        MeasurementConfidence.MEASURED,
        description=(
            "Whether the underlying report was actually supplied. NOT_MEASURED "
            "means the letter is a default, not evidence of quality."
        ),
    )

    class Config:
        use_enum_values = True


class DebtThresholds(BaseModel):
    """Thresholds for maintainability rating based on technical debt ratio."""
    a_max: float = Field(5.0, description="Maximum debt ratio (%) for rating A")
    b_max: float = Field(10.0, description="Maximum debt ratio (%) for rating B")
    c_max: float = Field(20.0, description="Maximum debt ratio (%) for rating C")
    d_max: float = Field(50.0, description="Maximum debt ratio (%) for rating D")
    # Above d_max is rating E


class ProjectRatings(BaseModel):
    """Complete A-E rating results for a project."""
    maintainability: DimensionRating = Field(
        ...,
        description="Maintainability rating based on technical debt ratio"
    )
    reliability: DimensionRating = Field(
        ...,
        description="Reliability rating based on worst severity bug found"
    )
    security: DimensionRating = Field(
        ...,
        description="Security rating based on worst severity vulnerability"
    )
    overall_rating: LetterRating = Field(
        ...,
        description="Overall project rating (worst of the three dimensions)"
    )
    scan_path: str = Field("", description="Root path that was rated")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When rating was calculated")

    # Composite scoring engine outputs (Plan 01). Optional for backward compat.
    composite_score: Optional[float] = Field(
        None, description="Hierarchical gated geometric composite score in [0, 1]; None when nothing was measured"
    )
    composite_grade: Optional[str] = Field(
        None, description="Project grade from the risk-profile footprint (not a mean of file scores)"
    )
    risk_profile: Optional[RiskProfile] = Field(
        None, description="Distribution of LOC across file grade bands (SIG risk profile)"
    )
    file_scores: List[FileQualityScore] = Field(
        default_factory=list, description="Per-file composite scores"
    )
    confidence: Optional[ScoreConfidence] = Field(
        None, description="Which report sources were present when scoring"
    )
    roi_actions: List[ROIAction] = Field(
        default_factory=list, description="Ranked marginal-ROI improvement actions"
    )

    class Config:
        use_enum_values = True


class RatingsConfig(BaseModel):
    """Configuration for the ratings calculator."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to rate")
    debt_thresholds: DebtThresholds = Field(
        default_factory=DebtThresholds,  # type: ignore[arg-type]
        description="Thresholds used for maintainability rating"
    )
    enable_maintainability: bool = Field(True, description="Enable maintainability rating")
    enable_reliability: bool = Field(True, description="Enable reliability rating")
    enable_security: bool = Field(True, description="Enable security rating")

    class Config:
        use_enum_values = True
