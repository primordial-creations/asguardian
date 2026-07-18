"""
Heimdall Technical Debt Models

Pydantic models for technical debt analysis and quantification.

Debt Categories:
1. Code Debt - Quality issues, maintainability problems
2. Design Debt - Architectural issues, coupling problems
3. Test Debt - Coverage gaps, test quality issues
4. Documentation Debt - Missing/poor documentation
5. Dependency Debt - Outdated/vulnerable dependencies
"""

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from typing import Literal

from pydantic import BaseModel, Field


class DebtType(str, Enum):
    """Types of technical debt."""
    CODE = "code"                   # Code quality issues
    DESIGN = "design"              # Architectural issues
    TEST = "test"                  # Testing gaps
    DOCUMENTATION = "documentation" # Missing/poor docs
    DEPENDENCIES = "dependencies"   # Outdated/vulnerable deps


class DebtSeverity(str, Enum):
    """Technical debt severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimeHorizon(str, Enum):
    """Analysis time horizons for debt projections."""
    SPRINT = "sprint"      # ~2 weeks
    QUARTER = "quarter"    # ~3 months
    YEAR = "year"          # ~12 months


class DebtRecommendation(str, Enum):
    """Recommended handling for a debt item or file (Plan 02)."""
    FIX = "fix"
    FIX_WHEN_TOUCHING = "fix_when_touching"
    REWRITE = "rewrite"
    TOLERATE = "tolerate"


class RemediationFunction(BaseModel):
    """
    SQALE-style remediation cost function attached to a debt rule.

    Cost is a function shape, not a scalar: constant per issue, linear in
    units above a threshold, or linear with a context-switch offset.
    """
    kind: Literal["constant", "linear", "linear_with_offset"] = Field(
        "constant", description="Remediation function shape"
    )
    base_minutes: float = Field(0.0, ge=0.0, description="Constant part / offset in minutes")
    coefficient_minutes: float = Field(
        0.0, ge=0.0, description="Minutes per unit above threshold (linear kinds)"
    )
    unit: str = Field("issue", description="Unit the coefficient applies to")
    batchability: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Geometric discount d: ~0.05 for mechanical debt, ~0.9 for cognitive debt"
    )
    discount_floor: float = Field(
        0.0, ge=0.0, le=1.0,
        description=(
            "Minimum per-item cost multiplier. 0 for mechanical debt (fully "
            "batchable); ~0.25 for cognitive debt so a pile of smells stays "
            "near-additive instead of being capped by the geometric series."
        ),
    )


class EffortInterval(BaseModel):
    """Remediation effort as an honest interval, never a point estimate."""
    low_minutes: float = Field(0.0, ge=0.0, description="Optimistic bound in minutes")
    high_minutes: float = Field(0.0, ge=0.0, description="Pessimistic bound in minutes")
    confidence: Literal["high", "medium", "low"] = Field(
        "medium", description="Confidence in the interval"
    )
    width_reason: str = Field("", description="Why the interval is as wide as it is")

    @property
    def midpoint_minutes(self) -> float:
        """Midpoint of the interval in minutes."""
        return (self.low_minutes + self.high_minutes) / 2.0

    @property
    def midpoint_hours(self) -> float:
        """Midpoint of the interval in hours (backward-compat effort_hours feed)."""
        return self.midpoint_minutes / 60.0


class FileFriction(BaseModel):
    """VCS-derived friction signals for a file (interest-model input, Plan 02 Phase D)."""
    churn_commits_90d: int = Field(0, ge=0, description="Commits touching the file in 90 days")
    distinct_authors_12m: int = Field(0, ge=0, description="Distinct authors in 12 months")
    bugfix_commits_12m: int = Field(0, ge=0, description="Fix/bug/hotfix commits in 12 months")


class DebtItem(BaseModel):
    """Individual technical debt item."""
    debt_type: DebtType = Field(..., description="Type of technical debt")
    file_path: str = Field(..., description="Path to file containing debt")
    line_number: int = Field(1, description="Line number where debt is located")
    description: str = Field(..., description="Description of the debt")
    severity: DebtSeverity = Field(DebtSeverity.MEDIUM, description="Severity level")
    effort_hours: float = Field(0.0, description="Estimated hours to remediate")
    business_impact: float = Field(0.5, ge=0.0, le=1.0, description="Business impact (0.0-1.0)")
    interest_rate: float = Field(0.05, description="How much worse it gets over time (per quarter)")
    remediation_strategy: str = Field("", description="Suggested remediation approach")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Detection confidence")
    effort_interval: Optional[EffortInterval] = Field(
        None, description="Pessimism-corrected effort interval (Plan 02); effort_hours stays the legacy point estimate"
    )
    non_remediation_factor: float = Field(
        15.0, ge=0.0,
        description="SBII business-impact penalty factor (Blocking 1000 / High 100 / Medium 15 / Low 10 / Info 4)"
    )
    recommendation: DebtRecommendation = Field(
        DebtRecommendation.FIX, description="Recommended handling for this item"
    )
    context: str = Field(
        "production",
        description=(
            "Code context this item's file was classified under (Plan 04 "
            "Phase A): production | test | generated | suspected_generated | "
            "script. Stamped automatically by the analyzer via "
            "Bragi.common.context_classifier."
        ),
    )
    priority_score_override: Optional[float] = Field(
        None,
        description=(
            "Plan 02 Phase D priority score (interest x non_remediation_factor "
            "/ remediation_minutes) when git friction telemetry was available; "
            "falls back to the legacy business_impact-based heuristic when unset."
        ),
    )

    class Config:
        use_enum_values = True

    @property
    def priority_score(self) -> float:
        """
        Calculate priority score based on ROI.

        When friction-derived telemetry is available (Plan 02 Phase D:
        `priority = interest x non_remediation_factor / remediation_minutes`),
        it takes precedence over the legacy business-impact heuristic.
        """
        if self.priority_score_override is not None:
            return self.priority_score_override
        severity_multiplier = {
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 5,
        }
        sev = self.severity if isinstance(self.severity, str) else self.severity.value
        roi = (self.business_impact * self.interest_rate) / max(self.effort_hours, 0.1)
        return roi * severity_multiplier.get(sev, 1)

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"


class ROIAnalysis(BaseModel):
    """Return on Investment analysis for debt remediation."""
    overall_roi: float = Field(0.0, description="Overall ROI for addressing all debt")
    roi_by_type: Dict[str, float] = Field(default_factory=dict, description="ROI by debt type")
    payback_period_months: float = Field(0.0, description="Months until investment pays off")
    total_effort_hours: float = Field(0.0, description="Total hours to remediate all debt")
    total_benefit: float = Field(0.0, description="Quantified benefit of remediation")


class TimeProjection(BaseModel):
    """Time horizon projections for debt growth."""
    current_debt_hours: float = Field(0.0, description="Current total debt in hours")
    projected_debt_hours: float = Field(0.0, description="Projected debt at time horizon")
    growth_percentage: float = Field(0.0, description="Percentage growth in debt")
    time_horizon: TimeHorizon = Field(TimeHorizon.QUARTER, description="Time horizon for projection")

    class Config:
        use_enum_values = True


class DebtReport(BaseModel):
    """Complete technical debt analysis report."""
    total_debt_hours: float = Field(0.0, description="Total technical debt in hours (legacy linear sum)")
    debt_ratio: float = Field(0.0, description="Debt hours per 1000 lines of code (legacy metric)")
    tdr_percent: Optional[float] = Field(
        None,
        description=(
            "Standard Technical Debt Ratio %: aggregated debt minutes / "
            "(LOC x 30 min/LOC development cost). Single source of truth for "
            "the Maintainability grade (Plan 02 Phase A)."
        ),
    )
    aggregated_debt_hours: Optional[float] = Field(
        None,
        description="Batched, pessimism-corrected debt total in hours (DebtAggregator output)"
    )
    effort_interval: Optional[EffortInterval] = Field(
        None, description="Project-level remediation effort interval"
    )
    file_recommendations: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-file recommendation (fix / fix_when_touching / rewrite / tolerate)"
    )
    total_lines_of_code: int = Field(0, description="Total lines of code analyzed")
    debt_by_type: Dict[str, float] = Field(default_factory=dict, description="Hours by debt type")
    debt_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    debt_items: List[DebtItem] = Field(default_factory=list, description="All identified debt items")
    prioritized_items: List[DebtItem] = Field(default_factory=list, description="Items sorted by priority")
    roi_analysis: ROIAnalysis = Field(default_factory=ROIAnalysis, description="ROI analysis")  # type: ignore[arg-type]
    time_projection: TimeProjection = Field(default_factory=TimeProjection, description="Time projection")  # type: ignore[arg-type]
    most_indebted_files: List[Tuple[str, float]] = Field(default_factory=list, description="Files with most debt")
    remediation_priorities: List[str] = Field(default_factory=list, description="Priority actions")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_debt_item(self, item: DebtItem) -> None:
        """Add a debt item to the report."""
        self.debt_items.append(item)
        self.total_debt_hours += item.effort_hours

        # Update type count
        debt_type = item.debt_type if isinstance(item.debt_type, str) else item.debt_type.value
        self.debt_by_type[debt_type] = self.debt_by_type.get(debt_type, 0.0) + item.effort_hours

        # Update severity count
        severity = item.severity if isinstance(item.severity, str) else item.severity.value
        self.debt_by_severity[severity] = self.debt_by_severity.get(severity, 0) + 1

    @property
    def has_debt(self) -> bool:
        """Check if any debt was detected."""
        return self.total_debt_hours > 0

    @property
    def critical_count(self) -> int:
        """Get count of critical debt items."""
        return self.debt_by_severity.get(DebtSeverity.CRITICAL.value, 0)

    @property
    def high_count(self) -> int:
        """Get count of high severity debt items."""
        return self.debt_by_severity.get(DebtSeverity.HIGH.value, 0)

    def get_items_by_type(self, debt_type: DebtType) -> List[DebtItem]:
        """Get all debt items of a specific type."""
        target = debt_type if isinstance(debt_type, str) else debt_type.value
        return [item for item in self.debt_items if item.debt_type == target]

    def get_items_by_severity(self, severity: DebtSeverity) -> List[DebtItem]:
        """Get all debt items of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [item for item in self.debt_items if item.severity == target]


