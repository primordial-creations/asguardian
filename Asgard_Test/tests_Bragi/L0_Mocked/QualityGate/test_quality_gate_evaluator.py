"""
Tests for Heimdall Quality Gate Evaluator Service

Unit tests for quality gate evaluation covering all metric types,
operators, gate statuses, and condition result fields.
"""

import pytest
from types import SimpleNamespace

from Asgard.Bragi.QualityGate.models.quality_gate_models import (
    ConditionResult,
    GateCondition,
    GateOperator,
    GateStatus,
    MetricType,
    QualityGate,
    QualityGateConfig,
    QualityGateResult,
)
from Asgard.Bragi.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator


class TestQualityGateEvaluator:
    """Tests for QualityGateEvaluator class."""

    def test_get_default_gate_returns_quality_gate(self):
        """Test that get_default_gate returns a QualityGate instance."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()

        assert isinstance(gate, QualityGate)

    def test_get_default_gate_has_name(self):
        """Test that the default gate has a name."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()

        assert gate.name != ""
        assert gate.name == "Asgard Way"

    def test_get_default_gate_has_at_least_one_condition(self):
        """Test that the default gate has at least one condition."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()

        assert len(gate.conditions) >= 1

    def test_get_default_gate_contains_security_condition(self):
        """Test that the default gate includes a security rating condition."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()

        metric_values = [c.metric for c in gate.conditions]
        assert MetricType.SECURITY_RATING in metric_values or "security_rating" in metric_values

    def test_get_default_gate_contains_critical_vulnerabilities_condition(self):
        """Test that the default gate includes a critical vulnerabilities condition."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()

        metric_values = [c.metric for c in gate.conditions]
        assert (
            MetricType.CRITICAL_VULNERABILITIES in metric_values
            or "critical_vulnerabilities" in metric_values
        )

    def test_evaluate_empty_metrics_is_not_evaluated(self):
        """Missing all metrics must never produce a passing gate (epistemic honesty)."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()
        result = evaluator.evaluate(gate, {})

        assert isinstance(result, QualityGateResult)
        # No metric was supplied -> every condition is NOT_EVALUATED, and the
        # gate reports NOT_EVALUATED rather than silently passing.
        assert result.status == GateStatus.NOT_EVALUATED or result.status == "not_evaluated"
        assert result.not_evaluated_count == len(gate.conditions)

    def test_evaluate_all_passing_returns_passed(self):
        """Test that all conditions passing results in GateStatus.PASSED."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="test-gate",
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
        metrics = {
            MetricType.CRITICAL_VULNERABILITIES: 0,
            MetricType.SECURITY_RATING: "A",
        }
        result = evaluator.evaluate(gate, metrics)

        assert result.status == GateStatus.PASSED or result.status == "passed"

    def test_evaluate_one_error_condition_fails_returns_failed(self):
        """Test that one failing error condition results in GateStatus.FAILED."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="test-gate",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
            ],
        )
        metrics = {
            MetricType.CRITICAL_VULNERABILITIES: 5,
        }
        result = evaluator.evaluate(gate, metrics)

        assert result.status == GateStatus.FAILED or result.status == "failed"

    def test_evaluate_warning_only_failure_returns_warning(self):
        """Test that a failing warning-only condition results in GateStatus.WARNING."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="test-gate",
            conditions=[
                GateCondition(
                    metric=MetricType.COMMENT_DENSITY,
                    operator=GateOperator.GREATER_THAN_OR_EQUAL,
                    threshold=10.0,
                    error_on_fail=False,
                ),
            ],
        )
        metrics = {
            MetricType.COMMENT_DENSITY: 5.0,
        }
        result = evaluator.evaluate(gate, metrics)

        assert result.status == GateStatus.WARNING or result.status == "warning"

    def test_evaluate_returns_quality_gate_result(self):
        """Test that evaluate returns a QualityGateResult instance."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()
        result = evaluator.evaluate(gate, {})

        assert isinstance(result, QualityGateResult)

    def test_evaluate_gate_name_preserved_in_result(self):
        """Test that the gate name is stored in the result."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="my-custom-gate",
            conditions=[],
        )
        result = evaluator.evaluate(gate, {})

        assert result.gate_name == "my-custom-gate"

    def test_evaluate_condition_results_count_matches_conditions(self):
        """Test that one ConditionResult is produced per gate condition."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="count-test",
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
                ),
            ],
        )
        result = evaluator.evaluate(gate, {
            MetricType.CRITICAL_VULNERABILITIES: 0,
            MetricType.COMMENT_DENSITY: 12.0,
        })

        assert len(result.condition_results) == 2

    def test_evaluate_scan_path_recorded(self):
        """Test that scan_path is stored in the result."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(name="g", conditions=[])
        result = evaluator.evaluate(gate, {}, scan_path="/some/path")

        assert result.scan_path == "/some/path"

    def test_evaluate_evaluated_at_set(self):
        """Test that evaluated_at is populated."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(name="g", conditions=[])
        result = evaluator.evaluate(gate, {})

        assert result.evaluated_at is not None


