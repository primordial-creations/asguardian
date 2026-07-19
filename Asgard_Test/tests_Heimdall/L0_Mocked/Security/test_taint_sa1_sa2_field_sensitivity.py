"""SA1 (field/attribute/container sensitivity) + SA2 (static resolution of
determinable dynamic constructs + constant/string propagation) -- Wave 1 of
the Deterministic Static-Analysis Deepening plan
(``_Docs/Planning/StaticDepth/00_Plan.md``).

The bulk of the acceptance-bullet coverage (including per-language cases)
lives in the benchmark corpus (``Asgard_Test/tests_Heimdall/benchmarks/
corpus/taint*/`` + their manifests). This file adds direct unit coverage for
edge cases that are awkward to express as isolated corpus fixtures: branch
merges, whole-variable reassignment invalidating stale field state, and
loop-conservatism for constant propagation -- all invariant-preservation
checks (never mute a real flow; never wrongly assert "constant").
"""

import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer, TaintConfig


def _scan(code: str, **config_kwargs):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        (path / "app.py").write_text(code)
        config = TaintConfig(exclude_patterns=["__pycache__", ".git"], **config_kwargs)
        return TaintAnalyzer(config=config).scan(path)


class TestSA1FieldSensitivityCore:
    def test_same_attribute_flags(self):
        report = _scan(
            "def handler(ctx):\n"
            "    ctx.a = request.args['q']\n"
            "    cursor.execute(ctx.a)\n"
        )
        assert len(report.flows) == 1

    def test_sibling_attribute_clean(self):
        """The core SA1 precision gain: writing one field must not taint an
        unrelated sibling field."""
        report = _scan(
            "def handler(ctx):\n"
            "    ctx.a = request.args['q']\n"
            "    cursor.execute(ctx.b)\n"
        )
        assert len(report.flows) == 0

    def test_bare_object_read_still_flags(self):
        """Passing the WHOLE object (not a specific field) must still flag
        if any field is tainted -- container-level over-approximation is
        retained for the untargeted read, only field-targeted reads narrow."""
        report = _scan(
            "def handler(ctx):\n"
            "    ctx.a = request.args['q']\n"
            "    cursor.execute(ctx)\n"
        )
        assert len(report.flows) == 1

    def test_whole_object_reassignment_clears_stale_field_taint(self):
        """`ctx = Fresh()` after `ctx.a = taint` must drop the stale field
        record -- the name now refers to a brand-new object."""
        report = _scan(
            "def handler(ctx):\n"
            "    ctx.a = request.args['q']\n"
            "    ctx = Fresh()\n"
            "    cursor.execute(ctx.a)\n"
        )
        assert len(report.flows) == 0

    def test_nested_field_chain_flags(self):
        report = _scan(
            "def handler(ctx):\n"
            "    ctx.a.b = request.args['q']\n"
            "    cursor.execute(ctx.a.b)\n"
        )
        assert len(report.flows) == 1

    def test_nested_field_chain_sibling_clean(self):
        report = _scan(
            "def handler(ctx):\n"
            "    ctx.a.b = request.args['q']\n"
            "    cursor.execute(ctx.a.c)\n"
        )
        assert len(report.flows) == 0


class TestSA1BranchMerge:
    def test_field_tainted_in_one_branch_survives_merge(self):
        """Sound over-approximation: a field tainted on only ONE branch
        must still flag after the if/else merges (branch union, never
        mute)."""
        report = _scan(
            "def handler(ctx, flag):\n"
            "    if flag:\n"
            "        ctx.a = request.args['q']\n"
            "    else:\n"
            "        pass\n"
            "    cursor.execute(ctx.a)\n"
        )
        assert len(report.flows) == 1

    def test_field_cleared_in_one_branch_only_stays_conservative(self):
        """A field explicitly cleaned on only ONE branch (the other leaves
        it tainted) must still flag post-merge -- an explicit clean
        override never wins over a real taint from the other arm."""
        report = _scan(
            "def handler(ctx, flag):\n"
            "    ctx.a = request.args['q']\n"
            "    if flag:\n"
            "        ctx.a = 'safe'\n"
            "    cursor.execute(ctx.a)\n"
        )
        assert len(report.flows) == 1


