"""
Freya Grade Calculator

Non-compensatory letter grading: the base score is a weighted mean kept
only for sorting/trending; the headline grade is capped by the highest
unresolved severity (DEEPTHINK_04: "the highest-severity unresolved
issue dictates the ceiling").
"""

from typing import Dict, List, Optional

from Asgard.Freya.Scoring.models.scoring_models import (
    SEVERITY_ORDER,
    Finding,
    GradedScore,
    QualityGrade,
    UniversalSeverity,
)

#: Score ceiling imposed by the highest unresolved severity.
SEVERITY_CAPS: Dict[UniversalSeverity, float] = {
    UniversalSeverity.BLOCKER: 59.0,   # -> F
    UniversalSeverity.CRITICAL: 69.0,  # -> D at best
    UniversalSeverity.MAJOR: 79.0,     # -> C at best
}

#: Grade bands over the capped score.
GRADE_BANDS = [
    (90.0, QualityGrade.A),
    (80.0, QualityGrade.B),
    (70.0, QualityGrade.C),
    (60.0, QualityGrade.D),
]


def score_to_grade(score: float) -> QualityGrade:
    """Map a 0-100 score to a letter grade."""
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return QualityGrade.F


def worst_severity(findings: List[Finding]) -> Optional[UniversalSeverity]:
    """Return the most severe severity among findings, or None."""
    present = {f.severity for f in findings}
    for severity in SEVERITY_ORDER:
        if severity in present:
            return severity
    return None


class GradeCalculator:
    """Computes capped letter grades from category scores and findings."""

    def calculate(
        self,
        category_scores: Dict[str, float],
        findings: List[Finding],
        weights: Optional[Dict[str, float]] = None,
    ) -> GradedScore:
        """
        Calculate a graded score.

        Args:
            category_scores: Per-category 0-100 scores
            findings: Normalized findings (only unresolved failures)
            weights: Optional per-category weights (default: equal)

        Returns:
            GradedScore with capping applied
        """
        base_score = self._weighted_mean(category_scores, weights)

        cap_severity = worst_severity(findings)
        cap_reason: Optional[str] = None
        capped_score = base_score

        if cap_severity is not None and cap_severity in SEVERITY_CAPS:
            cap = SEVERITY_CAPS[cap_severity]
            if cap < capped_score:
                capped_score = cap
            count = sum(1 for f in findings if f.severity == cap_severity)
            exemplar = next(f for f in findings if f.severity == cap_severity)
            plural = "s" if count != 1 else ""
            cap_reason = f"{count} {cap_severity.value}{plural}: {exemplar.check_id}"

        return GradedScore(
            base_score=base_score,
            capped_score=capped_score,
            grade=score_to_grade(capped_score),
            cap_reason=cap_reason,
            category_scores=dict(category_scores),
        )

    @staticmethod
    def _weighted_mean(
        category_scores: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Weighted mean of category scores; 100.0 when empty."""
        if not category_scores:
            return 100.0
        if not weights:
            return sum(category_scores.values()) / len(category_scores)
        total_weight = 0.0
        total = 0.0
        for category, score in category_scores.items():
            weight = weights.get(category, 1.0)
            total_weight += weight
            total += score * weight
        if total_weight <= 0:
            return sum(category_scores.values()) / len(category_scores)
        return total / total_weight
