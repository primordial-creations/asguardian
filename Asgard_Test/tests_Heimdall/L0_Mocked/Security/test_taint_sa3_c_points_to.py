"""SA3 (real C points-to analysis) -- Wave 2 of the Deterministic
Static-Analysis Deepening plan (``_Docs/Planning/StaticDepth/00_Plan.md``).

The bulk of the acceptance-bullet coverage lives in the benchmark corpus
(``Asgard_Test/tests_Heimdall/benchmarks/corpus/taint_c/`` + its manifest --
see the ``tp_pointer_*``/``fp_pointer_*`` sibling pairs). This file exercises
the points-to engine directly (``Security/TaintAnalysis/engine
.cst_taint_visitor``, C path) via ``DispatchEngine.scan_file`` for edge
cases and invariant-preservation checks that are clearer as isolated unit
tests than as corpus fixtures: transitive multi-level aliasing, the
struct-pointer alias-group canonical-root migration, and the never-mute
guard on an unresolved/unknown pointer.

Core invariant under test throughout (from ``ASGARD_UPLIFT_GOAL.md``):
points-to is a SOUND over-approximation -- a MAY-alias is always treated as
an alias (union), and an unresolved/unknown pointer must never be silently
treated as clean. Every "must flag" assertion below is a direct check of
that mandate; every "must stay clean" sibling proves the engine doesn't
over-approximate into uselessness (blanket-tainting everything in scope).
"""

import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine


def _scan_c(code: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "probe.c"
        path.write_text(code)
        return DispatchEngine().scan_file(path)


class TestMultiLevelPointerDeref:
    def test_double_pointer_deref_flags(self):
        """`char **pp = &p;` then `system(*pp);` must flag -- before SA3,
        `pointer_expression` (tree-sitter-c's node type for both `&x` and
        `*p`) had no case in `_eval` at all, so a dereferenced sink argument
        silently evaluated to no taint regardless of the alias union."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    char *p = buf;\n"
            "    char **pp = &p;\n"
            "    fgets(buf, 64, stdin);\n"
            "    system(*pp);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1
        assert result.taint_flows[0].cwe_id == "CWE-78"

    def test_triple_pointer_deref_flags(self):
        """Generalizes beyond double pointers: the alias-group union is
        transitive, so N levels of indirection are covered without any
        per-level bookkeeping."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    char *p = buf;\n"
            "    char **pp = &p;\n"
            "    char ***ppp = &pp;\n"
            "    fgets(buf, 64, stdin);\n"
            "    system(**ppp);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1

    def test_double_pointer_to_unrelated_buffer_stays_clean(self):
        """Never-mute's mirror image: aliasing must not blanket-taint every
        pointer in scope. `pp` chains to a buffer that is NEVER touched by
        fgets -- must stay clean even though an unrelated buffer (`buf`) in
        the same function is tainted."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    char safe[64] = \"echo hi\";\n"
            "    char *p = safe;\n"
            "    char **pp = &p;\n"
            "    fgets(buf, 64, stdin);\n"
            "    system(*pp);\n"
            "}\n"
        )
        assert result.taint_flows == []


class TestStructPointerFieldAliasing:
    def test_field_write_visible_through_later_pointer_alias(self):
        """`s->field = tainted;` recorded BEFORE `t = s;` unions the two
        pointers' alias groups must still be visible through `t->field` --
        this is the canonical-root migration in `_add_alias`/`_chain_path`,
        not merely Wave 1's single-pointer field-sensitivity (which only
        covered `s->field` read back through `s` itself)."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "struct cmd_ctx { char *field; };\n"
            "void run(void) {\n"
            "    struct cmd_ctx rec;\n"
            "    struct cmd_ctx *s = &rec;\n"
            "    char buf[64];\n"
            "    fgets(buf, 64, stdin);\n"
            "    s->field = buf;\n"
            "    struct cmd_ctx *t = s;\n"
            "    system(t->field);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1

    def test_field_write_visible_when_alias_precedes_write(self):
        """Same as above but with the alias union formed BEFORE the field
        write (`t = s;` then `s->field = tainted;` then read via `t`) --
        covers both orderings, mirroring the WS2 dynamic (never-snapshotted)
        lookup design this builds on."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "struct cmd_ctx { char *field; };\n"
            "void run(void) {\n"
            "    struct cmd_ctx rec;\n"
            "    struct cmd_ctx *s = &rec;\n"
            "    struct cmd_ctx *t = s;\n"
            "    char buf[64];\n"
            "    fgets(buf, 64, stdin);\n"
            "    s->field = buf;\n"
            "    system(t->field);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1

    def test_distinct_struct_instances_stay_unaliased(self):
        """`s` and `t` point at DIFFERENT struct instances (never unioned)
        -- `s`'s tainted field must not leak into `t->field`. Proves the
        canonical-root migration only fires when an actual alias union
        happened, not for merely-same-typed pointers."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "struct cmd_ctx { char *field; };\n"
            "void run(void) {\n"
            "    struct cmd_ctx rec_s;\n"
            "    struct cmd_ctx rec_t;\n"
            "    struct cmd_ctx *s = &rec_s;\n"
            "    struct cmd_ctx *t = &rec_t;\n"
            "    char buf[64];\n"
            "    char safe[64] = \"echo hi\";\n"
            "    fgets(buf, 64, stdin);\n"
            "    s->field = buf;\n"
            "    t->field = safe;\n"
            "    system(t->field);\n"
            "}\n"
        )
        assert result.taint_flows == []


