"""
Integration test for the plan-10 "make the corpus real" deliverable:
running the actual scanners (TaintAnalyzer + DispatchEngine) over the
vendored, hand-authored fixture corpus under
``Asgard_Test/tests_Heimdall/benchmarks/corpus/`` and asserting the
harness produces a non-trivial precision/recall/F-beta report plus an
isotonic calibration map with a bounded Brier score.

This is deliberately NOT the same thing as ``test_taint_corpus_precision_recall_via_harness``
(which only exercises the Python sub-corpus): it drives
``vendored_corpus.scan_vendored_corpus`` / ``evaluate_vendored_corpus``,
which combine Python + JS + TS + Java into one honestly-labeled report --
the same code path ``heimdall eval corpus`` uses.
"""

from pathlib import Path

from Asgard.Heimdall.evaluation.calibration import IsotonicCalibrator, brier_score
from Asgard.Heimdall.evaluation.gate import evaluate_gate
from Asgard.Heimdall.evaluation.vendored_corpus import (
    CORPUS_LABEL,
    evaluate_vendored_corpus,
    scan_vendored_corpus,
)

CORPUS_ROOT = Path(__file__).parent.parent / "benchmarks" / "corpus"


def test_vendored_corpus_scan_covers_python_at_minimum():
    """Python (ast-backed, no optional grammar dependency) must always be
    scanned -- the multilang sub-corpora degrade gracefully when the
    optional tree-sitter grammars aren't installed, but Python has no such
    dependency, so its coverage is unconditional."""
    scan = scan_vendored_corpus(CORPUS_ROOT)
    assert "python" in scan.languages_scanned
    assert scan.case_count >= 16, "expected at least the 16 vendored Python cases"
    assert scan.ground_truth, "expected at least one Python TP fixture as ground truth"
    # CWE breadth: SQLi, command injection, XSS-adjacent, path traversal,
    # deserialization, and open-redirect (the SSRF stand-in) must all be
    # represented -- see manifest.yml comments for why open redirect
    # substitutes for a dedicated SSRF sink.
    for cwe in ("CWE-89", "CWE-78", "CWE-22", "CWE-95", "CWE-601"):
        assert cwe in scan.cwe_coverage, f"expected {cwe} coverage in the vendored corpus"


def test_vendored_corpus_metrics_are_non_trivial():
    """The harness must report real (not NaN/zero-division) precision and
    recall on the vendored corpus -- the fixture pairs are engineered so
    every TP fixture yields exactly one flow and every FP fixture yields
    none, so a correctly-wired harness should score strongly here. This
    corpus is honestly labeled (CORPUS_LABEL) as vendored fixtures, not a
    CVE holdout -- the numbers are a harness/regression sanity check, not
    a real-world precision/recall claim."""
    metrics, scan = evaluate_vendored_corpus(CORPUS_ROOT)

    assert metrics.tp > 0, "expected at least one true positive on the vendored corpus"
    assert 0.0 <= metrics.precision <= 1.0
    assert 0.0 <= metrics.recall <= 1.0
    # The corpus is purpose-built to be cleanly separable, so precision and
    # recall should both be strong (not merely non-zero) -- a harness bug
    # (bad dedup/span-matching) would show up as a big drop here.
    assert metrics.precision >= 0.7, f"unexpectedly low precision {metrics.precision:.3f}"
    assert metrics.recall >= 0.5, f"unexpectedly low recall {metrics.recall:.3f}"

    brier = brier_score(metrics.calibration_records)
    assert 0.0 <= brier <= 1.0

    assert "vendored fixture corpus" in CORPUS_LABEL
    assert "not a CVE holdout" in CORPUS_LABEL or "NOT a CVE holdout" in CORPUS_LABEL


def test_vendored_corpus_produces_calibration_map():
    """The isotonic calibrator must fit a non-empty, monotonic raw ->
    calibrated map from the vendored corpus' (confidence, is_tp) records."""
    metrics, _ = evaluate_vendored_corpus(CORPUS_ROOT)
    assert metrics.calibration_records, "expected calibration records from the vendored corpus"

    calibrator = IsotonicCalibrator().fit(
        [c[0] for c in metrics.calibration_records],
        [c[1] for c in metrics.calibration_records],
    )
    calibration_map = calibrator.to_map()
    assert calibration_map, "expected a non-empty fitted calibration map"

    # Monotonic non-decreasing in the calibrated (y) value.
    ys = [y for _x, y in calibration_map]
    assert ys == sorted(ys)


def test_vendored_corpus_gate_runs_without_error():
    """Gate evaluation must run cleanly against the combined multi-language
    vendored-corpus metrics (mirrors the Python-only integration test but
    covers the JS/TS/Java sink categories too)."""
    metrics, _ = evaluate_vendored_corpus(CORPUS_ROOT)
    result = evaluate_gate(metrics, profile="B")
    assert isinstance(result.passed, bool)
    assert isinstance(result.reasons, list)
