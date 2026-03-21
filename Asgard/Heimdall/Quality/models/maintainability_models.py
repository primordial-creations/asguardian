"""
Heimdall Maintainability Models

Pydantic models for maintainability index calculation and analysis.

Maintainability Index Formula (Microsoft):
MI = 171 - 5.2 * ln(HV) - 0.23 * CC - 16.2 * ln(LOC) + 50 * sin(sqrt(2.4 * CM))

Where:
- HV = Halstead Volume
- CC = Cyclomatic Complexity
- LOC = Lines of Code
- CM = Comment percentage (0-100)
"""

import math
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class MaintainabilityLevel(str, Enum):
    """Maintainability level classification."""
    EXCELLENT = "excellent"   # 85-100
    GOOD = "good"             # 70-84
    MODERATE = "moderate"     # 50-69
    POOR = "poor"             # 25-49
    CRITICAL = "critical"     # 0-24


class LanguageProfile(str, Enum):
    """Supported language profiles for maintainability analysis."""
    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"


class HalsteadMetrics(BaseModel):
    """
    Halstead complexity metrics.

    Measures software complexity based on operators and operands.
    """
    n1: int = Field(0, description="Number of distinct operators")
    n2: int = Field(0, description="Number of distinct operands")
    N1: int = Field(0, description="Total number of operators")
    N2: int = Field(0, description="Total number of operands")

    @property
    def vocabulary(self) -> int:
        """Program vocabulary (n1 + n2)."""
        return self.n1 + self.n2

    @property
    def length(self) -> int:
        """Program length (N1 + N2)."""
        return self.N1 + self.N2

    @property
    def volume(self) -> float:
        """Program volume: Length * log2(Vocabulary)."""
        if self.vocabulary <= 0:
            return 0.0
        return self.length * math.log2(self.vocabulary)

    @property
    def difficulty(self) -> float:
        """Program difficulty: (n1/2) * (N2/n2)."""
        if self.n2 == 0:
            return 0.0
        return (self.n1 / 2) * (self.N2 / self.n2)

    @property
    def effort(self) -> float:
        """Programming effort: Difficulty * Volume."""
        return self.difficulty * self.volume


class FunctionMaintainability(BaseModel):
    """Maintainability analysis for a single function."""
    name: str = Field(..., description="Function name")
    file_path: str = Field(..., description="Path to containing file")
    line_number: int = Field(1, description="Starting line number")

    # Core metrics
    maintainability_index: float = Field(0.0, description="Maintainability Index (0-100)")
    cyclomatic_complexity: int = Field(1, description="Cyclomatic complexity")
    lines_of_code: int = Field(0, description="Lines of code in function")
    halstead_volume: float = Field(0.0, description="Halstead volume")
    comment_percentage: float = Field(0.0, description="Percentage of lines that are comments")

    # Component scores (for transparency)
    complexity_score: float = Field(0.0, description="Complexity contribution to MI")
    volume_score: float = Field(0.0, description="Volume contribution to MI")
    loc_score: float = Field(0.0, description="LOC contribution to MI")
    comment_score: float = Field(0.0, description="Comment contribution to MI")

    # Classification
    maintainability_level: MaintainabilityLevel = Field(
        MaintainabilityLevel.MODERATE,
        description="Maintainability level classification"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Specific improvement recommendations"
    )

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"

    @property
    def needs_attention(self) -> bool:
        """Check if function needs maintainability attention."""
        level = self.maintainability_level
        if isinstance(level, str):
            return level in ["poor", "critical"]
        return level in [MaintainabilityLevel.POOR, MaintainabilityLevel.CRITICAL]


class FileMaintainability(BaseModel):
    """Maintainability analysis for an entire file."""
    file_path: str = Field(..., description="Path to file")
    maintainability_index: float = Field(0.0, description="File-level maintainability index")
    maintainability_level: MaintainabilityLevel = Field(
        MaintainabilityLevel.MODERATE,
        description="Maintainability level classification"
    )
    total_lines: int = Field(0, description="Total lines in file")
    code_lines: int = Field(0, description="Lines of code")
    comment_lines: int = Field(0, description="Lines of comments")
    comment_percentage: float = Field(0.0, description="Comment percentage")
    function_count: int = Field(0, description="Number of functions")
    average_function_mi: float = Field(0.0, description="Average function maintainability")
    functions: List[FunctionMaintainability] = Field(
        default_factory=list,
        description="Function-level maintainability results"
    )

    class Config:
        use_enum_values = True

    @property
    def filename(self) -> str:
        """Return just the filename."""
        return os.path.basename(self.file_path)