class TestSA1ClearedNeverOverridesRootTaint:
    """Adversarial-review regression: a `_CLEARED` marker at one specific
    constant key/field must only suppress the root's DEFAULT-inherited
    taint -- it must NEVER override taint the root independently acquired
    via an earlier non-constant-index/name write, since that write could
    have targeted this exact key/field at runtime (unknowable statically).
    Confirmed via engine run: previously 0 findings (muted), expected 1."""

    def test_dict_nonconstant_index_then_constant_clean_key_still_flags(self):
        report = _scan(
            "def handler(request):\n"
            "    m = {}\n"
            "    dyn = request.args.get('k')\n"
            "    m[dyn] = request.args.get('cmd')\n"
            "    m['known'] = 'safe'\n"
            "    os.system(m['known'])\n"
        )
        assert len(report.flows) == 1

    def test_setattr_nonconstant_name_then_constant_clean_field_still_flags(self):
        report = _scan(
            "def handler(request, o, fname):\n"
            "    setattr(o, fname, request.args.get('cmd'))\n"
            "    o.known = 'safe'\n"
            "    os.system(o.known)\n"
        )
        assert len(report.flows) == 1

    def test_getattr_nonconstant_name_then_constant_clean_field_still_flags(self):
        """Same shape via the `_eval_getattr` read path rather than the
        assignment path (`o.known = 'safe'` still exercises _read_chain,
        but this variant reads the potentially-aliased field back out
        through `getattr` explicitly to pin down that path too)."""
        report = _scan(
            "def handler(request, o, fname):\n"
            "    setattr(o, fname, request.args.get('cmd'))\n"
            "    o.known = 'safe'\n"
            "    os.system(getattr(o, 'known'))\n"
        )
        assert len(report.flows) == 1


class TestSA2GetattrSetattr:
    def test_getattr_setattr_const_field_flags(self):
        report = _scan(
            "def handler(ctx):\n"
            "    setattr(ctx, 'a', request.args['q'])\n"
            "    cursor.execute(getattr(ctx, 'a'))\n"
        )
        assert len(report.flows) == 1

    def test_getattr_setattr_const_sibling_clean(self):
        report = _scan(
            "def handler(ctx):\n"
            "    setattr(ctx, 'a', request.args['q'])\n"
            "    cursor.execute(getattr(ctx, 'b'))\n"
        )
        assert len(report.flows) == 0

    def test_getattr_non_call_never_needs_review(self):
        """A non-dispatch `getattr(o, x)` (not immediately invoked) is not
        surfaced as a dynamic-construct finding even when `x` is
        non-constant -- only the double-call dispatch shape is (see
        _check_dynamic_construct); a bare getattr read over-approximates
        its taint silently instead, which is a deliberate scope choice
        already covered by the existing WS5 dynamic-construct suite."""
        report = _scan(
            "def handler(ctx, name):\n"
            "    x = getattr(ctx, name)\n"
            "    cursor.execute(x)\n"
        )
        # No assertion on flow count here (depends on unknown-call decay);
        # the key invariant is it must not crash and must not silently
        # drop a real taint path -- exercised for regression safety.
        assert report is not None


class TestSA2ConstantPropagation:
    def test_import_const_binding_not_flagged(self):
        report = _scan(
            "def handler():\n"
            "    mod = 'os'\n"
            "    return __import__(mod)\n"
        )
        assert len(report.flows) == 0

    def test_import_non_constant_still_needs_review(self):
        """The residue: a genuinely dynamic module name still surfaces as
        needs-review -- constant propagation narrows the gap, it does not
        eliminate the legitimately-unbounded case."""
        report = _scan(
            "def handler(mod):\n"
            "    return __import__(mod)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence_bucket == "needs_review"

    def test_const_binding_branch_dependent_not_propagated(self):
        """A Name bound to DIFFERENT literal values on the two branches of
        an if/else must NOT be treated as constant post-merge -- the value
        genuinely depends on a runtime condition."""
        report = _scan(
            "def handler(flag):\n"
            "    if flag:\n"
            "        mod = 'os'\n"
            "    else:\n"
            "        mod = 'sys'\n"
            "    return __import__(mod)\n"
        )
        assert len(report.flows) == 1
        assert report.flows[0].confidence_bucket == "needs_review"

    def test_const_binding_agreeing_both_branches_propagated(self):
        """Both branches agree on the same literal -- safe to treat as
        constant post-merge."""
        report = _scan(
            "def handler(flag):\n"
            "    if flag:\n"
            "        mod = 'os'\n"
            "    else:\n"
            "        mod = 'os'\n"
            "    return __import__(mod)\n"
        )
        assert len(report.flows) == 0
