"""
Regression tests for the adversarial-review findings on the multi-language
(JS/TS + Java) CST taint engine (plan 04 Phase 4).

Grammars are confirmed installed in the review environment, so these tests
run end-to-end through ``DispatchEngine.scan_file`` (the real dispatch
entry point) rather than unit-testing the visitor in isolation -- the
reviewer's repros were confirmed by real runs through this exact path.
Each test is skipped (not xfail/hidden) when the relevant tree-sitter
grammar is unavailable, matching the rest of this benchmark suite's
graceful-degradation policy.
"""
import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled

_JS_SKIP = pytest.mark.skipif(
    not is_engine_enabled("javascript"), reason="javascript tree-sitter grammar not installed"
)
_JAVA_SKIP = pytest.mark.skipif(
    not is_engine_enabled("java"), reason="java tree-sitter grammar not installed"
)


def _scan(tmp_path: Path, filename: str, source: str):
    file_path = tmp_path / filename
    file_path.write_text(source)
    engine = DispatchEngine()
    return engine.scan_file(file_path).taint_flows


# ---------------------------------------------------------------------------
# BLOCKER-1: branch-kill contradicted the stated over-approximation
# invariant. A linear single-pass walk let an unconditional else-branch
# clean assignment overwrite the if-branch's tainted value in `env`,
# silently muting a real flow. Fix: sticky taint -- a later assignment of a
# clean/None value never clears an already-tainted name; only an explicit
# sanitizer call downgrades/clears it.
# ---------------------------------------------------------------------------
@_JS_SKIP
def test_blocker1_branch_assigned_taint_is_not_killed_by_else_branch(tmp_path):
    source = (
        "app.get('/x', (req, res) => {\n"
        "    let x;\n"
        "    if (req.query.flag) {\n"
        "        x = req.query.a;\n"
        "    } else {\n"
        "        x = \"safe\";\n"
        "    }\n"
        "    db.query(\"SELECT * FROM t WHERE a = \" + x);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "branch_kill.js", source)
    assert flows, "if-branch taint on `x` must survive the else-branch clean re-assignment"


@_JS_SKIP
def test_blocker1_documented_fp_straight_line_reassignment_still_reports(tmp_path):
    """
    Documented, accepted trade-off of the sticky-taint fix: a straight-line
    `x = tainted; x = "safe"; sink(x)` now also reports (a false positive),
    because taint is never cleared by a plain re-assignment -- only by an
    explicit sanitizer call. This is intentional: muting a real flow is not
    acceptable, so we accept the extra FP here.
    """
    source = (
        "app.get('/x', (req, res) => {\n"
        "    let x = req.query.a;\n"
        "    x = \"safe\";\n"
        "    db.query(\"SELECT * FROM t WHERE a = \" + x);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "straight_line_fp.js", source)
    assert flows, "sticky taint deliberately over-approximates straight-line re-assignment too"


# ---------------------------------------------------------------------------
# BLOCKER-2: array/object subscript access was not evaluated in `_eval`,
# so `arr[0]` on a tainted-element array fell through to `return None`,
# muting the flow. Fix: index/member access on a tainted container returns
# the container's taint (container-granularity over-approximation).
# ---------------------------------------------------------------------------
@_JS_SKIP
def test_blocker2_js_array_subscript_access_flags(tmp_path):
    source = (
        "app.get('/x', (req, res) => {\n"
        "    const arr = [req.query.id];\n"
        "    db.query(\"SELECT * FROM t WHERE id = \" + arr[0]);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "subscript.js", source)
    assert flows, "arr[0] on a tainted-element array must propagate container taint"


@_JAVA_SKIP
def test_blocker2_java_array_index_access_flags(tmp_path):
    source = (
        "public class IdServlet extends HttpServlet {\n"
        "    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {\n"
        "        String[] arr = new String[1];\n"
        "        arr[0] = request.getParameter(\"id\");\n"
        "        Statement stmt = conn.createStatement();\n"
        "        stmt.executeQuery(\"SELECT * FROM items WHERE id = \" + arr[0]);\n"
        "    }\n"
        "}\n"
    )
    flows = _scan(tmp_path, "ArrIdServlet.java", source)
    assert flows, "arr[0] on a tainted-element Java array must propagate container taint"


@_JAVA_SKIP
def test_blocker2_java_list_get_access_flags(tmp_path):
    source = (
        "public class IdServlet extends HttpServlet {\n"
        "    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {\n"
        "        List<String> ids = new ArrayList<>();\n"
        "        ids.add(request.getParameter(\"id\"));\n"
        "        Statement stmt = conn.createStatement();\n"
        "        stmt.executeQuery(\"SELECT * FROM items WHERE id = \" + ids.get(0));\n"
        "    }\n"
        "}\n"
    )
    flows = _scan(tmp_path, "ListIdServlet.java", source)
    assert flows, "ids.get(0) on a tainted List must propagate container taint"


# ---------------------------------------------------------------------------
# MAJOR-3: multi-arg sink only reported the FIRST independently-tainted
# argument (a `break` after the first hit). `logger.info(a, b)` with both
# `a` and `b` tainted from distinct sources only surfaced `a`. Fix: emit a
# finding per independently-tainted argument.
# ---------------------------------------------------------------------------
@_JS_SKIP
def test_major3_multi_arg_sink_reports_all_tainted_args(tmp_path):
    source = (
        "app.get('/x', (req, res) => {\n"
        "    const a = req.query.a;\n"
        "    const b = req.body.b;\n"
        "    logger.info(a, b);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "multi_arg.js", source)
    assert len(flows) == 2, (
        f"logger.info(a, b) with two independently-tainted args must report "
        f"2 flows, got {len(flows)}: {[(f.sink_type, f.confidence) for f in flows]}"
    )


# ---------------------------------------------------------------------------
# BLOCKER-4: sanitizer laundering via a local no-op shadow. `escapeHtml` is
# in the exact-sanitizer list (factor 0.0, full drop), but with no
# import/binding resolution a locally-declared `function escapeHtml(x){
# return x}` fully clears a real SQLi flow. Fix: split exact sanitizers
# into unshadowable builtins (still full-drop) and shadowable library
# functions (downgrade only, never full-drop) -- `escapeHtml` moved to the
# shadowable/library set, so the flow must still surface at >= "possible".
# ---------------------------------------------------------------------------
@_JS_SKIP
def test_blocker4_noop_local_shadow_of_library_sanitizer_does_not_fully_clear(tmp_path):
    source = (
        "function escapeHtml(x) { return x; }\n"
        "app.get('/x', (req, res) => {\n"
        "    const a = req.query.a;\n"
        "    const clean = escapeHtml(a);\n"
        "    db.query(\"SELECT * FROM t WHERE a = \" + clean);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "shadow_sanitizer.js", source)
    assert flows, "a no-op local escapeHtml shadow must not fully launder the SQLi flow"
    assert all(f.confidence >= 0.25 for f in flows), (
        "downgraded (not dropped) flow must remain at or above the visible "
        "'possible' floor"
    )


@_JS_SKIP
def test_blocker4_unshadowable_builtin_sanitizer_still_fully_clears(tmp_path):
    """
    True-negative regression: unshadowable builtins (encodeURIComponent,
    parseInt, ...) must still fully drop the flow -- only the *shadowable
    library* set was downgraded, not the builtin set.
    """
    source = (
        "app.get('/search', (req, res) => {\n"
        "    const q = req.query.q;\n"
        "    const safe = encodeURIComponent(q);\n"
        "    res.redirect('/results?q=' + safe);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "builtin_sanitizer.js", source)
    assert flows == [], "encodeURIComponent is unshadowable and must still fully clear the flow"


# ---------------------------------------------------------------------------
# True-negative regressions explicitly called out by the reviewer: keep
# these clean after the sticky-taint / container-taint changes above.
# ---------------------------------------------------------------------------
@_JS_SKIP
def test_true_negative_parameterized_query_still_clean(tmp_path):
    source = (
        "app.get('/x', (req, res) => {\n"
        "    const id = req.query.id;\n"
        "    db.query(\"SELECT * FROM t WHERE id = ?\", [id]);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "parameterized.js", source)
    assert flows == [], "parameterized query (params array) must remain clean"


@_JS_SKIP
def test_true_negative_constant_concat_still_clean(tmp_path):
    source = (
        "app.get('/x', (req, res) => {\n"
        "    const q = \"SELECT * FROM t WHERE a = \" + \"literal\";\n"
        "    db.query(q);\n"
        "});\n"
    )
    flows = _scan(tmp_path, "constant_concat.js", source)
    assert flows == [], "constant-only concatenation must remain clean"


@_JAVA_SKIP
def test_true_negative_prepared_statement_still_clean(tmp_path):
    source = (
        "public class IdServlet extends HttpServlet {\n"
        "    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {\n"
        "        String id = request.getParameter(\"id\");\n"
        "        PreparedStatement ps = conn.prepareStatement(\"SELECT * FROM items WHERE id = ?\");\n"
        "        ps.setString(1, id);\n"
        "        ps.executeQuery();\n"
        "    }\n"
        "}\n"
    )
    flows = _scan(tmp_path, "PreparedIdServlet.java", source)
    assert flows == [], "PreparedStatement + setString parameterization must remain clean"
