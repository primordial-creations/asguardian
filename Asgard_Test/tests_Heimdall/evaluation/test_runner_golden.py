"""
Golden metric test (plan 10 "Testing / Bootstrapping"): a synthetic
corpus with known TP/FP/FN counts must yield exactly the expected
precision/recall/F-beta, validating the runner before trusting it on
real scanner output.
"""

import math

from Asgard.Heimdall.evaluation.corpus import GroundTruthInstance, ReportedFinding
from Asgard.Heimdall.evaluation.metrics import f_beta
from Asgard.Heimdall.evaluation.spans import ASTSpan
from Asgard.Heimdall.evaluation.runner import run_corpus


def _gt(id_, file_path, line, cwe):
    return GroundTruthInstance(
        id=id_,
        file_path=file_path,
        cwe=cwe,
        span=ASTSpan(file_path=file_path, start_line=line, end_line=line),
    )


def _finding(file_path, line, cwe, confidence, sink=None):
    return ReportedFinding(
        file_path=file_path, line=line, cwe=cwe, confidence=confidence, sink_node_id=sink or str(line)
    )


def test_golden_precision_recall_fbeta():
    # 3 ground-truth instances; 2 findings hit them (2 TP, 1 FN), plus
    # 1 finding that hits nothing (1 FP). precision = 2/3, recall = 2/3.
    ground_truth = [
        _gt("gt1", "a.py", 10, "CWE-89"),
        _gt("gt2", "a.py", 20, "CWE-89"),
        _gt("gt3", "a.py", 30, "CWE-78"),
    ]
    findings = [
        _finding("a.py", 10, "CWE-89", 0.9),
        _finding("a.py", 20, "CWE-89", 0.6),
        _finding("a.py", 99, "CWE-89", 0.4),  # matches nothing -> FP
    ]

    metrics = run_corpus(findings, ground_truth, total_loc=1000)

    assert metrics.tp == 2
    assert metrics.fp == 1
    assert metrics.fn == 1
    assert math.isclose(metrics.precision, 2 / 3, rel_tol=1e-9)
    assert math.isclose(metrics.recall, 2 / 3, rel_tol=1e-9)

    expected_f_half = f_beta(2 / 3, 2 / 3, beta=0.5)
    expected_f_two = f_beta(2 / 3, 2 / 3, beta=2.0)
    assert math.isclose(metrics.f_half, expected_f_half, rel_tol=1e-9)
    assert math.isclose(metrics.f_two, expected_f_two, rel_tol=1e-9)
    # Equal precision/recall means all F-beta variants equal that value.
    assert math.isclose(metrics.f_half, 2 / 3, rel_tol=1e-9)


def test_golden_alert_density():
    ground_truth = [_gt("gt1", "a.py", 10, "CWE-89")]
    findings = [
        _finding("a.py", 10, "CWE-89", 0.9),
        _finding("a.py", 500, "CWE-89", 0.3),  # FP
        _finding("a.py", 501, "CWE-89", 0.3),  # FP
    ]
    metrics = run_corpus(findings, ground_truth, total_loc=1000)
    assert metrics.fp == 2
    # 2 FP / 1000 LOC * 10000 = 20.0 per 10k LOC
    assert math.isclose(metrics.alert_density, 20.0, rel_tol=1e-9)


def test_golden_perfect_score():
    ground_truth = [_gt("gt1", "a.py", 10, "CWE-89"), _gt("gt2", "a.py", 20, "CWE-89")]
    findings = [_finding("a.py", 10, "CWE-89", 1.0), _finding("a.py", 20, "CWE-89", 1.0)]
    metrics = run_corpus(findings, ground_truth, total_loc=100)
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.fp == 0
    assert metrics.fn == 0


def test_golden_zero_findings_zero_gt_is_perfect_by_convention():
    metrics = run_corpus([], [], total_loc=100)
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.tp == metrics.fp == metrics.fn == 0


def test_dedup_applied_before_matching_avoids_double_counted_tp():
    # Two raw alerts on the same sink+cwe must collapse to 1 TP, not 2.
    ground_truth = [_gt("gt1", "a.py", 10, "CWE-89")]
    findings = [
        _finding("a.py", 10, "CWE-89", 0.5, sink="sinkA"),
        _finding("a.py", 10, "CWE-89", 0.9, sink="sinkA"),
    ]
    metrics = run_corpus(findings, ground_truth, total_loc=100)
    assert metrics.tp == 1
    assert metrics.fp == 0