class TestConditionResultFields:
    """Tests for ConditionResult fields."""

    def test_condition_result_passed_true_when_condition_met(self):
        """Test ConditionResult.passed is True when condition is satisfied."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="g",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 0})

        cond_result = result.condition_results[0]
        assert cond_result.passed is True

    def test_condition_result_passed_false_when_condition_not_met(self):
        """Test ConditionResult.passed is False when condition is violated."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="g",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 3})

        cond_result = result.condition_results[0]
        assert cond_result.passed is False

    def test_condition_result_actual_value_stored(self):
        """Test that the actual metric value is stored in ConditionResult."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="g",
            conditions=[
                GateCondition(
                    metric=MetricType.COMMENT_DENSITY,
                    operator=GateOperator.GREATER_THAN_OR_EQUAL,
                    threshold=10.0,
                    error_on_fail=False,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.COMMENT_DENSITY: 7.5})

        cond_result = result.condition_results[0]
        assert cond_result.actual_value == 7.5

    def test_condition_result_none_actual_when_metric_absent(self):
        """Test that actual_value is None when the metric is not provided."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="g",
            conditions=[
                GateCondition(
                    metric=MetricType.COMMENT_DENSITY,
                    operator=GateOperator.GREATER_THAN_OR_EQUAL,
                    threshold=10.0,
                    error_on_fail=False,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {})

        cond_result = result.condition_results[0]
        assert cond_result.actual_value is None

    def test_condition_result_message_non_empty(self):
        """Test that ConditionResult.message is populated for evaluated conditions."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="g",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 0})

        cond_result = result.condition_results[0]
        assert cond_result.message != ""

    def test_condition_result_condition_field_preserved(self):
        """Test that the original condition is accessible via ConditionResult.condition."""
        evaluator = QualityGateEvaluator()
        cond = GateCondition(
            metric=MetricType.CRITICAL_VULNERABILITIES,
            operator=GateOperator.EQUALS,
            threshold=0.0,
            error_on_fail=True,
            description="No critical vulns",
        )
        gate = QualityGate(name="g", conditions=[cond])
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 0})

        cond_result = result.condition_results[0]
        assert cond_result.condition.description == "No critical vulns"

    def test_condition_result_threshold_accessible(self):
        """Test that threshold is accessible from ConditionResult."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="g",
            conditions=[
                GateCondition(
                    metric=MetricType.COMMENT_DENSITY,
                    operator=GateOperator.GREATER_THAN_OR_EQUAL,
                    threshold=15.0,
                    error_on_fail=False,
                ),
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.COMMENT_DENSITY: 20.0})

        cond_result = result.condition_results[0]
        assert cond_result.condition.threshold == 15.0


