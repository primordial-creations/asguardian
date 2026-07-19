"""
Adversarial-review regression tests: 3 confirmed real-injection-muting bugs
in the JS/TS/Java CST alias-resolution / inter-procedural-summary taint
engine (``Security/TaintAnalysis/engine/cst_alias.py``,
``Security/TaintAnalysis/engine/cst_taint_visitor.py``,
``Security/TaintAnalysis/summaries.py``). Each test reproduces the
reviewer's EXACT repro and asserts the fix, not just "no crash".

BLOCKER-1 -- sanitizer-verification full-clears a no-op imported from ANY
module: ``_sanitizer_verified`` only checked alias-map MEMBERSHIP (any
import/require binding), not what the binding actually resolves to. A
relative-path import of a same-named no-op (``import { escapeHtml } from
'./evil_local_utils'``) was promoted to a full clear, muting a real DOM XSS.
Fixed by requiring the resolved import's raw (non-relative) specifier to
match an allow-list of real sanitizer packages
(``cst_alias.JS_SANITIZER_ALLOWED_MODULES`` / ``JAVA_SANITIZER_ALLOWED_MODULES``).

BLOCKER-2 -- inter-procedural resolution drops a real flow when the resolved
callee's OWN callee is out of the (directory-scoped) summary index:
``a.js -> b(x)`` [in-directory, resolved] where ``b`` forwards ``x`` into
``c`` in ``./sub/c`` [out of index] which does ``cp.exec(x)``. The old code
read "immediate callee summary exists, but shows no sink hit" as an
authoritative clean drop -- but the callee's OWN forwarding edge into an
unindexed file means that was never actually verified. Fixed in
``SummaryIndex._reachable_sinks_ex``/``resolve_call``: an unresolved
forwarding edge now marks the result "incomplete", which makes
``resolve_call`` fall back to the standard unknown-call decay (a non-zero,
over-approximated result) instead of a confident empty. This case cannot be
expressed as a ``DispatchEngine``/manifest flow-count assertion (the
injection sink lives in the never-indexed ``sub/c`` file, so no ``TaintFlow``
can ever be constructed for it by design -- the fix's acceptance bar,
verified directly against ``SummaryIndex.resolve_call`` below, is "not a
confident zero", matching the reviewer's own wording: "a flow, or at least a
non-zero over-approximated result").

MAJOR -- inline ``require('child_process').exec(cmd)`` (no intermediate
variable) never resolved: the member-expression's ``object`` is itself a
``call_expression`` (``require('child_process')``), and chain-flattening
returned the literal text "require" instead of the required module name, so
the sink pattern ``child_process.exec`` never matched. Fixed in
``_node_chain``.
"""

from pathlib import Path

import pytest

from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
from Asgard.Heimdall.Security.TaintAnalysis.engine.cst_alias import build_cst_alias_map
from Asgard.Heimdall.Security.TaintAnalysis.engine.cst_summaries import compute_cst_file_summaries
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintFlowStep, TaintSourceType
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_visitor import TaintState
from Asgard.Heimdall.Security.TaintAnalysis.summaries import SummaryIndex
from Asgard.Heimdall.treesitter.ast_engine import is_engine_enabled
from Asgard.Heimdall.treesitter.file_context import FileParseContext

pytestmark = pytest.mark.skipif(
    not is_engine_enabled("javascript"),
    reason="tree-sitter-javascript grammar not installed (optional [ast] extra)",
)

CORPUS_DIR = Path(__file__).parent / "benchmarks" / "corpus" / "taint_js"


def test_blocker1_relative_import_noop_sanitizer_still_flags():
    """Reviewer repro: `import { escapeHtml } from './evil_local_utils'`
    (a local no-op) must NOT full-clear -- the flow must still surface at
    'possible' confidence, same treatment as an unresolved local shadow."""
    engine = DispatchEngine()
    result = engine.scan_file(CORPUS_DIR / "tp_relative_import_noop_sanitizer.js")
    assert len(result.taint_flows) == 1, (
        "expected 1 flow (real XSS laundered via a relative-import no-op "
        f"'sanitizer'), got {[(f.sink_type, f.confidence) for f in result.taint_flows]}"
    )
    flow = result.taint_flows[0]
    assert flow.confidence_bucket == "possible"
    assert flow.cwe_id == "CWE-79"


