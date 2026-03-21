"""
Heimdall Complexity Analysis Models

Pydantic models for cyclomatic and cognitive complexity analysis.
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class ComplexitySeverity(str, Enum):
    """Severity levels for complexity violations."""
    LOW = "low"           # Complexity 1-5: Simple, easily understood
    MODERATE = "moderate"  # Complexity 6-10: Moderate complexity
    HIGH = "high"         # Complexity 11-20: High complexity, consider refactoring
    VERY_HIGH = "very_high"  # Complexity 21-50: Very high, needs refactoring
    CRITICAL = "critical"    # Complexity 50+: Unmaintainable, requires immediate attention


class FunctionComplexity(BaseModel):
    """Complexity analysis for a single function or method."""
    name: str = Field(..., description="Function or method name")
    line_number: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    cyclomatic_complexity: int = Field(..., description="McCabe cyclomatic complexity")
    cognitive_complexity: int = Field(..., description="SonarSource cognitive complexity")
    severity: ComplexitySeverity = Field(..., description="Severity based on max complexity")
    is_method: bool = Field(False, description="True if this is a class method")
    class_name: Optional[str] = Field(None, description="Parent class name if method")

    class Config:
        use_enum_values = True

    @classmethod
    def calculate_severity(cls, complexity: int) -> ComplexitySeverity:
        """Calculate severity based on complexity score."""
        if complexity <= 5:
            return ComplexitySeverity.LOW
        elif complexity <= 10:
            return ComplexitySeverity.MODERATE
        elif complexity <= 20:
            return ComplexitySeverity.HIGH
        elif complexity <= 50:
            return ComplexitySeverity.VERY_HIGH
        else:
            return ComplexitySeverity.CRITICAL

    @property
    def max_complexity(self) -> int:
        """Return the maximum of cyclomatic and cognitive complexity."""
        return max(self.cyclomatic_complexity, self.cognitive_complexity)

    @property
    def qualified_name(self) -> str:
        """Return fully qualified name (class.method or function)."""
        if self.class_name:
            return f"{self.class_name}.{self.name}"
        return self.name

    def format_display(self) -> str:
        """Format for CLI display."""
        name = self.qualified_name
        return (
            f"{name:<50} Line {self.line_number:>5}  "
            f"CC={self.cyclomatic_complexity:>3} COG={self.cognitive_complexity:>3}"
        )


class FileComplexityAnalysis(BaseModel):
    """Complexity analysis for a single file."""
    file_path: str = Field(..., description="Absolute path to the file")
    relative_path: str = Field(..., description="Path relative to scan root")
    total_functions: int = Field(0, description="Total number of functions analyzed")
    functions: List[FunctionComplexity] = Field(default_factory=list, description="Per-function analysis")
    average_cyclomatic: float = Field(0.0, description="Average cyclomatic complexity")
    average_cognitive: float = Field(0.0, description="Average cognitive complexity")
    max_cyclomatic: int = Field(0, description="Maximum cyclomatic complexity in file")
    max_cognitive: int = Field(0, description="Maximum cognitive complexity in file")
    total_cyclomatic: int = Field(0, description="Sum of all cyclomatic complexity")
    total_cognitive: int = Field(0, description="Sum of all cognitive complexity")
    violations: List[FunctionComplexity] = Field(default_factory=list, description="Functions exceeding thresholds")

    class Config:
        use_enum_values = True

    def add_function(self, func: FunctionComplexity) -> None:
        """Add a function's complexity analysis."""
        self.functions.append(func)
        self.total_functions += 1
        self.total_cyclomatic += func.cyclomatic_complexity
        self.total_cognitive += func.cognitive_complexity

        if func.cyclomatic_complexity > self.max_cyclomatic:
            self.max_cyclomatic = func.cyclomatic_complexity
        if func.cognitive_complexity > self.max_cognitive:
            self.max_cognitive = func.cognitive_complexity

        # Recalculate averages
        if self.total_functions > 0:
            self.average_cyclomatic = self.total_cyclomatic / self.total_functions
            self.average_cognitive = self.total_cognitive / self.total_functions

    def add_violation(self, func: FunctionComplexity) -> None:
        """Record a function that exceeds complexity thresholds."""
        self.violations.append(func)

    @property
    def has_violations(self) -> bool:
        """Check if any functions exceed thresholds."""
        return len(self.violations) > 0

    @property
    def worst_function(self) -> Optional[FunctionComplexity]:
        """Return the function with highest complexity."""
        if not self.functions:
            return None
        return max(self.functions, key=lambda f: f.max_complexity)


