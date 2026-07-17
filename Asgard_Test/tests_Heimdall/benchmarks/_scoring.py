"""Semgrep-style benchmark scoring for dual-engine rules.

Fixture files under ``benchmarks/<lang>/`` carry inline annotations:

- ``# ruleid: <rule_id>`` — the rule MUST flag this line (true positive);
- ``# ok: <rule_id>``     — the rule must NOT flag this line (a known
  regex-engine trap; flagging it is a false positive).

Acceptance gate per migrated rule (plan 01):
``Recall(AST) >= Recall(Regex)`` AND ``Precision(AST) > Precision(Regex)``
(strictness on whichever axis the fixture engineers a regex failure for).
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

_ANNOTATION_RE = re.compile(r"#\s*(ruleid|ok):\s*([\w.\-]+)")

BENCHMARK_ROOT = Path(__file__).parent


@dataclass
class Score:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 1.0


def load_annotations(fixture_path: Path) -> Dict[str, Dict[str, Set[int]]]:
    """Return {rule_id: {"ruleid": {1-based lines}, "ok": {...}}}."""
    annotations: Dict[str, Dict[str, Set[int]]] = {}
    lines = fixture_path.read_text(encoding="utf-8").splitlines()
    for lineno, line in enumerate(lines, start=1):
        for kind, rule_id in _ANNOTATION_RE.findall(line):
            entry = annotations.setdefault(rule_id, {"ruleid": set(), "ok": set()})
            entry[kind].add(lineno)
    return annotations


def score_predictions(predicted_lines: Set[int], expected_lines: Set[int]) -> Score:
    tp = len(predicted_lines & expected_lines)
    fp = len(predicted_lines - expected_lines)
    fn = len(expected_lines - predicted_lines)
    return Score(tp=tp, fp=fp, fn=fn)


def run_engine(rule_impl, fixture_path: Path, **kwargs) -> Set[int]:
    """Run a rule implementation over a fixture; return predicted 1-based lines."""
    lines: List[str] = fixture_path.read_text(encoding="utf-8").splitlines()
    findings = rule_impl(str(fixture_path), lines, True, **kwargs)
    return {f["line"] for f in findings}


def score_rule_on_fixture(rule, rule_id: str, fixture_path: Path) -> Dict[str, Score]:
    """Score a dual-engine rule's regex and AST implementations on one fixture.

    The AST score is only present when tree-sitter is available for python.
    """
    from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled
    from Asgard.Heimdall.treesitter.file_context import FileParseContext

    annotations = load_annotations(fixture_path)
    expected = annotations.get(rule_id, {"ruleid": set()})["ruleid"]

    scores: Dict[str, Score] = {}
    regex_predicted = run_engine(rule.__regex_impl__, fixture_path)
    scores["regex"] = score_predictions(regex_predicted, expected)

    if is_engine_enabled("python"):
        lines = fixture_path.read_text(encoding="utf-8").splitlines()
        ctx = FileParseContext.parse(fixture_path, lines, "python")
        findings = rule.__ast_impl__(str(fixture_path), ctx)
        scores["ast"] = score_predictions({f["line"] for f in findings}, expected)
    return scores
