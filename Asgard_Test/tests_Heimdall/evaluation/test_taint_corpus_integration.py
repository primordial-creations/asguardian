"""
Integration test: run the plan-10 harness (dedup -> AST-bbox match ->
metrics -> gate) over the *existing* taint benchmark corpus (plan 04),
converting its ``manifest.yml`` TP/FP fixture cases into ground truth via
``ground_truth_from_taint_manifest`` rather than duplicating fixture
authoring. This exercises the harness end-to-end on real scanner output
(``TaintAnalyzer``) instead of only synthetic golden data.
"""

from pathlib import Path

import yaml

from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer, TaintConfig
from Asgard.Heimdall.evaluation.corpus import (
    finding_from_taint_flow,
    ground_truth_from_taint_manifest,
)
from Asgard.Heimdall.evaluation.gate import evaluate_gate
from Asgard.Heimdall.evaluation.runner import run_corpus

CORPUS_DIR = Path(__file__).parent.parent / "benchmarks" / "corpus" / "taint"
MANIFEST = yaml.safe_load((CORPUS_DIR / "manifest.yml").read_text())


def test_taint_corpus_precision_recall_via_harness():
    config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
    report = TaintAnalyzer(config=config).scan(CORPUS_DIR)

    ground_truth = ground_truth_from_taint_manifest(CORPUS_DIR, MANIFEST["cases"])
    assert ground_truth, "expected at least one TP fixture in the taint corpus"

    findings = [finding_from_taint_flow(flow) for flow in report.flows]
    total_loc = sum(
        len((CORPUS_DIR / f).read_text(encoding="utf-8").splitlines())
        for f in {c["file"] for c in MANIFEST["cases"]}
    )

    metrics = run_corpus(findings, ground_truth, total_loc=total_loc)

    # The corpus is specifically engineered so every tp_*.py fixture has a
    # real flow and every fp_*.py fixture is clean at default reporting
    # confidence -- so recall should be strong (the harness must not
    # silently drop legitimate matches via an overly strict CWE/span
    # match), though not necessarily perfect since flow CWE tagging and
    # fixture CWE annotations are independent sources of truth.
    assert metrics.recall >= 0.5, (
        f"harness recall {metrics.recall:.2f} unexpectedly low on a corpus "
        f"plan 04 asserts is fully detected -- check span/CWE matching"
    )

    # Gate evaluation must run without error on real (non-synthetic) input.
    result = evaluate_gate(metrics, profile="B")
    assert isinstance(result.passed, bool)
    assert isinstance(result.reasons, list)
