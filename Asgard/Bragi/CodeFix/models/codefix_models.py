"""
Heimdall CodeFix Models

Data models for code fix suggestions generated from analysis findings.
"""

from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class FixConfidence(str, Enum):
    """Confidence level of the suggested fix."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FixType(str, Enum):
    """Type of fix action available."""
    AUTOMATED = "automated"
    SUGGESTED = "suggested"
    INFORMATIONAL = "informational"


class CodeFix(BaseModel):
    """A single code fix suggestion for a rule violation."""
    rule_id: str
    title: str
    description: str
    fix_type: FixType
    confidence: FixConfidence
    original_code: str = ""
    fixed_code: str = ""
    explanation: str = ""
    references: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class FixSuggestion(BaseModel):
    """A fix suggestion tied to a specific finding in a file."""
    file_path: str
    line_number: int
    rule_id: str
    finding_title: str
    fix: CodeFix

    class Config:
        use_enum_values = True


class CodeFixReport(BaseModel):
    """Aggregated report of all fix suggestions produced for a scan path."""
    total_suggestions: int = 0
    automated_count: int = 0
    suggested_count: int = 0
    suggestions: List[FixSuggestion] = Field(default_factory=list)
    scan_path: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True