class EffortModels(BaseModel):
    """Configurable effort estimation models."""
    complexity_reduction_factor: float = Field(0.5, description="Hours per complexity point")
    test_coverage_factor: float = Field(0.1, description="Hours per missing line of test coverage")
    documentation_factor: float = Field(0.25, description="Hours per undocumented function")
    refactoring_log_factor: float = Field(2.0, description="Log factor for refactoring effort")
    dependency_update_hours: float = Field(2.0, description="Fixed hours per dependency update")


class InterestRates(BaseModel):
    """Configurable interest rates for debt growth projections."""
    high_complexity: float = Field(0.10, description="10% worse per quarter for high complexity")
    no_tests: float = Field(0.15, description="15% worse per quarter for no tests")
    poor_docs: float = Field(0.05, description="5% worse per quarter for poor docs")
    outdated_deps: float = Field(0.20, description="20% worse per quarter for outdated deps")
    design_issues: float = Field(0.08, description="8% worse per quarter for design issues")


class DebtConfig(BaseModel):
    """Configuration for technical debt analysis."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    debt_types: Optional[List[str]] = Field(
        None,
        description="Types to analyze (None = all)"
    )
    time_horizon: TimeHorizon = Field(
        TimeHorizon.QUARTER,
        description="Time horizon for projections"
    )
    business_value_weights: Dict[str, float] = Field(
        default_factory=dict,
        description="Custom business value weights by path pattern"
    )
    effort_models: EffortModels = Field(
        default_factory=EffortModels,  # type: ignore[arg-type]
        description="Effort estimation models"
    )
    interest_rates: InterestRates = Field(
        default_factory=InterestRates,  # type: ignore[arg-type]
        description="Interest rates for debt growth"
    )
    include_extensions: Optional[List[str]] = Field(
        default_factory=lambda: [".py", ".pyw", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".rs", ".kt", ".swift", ".scala"],
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
        ],
        description="Patterns to exclude"
    )
    include_tests: bool = Field(False, description="Include test files in analysis")
    output_format: str = Field("text", description="Output format: text, json, markdown")
    verbose: bool = Field(False, description="Verbose output")

    class Config:
        use_enum_values = True

    def get_enabled_debt_types(self) -> List[str]:
        """Get list of enabled debt types."""
        if self.debt_types:
            return self.debt_types
        return [dt.value for dt in DebtType]
