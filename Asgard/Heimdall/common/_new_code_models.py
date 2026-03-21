"""
Heimdall New Code Period - data models.

Pydantic models and enumerations for the new code period detection system.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class NewCodePeriodType(str, Enum):
    """Defines the reference point for identifying new code."""
    SINCE_LAST_ANALYSIS = "since_last_analysis"
    SINCE_DATE = "since_date"
    SINCE_BRANCH_POINT = "since_branch_point"
    SINCE_VERSION = "since_version"


class NewCodePeriodConfig(BaseModel):
    """
    Configuration for the new code period detection.

    Determines how the detector identifies which files and lines are considered
    new or modified relative to a reference point.
    """
    period_type: NewCodePeriodType = Field(
        NewCodePeriodType.SINCE_LAST_ANALYSIS,
        description="Type of new code period to apply",
    )
    reference_date: Optional[datetime] = Field(
        None,
        description="Reference date for SINCE_DATE period type",
    )
    reference_branch: str = Field(
        "main",
        description="Base branch for SINCE_BRANCH_POINT period type",
    )
    reference_version: Optional[str] = Field(
        None,
        description="Tagged version for SINCE_VERSION period type",
    )
    baseline_path: Optional["Path"] = Field(  # type: ignore[name-defined]
        None,
        description="Path to a stored last-analysis snapshot for SINCE_LAST_ANALYSIS",
    )

    class Config:
        use_enum_values = True


class NewCodePeriodResult(BaseModel):
    """
    Result of new code period detection.

    Contains the list of new and modified files along with summary counts
    and a human-readable description of the reference point used.
    """
    period_type: NewCodePeriodType = Field(
        ...,
        description="The period type that was applied",
    )
    new_files: List[str] = Field(
        default_factory=list,
        description="Files added since the reference point",
    )
    modified_files: List[str] = Field(
        default_factory=list,
        description="Files modified since the reference point",
    )
    new_lines_count: int = Field(
        0,
        description="Approximate number of new or changed lines",
    )
    total_new_code_files: int = Field(
        0,
        description="Total number of files with new code (new + modified)",
    )
    reference_point: str = Field(
        "",
        description="Human-readable description of what constitutes new code",
    )
    detected_at: datetime = Field(
        default_factory=datetime.now,
        description="When the detection was performed",
    )

    class Config:
        use_enum_values = True
