"""
Runs the real scanners (TaintAnalyzer + DispatchEngine) over the vendored,
hand-authored fixture corpus under ``Asgard_Test/tests_Heimdall/benchmarks/
corpus/`` and reports precision/recall/F-beta/alert-density plus isotonic
calibration + Brier score via the plan-10 harness (``runner.py`` /
``calibration.py`` / ``gate.py``).

HONESTY LABEL (plan 10 / ASGARD_UPLIFT_GOAL "epistemic honesty"): the
corpus this module scans is a **vendored, hand-authored fixture corpus**,
not a CVE holdout or a sample of real-world repositories. Its TP/FP
fixture pairs are deliberately engineered per-CWE, single-flow examples
(see ``corpus.py``'s module docstring on the two kinds of ground truth).
The numbers this module reports are therefore a *sanity check that the
harness plumbing works end-to-end on real scanner output* and a
regression gate against future rule changes -- they are NOT a claim about
real-world precision/recall on production codebases. Any caller
presenting these numbers (CLI text/json output, CI logs, docs) MUST carry
this label; see ``CORPUS_LABEL`` below and ``report.py``'s
``metrics_to_dict`` "corpus_label" field.

Language coverage: Python (``ast``-backed, via ``TaintAnalyzer``) and
JavaScript / TypeScript / Java (tree-sitter CST-backed, via
``DispatchEngine`` -- gracefully degrades to "no flows" per-language when
the optional tree-sitter grammar for that language isn't installed,
which would otherwise manifest as false negatives rather than a crash).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import yaml

from Asgard.Heimdall.evaluation.corpus import (
    GroundTruthInstance,
    ReportedFinding,
    finding_from_taint_flow,
    ground_truth_from_taint_manifest,
)
from Asgard.Heimdall.evaluation.runner import CorpusMetrics, run_corpus
from Asgard.Heimdall.evaluation.spans import ASTSpan

CORPUS_LABEL = (
    "vendored fixture corpus (hand-authored TP/FP pairs), NOT a CVE holdout "
    "or a real-world repository sample -- see vendored_corpus.py docstring"
)

#: (corpus subdirectory name, language key for DispatchEngine / file glob).
#: "python" is scanned via TaintAnalyzer's own ast walk (no glob needed);
#: the rest are scanned file-by-file via DispatchEngine.scan_file.
_MULTILANG_DIRS: Tuple[Tuple[str, str, str], ...] = (
    ("taint_js", "javascript", "*.js"),
    ("taint_ts", "typescript", "*.ts"),
    ("taint_java", "java", "*.java"),
)
_PYTHON_DIR = "taint"


@dataclass(frozen=True)
class VendoredCorpusScan:
    """Raw scan output before metrics: findings + ground truth + LOC, kept
    separate from ``CorpusMetrics`` so callers can inspect per-language
    coverage before the harness collapses everything into one report."""

    findings: List[ReportedFinding]
    ground_truth: List[GroundTruthInstance]
    total_loc: int
    languages_scanned: List[str]
    languages_skipped: List[str]
    case_count: int
    cwe_coverage: List[str]


def _manifest_cases(corpus_dir: Path) -> List[dict]:
    manifest_path = corpus_dir / "manifest.yml"
    if not manifest_path.exists():
        return []
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return data.get("cases", []) if data else []


def _corpus_total_loc(corpus_dir: Path, cases: Sequence[dict]) -> int:
    files = {c["file"] for c in cases}
    total = 0
    for name in files:
        path = corpus_dir / name
        if path.exists():
            total += max(1, len(path.read_text(encoding="utf-8").splitlines()))
    return total


def scan_vendored_corpus(corpus_root: Path) -> VendoredCorpusScan:
    """Scan every language sub-corpus under ``corpus_root`` with the real
    analyzers and assemble the combined ``findings`` / ``ground_truth``
    inputs the plan-10 runner expects.

    ``corpus_root`` is normally
    ``Asgard_Test/tests_Heimdall/benchmarks/corpus`` (see the ``--corpus-dir``
    CLI hook for pointing this at a user-supplied corpus of the same shape).
    """
    from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer, TaintConfig

    findings: List[ReportedFinding] = []
    ground_truth: List[GroundTruthInstance] = []
    total_loc = 0
    languages_scanned: List[str] = []
    languages_skipped: List[str] = []
    case_count = 0
    cwe_coverage: set = set()

    # --- Python: TaintAnalyzer's own ast-based scan of the whole dir. ---
    py_dir = corpus_root / _PYTHON_DIR
    if py_dir.exists():
        py_cases = _manifest_cases(py_dir)
        case_count += len(py_cases)
        cwe_coverage.update(c["cwe"] for c in py_cases if c.get("cwe"))
        config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
        report = TaintAnalyzer(config=config).scan(py_dir)
        findings.extend(finding_from_taint_flow(flow) for flow in report.flows)
        ground_truth.extend(ground_truth_from_taint_manifest(py_dir, py_cases))
        total_loc += _corpus_total_loc(py_dir, py_cases)
        languages_scanned.append("python")

    # --- JS / TS / Java: DispatchEngine's CST taint path, file-by-file. ---
    from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
    from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled

    engine = DispatchEngine()
    for subdir, lang_key, _glob in _MULTILANG_DIRS:
        lang_dir = corpus_root / subdir
        if not lang_dir.exists():
            continue
        cases = _manifest_cases(lang_dir)
        if not is_engine_enabled(lang_key):
            languages_skipped.append(lang_key)
            continue
        case_count += len(cases)
        cwe_coverage.update(c["cwe"] for c in cases if c.get("cwe"))
        total_loc += _corpus_total_loc(lang_dir, cases)
        for case in cases:
            fixture_path = lang_dir / case["file"]
            if not fixture_path.exists():
                continue
            result = engine.scan_file(fixture_path)
            findings.extend(finding_from_taint_flow(flow) for flow in result.taint_flows)
            if case.get("expect") == "flow":
                n_lines = max(1, len(fixture_path.read_text(encoding="utf-8").splitlines()))
                ground_truth.append(
                    GroundTruthInstance(
                        id=f"{subdir}/{case['file']}",
                        file_path=str(fixture_path),
                        cwe=case.get("cwe", ""),
                        span=ASTSpan(file_path=str(fixture_path), start_line=1, end_line=n_lines),
                        source="fixture",
                    )
                )
        languages_scanned.append(lang_key)

    return VendoredCorpusScan(
        findings=findings,
        ground_truth=ground_truth,
        total_loc=total_loc,
        languages_scanned=languages_scanned,
        languages_skipped=languages_skipped,
        case_count=case_count,
        cwe_coverage=sorted(cwe_coverage),
    )


def evaluate_vendored_corpus(corpus_root: Path, fallback: int = 3) -> Tuple[CorpusMetrics, VendoredCorpusScan]:
    """Scan + run the plan-10 metrics/calibration pipeline over the vendored
    corpus in one call. Returns ``(metrics, scan)`` so callers get both the
    headline numbers and the coverage metadata for the honesty label."""
    scan = scan_vendored_corpus(corpus_root)
    metrics = run_corpus(scan.findings, scan.ground_truth, total_loc=scan.total_loc, fallback=fallback)
    return metrics, scan
