"""
Freya Quality Gate

Configurable CI gate (DEEPTHINK_04's CI-pipeline persona): the exit
decision is an explicit, explainable boolean, e.g.
"FAIL IF new Blockers > 0 OR grade < B".
"""

from typing import Any, Dict, List, Optional

from Asgard.Freya.Scoring.models.scoring_models import (
    Finding,
    GateConfig,
    GateResult,
    GradedScore,
    QualityGrade,
    UniversalSeverity,
)

_GRADE_RANK = {
    QualityGrade.A: 4,
    QualityGrade.B: 3,
    QualityGrade.C: 2,
    QualityGrade.D: 1,
    QualityGrade.F: 0,
}


def _safe_count(value: Any) -> int:
    """Coerce a count to int; non-numeric values (e.g. mocks) become 0."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


class QualityGate:
    """Evaluates findings and grades against a gate configuration."""

    def __init__(self, config: Optional[GateConfig] = None):
        self.config = config or GateConfig()

    def evaluate(
        self,
        findings: List[Finding],
        graded: Optional[GradedScore] = None,
    ) -> GateResult:
        """Evaluate the gate over a list of findings (and optional grade)."""
        counts: Dict[str, int] = {s.value: 0 for s in UniversalSeverity}
        for finding in findings:
            counts[finding.severity.value] = counts.get(finding.severity.value, 0) + 1
        grade = graded.grade if graded is not None else None
        return self.evaluate_counts(counts, grade=grade)

    def evaluate_counts(
        self,
        severity_counts: Dict[str, int],
        grade: Optional[QualityGrade] = None,
    ) -> GateResult:
        """Evaluate the gate over pre-computed severity counts."""
        counts = {s.value: _safe_count(severity_counts.get(s.value, 0)) for s in UniversalSeverity}
        reasons: List[str] = []

        for severity in self.config.fail_on:
            count = counts.get(severity.value, 0)
            if count > 0:
                reasons.append(f"{count} {severity.value} finding(s) present (fail_on: {severity.value})")

        if self.config.min_grade is not None and grade is not None:
            if _GRADE_RANK[grade] < _GRADE_RANK[self.config.min_grade]:
                reasons.append(
                    f"grade {grade.value} is below required minimum {self.config.min_grade.value}"
                )

        if self.config.max_findings is not None:
            total = sum(counts.values())
            if total > self.config.max_findings:
                reasons.append(f"{total} findings exceed maximum of {self.config.max_findings}")

        return GateResult(
            passed=not reasons,
            reasons=reasons,
            severity_counts=counts,
        )