class TestGateOperators:
    """Tests for each GateOperator value in gate evaluation."""

    def _single_condition_gate(
        self,
        metric: MetricType,
        operator: GateOperator,
        threshold,
        error_on_fail: bool = True,
    ) -> QualityGate:
        """Build a single-condition gate for operator testing."""
        return QualityGate(
            name="op-test",
            conditions=[
                GateCondition(
                    metric=metric,
                    operator=operator,
                    threshold=threshold,
                    error_on_fail=error_on_fail,
                )
            ],
        )

    def test_less_than_passes_when_actual_is_lower(self):
        """Test LESS_THAN passes when actual < threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.CYCLOMATIC_COMPLEXITY_MAX, GateOperator.LESS_THAN, 10.0
        )
        result = evaluator.evaluate(gate, {MetricType.CYCLOMATIC_COMPLEXITY_MAX: 9.0})
        assert result.condition_results[0].passed is True

    def test_less_than_fails_when_actual_equals_threshold(self):
        """Test LESS_THAN fails when actual == threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.CYCLOMATIC_COMPLEXITY_MAX, GateOperator.LESS_THAN, 10.0
        )
        result = evaluator.evaluate(gate, {MetricType.CYCLOMATIC_COMPLEXITY_MAX: 10.0})
        assert result.condition_results[0].passed is False

    def test_less_than_or_equal_passes_when_equal(self):
        """Test LESS_THAN_OR_EQUAL passes when actual == threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.DUPLICATION_PERCENTAGE, GateOperator.LESS_THAN_OR_EQUAL, 3.0
        )
        result = evaluator.evaluate(gate, {MetricType.DUPLICATION_PERCENTAGE: 3.0})
        assert result.condition_results[0].passed is True

    def test_less_than_or_equal_fails_when_greater(self):
        """Test LESS_THAN_OR_EQUAL fails when actual > threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.DUPLICATION_PERCENTAGE, GateOperator.LESS_THAN_OR_EQUAL, 3.0
        )
        result = evaluator.evaluate(gate, {MetricType.DUPLICATION_PERCENTAGE: 3.5})
        assert result.condition_results[0].passed is False

    def test_greater_than_passes_when_actual_is_higher(self):
        """Test GREATER_THAN passes when actual > threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.COMMENT_DENSITY, GateOperator.GREATER_THAN, 10.0
        )
        result = evaluator.evaluate(gate, {MetricType.COMMENT_DENSITY: 11.0})
        assert result.condition_results[0].passed is True

    def test_greater_than_fails_when_actual_equals_threshold(self):
        """Test GREATER_THAN fails when actual == threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.COMMENT_DENSITY, GateOperator.GREATER_THAN, 10.0
        )
        result = evaluator.evaluate(gate, {MetricType.COMMENT_DENSITY: 10.0})
        assert result.condition_results[0].passed is False

    def test_greater_than_or_equal_passes_when_equal(self):
        """Test GREATER_THAN_OR_EQUAL passes when actual == threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.API_DOCUMENTATION_COVERAGE,
            GateOperator.GREATER_THAN_OR_EQUAL,
            70.0,
        )
        result = evaluator.evaluate(gate, {MetricType.API_DOCUMENTATION_COVERAGE: 70.0})
        assert result.condition_results[0].passed is True

    def test_greater_than_or_equal_fails_when_less(self):
        """Test GREATER_THAN_OR_EQUAL fails when actual < threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.API_DOCUMENTATION_COVERAGE,
            GateOperator.GREATER_THAN_OR_EQUAL,
            70.0,
        )
        result = evaluator.evaluate(gate, {MetricType.API_DOCUMENTATION_COVERAGE: 60.0})
        assert result.condition_results[0].passed is False

    def test_equals_passes_when_matching(self):
        """Test EQUALS passes when actual == threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.CRITICAL_VULNERABILITIES, GateOperator.EQUALS, 0.0
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 0})
        assert result.condition_results[0].passed is True

    def test_equals_fails_when_not_matching(self):
        """Test EQUALS fails when actual != threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.CRITICAL_VULNERABILITIES, GateOperator.EQUALS, 0.0
        )
        result = evaluator.evaluate(gate, {MetricType.CRITICAL_VULNERABILITIES: 1})
        assert result.condition_results[0].passed is False

    def test_not_equals_passes_when_different(self):
        """Test NOT_EQUALS passes when actual != threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.NAMING_VIOLATIONS, GateOperator.NOT_EQUALS, 0.0
        )
        result = evaluator.evaluate(gate, {MetricType.NAMING_VIOLATIONS: 5})
        assert result.condition_results[0].passed is True

    def test_not_equals_fails_when_matching(self):
        """Test NOT_EQUALS fails when actual == threshold."""
        evaluator = QualityGateEvaluator()
        gate = self._single_condition_gate(
            MetricType.NAMING_VIOLATIONS, GateOperator.NOT_EQUALS, 0.0
        )
        result = evaluator.evaluate(gate, {MetricType.NAMING_VIOLATIONS: 0})
        assert result.condition_results[0].passed is False


class TestLetterRatingOperators:
    """Tests for letter rating (A-E) comparisons in gate evaluation."""

    def _make_rating_gate(
        self,
        metric: MetricType,
        operator: GateOperator,
        threshold: str,
        error_on_fail: bool = True,
    ) -> QualityGate:
        """Build a single rating condition gate."""
        return QualityGate(
            name="rating-test",
            conditions=[
                GateCondition(
                    metric=metric,
                    operator=operator,
                    threshold=threshold,
                    error_on_fail=error_on_fail,
                )
            ],
        )

    def test_security_rating_a_passes_lte_b(self):
        """Test security rating A passes a <= B condition."""
        evaluator = QualityGateEvaluator()
        gate = self._make_rating_gate(
            MetricType.SECURITY_RATING, GateOperator.LESS_THAN_OR_EQUAL, "B"
        )
        result = evaluator.evaluate(gate, {MetricType.SECURITY_RATING: "A"})
        assert result.condition_results[0].passed is True

    def test_security_rating_c_fails_lte_b(self):
        """Test security rating C fails a <= B condition."""
        evaluator = QualityGateEvaluator()
        gate = self._make_rating_gate(
            MetricType.SECURITY_RATING, GateOperator.LESS_THAN_OR_EQUAL, "B"
        )
        result = evaluator.evaluate(gate, {MetricType.SECURITY_RATING: "C"})
        assert result.condition_results[0].passed is False

    def test_reliability_rating_b_passes_lte_c(self):
        """Test reliability rating B passes a <= C condition."""
        evaluator = QualityGateEvaluator()
        gate = self._make_rating_gate(
            MetricType.RELIABILITY_RATING, GateOperator.LESS_THAN_OR_EQUAL, "C"
        )
        result = evaluator.evaluate(gate, {MetricType.RELIABILITY_RATING: "B"})
        assert result.condition_results[0].passed is True

    def test_reliability_rating_d_fails_lte_c(self):
        """Test reliability rating D fails a <= C condition."""
        evaluator = QualityGateEvaluator()
        gate = self._make_rating_gate(
            MetricType.RELIABILITY_RATING, GateOperator.LESS_THAN_OR_EQUAL, "C"
        )
        result = evaluator.evaluate(gate, {MetricType.RELIABILITY_RATING: "D"})
        assert result.condition_results[0].passed is False

    def test_maintainability_rating_equals_a(self):
        """Test maintainability rating equals A condition."""
        evaluator = QualityGateEvaluator()
        gate = self._make_rating_gate(
            MetricType.MAINTAINABILITY_RATING, GateOperator.EQUALS, "A"
        )
        result = evaluator.evaluate(gate, {MetricType.MAINTAINABILITY_RATING: "A"})
        assert result.condition_results[0].passed is True

    def test_rating_e_is_worst(self):
        """Test that E rating fails a <= C condition."""
        evaluator = QualityGateEvaluator()
        gate = self._make_rating_gate(
            MetricType.SECURITY_RATING, GateOperator.LESS_THAN_OR_EQUAL, "C"
        )
        result = evaluator.evaluate(gate, {MetricType.SECURITY_RATING: "E"})
        assert result.condition_results[0].passed is False


class TestCustomGates:
    """Tests for custom gate creation and evaluation."""

    def test_custom_gate_single_condition(self):
        """Test custom gate with a single condition evaluates correctly."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="strict-debt-gate",
            description="Custom gate for strict debt control",
            conditions=[
                GateCondition(
                    metric=MetricType.TECHNICAL_DEBT_HOURS,
                    operator=GateOperator.LESS_THAN,
                    threshold=50.0,
                    error_on_fail=True,
                    description="Technical debt must be under 50 hours",
                )
            ],
        )
        result = evaluator.evaluate(gate, {MetricType.TECHNICAL_DEBT_HOURS: 30.0})

        assert result.status == GateStatus.PASSED or result.status == "passed"
        assert result.gate_name == "strict-debt-gate"

    def test_custom_gate_multiple_conditions_all_pass(self):
        """Test custom gate with multiple conditions all passing."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="multi-cond-gate",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
                GateCondition(
                    metric=MetricType.HIGH_VULNERABILITIES,
                    operator=GateOperator.LESS_THAN_OR_EQUAL,
                    threshold=5.0,
                    error_on_fail=True,
                ),
                GateCondition(
                    metric=MetricType.COMMENT_DENSITY,
                    operator=GateOperator.GREATER_THAN_OR_EQUAL,
                    threshold=10.0,
                    error_on_fail=False,
                ),
            ],
        )
        metrics = {
            MetricType.CRITICAL_VULNERABILITIES: 0,
            MetricType.HIGH_VULNERABILITIES: 3,
            MetricType.COMMENT_DENSITY: 15.0,
        }
        result = evaluator.evaluate(gate, metrics)

        assert result.status == GateStatus.PASSED or result.status == "passed"
        assert result.passed_count == 3

    def test_custom_gate_mixed_pass_fail(self):
        """Test custom gate where some conditions pass and one error condition fails."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="mixed-gate",
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
                ),
            ],
        )
        metrics = {
            MetricType.CRITICAL_VULNERABILITIES: 2,
            MetricType.COMMENT_DENSITY: 20.0,
        }
        result = evaluator.evaluate(gate, metrics)

        assert result.status == GateStatus.FAILED or result.status == "failed"
        assert result.failed_count == 1

    def test_quality_gate_result_error_failures_property(self):
        """Test error_failures property returns only error-level failures."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="err-warn-gate",
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
                ),
            ],
        )
        metrics = {
            MetricType.CRITICAL_VULNERABILITIES: 1,
            MetricType.COMMENT_DENSITY: 5.0,
        }
        result = evaluator.evaluate(gate, metrics)

        assert len(result.error_failures) == 1
        assert len(result.warning_failures) == 1

    def test_quality_gate_result_warning_failures_property(self):
        """Test warning_failures property returns only warning-level failures."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="warn-only-gate",
            conditions=[
                GateCondition(
                    metric=MetricType.COMMENT_DENSITY,
                    operator=GateOperator.GREATER_THAN_OR_EQUAL,
                    threshold=10.0,
                    error_on_fail=False,
                ),
            ],
        )
        metrics = {MetricType.COMMENT_DENSITY: 5.0}
        result = evaluator.evaluate(gate, metrics)

        assert len(result.warning_failures) == 1
        assert len(result.error_failures) == 0

    def test_gate_with_no_conditions_passes(self):
        """Test that a gate with no conditions always passes."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(name="empty-gate", conditions=[])
        result = evaluator.evaluate(gate, {})

        assert result.status == GateStatus.PASSED or result.status == "passed"

    def test_evaluate_summary_populated(self):
        """Test that summary field is populated after evaluation."""
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()
        result = evaluator.evaluate(gate, {})

        assert result.summary != ""

    def test_passed_count_and_failed_count(self):
        """Test passed_count and failed_count properties."""
        evaluator = QualityGateEvaluator()
        gate = QualityGate(
            name="count-test",
            conditions=[
                GateCondition(
                    metric=MetricType.CRITICAL_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
                GateCondition(
                    metric=MetricType.HIGH_VULNERABILITIES,
                    operator=GateOperator.EQUALS,
                    threshold=0.0,
                    error_on_fail=True,
                ),
            ],
        )
        metrics = {
            MetricType.CRITICAL_VULNERABILITIES: 0,
            MetricType.HIGH_VULNERABILITIES: 3,
        }
        result = evaluator.evaluate(gate, metrics)

        assert result.passed_count == 1
        assert result.failed_count == 1


class TestAllMetricTypes:
    """Tests that all defined MetricType values can be used in conditions."""

    def test_all_metric_types_accepted(self):
        """Test that a gate condition can be created for every MetricType."""
        evaluator = QualityGateEvaluator()
        numeric_types = {
            MetricType.MAINTAINABILITY_INDEX,
            MetricType.CYCLOMATIC_COMPLEXITY_MAX,
            MetricType.DUPLICATION_PERCENTAGE,
            MetricType.COMMENT_DENSITY,
            MetricType.API_DOCUMENTATION_COVERAGE,
            MetricType.CRITICAL_VULNERABILITIES,
            MetricType.HIGH_VULNERABILITIES,
            MetricType.TECHNICAL_DEBT_HOURS,
            MetricType.NAMING_VIOLATIONS,
        }
        rating_types = {
            MetricType.SECURITY_RATING,
            MetricType.RELIABILITY_RATING,
            MetricType.MAINTAINABILITY_RATING,
        }

        for metric in numeric_types:
            gate = QualityGate(
                name=f"test-{metric}",
                conditions=[
                    GateCondition(
                        metric=metric,
                        operator=GateOperator.GREATER_THAN_OR_EQUAL,
                        threshold=0.0,
                        error_on_fail=True,
                    )
                ],
            )
            result = evaluator.evaluate(gate, {metric: 5.0})
            assert len(result.condition_results) == 1

        for metric in rating_types:
            gate = QualityGate(
                name=f"test-{metric}",
                conditions=[
                    GateCondition(
                        metric=metric,
                        operator=GateOperator.LESS_THAN_OR_EQUAL,
                        threshold="C",
                        error_on_fail=True,
                    )
                ],
            )
            result = evaluator.evaluate(gate, {metric: "A"})
            assert len(result.condition_results) == 1
