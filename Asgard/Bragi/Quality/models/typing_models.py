"""
Heimdall Type Annotation Coverage Models

Pydantic models for analyzing type annotation coverage in Python code.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class AnnotationStatus(str, Enum):
    """Status of type annotations for a function."""
    FULLY_ANNOTATED = "fully_annotated"         # All params and return annotated
    PARTIALLY_ANNOTATED = "partially_annotated"  # Some but not all annotations
    NOT_ANNOTATED = "not_annotated"             # No annotations


class AnnotationSeverity(str, Enum):
    """Severity levels for missing annotations."""
    LOW = "low"         # Private methods or tests
    MEDIUM = "medium"   # Internal helper functions
    HIGH = "high"       # Public API functions


class FunctionAnnotation(BaseModel):
    """Represents annotation status for a single function."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where function is defined")
    function_name: str = Field(..., description="Name of the function")
    class_name: Optional[str] = Field(None, description="Class name if this is a method")
    is_async: bool = Field(False, description="Whether function is async")
    is_method: bool = Field(False, description="Whether function is a method")
    is_private: bool = Field(False, description="Whether function name starts with _")
    is_dunder: bool = Field(False, description="Whether function is dunder method")
    status: AnnotationStatus = Field(..., description="Annotation status")
    severity: AnnotationSeverity = Field(..., description="Severity of missing annotations")
    total_parameters: int = Field(0, description="Total number of parameters")
    annotated_parameters: int = Field(0, description="Number of annotated parameters")
    has_return_annotation: bool = Field(False, description="Whether return type is annotated")
    missing_parameter_names: List[str] = Field(default_factory=list, description="Names of unannotated parameters")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"

    @property
    def qualified_name(self) -> str:
        """Return fully qualified function name."""
        if self.class_name:
            return f"{self.class_name}.{self.function_name}"
        return self.function_name

    @property
    def annotation_percentage(self) -> float:
        """Calculate annotation percentage for this function."""
        # Count return type as one annotation target
        total_targets = self.total_parameters + 1
        annotated = self.annotated_parameters + (1 if self.has_return_annotation else 0)
        if total_targets == 0:
            return 100.0
        return (annotated / total_targets) * 100


class FileTypingStats(BaseModel):
    """Typing statistics for a single file."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    total_functions: int = Field(0, description="Total number of functions")
    fully_annotated: int = Field(0, description="Fully annotated functions")
    partially_annotated: int = Field(0, description="Partially annotated functions")
    not_annotated: int = Field(0, description="Functions with no annotations")
    coverage_percentage: float = Field(0.0, description="Typing coverage percentage")
    functions: List[FunctionAnnotation] = Field(default_factory=list, description="All functions in file")

    class Config:
        use_enum_values = True

    @property
    def is_passing(self) -> bool:
        """Check if file meets minimum coverage."""
        return self.coverage_percentage >= 80.0


class TypingReport(BaseModel):
    """Complete typing coverage analysis report."""
    total_functions: int = Field(0, description="Total number of functions analyzed")
    fully_annotated: int = Field(0, description="Fully annotated functions")
    partially_annotated: int = Field(0, description="Partially annotated functions")
    not_annotated: int = Field(0, description="Functions with no annotations")
    coverage_percentage: float = Field(0.0, description="Overall typing coverage percentage")
    threshold: float = Field(80.0, description="Minimum coverage threshold")
    is_passing: bool = Field(True, description="Whether coverage meets threshold")
    files_analyzed: List[FileTypingStats] = Field(default_factory=list, description="Stats per file")
    unannotated_functions: List[FunctionAnnotation] = Field(default_factory=list, description="Functions needing annotations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_file_stats(self, file_stats: FileTypingStats) -> None:
        """Add file statistics to the report."""
        self.files_analyzed.append(file_stats)
        self.total_functions += file_stats.total_functions
        self.fully_annotated += file_stats.fully_annotated
        self.partially_annotated += file_stats.partially_annotated
        self.not_annotated += file_stats.not_annotated

        # Collect unannotated functions
        for func in file_stats.functions:
            if func.status != AnnotationStatus.FULLY_ANNOTATED:
                self.unannotated_functions.append(func)

    def calculate_coverage(self) -> None:
        """Calculate overall coverage percentage."""
        if self.total_functions == 0:
            self.coverage_percentage = 100.0
        else:
            self.coverage_percentage = (self.fully_annotated / self.total_functions) * 100
        self.is_passing = self.coverage_percentage >= self.threshold

    @property
    def has_violations(self) -> bool:
        """Check if there are any violations (coverage below threshold)."""
        return not self.is_passing

    @property
    def is_compliant(self) -> bool:
        """Check if codebase meets typing coverage threshold."""
        return self.is_passing

    def get_files_below_threshold(self) -> List[FileTypingStats]:
        """Get all files with coverage below threshold."""
        return [f for f in self.files_analyzed if f.coverage_percentage < self.threshold]


class TypingConfig(BaseModel):
    """Configuration for typing coverage scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    minimum_coverage: float = Field(
        80.0,
        description="Minimum percentage of functions that must have full type annotations",
        ge=0.0,
        le=100.0
    )
    require_return_type: bool = Field(True, description="Require return type annotations")
    require_parameter_types: bool = Field(True, description="Require parameter type annotations")
    exclude_private: bool = Field(False, description="Exclude private methods (_method)")
    exclude_dunder: bool = Field(True, description="Exclude dunder methods (__method__)")
    exclude_self_cls: bool = Field(True, description="Exclude 'self' and 'cls' from parameter count")
    output_format: str = Field("text", description="Output format: text, json, markdown")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "*.pyc",
            "**/test_*.py",
            "**/conftest.py",
        ],
        description="Patterns to exclude"
    )
    include_tests: bool = Field(False, description="Include test files")
    verbose: bool = Field(False, description="Show verbose output")

    class Config:
        use_enum_values = True
