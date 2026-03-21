"""
Heimdall Quality Gate - helper functions and default gate definition.

Standalone utilities for gate evaluation: value comparison, default gate
construction, metric extraction from report objects.
"""

from typing import Dict, Union

from Asgard.Heimdall.QualityGate.models.quality_gate_models import (
    GateCondition,
    GateOperator,
    MetricType,
    QualityGate,
)


# Letter rating ordering for comparison (lower ordinal = better)
RATING_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}


def build_asgard_way_gate() -> QualityGate:
    """Build and return the built-in 'Asgard Way' quality gate."""
    return QualityGate(
        name="Asgard Way",
        description=(
            "Default quality gate inspired by SonarQube's recommended gate. "
            "Hard-fails on critical security/reliability/maintainability thresholds; "
            "warns on documentation and duplication."
        ),
        conditions=[
            GateCondition(
                metric=MetricType.SECURITY_RATING,
                operator=GateOperator.LESS_THAN_OR_EQUAL,
                threshold="B",
                error_on_fail=True,
                description="Security rating must be B or better",
            ),
            GateCondition(
                metric=MetricType.RELIABILITY_RATING,
                operator=GateOperator.LESS_THAN_OR_EQUAL,
                threshold="C",
                error_on_fail=True,
                description="Reliability rating must be C or better",
            ),
            GateCondition(
                metric=MetricType.MAINTAINABILITY_RATING,
                operator=GateOperator.LESS_THAN_OR_EQUAL,
                threshold="C",
                error_on_fail=True,
                description="Maintainability rating must be C or better",
            ),
            GateCondition(
                metric=MetricType.DUPLICATION_PERCENTAGE,
                operator=GateOperator.LESS_THAN_OR_EQUAL,
                threshold=3.0,
                error_on_fail=False,
                description="Code duplication should be 3% or less",
            ),
            GateCondition(
                metric=MetricType.COMMENT_DENSITY,
                operator=GateOperator.GREATER_THAN_OR_EQUAL,
                threshold=10.0,
                error_on_fail=False,
                description="Comment density should be 10% or more",
            ),
            GateCondition(
                metric=MetricType.API_DOCUMENTATION_COVERAGE,
                operator=GateOperator.GREATER_THAN_OR_EQUAL,
                threshold=70.0,
                error_on_fail=False,
                description="Public API documentation coverage should be 70% or more",
            ),
            GateCondition(
                metric=MetricType.CRITICAL_VULNERABILITIES,
                operator=GateOperator.EQUALS,
                threshold=0.0,
                error_on_fail=True,
                description="No critical security vulnerabilities are permitted",
            ),
        ],
    )


def compare_values(
    actual: Union[float, str],
    operator: GateOperator,
    threshold: Union[float, str],
) -> bool:
    """
    Compare actual vs threshold using the given operator.

    Letter rating strings (A-E) are compared by their ordinal (A=1 best, E=5 worst).
    Numeric values are compared directly.
    """
    if isinstance(threshold, str) and threshold.upper() in RATING_ORDER:
        actual_str = str(actual).upper() if actual is not None else "E"
        actual_ord = RATING_ORDER.get(actual_str, 5)
        threshold_ord = RATING_ORDER.get(threshold.upper(), 5)
        if operator == GateOperator.LESS_THAN:
            return actual_ord < threshold_ord
        elif operator == GateOperator.LESS_THAN_OR_EQUAL:
            return actual_ord <= threshold_ord
        elif operator == GateOperator.GREATER_THAN:
            return actual_ord > threshold_ord
        elif operator == GateOperator.GREATER_THAN_OR_EQUAL:
            return actual_ord >= threshold_ord
        elif operator == GateOperator.EQUALS:
            return actual_ord == threshold_ord
        elif operator == GateOperator.NOT_EQUALS:
            return actual_ord != threshold_ord
        return False

    try:
        actual_num = float(actual) if actual is not None else 0.0
        threshold_num = float(threshold)
    except (TypeError, ValueError):
        return False

    if operator == GateOperator.LESS_THAN:
        return actual_num < threshold_num
    elif operator == GateOperator.LESS_THAN_OR_EQUAL:
        return actual_num <= threshold_num
    elif operator == GateOperator.GREATER_THAN:
        return actual_num > threshold_num
    elif operator == GateOperator.GREATER_THAN_OR_EQUAL:
        return actual_num >= threshold_num
    elif operator == GateOperator.EQUALS:
        return actual_num == threshold_num
    elif operator == GateOperator.NOT_EQUALS:
        return actual_num != threshold_num
    return False


