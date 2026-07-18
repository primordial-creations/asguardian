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
    # Differential / new-code metrics (Plan Bragi-06 / Heimdall-09)
    COMPOSITE_SCORE = "composite_score"
    NEW_BLOCKER_ISSUES = "new_blocker_issues"
    NEW_CODE_COMPOSITE_SCORE = "new_code_composite_score"
    DEBT_DELTA_MINUTES = "debt_delta_minutes"
    PROHIBITED_LICENSE_COUNT = "prohibited_license_count"
    DEPENDENCY_CYCLES = "dependency_cycles"
    RISK_PROFILE_E_LOC_PCT = "risk_profile_e_loc_pct"
    SCAN_COMPLETENESS = "scan_completeness"


class MetricDeterminism(str, Enum):
    """
    Determinism class of a metric (DEEPTHINK_02: only zero-ambiguity,
    mechanically verifiable conditions may hard-block a pipeline).
    """
    FACT = "fact"
    HEURISTIC = "heuristic"


# Determinism annotation for each metric type. FACT metrics are mechanically
# countable and deterministic; HEURISTIC metrics involve judgement, sampling,
# or tunable scoring and should not be attached to error_on_fail conditions.
METRIC_DETERMINISM: Dict[MetricType, MetricDeterminism] = {
    MetricType.SECURITY_RATING: MetricDeterminism.HEURISTIC,
    MetricType.RELIABILITY_RATING: MetricDeterminism.HEURISTIC,
    MetricType.MAINTAINABILITY_RATING: MetricDeterminism.HEURISTIC,
    MetricType.MAINTAINABILITY_INDEX: MetricDeterminism.HEURISTIC,
    MetricType.CYCLOMATIC_COMPLEXITY_MAX: MetricDeterminism.FACT,
    MetricType.DUPLICATION_PERCENTAGE: MetricDeterminism.HEURISTIC,
    MetricType.COMMENT_DENSITY: MetricDeterminism.FACT,
    MetricType.API_DOCUMENTATION_COVERAGE: MetricDeterminism.FACT,
    MetricType.CRITICAL_VULNERABILITIES: MetricDeterminism.FACT,
    MetricType.HIGH_VULNERABILITIES: MetricDeterminism.FACT,
    MetricType.TECHNICAL_DEBT_HOURS: MetricDeterminism.HEURISTIC,
    MetricType.NAMING_VIOLATIONS: MetricDeterminism.FACT,
    MetricType.COMPOSITE_SCORE: MetricDeterminism.HEURISTIC,
    MetricType.NEW_BLOCKER_ISSUES: MetricDeterminism.FACT,
    MetricType.NEW_CODE_COMPOSITE_SCORE: MetricDeterminism.HEURISTIC,
    MetricType.DEBT_DELTA_MINUTES: MetricDeterminism.HEURISTIC,
    MetricType.PROHIBITED_LICENSE_COUNT: MetricDeterminism.FACT,
    MetricType.DEPENDENCY_CYCLES: MetricDeterminism.FACT,
    MetricType.RISK_PROFILE_E_LOC_PCT: MetricDeterminism.HEURISTIC,
    MetricType.SCAN_COMPLETENESS: MetricDeterminism.FACT,
}


class OnMissing(str, Enum):
    """Behaviour when the metric for a condition was not supplied."""
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


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
    on_missing: OnMissing = Field(
        OnMissing.WARN,
        description=(
            "What happens when the metric is not supplied: 'fail' fails the gate, "
            "'warn' marks the condition NOT_EVALUATED and degrades the gate to at "
            "best WARNING, 'skip' excludes the condition by policy. A missing "
            "metric never counts as a pass."
        ),
    )

    class Config:
        use_enum_values = True


class ConditionResult(BaseModel):
    """
    Evaluation result for a single gate condition.

    `passed` is tri-state: True (met), False (violated), None (NOT_EVALUATED —
    the metric was not supplied, so nothing can honestly be claimed).
    """
    condition: GateCondition = Field(..., description="The condition that was evaluated")
    actual_value: Union[float, str, None] = Field(
        None,
        description="The actual metric value at evaluation time"
    )
    passed: Optional[bool] = Field(
        True,
        description="True=met, False=violated, None=not evaluated (metric missing)"
    )
    message: str = Field("", description="Human-readable result message")

    class Config:
        use_enum_values = True

    @property
    def evaluated(self) -> bool:
        """Whether the condition was actually evaluated against a real value."""
        return self.passed is not None


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
        return sum(1 for r in self.condition_results if r.passed is True)

    @property
    def failed_count(self) -> int:
        """Count of conditions that failed (not-evaluated conditions excluded)."""
        return sum(1 for r in self.condition_results if r.passed is False)

    @property
    def not_evaluated_count(self) -> int:
        """Count of conditions that could not be evaluated (metric missing)."""
        return sum(1 for r in self.condition_results if r.passed is None)

    @property
    def not_evaluated_conditions(self) -> List[ConditionResult]:
        """Conditions that could not be evaluated because the metric was missing."""
        return [r for r in self.condition_results if r.passed is None]

    @property
    def error_failures(self) -> List[ConditionResult]:
        """Conditions that failed and have error_on_fail=True."""
        return [
            r for r in self.condition_results
            if r.passed is False and r.condition.error_on_fail
        ]

    @property
    def warning_failures(self) -> List[ConditionResult]:
        """Conditions that failed but have error_on_fail=False (warnings only)."""
        return [
            r for r in self.condition_results
            if r.passed is False and not r.condition.error_on_fail
        ]


