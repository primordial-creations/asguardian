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
    METRIC_DETERMINISM,
    BreakGlassRecord,
    ConditionResult,
    DifferentialGateResult,
    FindingSeverity,
    GateCondition,
    GateFinding,
    GateOperator,
    GateStatus,
    MetricDeterminism,
    MetricType,
    NewCodeDefinition,
    OnMissing,
    QualityGate,
    QualityGateConfig,
    QualityGateResult,
)
from Asgard.Bragi.QualityGate.baseline_store import (
    BranchBaseline,
    FingerprintBaselineStore,
)
from Asgard.Bragi.QualityGate.fingerprint import (
    compute_fingerprint,
    fingerprint_with_anchor,
)
from Asgard.Bragi.QualityGate.suppressions import (
    SuppressionDirective,
    SuppressionKind,
    lint_suppressions,
    parse_suppressions,
)
from Asgard.Bragi.QualityGate.services._differential_engine import (
    DifferentialGateEngine,
    coerce_finding,
    verify_scan_determinism,
)
from Asgard.Bragi.QualityGate.services._git_diff import (
    LineRange,
    git_changed_lines,
    parse_unified_diff,
    total_changed_lines,
)
from Asgard.Bragi.QualityGate.services._hotspot_ranker import (
    Hotspot,
    HotspotRanker,
    RootCauseGroup,
    git_churn,
)
from Asgard.Bragi.QualityGate.services._project_state_store import (
    ProjectState,
    ProjectStateStore,
    ReadOnlyStateError,
)
from Asgard.Bragi.QualityGate.services._quality_gate_helpers import (
    build_asgard_main_gate,
    build_asgard_pr_gate,
    build_asgard_way_gate,
    validate_gate_determinism,
)
from Asgard.Bragi.QualityGate.services.quality_gate_evaluator import QualityGateEvaluator

__all__ = [
    "METRIC_DETERMINISM",
    "BranchBaseline",
    "BreakGlassRecord",
    "ConditionResult",
    "DifferentialGateEngine",
    "DifferentialGateResult",
    "FindingSeverity",
    "FingerprintBaselineStore",
    "GateCondition",
    "GateFinding",
    "GateOperator",
    "GateStatus",
    "Hotspot",
    "HotspotRanker",
    "LineRange",
    "MetricDeterminism",
    "MetricType",
    "NewCodeDefinition",
    "OnMissing",
    "QualityGate",
    "QualityGateConfig",
    "QualityGateEvaluator",
    "ProjectState",
    "ProjectStateStore",
    "QualityGateResult",
    "ReadOnlyStateError",
    "RootCauseGroup",
    "SuppressionDirective",
    "SuppressionKind",
    "build_asgard_main_gate",
    "build_asgard_pr_gate",
    "build_asgard_way_gate",
    "coerce_finding",
    "compute_fingerprint",
    "fingerprint_with_anchor",
    "git_changed_lines",
    "git_churn",
    "lint_suppressions",
    "parse_suppressions",
    "parse_unified_diff",
    "total_changed_lines",
    "validate_gate_determinism",
    "verify_scan_determinism",
]