def test_major_inline_require_command_injection_flags():
    """Reviewer repro: `require('child_process').exec(cmd)` with no
    intermediate variable must resolve to the child_process.exec sink."""
    engine = DispatchEngine()
    result = engine.scan_file(CORPUS_DIR / "tp_inline_require_command_injection.js")
    assert len(result.taint_flows) == 1, (
        f"expected 1 command-injection flow, got "
        f"{[(f.sink_type, f.confidence) for f in result.taint_flows]}"
    )
    assert result.taint_flows[0].cwe_id == "CWE-78"


def test_blocker2_cross_directory_forwarding_not_confidently_clean():
    """Reviewer repro: a.js -> b(x) [in-dir, resolved] -> b forwards x into
    c in ./sub/c [never indexed -- directory-scoped, non-recursive sibling
    index] which does `cp.exec(x)`.

    Build b's summary exactly as the real pipeline would (compute_cst_file_
    summaries over b's own source), add ONLY b to a SummaryIndex (c is
    deliberately absent, matching the real bug: sub/ is never scanned), then
    resolve a call to b carrying real tainted data and assert the result is
    NOT read as an authoritative clean drop.
    """
    b_src = (
        "const { runC } = require('./sub/tp_cross_dir_helper_c');\n"
        "function runB(cmd) {\n"
        "    runC(cmd);\n"
        "}\n"
        "module.exports = { runB };\n"
    )
    b_path = "tp_cross_dir_helper_b.js"
    ctx = FileParseContext.parse(Path(b_path), b_src.splitlines(), "javascript")
    assert ctx.root is not None
    alias_map = build_cst_alias_map(ctx, "javascript")
    summaries = compute_cst_file_summaries(b_path, ctx, "javascript", alias_map)
    assert "runB" in summaries
    # Sanity: b's summary really does forward its param into an unresolved
    # callee (the precondition for the bug) -- if this ever stops being
    # true the rest of the assertion is vacuous.
    assert summaries["runB"].param_calls, "expected runB to record a param-forwarding call edge"

    index = SummaryIndex()
    # Deliberately do NOT add a summary for tp_cross_dir_helper_c -- it is
    # out of the (directory-scoped, non-recursive) index, exactly like the
    # real bug (sub/ is a subdirectory, never walked by dispatch.py's
    # sibling scan).
    index.add_file(b_path, summaries, {"tp_cross_dir_helper_c"}, b_src.splitlines())
    index.set_current_file("a.js")

    tainted_arg = TaintState(
        source_step=TaintFlowStep(
            file_path="a.js", line_number=1, function_name="handler",
            step_type="source", code_snippet="", variable_name="cmd",
        ),
        source_type=TaintSourceType.HTTP_PARAMETER,
        confidence=1.0,
    )
    # From a.js's perspective the call is alias-resolved to the dotted
    # "<module_stem>.runB" chain (a require/import of tp_cross_dir_helper_b),
    # exactly how `_eval_call` in cst_taint_visitor.py invokes the resolver.
    resolved = index.resolve_call("tp_cross_dir_helper_b.runB", [tainted_arg], call_line=1)
    assert resolved.resolved is True
    # The bug: resolved=True, flows=[], return_state=None was read as an
    # authoritative clean drop for the ENTIRE call, laundering the real
    # command injection in sub/c down to 0 flows / 0 signal. The fix: since
    # runB forwards `cmd` into an out-of-index callee, this must NOT present
    # as a confident clean -- either a flow surfaces, or the returned state
    # carries a non-zero, over-approximated confidence.
    assert resolved.flows or (
        resolved.return_state is not None and resolved.return_state.confidence > 0.0
    ), (
        "BLOCKER-2 regressed: unresolved cross-directory forwarding call "
        "was treated as an authoritative clean drop (real flow muted)"
    )