class MaintainabilityReport(BaseModel):
    """Complete maintainability analysis report."""
    overall_index: float = Field(0.0, description="Project-wide maintainability index")
    overall_level: MaintainabilityLevel = Field(
        MaintainabilityLevel.MODERATE,
        description="Overall maintainability level"
    )
    total_files: int = Field(0, description="Total files analyzed")
    total_functions: int = Field(0, description="Total functions analyzed")
    total_lines_of_code: int = Field(0, description="Total lines of code")
    average_index: float = Field(0.0, description="Average maintainability index")

    # Distribution
    files_by_level: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of files by maintainability level"
    )
    functions_by_level: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of functions by maintainability level"
    )

    # Detailed results
    file_results: List[FileMaintainability] = Field(
        default_factory=list,
        description="File-level maintainability results"
    )
    worst_functions: List[FunctionMaintainability] = Field(
        default_factory=list,
        description="Functions with lowest maintainability"
    )

    # Recommendations
    improvement_priorities: List[str] = Field(
        default_factory=list,
        description="Priority recommendations for improvement"
    )

    # Metadata
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_file_result(self, file_result: FileMaintainability) -> None:
        """Add a file result to the report."""
        self.file_results.append(file_result)
        self.total_files += 1
        self.total_functions += file_result.function_count
        self.total_lines_of_code += file_result.code_lines

        # Update level counts
        level: str = file_result.maintainability_level.value if isinstance(file_result.maintainability_level, MaintainabilityLevel) else file_result.maintainability_level
        self.files_by_level[level] = self.files_by_level.get(level, 0) + 1

        for func in file_result.functions:
            func_level: str = func.maintainability_level.value if isinstance(func.maintainability_level, MaintainabilityLevel) else func.maintainability_level
            self.functions_by_level[func_level] = self.functions_by_level.get(func_level, 0) + 1

    @property
    def critical_count(self) -> int:
        """Get count of critical maintainability files."""
        return self.files_by_level.get(MaintainabilityLevel.CRITICAL.value, 0)

    @property
    def poor_count(self) -> int:
        """Get count of poor maintainability files."""
        return self.files_by_level.get(MaintainabilityLevel.POOR.value, 0)

    @property
    def has_issues(self) -> bool:
        """Check if there are maintainability issues."""
        return self.critical_count > 0 or self.poor_count > 0


class LanguageWeights(BaseModel):
    """Language-specific weights for maintainability calculation."""
    complexity_weight: float = Field(0.23, description="Weight for cyclomatic complexity")
    volume_weight: float = Field(5.2, description="Weight for Halstead volume")
    loc_weight: float = Field(16.2, description="Weight for lines of code")
    comment_factor: float = Field(50.0, description="Factor for comment contribution")


class MaintainabilityThresholds(BaseModel):
    """Thresholds for maintainability level classification."""
    excellent: int = Field(85, description="Minimum index for excellent")
    good: int = Field(70, description="Minimum index for good")
    moderate: int = Field(50, description="Minimum index for moderate")
    poor: int = Field(25, description="Minimum index for poor")
    # Below poor threshold is critical (0-24)


class MaintainabilityConfig(BaseModel):
    """Configuration for maintainability analysis."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    include_halstead: bool = Field(True, description="Include Halstead metrics in calculation")
    include_comments: bool = Field(True, description="Factor in comment density")
    language_profile: LanguageProfile = Field(
        LanguageProfile.PYTHON,
        description="Language-specific scoring profile"
    )
    thresholds: MaintainabilityThresholds = Field(
        default_factory=MaintainabilityThresholds,  # type: ignore[arg-type]
        description="Maintainability level thresholds"
    )
    language_weights: Optional[LanguageWeights] = Field(
        None,
        description="Custom language weights (overrides profile defaults)"
    )
    include_extensions: List[str] = Field(
        default_factory=lambda: [".py"],
        description="File extensions to include"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "migrations",
            "test_*",
            "*_test.py",
        ],
        description="Patterns to exclude"
    )
    include_tests: bool = Field(False, description="Include test files in analysis")
    output_format: str = Field("text", description="Output format: text, json, markdown")
    verbose: bool = Field(False, description="Verbose output")

    class Config:
        use_enum_values = True

    def get_language_weights(self) -> LanguageWeights:
        """Get effective language weights."""
        if self.language_weights:
            return self.language_weights

        # Default weights by language
        defaults = {
            "python": LanguageWeights(complexity_weight=0.23, volume_weight=5.2, loc_weight=16.2, comment_factor=50.0),
            "java": LanguageWeights(complexity_weight=0.25, volume_weight=5.5, loc_weight=16.2, comment_factor=50.0),
            "javascript": LanguageWeights(complexity_weight=0.20, volume_weight=4.8, loc_weight=16.2, comment_factor=50.0),
        }

        profile: str = self.language_profile.value if isinstance(self.language_profile, LanguageProfile) else self.language_profile

        return defaults.get(profile, LanguageWeights())  # type: ignore[call-arg]
