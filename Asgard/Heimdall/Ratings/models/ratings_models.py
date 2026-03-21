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
