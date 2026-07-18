"""
Freya Scoring Models Tests

L0 tests for the universal severity/grading models.
"""

import pytest

from Asgard.Freya.Scoring.models.scoring_models import (
    SEVERITY_ORDER,
    Finding,
    GateConfig,
    GateResult,
    GradedScore,
    QualityGrade,
    UniversalSeverity,
)


class TestUniversalSeverity:
    def test_four_values(self):
        assert {s.value for s in UniversalSeverity} == {"blocker", "critical", "major", "minor"}

    def test_order_worst_first(self):
        assert SEVERITY_ORDER[0] == UniversalSeverity.BLOCKER
        assert SEVERITY_ORDER[-1] == UniversalSeverity.MINOR


class TestFinding:
    def test_defaults(self):
        finding = Finding(
            category="accessibility",
            severity=UniversalSeverity.MAJOR,
            check_id="wcag.1.4.3",
            message="Insufficient contrast",
        )
        assert finding.url is None
        assert finding.selector is None
        assert finding.source_severity is None
        assert finding.needs_review is False

    def test_serialization_roundtrip(self):
        finding = Finding(
            category="security",
            severity=UniversalSeverity.BLOCKER,
            check_id="security.csp.missing",
            message="No CSP",
            needs_review=True,
        )
        restored = Finding.model_validate_json(finding.model_dump_json())
        assert restored == finding


class TestGradedScore:
    def test_fields(self):
        graded = GradedScore(
            base_score=90.0,
            capped_score=59.0,
            grade=QualityGrade.F,
            cap_reason="1 blocker: security.csp.missing",
            category_scores={"security": 40.0},
        )
        assert graded.grade == QualityGrade.F
        assert graded.capped_score <= graded.base_score


class TestGateConfig:
    def test_default_fail_on(self):
        config = GateConfig()
        assert config.fail_on == [UniversalSeverity.BLOCKER, UniversalSeverity.CRITICAL]
        assert config.min_grade is None
        assert config.max_findings is None


class TestGateResult:
    def test_defaults(self):
        result = GateResult(passed=True)
        assert result.reasons == []
        assert result.severity_counts == {}