class TestArrayDecayAliasing:
    def test_array_decay_pointer_flags(self):
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char arr[64];\n"
            "    char *p = arr;\n"
            "    fgets(arr, 64, stdin);\n"
            "    system(p);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1

    def test_array_decay_from_unrelated_array_stays_clean(self):
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char arr[64];\n"
            "    char safe[64] = \"echo hi\";\n"
            "    char *p = safe;\n"
            "    fgets(arr, 64, stdin);\n"
            "    system(p);\n"
            "}\n"
        )
        assert result.taint_flows == []


class TestUnresolvedPointerNeverMute:
    """The never-mute guard: an "unresolved"/unknown pointer -- one whose
    RHS is neither a bare identifier nor an address-of (pointer arithmetic,
    here) -- must still over-approximate and flag, not silently drop the
    flow. Confidence is decayed relative to a direct alias (the exact
    aliasing is inferred, not a proven copy) but the flow itself must never
    disappear."""

    def test_pointer_arithmetic_still_flags(self):
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    fgets(buf, 64, stdin);\n"
            "    char *p = buf + 1;\n"
            "    system(p);\n"
            "}\n"
        )
        assert len(result.taint_flows) == 1
        assert result.taint_flows[0].confidence > 0.0

    def test_pointer_arithmetic_confidence_below_direct_alias(self):
        """The inferred (unresolved-RHS) union carries strictly less
        confidence than a direct bare-identifier alias -- the analysis is
        honest about being less certain here, even though it still flags."""
        direct = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    char *p = buf;\n"
            "    fgets(buf, 64, stdin);\n"
            "    system(p);\n"
            "}\n"
        )
        arithmetic = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    fgets(buf, 64, stdin);\n"
            "    char *p = buf + 1;\n"
            "    system(p);\n"
            "}\n"
        )
        assert len(direct.taint_flows) == 1
        assert len(arithmetic.taint_flows) == 1
        assert arithmetic.taint_flows[0].confidence < direct.taint_flows[0].confidence

    def test_scalar_arithmetic_never_treated_as_pointer_alias(self):
        """The unresolved-RHS fallback is gated on the LHS being
        syntactically pointer-typed (`is_pointer_decl`) -- a plain scalar
        (`int total = a + b;`) must never be swept into a pointer-alias
        group, and must not cause any spurious cross-contamination of an
        unrelated, genuinely clean pointer."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    fgets(buf, 64, stdin);\n"
            "    int a = 1;\n"
            "    int b = 2;\n"
            "    int total = a + b;\n"
            "    char safe[64] = \"echo hi\";\n"
            "    char *p = safe + total;\n"
            "    system(p);\n"
            "}\n"
        )
        assert result.taint_flows == []

    def test_unresolved_call_result_pointer_with_no_identifiers_stays_clean(self):
        """A pointer assigned from an RHS with NO identifiers at all (a
        fresh allocation with only constant arguments) has nothing to union
        with and correctly stays untracked/clean -- over-approximation
        unions with referenced identifiers, it does not invent taint from
        nothing."""
        result = _scan_c(
            "#include <stdio.h>\n"
            "#include <stdlib.h>\n"
            "void run(void) {\n"
            "    char buf[64];\n"
            "    fgets(buf, 64, stdin);\n"
            "    char *p = malloc(64);\n"
            "    system(p);\n"
            "}\n"
        )
        assert result.taint_flows == []
