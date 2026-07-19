"""
Whole-project inter-procedural taint index (WS1) + alias/summary
completeness (WS3) regression tests.

Fixtures live under ``project_index_fixtures/`` (each subdir is its own
mini "project" with a root marker -- ``package.json`` or ``pom.xml`` -- so
project-root discovery does not walk all the way up to the Asgard repo
root and swallow the whole monorepo into one index).

Tree-sitter is optional (plan 01: "tree-sitter stays optional"); every
case here skips per-language when the grammar is unavailable, matching the
existing corpus-runner convention (see
``benchmarks/test_taint_benchmark_corpus_multilang.py``).
"""

import os
import shutil
import time
from pathlib import Path

import pytest

from Asgard.Heimdall.Security.engine.dispatch import (
    DispatchEngine,
    _find_project_root,
)
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled

FIXTURES_ROOT = Path(__file__).parent / "project_index_fixtures"

_JS_SKIP = pytest.mark.skipif(
    not is_engine_enabled("javascript"), reason="JS tree-sitter grammar unavailable"
)
_JAVA_SKIP = pytest.mark.skipif(
    not is_engine_enabled("java"), reason="Java tree-sitter grammar unavailable"
)


def _cache_dir(project_root: Path) -> Path:
    return project_root / ".asgard_cache"


def _clear_cache(project_root: Path) -> None:
    shutil.rmtree(_cache_dir(project_root), ignore_errors=True)


# --------------------------------------------------------------- WS1 tests

@_JS_SKIP
def test_project_root_discovery_finds_package_json():
    proj1 = FIXTURES_ROOT / "proj1"
    root = _find_project_root(proj1 / "a" / "main.js")
    assert root == proj1.resolve()


@_JS_SKIP
def test_cross_subdirectory_flow_resolves():
    """a/main.js calls a sink helper defined two levels down in b/sub/util.js
    -- with the OLD directory-scoped SummaryIndex this call would NOT
    resolve (main.js and util.js are never siblings in the same directory),
    so the flow would be silently missed. The project-rooted index must
    resolve it."""
    proj1 = FIXTURES_ROOT / "proj1"
    _clear_cache(proj1)
    engine = DispatchEngine()
    result = engine.scan_file(proj1 / "a" / "main.js")
    assert len(result.taint_flows) == 1, (
        f"expected the cross-subdirectory SQLi flow to resolve, got "
        f"{[(f.sink_type, f.confidence) for f in result.taint_flows]}"
    )
    flow = result.taint_flows[0]
    assert flow.cwe_id == "CWE-89"
    assert flow.confidence > 0.5  # resolved hop, not the 0.5 unknown-call decay


@_JS_SKIP
def test_three_file_cross_package_chain_resolves():
    """file1 -> file2 (nested subdir) -> file3 (sibling dir), taint flows
    through all three hops to a shell-command sink in file3."""
    proj2 = FIXTURES_ROOT / "proj2"
    _clear_cache(proj2)
    engine = DispatchEngine()
    result = engine.scan_file(proj2 / "file1dir" / "file1.js")
    assert len(result.taint_flows) == 1, (
        f"expected the 3-hop command-injection flow to resolve, got "
        f"{[(f.sink_type, f.confidence) for f in result.taint_flows]}"
    )
    assert result.taint_flows[0].cwe_id == "CWE-78"


