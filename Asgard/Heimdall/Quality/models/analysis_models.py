"""
Heimdall Quality Analysis Models

Pydantic models for code quality analysis operations and results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, cast

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    """Severity level for file length violations."""
    WARNING = "warning"      # 1-50 lines over threshold
    MODERATE = "moderate"    # 51-100 lines over threshold
    SEVERE = "severe"        # 101-200 lines over threshold
    CRITICAL = "critical"    # 200+ lines over threshold


class FileAnalysis(BaseModel):
    """Result of analyzing a single file."""
    file_path: str = Field(..., description="Path to the analyzed file")
    line_count: int = Field(..., description="Total number of lines in the file")
    threshold: int = Field(..., description="Line threshold used for analysis")
    lines_over: int = Field(..., description="Number of lines over threshold")
    severity: SeverityLevel = Field(..., description="Severity of the violation")
    file_extension: str = Field(..., description="File extension")
    relative_path: str = Field(..., description="Path relative to scan root")

    class Config:
        use_enum_values = True

    @classmethod
    def calculate_severity(cls, lines_over: int) -> SeverityLevel:
        """Calculate severity based on lines over threshold."""
        if lines_over <= 50:
            return SeverityLevel.WARNING
        elif lines_over <= 100:
            return SeverityLevel.MODERATE
        elif lines_over <= 200:
            return SeverityLevel.SEVERE
        else:
            return SeverityLevel.CRITICAL

    def format_display(self) -> str:
        """Format for CLI display."""
        return f"{self.relative_path:<60} {self.line_count:>6} lines  (+{self.lines_over} over threshold)"


class AnalysisResult(BaseModel):
    """Complete result of a code quality analysis."""
    total_files_scanned: int = Field(0, description="Number of files scanned")
    files_exceeding_threshold: int = Field(0, description="Number of files exceeding line threshold")
    default_threshold: int = Field(..., description="Default line threshold used for analysis")
    extension_thresholds: dict = Field(default_factory=dict, description="Per-extension thresholds used")
    scan_path: str = Field(..., description="Root path that was scanned")
    violations: List[FileAnalysis] = Field(default_factory=list, description="List of files exceeding threshold")
    scan_duration_seconds: float = Field(0.0, description="Time taken for the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    longest_file: Optional[FileAnalysis] = Field(None, description="The longest file found")
    skipped_directories: List[str] = Field(default_factory=list, description="Directories that were skipped")
    skipped_patterns: List[str] = Field(default_factory=list, description="File patterns that were skipped")

    class Config:
        use_enum_values = True

    def add_violation(self, analysis: FileAnalysis) -> None:
        """Record a file that exceeds the threshold."""
        self.files_exceeding_threshold += 1
        self.violations.append(analysis)

        # Track longest file
        if self.longest_file is None or analysis.line_count > self.longest_file.line_count:
            self.longest_file = analysis

    def increment_files_scanned(self) -> None:
        """Increment the files scanned counter."""
        self.total_files_scanned += 1

    @property
    def has_violations(self) -> bool:
        """Check if any files exceed the threshold."""
        return self.files_exceeding_threshold > 0

    @property
    def compliance_rate(self) -> float:
        """Calculate the percentage of files within threshold."""
        if self.total_files_scanned == 0:
            return 100.0
        return ((self.total_files_scanned - self.files_exceeding_threshold) / self.total_files_scanned) * 100

    def get_violations_by_severity(self) -> dict:
        """Group violations by severity level."""
        result: dict = {
            SeverityLevel.CRITICAL.value: [],
            SeverityLevel.SEVERE.value: [],
            SeverityLevel.MODERATE.value: [],
            SeverityLevel.WARNING.value: [],
        }
        for violation in self.violations:
            result[violation.severity].append(violation)
        return result


# Default thresholds by file type category
DEFAULT_EXTENSION_THRESHOLDS: dict = {
    # Style files - more lenient (500 lines)
    ".css": 500,
    ".scss": 500,
    ".sass": 500,
    ".less": 500,
    # Config/data files - moderate (500 lines)
    ".json": 500,
    ".yaml": 500,
    ".yml": 500,
    # All other code files use the base threshold (300 lines)
}


class AnalysisConfig(BaseModel):
    """Configuration for the analysis operation."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    threshold: int = Field(300, description="Default maximum allowed lines per file")
    extension_thresholds: dict = Field(
        default_factory=lambda: DEFAULT_EXTENSION_THRESHOLDS.copy(),
        description="Per-extension threshold overrides (e.g., {'.css': 500})"
    )
    output_format: str = Field("text", description="Output format: text, json, or markdown")
    include_extensions: Optional[List[str]] = Field(
        None,
        description="File extensions to include (None = all code files)"
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
            ".next",
            "coverage",
            ".pytest_cache",
            ".mypy_cache",
            "eggs",
            "*.egg-info",
        ],
        description="Directory patterns to exclude"
    )
    verbose: bool = Field(False, description="Show all scanned files, not just violations")

    class Config:
        use_enum_values = True

    def get_threshold_for_extension(self, extension: str) -> int:
        """
        Get the appropriate threshold for a file extension.

        Args:
            extension: File extension including dot (e.g., ".py", ".css")

        Returns:
            The threshold for that extension, or the default threshold
        """
        ext_lower = extension.lower()
        return cast(int, self.extension_thresholds.get(ext_lower, self.threshold))