class ComplexityResult(BaseModel):
    """Complete result of complexity analysis."""
    total_files_scanned: int = Field(0, description="Number of files scanned")
    total_functions_analyzed: int = Field(0, description="Total functions analyzed")
    files_with_violations: int = Field(0, description="Number of files with violations")
    total_violations: int = Field(0, description="Total number of violation functions")
    cyclomatic_threshold: int = Field(..., description="Cyclomatic complexity threshold")
    cognitive_threshold: int = Field(..., description="Cognitive complexity threshold")
    scan_path: str = Field(..., description="Root path that was scanned")
    file_analyses: List[FileComplexityAnalysis] = Field(default_factory=list, description="Per-file results")
    violations: List[FunctionComplexity] = Field(default_factory=list, description="All functions exceeding thresholds")
    scan_duration_seconds: float = Field(0.0, description="Time taken for the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    # Aggregate statistics
    average_cyclomatic: float = Field(0.0, description="Overall average cyclomatic complexity")
    average_cognitive: float = Field(0.0, description="Overall average cognitive complexity")
    max_cyclomatic: int = Field(0, description="Maximum cyclomatic complexity found")
    max_cognitive: int = Field(0, description="Maximum cognitive complexity found")

    class Config:
        use_enum_values = True

    def add_file_analysis(self, analysis: FileComplexityAnalysis) -> None:
        """Add a file's complexity analysis to the result."""
        self.file_analyses.append(analysis)
        self.total_files_scanned += 1
        self.total_functions_analyzed += analysis.total_functions

        if analysis.has_violations:
            self.files_with_violations += 1
            self.total_violations += len(analysis.violations)
            self.violations.extend(analysis.violations)

        # Update max values
        if analysis.max_cyclomatic > self.max_cyclomatic:
            self.max_cyclomatic = analysis.max_cyclomatic
        if analysis.max_cognitive > self.max_cognitive:
            self.max_cognitive = analysis.max_cognitive

        # Recalculate overall averages
        if self.total_functions_analyzed > 0:
            total_cc = sum(f.total_cyclomatic for f in self.file_analyses)
            total_cog = sum(f.total_cognitive for f in self.file_analyses)
            self.average_cyclomatic = total_cc / self.total_functions_analyzed
            self.average_cognitive = total_cog / self.total_functions_analyzed

    @property
    def has_violations(self) -> bool:
        """Check if any functions exceed thresholds."""
        return self.total_violations > 0

    @property
    def compliance_rate(self) -> float:
        """Calculate percentage of functions within thresholds."""
        if self.total_functions_analyzed == 0:
            return 100.0
        compliant = self.total_functions_analyzed - self.total_violations
        return (compliant / self.total_functions_analyzed) * 100

    def get_violations_by_severity(self) -> dict:
        """Group violations by severity level."""
        result: dict = {
            ComplexitySeverity.CRITICAL.value: [],
            ComplexitySeverity.VERY_HIGH.value: [],
            ComplexitySeverity.HIGH.value: [],
            ComplexitySeverity.MODERATE.value: [],
            ComplexitySeverity.LOW.value: [],
        }
        for violation in self.violations:
            result[violation.severity].append(violation)
        return result

    @property
    def worst_functions(self) -> List[FunctionComplexity]:
        """Return top 10 most complex functions."""
        return sorted(self.violations, key=lambda f: f.max_complexity, reverse=True)[:10]


class ComplexityConfig(BaseModel):
    """Configuration for complexity analysis."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    cyclomatic_threshold: int = Field(10, description="Maximum allowed cyclomatic complexity")
    cognitive_threshold: int = Field(15, description="Maximum allowed cognitive complexity")
    output_format: str = Field("text", description="Output format: text, json, or markdown")
    include_extensions: Optional[List[str]] = Field(
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
            "test_",
            "_test.py",
            "tests/",
        ],
        description="Patterns to exclude from analysis"
    )
    include_tests: bool = Field(False, description="Include test files in analysis")
    verbose: bool = Field(False, description="Show all functions, not just violations")

    class Config:
        use_enum_values = True
