"""
Freya Grade Calculator Tests

L0 tests for non-compensatory grade capping (DEEPTHINK_04).
"""

import pytest

from Asgard.Freya.Scoring.models.scoring_models import (
    Finding,
    QualityGrade,
    UniversalSeverity,
)
from Asgard.Freya.Scoring.services.grade_calculator import (
    GradeCalculator,
    score_to_grade,
    worst_severity,
)


def _finding(severity: UniversalSeverity, check_id: str = "check.x") -> Finding:
    return Finding(
        category="accessibility",
        severity=severity,
        check_id=check_id,
        message="msg",
    )


class TestScoreToGrade:
    @pytest.mark.parametrize("score,grade", [
        (100.0, QualityGrade.A), (90.0, QualityGrade.A),
        (89.9, QualityGrade.B), (80.0, QualityGrade.B),
        (79.9, QualityGrade.C), (70.0, QualityGrade.C),
        (69.9, QualityGrade.D), (60.0, QualityGrade.D),
        (59.9, QualityGrade.F), (0.0, QualityGrade.F),
    ])
    def test_bands(self, score, grade):
        assert score_to_grade(score) == grade


class TestWorstSeverity:
    def test_empty(self):
        assert worst_severity([]) is None

    def test_blocker_wins(self):
        findings = [
            _finding(UniversalSeverity.MINOR),
            _finding(UniversalSeverity.BLOCKER),
            _finding(UniversalSeverity.MAJOR),
        ]
        assert worst_severity(findings) == UniversalSeverity.BLOCKER


class TestGradeCalculator:
    def test_no_findings_perfect_scores(self):
        graded = GradeCalculator().calculate({"a": 100.0, "b": 100.0}, [])
        assert graded.base_score == 100.0
        assert graded.capped_score == 100.0
        assert graded.grade == QualityGrade.A
        assert graded.cap_reason is None

    def test_empty_category_scores_default_100(self):
        graded = GradeCalculator().calculate({}, [])
        assert graded.base_score == 100.0
        assert graded.grade == QualityGrade.A

    def test_blocker_caps_to_f(self):
        graded = GradeCalculator().calculate(
            {"a": 100.0}, [_finding(UniversalSeverity.BLOCKER, "wcag.2.1.2")]
        )
        assert graded.capped_score == 59.0
        assert graded.grade == QualityGrade.F
        assert "blocker" in graded.cap_reason
        assert "wcag.2.1.2" in graded.cap_reason

    def test_critical_caps_to_d(self):
        graded = GradeCalculator().calculate(
            {"a": 95.0}, [_finding(UniversalSeverity.CRITICAL)]
        )
        assert graded.capped_score == 69.0
        assert graded.grade == QualityGrade.D

    def test_major_caps_to_c(self):
        graded = GradeCalculator().calculate(
            {"a": 95.0}, [_finding(UniversalSeverity.MAJOR)]
        )
        assert graded.capped_score == 79.0
        assert graded.grade == QualityGrade.C

    def test_minor_does_not_cap(self):
        graded = GradeCalculator().calculate(
            {"a": 95.0}, [_finding(UniversalSeverity.MINOR)]
        )
        assert graded.capped_score == 95.0
        assert graded.grade == QualityGrade.A
        assert graded.cap_reason is None

    def test_cap_does_not_raise_low_base(self):
        graded = GradeCalculator().calculate(
            {"a": 30.0}, [_finding(UniversalSeverity.MAJOR)]
        )
        assert graded.capped_score == 30.0
        assert graded.grade == QualityGrade.F

    def test_worst_finding_dictates_ceiling(self):
        graded = GradeCalculator().calculate(
            {"a": 100.0},
            [_finding(UniversalSeverity.MAJOR), _finding(UniversalSeverity.BLOCKER)],
        )
        assert graded.grade == QualityGrade.F

    def test_weighted_mean(self):
        graded = GradeCalculator().calculate(
            {"a": 100.0, "b": 50.0}, [], weights={"a": 3.0, "b": 1.0}
        )
        assert graded.base_score == pytest.approx(87.5)

    def test_cap_reason_counts_findings(self):
        graded = GradeCalculator().calculate(
            {"a": 100.0},
            [
                _finding(UniversalSeverity.CRITICAL, "c.1"),
                _finding(UniversalSeverity.CRITICAL, "c.2"),
            ],
        )
        assert graded.cap_reason.startswith("2 criticals")

    @pytest.mark.parametrize("severity", list(UniversalSeverity))
    def test_capped_never_exceeds_base(self, severity):
        for base in (0.0, 42.0, 59.0, 69.0, 79.0, 100.0):
            graded = GradeCalculator().calculate({"a": base}, [_finding(severity)])
            assert graded.capped_score <= graded.base_score

    def test_grade_monotonic_in_capped_score(self):
        calc = GradeCalculator()
        rank = {QualityGrade.F: 0, QualityGrade.D: 1, QualityGrade.C: 2,
                QualityGrade.B: 3, QualityGrade.A: 4}
        previous = -1
        for score in range(0, 101, 5):
            grade = score_to_grade(float(score))
            assert rank[grade] >= previous
            previous = rank[grade]

    def test_category_scores_passthrough(self):
        scores = {"accessibility": 80.0, "visual": 90.0}
        graded = GradeCalculator().calculate(scores, [])
        assert graded.category_scores == scores