# ---------------------------------------------------------------------------
# Differential ("clean as you code") gate models — Plan Bragi-06 / Heimdall-09
# ---------------------------------------------------------------------------


class FindingSeverity(str, Enum):
    """Normalized severity ladder for gate findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GateFinding(BaseModel):
    """
    A single analysis finding as seen by the differential gate.

    This is a tool-agnostic projection: any scanner's finding can be coerced
    into it (rule id + location + severity + optional confidence/snippet).
    """
    rule_id: str = Field(..., description="Identifier of the rule that produced the finding")
    file_path: str = Field(..., description="Path of the file containing the finding")
    line: Optional[int] = Field(None, description="1-based line number, if known")
    severity: FindingSeverity = Field(
        FindingSeverity.MEDIUM, description="Normalized severity"
    )
    confidence: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Probability the finding is a true positive (orthogonal to severity)",
    )
    message: str = Field("", description="Human-readable finding message")
    snippet: str = Field("", description="Source snippet at the finding site, if available")
    fingerprint: str = Field(
        "", description="Stable fingerprint (computed if empty)"
    )

    class Config:
        use_enum_values = True


class NewCodeDefinition(BaseModel):
    """How 'new code' is delimited for differential evaluation."""
    mode: str = Field(
        "reference_branch",
        description="One of: reference_branch, since_commit, days",
    )
    value: str = Field("main", description="Branch name, commit sha, or day count")

    class Config:
        use_enum_values = True


class BreakGlassRecord(BaseModel):
    """
    Audit record for an emergency gate bypass (`emergency-sec-bypass`).

    The bypass never silently passes: it is recorded, carries a mandatory
    reason and actor, and implies a follow-up remediation obligation.
    """
    actor: str = Field(..., description="Who invoked the bypass")
    reason: str = Field(..., description="Why the bypass was necessary")
    invoked_at: datetime = Field(default_factory=datetime.now)
    remediation_sla_hours: int = Field(48, description="Hours allowed for remediation")
    bypassed_findings: List[str] = Field(
        default_factory=list, description="Fingerprints of findings that were bypassed"
    )

    class Config:
        use_enum_values = True


class DifferentialGateResult(BaseModel):
    """Result of a fingerprint-based differential (new-code) gate evaluation."""
    status: GateStatus = Field(GateStatus.NOT_EVALUATED, description="Overall status")
    baseline_available: bool = Field(
        False, description="Whether a baseline fingerprint set was available"
    )
    baseline_branch: str = Field("", description="Branch the baseline was taken from")
    baseline_commit: str = Field("", description="Commit the baseline was captured at")
    new_findings: List[GateFinding] = Field(
        default_factory=list, description="Findings absent from the baseline"
    )
    blocking_findings: List[GateFinding] = Field(
        default_factory=list,
        description="New findings that block (HIGH/CRITICAL, confident, deterministic rule)",
    )
    advisory_findings: List[GateFinding] = Field(
        default_factory=list,
        description="New findings that do not block (lower severity/confidence, or flaky rule)",
    )
    suppressed_findings: List[GateFinding] = Field(
        default_factory=list, description="New findings silenced by a valid suppression"
    )
    preexisting_count: int = Field(
        0, description="Findings already in the baseline (never block; async burndown)"
    )
    legacy_touched_findings: List[GateFinding] = Field(
        default_factory=list,
        description=(
            "Pre-existing findings sitting on lines the PR modified — "
            "surfaced as warnings (DEEPTHINK_09); untouched legacy stays "
            "invisible in this channel"
        ),
    )
    changed_lines: int = Field(
        0, description="Total added/modified lines when a diff was supplied"
    )
    skipped_small_change: bool = Field(
        False,
        description=(
            "True when evaluation was skipped by policy because the change "
            "was below small_change_threshold_lines"
        ),
    )
    suppression_violations: List[str] = Field(
        default_factory=list,
        description="Invalid/expired suppression directives (each fails the gate)",
    )
    demoted_flaky_rules: List[str] = Field(
        default_factory=list,
        description="Rules stripped of blocking rights for proven non-determinism",
    )
    break_glass: Optional[BreakGlassRecord] = Field(
        None, description="Populated when the gate was bypassed via break-glass"
    )
    summary: str = Field("", description="Human-readable summary")
    evaluated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True


class QualityGateConfig(BaseModel):
    """Configuration for the quality gate evaluator."""
    gate: QualityGate = Field(..., description="The quality gate to evaluate")
    small_change_threshold_lines: int = Field(
        20,
        description="Skip gate evaluation if total changed lines is below this threshold"
    )

    class Config:
        use_enum_values = True
