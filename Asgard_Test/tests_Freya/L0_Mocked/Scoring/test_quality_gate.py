"""
Freya Quality Gate Tests

L0 tests for configurable CI gate evaluation.
"""

from unittest.mock import Mock

import pytest

from Asgard.Freya.Scoring.models.scoring_models import (
    Finding,
    GateConfig,
    GradedScore,
    QualityGrade,
    UniversalSeverity,
)
from Asgard.Freya.Scoring.services.quality_gate import QualityGate


def _finding(severity: UniversalSeverity) -> Finding:
    return Finding(category="security", severity=severity, check_id="c", message="m")


def _graded(grade: QualityGrade) -> GradedScore:
    return GradedScore(base_score=80.0, capped_score=80.0, grade=grade)


class TestDefaultGate:
    def test_passes_empty(self):
        result = QualityGate().evaluate([])
        assert result.passed
        assert result.reasons == []

    def test_fails_on_blocker(self):
        result = QualityGate().evaluate([_finding(UniversalSeverity.BLOCKER)])
        assert not result.passed
        assert any("blocker" in r for r in result.reasons)

    def test_fails_on_critical(self):
        result = QualityGate().evaluate([_finding(UniversalSeverity.CRITICAL)])
        assert not result.passed

    def test_passes_on_major_minor(self):
        result = QualityGate().evaluate([
            _finding(UniversalSeverity.MAJOR),
            _finding(UniversalSeverity.MINOR),
        ])
        assert result.passed
        assert result.severity_counts["major"] == 1


class TestGateMatrix:
    @pytest.mark.parametrize("fail_on,severity,expected_pass", [
        ([UniversalSeverity.BLOCKER], UniversalSeverity.CRITICAL, True),
        ([UniversalSeverity.BLOCKER], UniversalSeverity.BLOCKER, False),
        ([UniversalSeverity.MINOR], UniversalSeverity.MINOR, False),
        ([], UniversalSeverity.BLOCKER, True),
    ])
    def test_fail_on_combinations(self, fail_on, severity, expected_pass):
        gate = QualityGate(GateConfig(fail_on=fail_on))
        assert gate.evaluate([_finding(severity)]).passed is expected_pass

    def test_min_grade(self):
        gate = QualityGate(GateConfig(fail_on=[], min_grade=QualityGrade.B))
        assert not gate.evaluate([], graded=_graded(QualityGrade.C)).passed
        assert gate.evaluate([], graded=_graded(QualityGrade.B)).passed
        assert gate.evaluate([], graded=_graded(QualityGrade.A)).passed

    def test_max_findings(self):
        gate = QualityGate(GateConfig(fail_on=[], max_findings=1))
        findings = [_finding(UniversalSeverity.MINOR)] * 2
        assert not gate.evaluate(findings).passed


class TestEvaluateCounts:
    def test_counts_path(self):
        result = QualityGate().evaluate_counts({"critical": 2})
        assert not result.passed
        assert result.severity_counts["critical"] == 2

    def test_non_numeric_counts_are_zero(self):
        """Mock/None values must never crash the gate - they count as 0."""
        result = QualityGate().evaluate_counts({"blocker": Mock(), "critical": None})
        assert result.passed
        assert result.severity_counts["blocker"] == 0

    def test_float_counts_coerced(self):
        result = QualityGate().evaluate_counts({"critical": 1.0})
        assert not result.passed
