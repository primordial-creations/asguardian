"""
Heimdall Coverage Models

Data models for test coverage analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class CoverageSeverity(Enum):
    """Severity of coverage gaps."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SuggestionPriority(Enum):
    """Priority of test suggestions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MethodType(Enum):
    """Type of method."""

    PUBLIC = "public"
    PRIVATE = "private"
    DUNDER = "dunder"
    PROPERTY = "property"
    CLASSMETHOD = "classmethod"
    STATICMETHOD = "staticmethod"


@dataclass
class CoverageConfig:
    """Configuration for coverage analysis."""

    scan_path: Path = field(default_factory=lambda: Path("."))
    test_paths: List[Path] = field(default_factory=list)
    exclude_patterns: List[str] = field(
        default_factory=lambda: ["__pycache__", ".git", ".venv", "node_modules"]
    )
    include_extensions: List[str] = field(default_factory=lambda: [".py"])

    # Coverage thresholds
    min_coverage_percent: float = 80.0
    min_method_coverage: float = 70.0

    # Analysis options
    include_private: bool = False
    include_dunder: bool = False
    analyze_branches: bool = True

    def __post_init__(self) -> None:
        """Ensure scan_path is a Path."""
        if isinstance(self.scan_path, str):
            self.scan_path = Path(self.scan_path)


@dataclass
class MethodInfo:
    """Information about a method."""

    name: str
    class_name: Optional[str]
    file_path: str
    line_number: int
    method_type: MethodType = MethodType.PUBLIC
    complexity: int = 1
    has_branches: bool = False
    branch_count: int = 0
    parameter_count: int = 0
    is_async: bool = False
    docstring: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get full method name including class."""
        if self.class_name:
            return f"{self.class_name}.{self.name}"
        return self.name


@dataclass
class CoverageGap:
    """A gap in test coverage."""

    method: MethodInfo
    gap_type: str
    severity: CoverageSeverity
    message: str
    details: str = ""

    @property
    def file_path(self) -> str:
        """Get file path."""
        return self.method.file_path

    @property
    def line_number(self) -> int:
        """Get line number."""
        return self.method.line_number


@dataclass
class TestSuggestion:
    """A suggested test case."""

    method: MethodInfo
    test_name: str
    test_type: str
    priority: SuggestionPriority
    description: str
    test_cases: List[str] = field(default_factory=list)
    rationale: str = ""

    @property
    def file_path(self) -> str:
        """Get file path."""
        return self.method.file_path


@dataclass
class ClassCoverage:
    """Coverage metrics for a class."""

    class_name: str
    file_path: str
    total_methods: int = 0
    covered_methods: int = 0
    uncovered_methods: List[str] = field(default_factory=list)
    coverage_percent: float = 0.0

    @property
    def is_fully_covered(self) -> bool:
        """Check if class is fully covered."""
        return self.covered_methods == self.total_methods


@dataclass
class CoverageMetrics:
    """Aggregate coverage metrics."""

    total_files: int = 0
    total_classes: int = 0
    total_methods: int = 0
    covered_methods: int = 0
    total_branches: int = 0
    covered_branches: int = 0

    @property
    def method_coverage_percent(self) -> float:
        """Get method coverage percentage."""
        if self.total_methods == 0:
            return 100.0
        return (self.covered_methods / self.total_methods) * 100

    @property
    def branch_coverage_percent(self) -> float:
        """Get branch coverage percentage."""
        if self.total_branches == 0:
            return 100.0
        return (self.covered_branches / self.total_branches) * 100


@dataclass
class CoverageReport:
    """Complete coverage analysis report."""

    scan_path: str = ""
    scanned_at: datetime = field(default_factory=datetime.now)
    metrics: CoverageMetrics = field(default_factory=CoverageMetrics)
    gaps: List[CoverageGap] = field(default_factory=list)
    suggestions: List[TestSuggestion] = field(default_factory=list)
    class_coverage: List[ClassCoverage] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    @property
    def total_gaps(self) -> int:
        """Get total gap count."""
        return len(self.gaps)

    @property
    def total_suggestions(self) -> int:
        """Get total suggestion count."""
        return len(self.suggestions)

    @property
    def gaps_by_severity(self) -> Dict[CoverageSeverity, List[CoverageGap]]:
        """Group gaps by severity."""
        result: Dict[CoverageSeverity, List[CoverageGap]] = {
            s: [] for s in CoverageSeverity
        }
        for gap in self.gaps:
            result[gap.severity].append(gap)
        return result

    @property
    def suggestions_by_priority(self) -> Dict[SuggestionPriority, List[TestSuggestion]]:
        """Group suggestions by priority."""
        result: Dict[SuggestionPriority, List[TestSuggestion]] = {
            p: [] for p in SuggestionPriority
        }
        for sug in self.suggestions:
            result[sug.priority].append(sug)
        return result

    @property
    def has_gaps(self) -> bool:
        """Check if any gaps exist."""
        return len(self.gaps) > 0

    def add_gap(self, gap: CoverageGap) -> None:
        """Add a coverage gap."""
        self.gaps.append(gap)

    def add_suggestion(self, suggestion: TestSuggestion) -> None:
        """Add a test suggestion."""
        self.suggestions.append(suggestion)

    def add_class_coverage(self, class_cov: ClassCoverage) -> None:
        """Add class coverage metrics."""
        self.class_coverage.append(class_cov)