@_JS_SKIP
def test_cache_reuse_second_run_skips_rebuild(monkeypatch):
    """Two scans of the same unchanged fixture tree: the SECOND run must
    reuse the on-disk .asgard_cache entries rather than recomputing base
    summaries (proven by spying on ``compute_cst_file_summaries``, which is
    only invoked on a cache MISS)."""
    proj1 = FIXTURES_ROOT / "proj1"
    _clear_cache(proj1)
    monkeypatch.delenv("ASGARD_NO_CACHE", raising=False)

    import Asgard.Heimdall.Security.engine.dispatch as dispatch_mod

    calls = {"n": 0}
    original = dispatch_mod.compute_cst_file_summaries

    def _spy(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(dispatch_mod, "compute_cst_file_summaries", _spy)

    engine1 = DispatchEngine()
    engine1.scan_file(proj1 / "a" / "main.js")
    first_run_calls = calls["n"]
    assert first_run_calls > 0, "first run must build summaries (cold cache)"
    assert (_cache_dir(proj1) / "cst_summaries_javascript.json").exists()

    calls["n"] = 0
    # Fresh engine -- no in-memory reuse possible; only the on-disk cache
    # can make this cheap.
    engine2 = DispatchEngine()
    result2 = engine2.scan_file(proj1 / "a" / "main.js")
    assert calls["n"] == 0, (
        f"second run should hit the on-disk cache for every unchanged "
        f"file and never call compute_cst_file_summaries, but it was "
        f"called {calls['n']} time(s)"
    )
    assert len(result2.taint_flows) == 1  # finding is unchanged


@_JS_SKIP
def test_cache_correctness_edit_invalidates_and_reflects_in_finding(monkeypatch, tmp_path):
    """SECURITY CRITICAL: editing a file's content must invalidate ITS
    cached summary and the dependent finding must change accordingly on
    the next scan -- a stale cache causing a false 'clean' is a severe
    bug."""
    proj = tmp_path / "editproj"
    (proj / "b" / "sub").mkdir(parents=True)
    (proj / "a").mkdir()
    (proj / "package.json").write_text('{"name": "editproj"}')
    (proj / "a" / "main.js").write_text(
        "const { runQuery } = require('../b/sub/util');\n"
        "app.get('/user', (req, res) => { runQuery(req.query.id); res.send('ok'); });\n"
    )
    util_path = proj / "b" / "sub" / "util.js"
    util_path.write_text(
        'function runQuery(id) { return id; }\n'  # clean: no sink use
        "module.exports = { runQuery };\n"
    )
    monkeypatch.delenv("ASGARD_NO_CACHE", raising=False)

    engine1 = DispatchEngine()
    clean_result = engine1.scan_file(proj / "a" / "main.js")
    assert clean_result.taint_flows == [], "helper does not reach a sink -- must be clean"

    # Edit the helper to introduce a real SQLi sink.
    util_path.write_text(
        'function runQuery(id) { db.query("SELECT * FROM t WHERE id=" + id); }\n'
        "module.exports = { runQuery };\n"
    )

    engine2 = DispatchEngine()
    tainted_result = engine2.scan_file(proj / "a" / "main.js")
    assert len(tainted_result.taint_flows) == 1, (
        "editing the helper to add a sink must be reflected in the next "
        "scan's finding -- a stale cache entry would incorrectly keep "
        "reporting 'clean'"
    )
    assert tainted_result.taint_flows[0].cwe_id == "CWE-89"


@_JS_SKIP
def test_asgard_no_cache_bypasses_cache(monkeypatch):
    proj1 = FIXTURES_ROOT / "proj1"
    _clear_cache(proj1)
    monkeypatch.setenv("ASGARD_NO_CACHE", "1")
    engine = DispatchEngine()
    engine.scan_file(proj1 / "a" / "main.js")
    # No cache file should have been written when ASGARD_NO_CACHE is set.
    assert not (_cache_dir(proj1) / "cst_summaries_javascript.json").exists()
    monkeypatch.delenv("ASGARD_NO_CACHE", raising=False)
    _clear_cache(proj1)


@_JS_SKIP
def test_destructured_param_cross_function_flow_resolves():
    """``handle({id})`` -- a destructured param -- receives a tainted
    object positionally from the caller; taint must flow through the
    bound name `id` to the SQLi sink inside the callee."""
    proj = FIXTURES_ROOT / "proj_destructure"
    _clear_cache(proj)
    engine = DispatchEngine()
    result = engine.scan_file(proj / "caller.js")
    assert len(result.taint_flows) == 1, (
        f"expected the destructured-param SQLi flow to resolve, got "
        f"{[(f.sink_type, f.confidence) for f in result.taint_flows]}"
    )
    assert result.taint_flows[0].cwe_id == "CWE-89"


@_JAVA_SKIP
def test_java_wildcard_import_member_sink_resolves():
    """``import java.util.*;`` -- a wildcard-resolved class's method
    (``Runtime.exec``) is a shell-command sink; tainted
    ``request.getParameter(...)`` data reaching it must still be flagged."""
    proj = FIXTURES_ROOT / "proj_java_wildcard"
    _clear_cache(proj)
    engine = DispatchEngine()
    result = engine.scan_file(proj / "Handler.java")
    assert len(result.taint_flows) == 1, (
        f"expected the wildcard-import shell-command flow, got "
        f"{[(f.sink_type, f.confidence) for f in result.taint_flows]}"
    )
    assert result.taint_flows[0].cwe_id == "CWE-78"


@_JS_SKIP
def test_bound_and_truncate_synthetic_1000_files(tmp_path):
    """Generate a synthetic ~1000-file JS tree (not checked in) and verify
    indexing completes in bounded time without exceeding the configured
    file-count bound; truncation (when the bound is exceeded) must be
    recorded, never silent."""
    proj = tmp_path / "bigproj"
    proj.mkdir()
    (proj / "package.json").write_text('{"name": "bigproj"}')
    n_files = 1000
    for i in range(n_files):
        d = proj / f"pkg{i % 50}"
        d.mkdir(exist_ok=True)
        (d / f"mod{i}.js").write_text(
            f"function f{i}(x) {{ return x + {i}; }}\nmodule.exports = {{ f{i} }};\n"
        )
    entry = proj / "pkg0" / "mod0.js"

    engine = DispatchEngine()
    max_files = 200  # small bound so the truncation path is exercised
    start = time.monotonic()
    from Asgard.Heimdall.Security.engine.dispatch import _JS_SIBLING_EXTS
    index = engine._cst_summary_index(entry, "javascript", _JS_SIBLING_EXTS, max_files=max_files)
    elapsed = time.monotonic() - start

    assert index.indexed_file_count <= max_files
    assert index.truncated is True
    assert elapsed < 60, f"indexing {n_files} files took too long: {elapsed:.2f}s"


@_JS_SKIP
def test_bound_default_not_truncated_for_small_project():
    proj1 = FIXTURES_ROOT / "proj1"
    _clear_cache(proj1)
    engine = DispatchEngine()
    engine.scan_file(proj1 / "a" / "main.js")
    key = (str(_find_project_root(proj1 / "a" / "main.js")), "javascript")
    index = engine._cst_summary_indexes[key]
    assert index.truncated is False
    assert index.indexed_file_count >= 2
