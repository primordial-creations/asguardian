"""
Heimdall Quality Gate Evaluator Service

Evaluates a QualityGate against a set of metric values extracted from
existing Heimdall analysis report objects.

The built-in "Asgard Way" gate provides a sensible default configuration
mirroring SonarQube's default quality gate behaviour.
"""

from datetime import datetime
from typing import Dict, List, Union

from Asgard.Heimdall.QualityGate.models.quality_gate_models import (
    ConditionResult,
    GateOperator,
    GateStatus,
    MetricType,
    QualityGate,
    QualityGateResult,
)
from Asgard.Heimdall.QualityGate.services._quality_gate_helpers import (
    build_asgard_way_gate,
    compare_values,
    extract_metrics_from_reports,
)


class QualityGateEvaluator:
    """
    Evaluates a QualityGate against a dictionary of metric values or report objects.

    Usage:
        evaluator = QualityGateEvaluator()
        gate = evaluator.get_default_gate()

        # Evaluate from raw metrics
        result = evaluator.evaluate(gate, {
            MetricType.SECURITY_RATING: "A",
            MetricType.CRITICAL_VULNERABILITIES: 0,
            MetricType.COMMENT_DENSITY: 12.5,
        })
        print(f"Gate status: {result.status}")

        # Evaluate from reports
        result = evaluator.evaluate_from_reports(
            gate,
            ratings=project_ratings,
            documentation_report=doc_report,
            security_report=security_report,
        )
    """

    def get_default_gate(self) -> QualityGate:
        """
        Return the built-in 'Asgard Way' quality gate.

        Returns:
            QualityGate configured with the Asgard Way conditions
        """
        return build_asgard_way_gate()

    def evaluate(
        self,
        gate: QualityGate,
        metrics_dict: Dict[MetricType, Union[float, str]],
        scan_path: str = "",
    ) -> QualityGateResult:
        """
        Evaluate a gate against a dictionary of raw metric values.

        Args:
            gate: The QualityGate to evaluate
            metrics_dict: Mapping from MetricType to its current value
            scan_path: Optional scan path string for the result metadata

        Returns:
            QualityGateResult with per-condition results and overall status
        """
        condition_results: List[ConditionResult] = []

        for condition in gate.conditions:
            metric_key = condition.metric
            if isinstance(metric_key, str):
                metric_key = MetricType(metric_key)

            actual_value = metrics_dict.get(metric_key)

            if actual_value is None:
                result = ConditionResult(
                    condition=condition,
                    actual_value=None,
                    passed=True,
                    message=f"Metric '{condition.metric}' not provided; condition skipped",
                )
            else:
                operator = condition.operator
                if isinstance(operator, str):
                    operator = GateOperator(operator)

                passed = compare_values(actual_value, operator, condition.threshold)
                message = self._build_condition_message(condition, actual_value, passed)

                result = ConditionResult(
                    condition=condition,
                    actual_value=actual_value,
                    passed=passed,
                    message=message,
                )

            condition_results.append(result)

        has_error_failure = any(
            not r.passed and r.condition.error_on_fail for r in condition_results
        )
        has_warning_failure = any(
            not r.passed and not r.condition.error_on_fail for r in condition_results
        )

        if has_error_failure:
            status = GateStatus.FAILED
        elif has_warning_failure:
            status = GateStatus.WARNING
        else:
            status = GateStatus.PASSED

        gate_result = QualityGateResult(
            gate_name=gate.name,
            status=status,
            condition_results=condition_results,
            scan_path=scan_path,
            evaluated_at=datetime.now(),
        )

        gate_result.summary = self._build_summary(gate_result)

        return gate_result

    def evaluate_from_reports(
        self,
        gate: QualityGate,
        *,
        ratings=None,
        duplication_result=None,
        documentation_report=None,
        security_report=None,
        debt_report=None,
        scan_path: str = "",
    ) -> QualityGateResult:
        """
        Evaluate a gate by extracting metrics from Heimdall report objects.

        Args:
            gate: The QualityGate to evaluate
            ratings: Optional ProjectRatings from RatingsCalculator
            duplication_result: Optional DuplicationResult from DuplicationDetector
            documentation_report: Optional DocumentationReport from DocumentationScanner
            security_report: Optional SecurityReport from StaticSecurityService
            debt_report: Optional DebtReport from TechnicalDebtAnalyzer
            scan_path: Optional scan path string for result metadata

        Returns:
            QualityGateResult with per-condition results and overall status
        """
        metrics = extract_metrics_from_reports(
            ratings=ratings,
            duplication_result=duplication_result,
            documentation_report=documentation_report,
            security_report=security_report,
            debt_report=debt_report,
        )
        return self.evaluate(gate, metrics, scan_path=scan_path)

    def _build_condition_message(
        self,
        condition,
        actual_value: Union[float, str],
        passed: bool,
    ) -> str:
        """Build a human-readable message for a condition result."""
        operator_display = {
            GateOperator.LESS_THAN: "<",
            GateOperator.LESS_THAN_OR_EQUAL: "<=",
            GateOperator.GREATER_THAN: ">",
            GateOperator.GREATER_THAN_OR_EQUAL: ">=",
            GateOperator.EQUALS: "==",
            GateOperator.NOT_EQUALS: "!=",
        }
        op = condition.operator
        if isinstance(op, str):
            op = GateOperator(op)
        op_str = operator_display.get(op, str(op))

        status = "PASS" if passed else "FAIL"
        return (
            f"[{status}] {condition.metric}: "
            f"{actual_value} {op_str} {condition.threshold}"
        )

    def _build_summary(self, result: QualityGateResult) -> str:
        """Build a summary string for the gate result."""
        total = len(result.condition_results)
        passed = result.passed_count
        errors = len(result.error_failures)
        warnings = len(result.warning_failures)

        if result.status == GateStatus.PASSED:
            return f"Gate '{result.gate_name}': PASSED ({passed}/{total} conditions met)"
        elif result.status == GateStatus.WARNING:
            return (
                f"Gate '{result.gate_name}': WARNING "
                f"({errors} error(s), {warnings} warning(s) out of {total} conditions)"
            )
        else:
            return (
                f"Gate '{result.gate_name}': FAILED "
                f"({errors} error failure(s), {warnings} warning(s) out of {total} conditions)"
            )
