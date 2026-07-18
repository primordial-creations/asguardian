"""
Heimdall evaluation & benchmarking harness (Heimdall plan 10).

Pure-measurement machinery layered on top of the existing per-rule
benchmark fixtures (``Asgard_Test/tests_Heimdall/benchmarks/``) and the
``confidence`` field already present on ``VulnerabilityFinding`` /
``TaintFlow``. This package never modifies scanner behaviour -- it only
reads scanner output, scores it against ground truth, and (optionally)
fits a calibration map that callers may apply to raw confidence scores.

Modules:
    spans        -- AST bounding-box representation + spatial matching.
    corpus       -- ground-truth / reported-finding dataclasses + JSON
                     manifest loading (fixtures + CVE holdout references).
    dedup        -- semantic-instance dedup by (file, sink node, CWE).
    metrics      -- precision/recall/F-beta/alert-density computation.
    calibration  -- reliability diagrams, isotonic regression, Brier score.
    runner       -- corpus orchestration: match -> dedup -> metrics.
    gate         -- CI acceptance-threshold + non-regression gate.
    report       -- human-readable + JSON report rendering.
"""

from Asgard.Heimdall.evaluation.spans import ASTSpan, spans_overlap
from Asgard.Heimdall.evaluation.corpus import GroundTruthInstance, ReportedFinding
from Asgard.Heimdall.evaluation.dedup import dedup_findings
from Asgard.Heimdall.evaluation.metrics import (
    MatchResult,
    match_findings,
    precision,
    recall,
    f_beta,
    alert_density,
)
from Asgard.Heimdall.evaluation.calibration import (
    reliability_diagram,
    isotonic_regression,
    IsotonicCalibrator,
    brier_score,
)
from Asgard.Heimdall.evaluation.runner import CorpusMetrics, run_corpus
from Asgard.Heimdall.evaluation.gate import GateResult, evaluate_gate, ACCEPTANCE_PROFILES

__all__ = [
    "ASTSpan",
    "spans_overlap",
    "GroundTruthInstance",
    "ReportedFinding",
    "dedup_findings",
    "MatchResult",
    "match_findings",
    "precision",
    "recall",
    "f_beta",
    "alert_density",
    "reliability_diagram",
    "isotonic_regression",
    "IsotonicCalibrator",
    "brier_score",
    "CorpusMetrics",
    "run_corpus",
    "GateResult",
    "evaluate_gate",
    "ACCEPTANCE_PROFILES",
]
