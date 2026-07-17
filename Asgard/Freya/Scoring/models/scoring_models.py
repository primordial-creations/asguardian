"""
Freya Universal Scoring Models

Universal severity scale, letter grading with non-compensatory capping,
findings, and quality-gate models shared by every Freya subpackage.

Design notes (DEEPTHINK_04):
    - One severity vocabulary (Blocker/Critical/Major/Minor) across all
      categories, replacing the per-subpackage vocabularies.
    - Letter grades are capped by the highest unresolved severity: a
      purely compensatory arithmetic mean is the "Fungibility Fallacy"
      anti-pattern and is deliberately not used as the headline number.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class UniversalSeverity(str, Enum):
    """Universal severity scale shared by all Freya categories."""
    BLOCKER = "blocker"    # journey failure / legal liability / severe data risk
    CRITICAL = "critical"  # severe UX exclusion or high financial penalty
    MAJOR = "major"        # friction, sub-optimal compliance
    MINOR = "minor"        # technical debt


#: Ordered from most to least severe (index 0 = worst).
SEVERITY_ORDER: List[UniversalSeverity] = [
    UniversalSeverity.BLOCKER,
    UniversalSeverity.CRITICAL,
    UniversalSeverity.MAJOR,
    UniversalSeverity.MINOR,
]


class QualityGrade(str, Enum):
    """Letter grades, consistent with Heimdall's A-E Ratings precedent."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class Finding(BaseModel):
    """A single normalized finding in the universal severity currency."""
    category: str = Field(description='Category, e.g. "accessibility", "performance"')
    severity: UniversalSeverity = Field(description="Universal severity")
    check_id: str = Field(description='Check identifier, e.g. "wcag.1.4.3"')
    message: str = Field(description="Human-readable finding message")
    url: Optional[str] = Field(default=None, description="Page URL")
    selector: Optional[str] = Field(default=None, description="CSS selector of the element")
    source_severity: Optional[str] = Field(
        default=None,
        description="Original severity vocabulary, kept for traceability"
    )
    needs_review: bool = Field(
        default=False,
        description="True when automation cannot decide and a human must verify"
    )


class GradedScore(BaseModel):
    """A letter grade with non-compensatory capping applied."""
    base_score: float = Field(
        description="Weighted mean of category scores; for sorting/trending only"
    )
    capped_score: float = Field(description="Score after severity capping")
    grade: QualityGrade = Field(description="Letter grade derived from capped score")
    cap_reason: Optional[str] = Field(
        default=None,
        description='Why the grade is capped, e.g. "1 blocker: security.csp.missing"'
    )
    category_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-category 0-100 scores (radar data)"
    )


class GateConfig(BaseModel):
    """Configuration for the CI quality gate."""
    fail_on: List[UniversalSeverity] = Field(
        default_factory=lambda: [UniversalSeverity.BLOCKER, UniversalSeverity.CRITICAL],
        description="Severities that fail the gate when any finding is present"
    )
    min_grade: Optional[QualityGrade] = Field(
        default=None,
        description="Fail the gate when the letter grade is worse than this"
    )
    max_findings: Optional[int] = Field(
        default=None,
        description="Fail the gate when total finding count exceeds this"
    )


class GateResult(BaseModel):
    """Result of evaluating the quality gate."""
    passed: bool = Field(description="Whether the gate passed")
    reasons: List[str] = Field(
        default_factory=list,
        description="Reasons the gate failed (empty when passed)"
    )
    severity_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Finding counts by universal severity"
    )