def extract_metrics_from_reports(
    ratings=None,
    duplication_result=None,
    documentation_report=None,
    security_report=None,
    debt_report=None,
) -> Dict[MetricType, Union[float, str]]:
    """
    Extract metric values from Heimdall report objects.

    Returns a dict mapping MetricType to its current value.
    """
    metrics: Dict[MetricType, Union[float, str]] = {}

    if ratings is not None:
        maintainability = getattr(ratings, "maintainability", None)
        reliability = getattr(ratings, "reliability", None)
        security_dim = getattr(ratings, "security", None)

        if maintainability is not None:
            metrics[MetricType.MAINTAINABILITY_RATING] = str(
                getattr(maintainability, "rating", "A")
            )
        if reliability is not None:
            metrics[MetricType.RELIABILITY_RATING] = str(
                getattr(reliability, "rating", "A")
            )
        if security_dim is not None:
            metrics[MetricType.SECURITY_RATING] = str(
                getattr(security_dim, "rating", "A")
            )

    if duplication_result is not None:
        dup_pct = getattr(duplication_result, "duplication_percentage", None)
        if dup_pct is None:
            total_lines = getattr(duplication_result, "total_lines", 0) or 0
            duplicated_lines = getattr(duplication_result, "total_duplicated_lines", 0) or 0
            if total_lines > 0:
                dup_pct = (duplicated_lines / total_lines) * 100.0
            else:
                dup_pct = 0.0
        metrics[MetricType.DUPLICATION_PERCENTAGE] = float(dup_pct)

    if documentation_report is not None:
        comment_density = getattr(documentation_report, "overall_comment_density", None)
        api_coverage = getattr(documentation_report, "overall_api_coverage", None)
        if comment_density is not None:
            metrics[MetricType.COMMENT_DENSITY] = float(comment_density)
        if api_coverage is not None:
            metrics[MetricType.API_DOCUMENTATION_COVERAGE] = float(api_coverage)

    if security_report is not None:
        critical_count = 0
        high_count = 0

        for attr in ("vulnerability_findings", "vulnerabilities", "findings"):
            findings = getattr(security_report, attr, None) or []
            if findings:
                for finding in findings:
                    sev = str(getattr(finding, "severity", "")).lower()
                    if sev == "critical":
                        critical_count += 1
                    elif sev == "high":
                        high_count += 1
                break

        vuln_report = getattr(security_report, "vulnerability_report", None)
        if vuln_report is not None:
            for attr in ("findings", "vulnerabilities"):
                findings = getattr(vuln_report, attr, None) or []
                if findings:
                    for finding in findings:
                        sev = str(getattr(finding, "severity", "")).lower()
                        if sev == "critical":
                            critical_count += 1
                        elif sev == "high":
                            high_count += 1
                    break

        metrics[MetricType.CRITICAL_VULNERABILITIES] = float(critical_count)
        metrics[MetricType.HIGH_VULNERABILITIES] = float(high_count)

    if debt_report is not None:
        debt_hours = getattr(debt_report, "total_debt_hours", None)
        if debt_hours is not None:
            metrics[MetricType.TECHNICAL_DEBT_HOURS] = float(debt_hours)

    return metrics
