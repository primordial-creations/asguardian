"""Acceptance-gate benchmark for the wave-1 Python pilot rules.

Gate per plan 01: on the annotated fixtures,
``Recall(AST) >= Recall(Regex)`` AND ``Precision(AST) >= Precision(Regex)``
with a strict improvement on at least one axis per rule (every fixture
engineers at least one regex trap).

Regex-only scoring always runs; AST comparisons are skipped without the
optional tree-sitter extra.
"""
import time

import pytest

from Asgard.Heimdall.Security.services._ast_python_rules import (
    check_eval_exec,
    check_injection_sink_candidates,
    check_route_missing_auth,
    check_subprocess_shell_true,
    check_yaml_unsafe_load,
    run_python_pilot_rules,
)
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled
from Asgard.Heimdall.treesitter.file_context import FileParseContext

from Asgard_Test.tests_Heimdall.benchmarks._scoring import (
    BENCHMARK_ROOT,
    load_annotations,
    score_rule_on_fixture,
)

PILOT_CASES = [
    (check_eval_exec, "python.eval-exec-usage", "eval_exec.py"),
    (check_yaml_unsafe_load, "python.yaml-unsafe-load", "yaml_load.py"),
    (check_subprocess_shell_true, "python.subprocess-shell-true", "subprocess_shell.py"),
    (check_route_missing_auth, "python.route-missing-auth", "route_auth.py"),
    (check_injection_sink_candidates, "python.injection-sink-candidate", "sink_prefilter.py"),
]

requires_ast = pytest.mark.skipif(
    not is_engine_enabled("python"), reason="tree-sitter not installed"
)


def _fixture(name):
    return BENCHMARK_ROOT / "python" / name


@pytest.mark.parametrize("rule,rule_id,fixture", PILOT_CASES,
                         ids=[c[1] for c in PILOT_CASES])
def test_fixture_has_annotations(rule, rule_id, fixture):
    annotations = load_annotations(_fixture(fixture))
    assert rule_id in annotations
    assert annotations[rule_id]["ruleid"], "fixture must contain at least one ruleid line"
    assert annotations[rule_id]["ok"], "fixture must contain at least one regex-trap ok line"


@pytest.mark.parametrize("rule,rule_id,fixture", PILOT_CASES,
                         ids=[c[1] for c in PILOT_CASES])
def test_regex_engine_baseline_scores(rule, rule_id, fixture):
    scores = score_rule_on_fixture(rule, rule_id, _fixture(fixture))
    regex = scores["regex"]
    # The regex engine must at least find something on every fixture.
    assert regex.tp > 0, f"regex baseline found nothing for {rule_id}"


@requires_ast
@pytest.mark.parametrize("rule,rule_id,fixture", PILOT_CASES,
                         ids=[c[1] for c in PILOT_CASES])
def test_ast_engine_meets_acceptance_gate(rule, rule_id, fixture):
    scores = score_rule_on_fixture(rule, rule_id, _fixture(fixture))
    regex, ast = scores["regex"], scores["ast"]

    assert ast.recall >= regex.recall, (
        f"{rule_id}: Recall(AST)={ast.recall:.2f} < Recall(Regex)={regex.recall:.2f}"
    )
    assert ast.precision >= regex.precision, (
        f"{rule_id}: Precision(AST)={ast.precision:.2f} < Precision(Regex)={regex.precision:.2f}"
    )
    assert ast.precision > regex.precision or ast.recall > regex.recall, (
        f"{rule_id}: AST engine shows no improvement over regex on its fixture"
    )
    # AST engine must be clean on the engineered fixtures.
    assert ast.fp == 0, f"{rule_id}: AST produced {ast.fp} false positive(s)"
    assert ast.fn == 0, f"{rule_id}: AST missed {ast.fn} annotated finding(s)"


@requires_ast
def test_single_file_parse_and_rules_within_budget():
    """Plan 01 performance budget: parse+query <= 25ms typical per file.

    Asserted with headroom (100ms warm) to stay deterministic on CI.
    """
    fixture = _fixture("sink_prefilter.py")
    lines = fixture.read_text(encoding="utf-8").splitlines()
    # Warm-up (grammar load, query/parser caches)
    run_python_pilot_rules(fixture, lines)
    start = time.perf_counter()
    ctx = FileParseContext.parse(fixture, lines, "python")
    run_python_pilot_rules(fixture, lines, parse_context=ctx)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 100, f"parse+rules took {elapsed_ms:.1f}ms (budget 100ms)"
