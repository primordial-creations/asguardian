"""
Multi-language taint benchmark corpus runner (plan 04 Phase 4: JS/TS + Java
via the tree-sitter CST engine; plan 01 waves 2-3 acceptance gate).

Mirrors ``test_taint_benchmark_corpus.py`` (the Python ``ast``-backed
runner) but drives fixtures through ``DispatchEngine.scan_file`` -- the
entry point that routes JS/TS/Java files to the CST taint path
(``Security/TaintAnalysis/engine/cst_taint_visitor.py``).

Tree-sitter is an optional extra (plan 01: "tree-sitter stays optional").
When the JS or Java grammar is unavailable, ``DispatchEngine`` degrades
gracefully to "no taint findings" for that file -- which would make every
``expect: flow`` case fail. Rather than asserting a false negative as a
suite failure, these tests skip per-language when the grammar is missing,
so the suite passes unconditionally with or without ``[ast]`` installed.
"""

from pathlib import Path

import pytest
import yaml

from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled

CORPUS_ROOT = Path(__file__).parent / "corpus"

_LANG_DIRS = {
    "javascript": (CORPUS_ROOT / "taint_js", "javascript"),
    "java": (CORPUS_ROOT / "taint_java", "java"),
    "typescript": (CORPUS_ROOT / "taint_ts", "typescript"),
    "go": (CORPUS_ROOT / "taint_go", "go"),
    "c": (CORPUS_ROOT / "taint_c", "c"),
}


def _load_cases(lang_key: str):
    corpus_dir, _ = _LANG_DIRS[lang_key]
    manifest = corpus_dir / "manifest.yml"
    if not manifest.exists():
        return []
    return yaml.safe_load(manifest.read_text())["cases"]


def _scan_fixture(corpus_dir: Path, fixture_name: str):
    path = corpus_dir / fixture_name
    engine = DispatchEngine()
    return engine.scan_file(path)


def _run_case(corpus_dir: Path, case: dict) -> None:
    result = _scan_fixture(corpus_dir, case["file"])
    flows = result.taint_flows
    if case["expect"] == "no_flow":
        assert flows == [], (
            f"{case['file']}: expected clean, got "
            f"{[(f.sink_type, f.confidence) for f in flows]}"
        )
        return
    assert len(flows) == case["count"], (
        f"{case['file']}: expected {case['count']} flow(s), got "
        f"{[(f.sink_type, f.confidence) for f in flows]}"
    )
    flow = flows[0]
    assert flow.severity == case["severity"]
    assert flow.confidence_bucket in case["bucket_in"], (
        f"{case['file']}: bucket {flow.confidence_bucket} "
        f"(confidence {flow.confidence}) not in {case['bucket_in']}"
    )
    if case.get("cwe"):
        assert flow.cwe_id == case["cwe"]
    if case.get("finding_class"):
        # WS5 dynamic-construct surfacing: findings for eval/exec/reflection
        # sinks are tagged with a distinct finding_class ("dynamic_construct")
        # rather than the default "taint_flow", and always carry LOW/
        # "needs_review" confidence -- never certain, since the analysis
        # cannot statically prove what the dynamic construct will do.
        assert flow.finding_class == case["finding_class"]


_JS_CASES = _load_cases("javascript")
_JAVA_CASES = _load_cases("java")
_TS_CASES = _load_cases("typescript")
_GO_CASES = _load_cases("go")
_C_CASES = _load_cases("c")


@pytest.mark.skipif(
    not is_engine_enabled("javascript"),
    reason="tree-sitter-javascript grammar not installed (optional [ast] extra)",
)
@pytest.mark.parametrize(
    "case", _JS_CASES, ids=[c["file"].removesuffix(".js") for c in _JS_CASES]
)
def test_js_corpus_case(case):
    _run_case(_LANG_DIRS["javascript"][0], case)


@pytest.mark.skipif(
    not is_engine_enabled("java"),
    reason="tree-sitter-java grammar not installed (optional [ast] extra)",
)
@pytest.mark.parametrize(
    "case", _JAVA_CASES, ids=[c["file"].removesuffix(".java") for c in _JAVA_CASES]
)
def test_java_corpus_case(case):
    _run_case(_LANG_DIRS["java"][0], case)


@pytest.mark.skipif(
    not is_engine_enabled("typescript"),
    reason="tree-sitter-typescript grammar not installed (optional [ast] extra)",
)
@pytest.mark.parametrize(
    "case", _TS_CASES, ids=[c["file"].removesuffix(".ts") for c in _TS_CASES]
)
def test_ts_corpus_case(case):
    _run_case(_LANG_DIRS["typescript"][0], case)


@pytest.mark.skipif(
    not is_engine_enabled("go"),
    reason="tree-sitter-go grammar not installed (optional [ast] extra)",
)
@pytest.mark.parametrize(
    "case", _GO_CASES, ids=[c["file"].removesuffix(".go") for c in _GO_CASES]
)
def test_go_corpus_case(case):
    _run_case(_LANG_DIRS["go"][0], case)


@pytest.mark.skipif(
    not is_engine_enabled("c"),
    reason="tree-sitter-c grammar not installed (optional [ast] extra)",
)
@pytest.mark.parametrize(
    "case", _C_CASES, ids=[c["file"].removesuffix(".c") for c in _C_CASES]
)
def test_c_corpus_case(case):
    _run_case(_LANG_DIRS["c"][0], case)


@pytest.mark.skipif(
    not (is_engine_enabled("javascript") and is_engine_enabled("java")),
    reason="tree-sitter JS/Java grammars not installed (optional [ast] extra)",
)
def test_corpus_determinism_multilang():
    """Two consecutive scans on identical input yield identical findings."""
    for corpus_dir, cases in (
        (_LANG_DIRS["javascript"][0], _JS_CASES),
        (_LANG_DIRS["java"][0], _JAVA_CASES),
    ):
        for case in cases[:2]:
            r1 = _scan_fixture(corpus_dir, case["file"])
            r2 = _scan_fixture(corpus_dir, case["file"])
            f1 = [f.model_dump() for f in r1.taint_flows]
            f2 = [f.model_dump() for f in r2.taint_flows]
            assert f1 == f2


@pytest.mark.skipif(
    not (is_engine_enabled("go") and is_engine_enabled("c")),
    reason="tree-sitter Go/C grammars not installed (optional [ast] extra)",
)
def test_corpus_determinism_go_c():
    """Two consecutive scans on identical input yield identical findings."""
    for corpus_dir, cases in (
        (_LANG_DIRS["go"][0], _GO_CASES),
        (_LANG_DIRS["c"][0], _C_CASES),
    ):
        for case in cases[:2]:
            r1 = _scan_fixture(corpus_dir, case["file"])
            r2 = _scan_fixture(corpus_dir, case["file"])
            f1 = [f.model_dump() for f in r1.taint_flows]
            f2 = [f.model_dump() for f in r2.taint_flows]
            assert f1 == f2


def test_engine_disabled_degrades_to_no_flows(monkeypatch):
    """When the AST engine is disabled, JS/TS/Java routing must not crash
    and must simply yield no taint flows (Layer 1 regex still runs)."""
    import Asgard.Heimdall.Security.engine.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "is_engine_enabled", lambda lang: False)
    fixture = _LANG_DIRS["javascript"][0] / "tp_sqli_concat.js"
    if not fixture.exists():
        pytest.skip("fixture missing")
    result = DispatchEngine().scan_file(fixture)
    assert result.taint_flows == []
