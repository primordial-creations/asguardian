"""
Heimdall QualityGate - Quality Gate Evaluation System

Evaluates a named set of conditions (a "gate") against analysis results.
Conditions may be hard failures (error_on_fail=True) or soft warnings.

The built-in 'Asgard Way' gate mirrors SonarQube's recommended defaults.

Usage:
    from Asgard.Bragi.QualityGate import QualityGateEvaluator, MetricType

    evaluator = QualityGateEvaluator()
    gate = evaluator.get_default_gate()

    result = evaluator.evaluate(gate, {
        MetricType.SECURITY_RATING: "A",
        MetricType.CRITICAL_VULNERABILITIES: 0,
        MetricType.COMMENT_DENSITY: 15.0,
    })
    print(f"Gate status: {result.status}")

    # Or evaluate directly from report objects:
    result = evaluator.evaluate_from_reports(
        gate,
        ratings=project_ratings,
        documentation_report=doc_report,
        security_report=security_report,
    )
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

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

__all__ = [
    "ConditionResult",
    "GateCondition",
    "GateOperator",
    "GateStatus",
    "MetricType",
    "QualityGate",
    "QualityGateConfig",
    "QualityGateEvaluator",
    "QualityGateResult",
]
