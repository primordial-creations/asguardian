"""CI acceptance gate: profile thresholds, overfit rejection, Brier
non-regression (plan 10 s3)."""

from Asgard.Heimdall.evaluation.corpus import GroundTruthInstance, ReportedFinding
from Asgard.Heimdall.evaluation.gate import evaluate_gate
from Asgard.Heimdall.evaluation.runner import run_corpus
from Asgard.Heimdall.evaluation.spans import ASTSpan


def _gt(id_, line, cwe="CWE-89"):
    return GroundTruthInstance(
        id=id_, file_path="a.py", cwe=cwe, span=ASTSpan(file_path="a.py", start_line=line, end_line=line)
    )


def _finding(line, confidence, cwe="CWE-89"):
    return ReportedFinding(file_path="a.py", line=line, cwe=cwe, confidence=confidence, sink_node_id=str(line))


def test_profile_a_passes_on_strong_metrics():
    ground_truth = [_gt(f"gt{i}", i * 10) for i in range(1, 6)]
    findings = [_finding(i * 10, 0.9) for i in range(1, 6)]  # perfect P/R
    metrics = run_corpus(findings, ground_truth, total_loc=10_000)
    result = evaluate_gate(metrics, profile="A")
    assert result.passed
    assert result.reasons == []


def test_profile_a_fails_on_weak_recall():
    ground_truth = [_gt(f"gt{i}", i * 10) for i in range(1, 11)]
    findings = [_finding(10, 0.9)]  # 1/10 recall
    metrics = run_corpus(findings, ground_truth, total_loc=10_000)
    result = evaluate_gate(metrics, profile="A")
    assert not result.passed
    assert any("recall" in r for r in result.reasons)


def test_profile_b_more_lenient_on_precision_than_profile_a():
    # Low precision, high recall -- should fail A on precision but can
    # pass B given B's lower precision floor and F2 emphasis on recall.
    ground_truth = [_gt(f"gt{i}", i * 10) for i in range(1, 5)]
    findings = [_finding(i * 10, 0.9) for i in range(1, 5)] + [
        _finding(1000 + i, 0.3) for i in range(15)
    ]
    metrics = run_corpus(findings, ground_truth, total_loc=100_000)
    result_a = evaluate_gate(metrics, profile="A")
    result_b = evaluate_gate(metrics, profile="B")
    assert not result_a.passed
    assert result_b.passed


def test_overfit_rejection_triggers_on_large_recall_drop():
    ground_truth = [_gt(f"gt{i}", i * 10) for i in range(1, 6)]
    findings = [_finding(i * 10, 0.9) for i in range(1, 6)]
    metrics = run_corpus(findings, ground_truth, total_loc=10_000)
    result = evaluate_gate(
        metrics, profile="A", fixture_recall=0.90, holdout_recall=0.50
    )
    assert not result.passed
    assert any("overfit rejection" in r for r in result.reasons)


def test_overfit_rejection_allows_small_recall_drop():
    ground_truth = [_gt(f"gt{i}", i * 10) for i in range(1, 6)]
    findings = [_finding(i * 10, 0.9) for i in range(1, 6)]
    metrics = run_corpus(findings, ground_truth, total_loc=10_000)
    result = evaluate_gate(
        metrics, profile="A", fixture_recall=0.90, holdout_recall=0.80
    )
    assert not any("overfit rejection" in r for r in result.reasons)


def test_brier_non_regression_check():
    ground_truth = [_gt(f"gt{i}", i * 10) for i in range(1, 6)]
    findings = [_finding(i * 10, 0.9) for i in range(1, 6)]
    metrics = run_corpus(findings, ground_truth, total_loc=10_000)

    ok = evaluate_gate(metrics, profile="A", baseline_brier=0.10, new_brier=0.08)
    assert not any("Brier" in r for r in ok.reasons)

    regressed = evaluate_gate(metrics, profile="A", baseline_brier=0.10, new_brier=0.15)
    assert any("Brier" in r for r in regressed.reasons)


def test_unknown_profile_raises():
    ground_truth = [_gt("gt1", 10)]
    findings = [_finding(10, 0.9)]
    metrics = run_corpus(findings, ground_truth, total_loc=100)
    try:
        evaluate_gate(metrics, profile="Z")
        assert False, "expected ValueError"
    except ValueError:
        pass
