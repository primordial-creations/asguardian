"""
Tests for gate epistemic honesty (Plan Bragi-06 §3.1, Phase A).

A missing metric must never silently pass: conditions become NOT_EVALUATED
(tri-state passed=None), `on_missing` controls escalation, and determinism
annotations warn against hard-blocking heuristic metrics.
"""

from Asgard.Bragi.QualityGate.models.quality_gate_models import (
    METRIC_DETERMINISM,
    GateCondition,
    GateOperator,
    GateStatus,
    MetricDeterminism,
    MetricType,
    OnMissing,
    QualityGate,
)
from Asgard.Bragi.QualityGate.services._quality_gate_helpers import (
    build_asgard_main_gate,
    build_asgard_pr_gate,
    build_asgard_way_gate,
    validate_gate_determinism,
)
from Asgard.Bragi.QualityGate.services.quality_gate_evaluator import (
    QualityGateEvaluator,
)


def gate_with(metric, on_missing=OnMissing.WARN, error_on_fail=True,
              operator=GateOperator.EQUALS, threshold=0.0):
    return QualityGate(
        name="honesty-test",
        conditions=[
            GateCondition(
                metric=metric,
                operator=operator,
                threshold=threshold,
                error_on_fail=error_on_fail,
                on_missing=on_missing,
            )
        ],
    )


class TestNotEvaluatedSemantics:
    def test_missing_metric_condition_is_tri_state_none(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(gate_with(MetricType.CRITICAL_VULNERABILITIES), {})
        assert result.condition_results[0].passed is None
        assert result.condition_results[0].evaluated is False

    def test_security_condition_without_report_is_not_passed(self):
        """The named regression: a gate whose security scan failed to run
        must not report PASSED."""
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(gate_with(MetricType.SECURITY_RATING), {})
        assert result.status != GateStatus.PASSED and result.status != "passed"
        assert result.status == GateStatus.NOT_EVALUATED or result.status == "not_evaluated"

    def test_missing_metric_message_mentions_not_evaluated(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(gate_with(MetricType.SECURITY_RATING), {})
        assert "NOT_EVALUATED" in result.condition_results[0].message

    def test_summary_lists_unevaluated_conditions(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(gate_with(MetricType.SECURITY_RATING), {})
        assert "NOT EVALUATED" in result.summary
        assert "security_rating" in result.summary

    def test_partial_metrics_degrade_to_warning(self):
        """Passing conditions plus a missing warn-level metric => WARNING, not PASSED."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="partial",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
                GateCondition(
                    metric=MetricType.SECURITY_RATING,
                    operator=GateOperator.LESS_THAN_OR_EQUAL,
                    threshold="B",
                    error_on_fail=True,
                    on_missing=OnMissing.WARN,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 0})
        assert result.status == GateStatus.WARNING or result.status == "warning"
        assert result.not_evaluated_count == 1

    def test_on_missing_fail_fails_the_gate(self):
        """'security scan must have run' is expressible via on_missing=fail."""
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(
            gate_with(MetricType.SECURITY_RATING, on_missing=OnMissing.FAIL), {}
        )
        assert result.status == GateStatus.FAILED or result.status == "failed"

    def test_on_missing_skip_does_not_degrade(self):
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="skip",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
                GateCondition(
                    metric=MetricType.COMMENT_DENSITY,
                    operator=GateOperator.GREATER_THAN_OR_EQUAL,
                    threshold=10.0,
                    error_on_fail=False,
                    on_missing=OnMissing.SKIP,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 0})
        assert result.status == GateStatus.PASSED or result.status == "passed"

    def test_real_failure_still_wins_over_missing(self):
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="fail-wins",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
                GateCondition(
                    metric=MetricType.SECURITY_RATING,
                    operator=GateOperator.LESS_THAN_OR_EQUAL,
                    threshold="B",
                    error_on_fail=True,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 2})
        assert result.status == GateStatus.FAILED or result.status == "failed"

    def test_not_evaluated_counts_and_properties(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(gate_with(MetricType.SECURITY_RATING), {})
        assert result.not_evaluated_count == 1
        assert len(result.not_evaluated_conditions) == 1
        assert result.passed_count == 0
        assert result.failed_count == 0


class TestDeterminismAnnotations:
    def test_every_metric_has_a_determinism_class(self):
        for metric in MetricType:
            assert metric in METRIC_DETERMINISM

    def test_counting_metrics_are_facts(self):
        assert METRIC_DETERMINISM[MetricType.CRITICAL_VULNERABILITIES] == MetricDeterminism.FACT
        assert METRIC_DETERMINISM[MetricType.NEW_BLOCKER_ISSUES] == MetricDeterminism.FACT
        assert METRIC_DETERMINISM[MetricType.SCAN_COMPLETENESS] == MetricDeterminism.FACT

    def test_rating_metrics_are_heuristic(self):
        assert METRIC_DETERMINISM[MetricType.SECURITY_RATING] == MetricDeterminism.HEURISTIC
        assert METRIC_DETERMINISM[MetricType.TECHNICAL_DEBT_HOURS] == MetricDeterminism.HEURISTIC

    def test_validate_warns_on_blocking_heuristic(self):
        gate = gate_with(MetricType.SECURITY_RATING, error_on_fail=True,
                         operator=GateOperator.LESS_THAN_OR_EQUAL, threshold="B")
        warnings = validate_gate_determinism(gate)
        assert len(warnings) == 1
        assert "HEURISTIC" in warnings[0]

    def test_validate_clean_on_blocking_fact(self):
        gate = gate_with(MetricType.CRITICAL_VULNERABILITIES, error_on_fail=True)
        assert validate_gate_determinism(gate) == []

    def test_validate_clean_on_warning_heuristic(self):
        gate = gate_with(MetricType.SECURITY_RATING, error_on_fail=False,
                         operator=GateOperator.LESS_THAN_OR_EQUAL, threshold="B")
        assert validate_gate_determinism(gate) == []


class TestBuiltInGates:
    def test_asgard_way_still_importable_and_named(self):
        gate = build_asgard_way_gate()
        assert gate.name == "Asgard Way"

    def test_asgard_main_is_alias_of_asgard_way(self):
        assert build_asgard_main_gate().model_dump() == build_asgard_way_gate().model_dump()

    def test_asgard_pr_gate_blocks_only_on_facts(self):
        gate = build_asgard_pr_gate()
        assert validate_gate_determinism(gate) == []

    def test_asgard_pr_gate_fails_when_scan_missing(self):
        """asgard-pr requires its inputs: skipped scan fails, never passes."""
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(build_asgard_pr_gate(), {})
        assert result.status == GateStatus.FAILED or result.status == "failed"

    def test_asgard_pr_gate_passes_on_clean_new_code(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(build_asgard_pr_gate(), {
            MetricType.NEW_BLOCKER_ISSUES: 0,
            MetricType.SCAN_COMPLETENESS: 1.0,
            MetricType.DEBT_DELTA_MINUTES: -5.0,
        })
        assert result.status == GateStatus.PASSED or result.status == "passed"

    def test_asgard_pr_gate_fails_on_new_blockers(self):
        evaluator = QualityGateEvaluator()
        result = evaluator.evaluate(build_asgard_pr_gate(), {
            MetricType.NEW_BLOCKER_ISSUES: 2,
            MetricType.SCAN_COMPLETENESS: 1.0,
            MetricType.DEBT_DELTA_MINUTES: 0.0,
        })
        assert result.status == GateStatus.FAILED or result.status == "failed"
