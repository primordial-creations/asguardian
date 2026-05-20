"""
Heimdall Quality Gate Models

Pydantic models for the quality gate evaluation system.

A quality gate is a set of conditions that analysis results must meet.
Each condition specifies a metric, an operator, a threshold value, and
whether a failure is a hard error or just a warning.

The built-in "Asgard Way" gate defines sensible default conditions.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MetricType(str, Enum):
    """Supported metric types that can be used in gate conditions."""
    SECURITY_RATING = "security_rating"
    RELIABILITY_RATING = "reliability_rating"
    MAINTAINABILITY_RATING = "maintainability_rating"
    MAINTAINABILITY_INDEX = "maintainability_index"
    CYCLOMATIC_COMPLEXITY_MAX = "cyclomatic_complexity_max"
    DUPLICATION_PERCENTAGE = "duplication_percentage"
    COMMENT_DENSITY = "comment_density"
    API_DOCUMENTATION_COVERAGE = "api_documentation_coverage"
    CRITICAL_VULNERABILITIES = "critical_vulnerabilities"
    HIGH_VULNERABILITIES = "high_vulnerabilities"
    TECHNICAL_DEBT_HOURS = "technical_debt_hours"
    NAMING_VIOLATIONS = "naming_violations"


class GateOperator(str, Enum):
    """Comparison operators for gate conditions."""
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"


class GateCondition(BaseModel):
    """A single condition within a quality gate."""
    metric: MetricType = Field(..., description="The metric to evaluate")
    operator: GateOperator = Field(..., description="Comparison operator")
    threshold: Union[float, str] = Field(..., description="Threshold value to compare against")
    error_on_fail: bool = Field(
        True,
        description="If True, failing this condition fails the gate. If False, it is a warning only."
    )
    description: str = Field("", description="Human-readable description of this condition")

    class Config:
        use_enum_values = True


class ConditionResult(BaseModel):
    """Evaluation result for a single gate condition."""
    condition: GateCondition = Field(..., description="The condition that was evaluated")
    actual_value: Union[float, str, None] = Field(
        None,
        description="The actual metric value at evaluation time"
    )
    passed: bool = Field(True, description="Whether the condition passed")
    message: str = Field("", description="Human-readable result message")

    class Config:
        use_enum_values = True


class GateStatus(str, Enum):
    """Overall status of a quality gate evaluation."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_EVALUATED = "not_evaluated"


class QualityGate(BaseModel):
    """A named set of quality gate conditions."""
    name: str = Field(..., description="Name of the quality gate")
    conditions: List[GateCondition] = Field(
        default_factory=list,
        description="List of conditions that must be met"
    )
    description: str = Field("", description="Description of the gate's purpose")

    class Config:
        use_enum_values = True


class QualityGateResult(BaseModel):
    """Result of evaluating a quality gate against a set of metrics."""
    gate_name: str = Field(..., description="Name of the gate that was evaluated")
    status: GateStatus = Field(GateStatus.NOT_EVALUATED, description="Overall gate status")
    condition_results: List[ConditionResult] = Field(
        default_factory=list,
        description="Results for each individual condition"
    )
    summary: str = Field("", description="Human-readable summary of the gate evaluation")
    scan_path: str = Field("", description="Path that was evaluated")
    evaluated_at: datetime = Field(
        default_factory=datetime.now,
        description="When the gate was evaluated"
    )

    class Config:
        use_enum_values = True

    @property
    def passed_count(self) -> int:
        """Count of conditions that passed."""
        return sum(1 for r in self.condition_results if r.passed)

    @property
    def failed_count(self) -> int:
        """Count of conditions that failed."""
        return sum(1 for r in self.condition_results if not r.passed)

    @property
    def error_failures(self) -> List[ConditionResult]:
        """Conditions that failed and have error_on_fail=True."""
        return [
            r for r in self.condition_results
            if not r.passed and r.condition.error_on_fail
        ]

    @property
    def warning_failures(self) -> List[ConditionResult]:
        """Conditions that failed but have error_on_fail=False (warnings only)."""
        return [
            r for r in self.condition_results
            if not r.passed and not r.condition.error_on_fail
        ]


class QualityGateConfig(BaseModel):
    """Configuration for the quality gate evaluator."""
    gate: QualityGate = Field(..., description="The quality gate to evaluate")
    small_change_threshold_lines: int = Field(
        20,
        description="Skip gate evaluation if total changed lines is below this threshold"
    )

    class Config:
        use_enum_values = True
