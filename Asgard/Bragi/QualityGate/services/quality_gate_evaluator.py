"""
Heimdall Quality Gate Evaluator Service

Evaluates a QualityGate against a set of metric values extracted from
existing Heimdall analysis report objects.

The built-in "Asgard Way" gate provides a sensible default configuration
mirroring SonarQube's default quality gate behaviour.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

from Asgard.Bragi.QualityGate.models.quality_gate_models import (
    ConditionResult,
    GateOperator,
    GateStatus,
    MetricType,
    OnMissing,
    QualityGate,
    QualityGateResult,
)
from Asgard.Bragi.QualityGate.services._quality_gate_helpers import (
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
                on_missing = condition.on_missing
                if isinstance(on_missing, str):
                    on_missing = OnMissing(on_missing)
                if on_missing == OnMissing.SKIP:
                    message = (
                        f"Metric '{condition.metric}' not provided; "
                        "condition skipped by policy (on_missing=skip)"
                    )
                else:
                    message = (
                        f"[NOT_EVALUATED] Metric '{condition.metric}' was not "
                        "provided; the condition could not be verified"
                    )
                result = ConditionResult(
                    condition=condition,
                    actual_value=None,
                    passed=None,
                    message=message,
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

        status = self._compute_status(condition_results)

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

    def evaluate_differential(
        self,
        findings,
        *,
        project_path=None,
        base_branch: str = "main",
        head: str = "HEAD",
        sources=None,
        suppressions=None,
        flaky_rules=None,
        break_glass=None,
        baseline=None,
        mode: str = "baseline",
        changed_files=None,
        small_change_threshold_lines=None,
    ):
        """
        Evaluate the fingerprint-based differential ("clean as you code") gate.

        Only NEW HIGH/CRITICAL findings with Certain/Probable confidence from
        deterministic rules block; pre-existing baseline findings never do.
        With no baseline available the result is NOT_EVALUATED — never PASSED.

        Args:
            findings: scanner findings (any objects coercible to GateFinding)
            project_path: project root (locates the fingerprint baseline store)
            base_branch: reference branch whose baseline to diff against
            sources: optional {file_path: source_text} for AST anchoring
            suppressions: parsed SuppressionDirective list
            flaky_rules: rule ids demoted to warn-only (zero-flakiness policy)
            break_glass: optional BreakGlassRecord for an audited bypass
            baseline: explicit BranchBaseline (overrides store lookup)
            mode: "baseline" (fingerprints only) or "diff" — in diff mode the
                git-diff engine computes changed files/lines from
                `base_branch...head`, enabling the small-change threshold and
                the legacy-touched warning channel
            changed_files: pre-computed {path: [LineRange]} (overrides the
                git diff; implies diff behaviour)
            small_change_threshold_lines: below this many changed lines the
                gate returns PASSED (small change) with conditions skipped
                by explicit policy (QualityGateConfig wiring)

        Returns:
            DifferentialGateResult
        """
        from Asgard.Bragi.QualityGate.baseline_store import FingerprintBaselineStore
        from Asgard.Bragi.QualityGate.services._differential_engine import (
            DifferentialGateEngine,
        )
        from Asgard.Bragi.QualityGate.services._git_diff import git_changed_lines

        if baseline is None and project_path is not None:
            baseline = FingerprintBaselineStore(project_path).load(base_branch)

        if mode == "diff" and changed_files is None and project_path is not None:
            changed_files = git_changed_lines(
                Path(project_path), base=base_branch, head=head)

        engine = DifferentialGateEngine(flaky_rules=flaky_rules)
        return engine.evaluate(
            findings,
            baseline,
            sources=sources,
            suppressions=suppressions,
            break_glass=break_glass,
            changed_files=changed_files,
            small_change_threshold_lines=small_change_threshold_lines,
        )

    def _compute_status(self, condition_results: List[ConditionResult]) -> GateStatus:
        """
        Compute overall gate status with honest missing-metric semantics.

        - Any real failure of an error_on_fail condition => FAILED.
        - Any missing metric with on_missing=fail => FAILED.
        - Missing metrics with on_missing=warn degrade the gate: at best
          WARNING; if nothing at all was evaluated, NOT_EVALUATED.
        - on_missing=skip conditions are excluded by explicit policy and do
          not degrade the status.
        A missing scan input can never produce a clean PASSED.
        """
        def _on_missing(result: ConditionResult) -> OnMissing:
            value = result.condition.on_missing
            return OnMissing(value) if isinstance(value, str) else value

        has_error_failure = any(
            r.passed is False and r.condition.error_on_fail
            for r in condition_results
        )
        has_missing_fail = any(
            r.passed is None and _on_missing(r) == OnMissing.FAIL
            for r in condition_results
        )
        has_warning_failure = any(
            r.passed is False and not r.condition.error_on_fail
            for r in condition_results
        )
        has_missing_warn = any(
            r.passed is None and _on_missing(r) == OnMissing.WARN
            for r in condition_results
        )
        evaluated_any = any(r.passed is not None for r in condition_results)
        considered = [
            r for r in condition_results
            if not (r.passed is None and _on_missing(r) == OnMissing.SKIP)
        ]

        if has_error_failure or has_missing_fail:
            return GateStatus.FAILED
        if not evaluated_any and considered:
            return GateStatus.NOT_EVALUATED
        if has_warning_failure or has_missing_warn:
            return GateStatus.WARNING
        return GateStatus.PASSED

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
        not_evaluated = result.not_evaluated_count

        suffix = ""
        if not_evaluated:
            names = ", ".join(
                str(r.condition.metric) for r in result.not_evaluated_conditions
            )
            suffix = f"; {not_evaluated} condition(s) NOT EVALUATED ({names})"

        if result.status == GateStatus.PASSED:
            return (
                f"Gate '{result.gate_name}': PASSED "
                f"({passed}/{total} conditions met){suffix}"
            )
        elif result.status == GateStatus.NOT_EVALUATED:
            return (
                f"Gate '{result.gate_name}': NOT EVALUATED "
                f"({not_evaluated}/{total} conditions had no metric supplied; "
                f"missing scan input is not a pass){suffix}"
            )
        elif result.status == GateStatus.WARNING:
            return (
                f"Gate '{result.gate_name}': WARNING "
                f"({errors} error(s), {warnings} warning(s) out of {total} "
                f"conditions){suffix}"
            )
        else:
            return (
                f"Gate '{result.gate_name}': FAILED "
                f"({errors} error failure(s), {warnings} warning(s) out of "
                f"{total} conditions){suffix}"
            )
