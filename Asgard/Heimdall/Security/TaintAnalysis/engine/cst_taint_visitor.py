"""
CST-backed taint visitor for JavaScript/TypeScript and Java (Phase 4,
multi-language taint per plan 04).

Mirrors the confidence-propagation, sanitizer-taxonomy, and sink kwarg
model of the Python ``ast`` visitor (``services/_taint_visitor.py``) but
walks tree-sitter CST nodes instead of stdlib ``ast`` nodes. This module is
independent of ``ast``/CPython grammar entirely -- it never imports
``_taint_visitor``'s AST-specific helpers, only the language-agnostic
``TaintState`` dataclass and taint models.

Scope and honesty notes (mirrors DEEPTHINK_04 top-level algorithm, adapted
to a CST substrate):

- Intra-procedural, forward, single-pass per function/method body. There is
  no branch-union scope stack (unlike the Python engine): taint assigned in
  any branch is kept for the remainder of the function scan. This is a
  *safe* over-approximation for a security tool (more false positives are
  acceptable; muting a real flow is not) but is coarser than the Python
  engine's precise branch union -- documented deviation.
- Inter-procedural resolution (cross-function, cross-file) is now available
  via an optional ``call_resolver`` (``engine/cst_summaries.py``'s
  ``CstSummaryIndex``, mirroring ``TaintAnalysis/summaries.py``'s Python
  design). Without a resolver, unresolved calls fall back to the x0.5
  "unknown call" decay (over-approximate, never dropped).
- Import/require aliasing IS resolved via an optional ``alias_map``
  (``engine/cst_alias.py``, built once per file) using the same
  language-agnostic ``resolve_chain`` dotted-string canonicalization as the
  Python engine: ``const cp = require('child_process'); cp.exec(x)`` and
  ``import {exec as run} from 'child_process'; run(x)`` both canonicalize to
  ``child_process.exec``. Catalog patterns also still match the
  *conventional* receiver names directly (``req``, ``db``, ...) as a
  fallback when no alias map is supplied or the receiver isn't imported.
- Java generics/annotations/lambdas are walked structurally; Spring
  ``@RequestMapping``-style route parameter seeding is not yet implemented
  (Java params are only tainted via explicit ``request.getParameter(...)``
  calls, not via method-parameter annotations) -- documented gap for a
  future summary-computation pass.
"""

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Set, Tuple

from Asgard.Heimdall.Security.normalization.priority import confidence_bucket
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sanitizers import (
    SanitizerMatch,
    classify_sanitizer,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import JAVA_SINK_SPECS, JS_SINK_SPECS, SinkSpec
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import (
    JAVA_SOURCE_SPECS,
    JS_SOURCE_SPECS,
    SourceSpec,
)
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    SanitizerRecord,
    TaintFlow,
    TaintFlowStep,
    TaintSinkType,
    TaintSourceType,
)
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_patterns import (
    SINK_CWE,
    SINK_OWASP,
    SINK_TITLES,
)
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_visitor import (
    CallResolver,
    ResolvedCall,
    TaintState,
    resolve_chain,
)
from Asgard.Heimdall.Security.TaintAnalysis.engine.cst_alias import (
    AliasOrigin,
    is_verified_sanitizer_origin,
    module_target,
)

PROPAGATOR_DECAY = 0.9
UNKNOWN_CALL_DECAY = 0.5
MOCK_NAME_FACTOR = 0.3
TEST_PATH_CONFIDENCE_CAP = 0.1
_MOCK_PREFIXES = ("mock_", "test_", "dummy_", "fake_", "sample_", "example_")

_JS_LANGS = frozenset({"javascript", "typescript", "tsx"})

_FIRST_ARG_SINKS = {
    TaintSinkType.SQL_QUERY,
    TaintSinkType.SHELL_COMMAND,
    TaintSinkType.EVAL_EXEC,
    TaintSinkType.FILE_PATH,
    TaintSinkType.TEMPLATE_RENDER,
    TaintSinkType.REDIRECT,
}

_CONTAINER_MUTATORS = frozenset({
    "append", "push", "unshift", "add", "addAll", "put", "set", "offer",
    "insert", "extend", "update", "setdefault",
})

# Container-read accessors: `list.get(i)`/`map.get(k)` etc. propagate the
# *receiver's* taint (container-granularity over-approximation), mirroring
# the subscript/index-access handling in `_eval` for `arr[0]`/`obj['k']`.
_CONTAINER_READERS = frozenset({"get", "getOrDefault", "peek", "element"})

_FUNCTION_TYPES_JS = frozenset({
    "function_declaration", "function_expression", "arrow_function",
    "method_definition", "generator_function_declaration",
})
_FUNCTION_TYPES_JAVA = frozenset({
    "method_declaration", "constructor_declaration", "lambda_expression",
})
_ALL_FUNCTION_TYPES = _FUNCTION_TYPES_JS | _FUNCTION_TYPES_JAVA

_DOM_SINK_PROPERTIES = frozenset({"innerHTML", "outerHTML"})


# ---------------------------------------------------------------- chain util

def _node_chain(node, ctx) -> str:
    """Flatten a member/field access or call target into a dotted chain."""
    if node is None:
        return ""
    t = node.type
    if t in (
        "identifier", "property_identifier", "private_property_identifier",
        "type_identifier", "shorthand_property_identifier",
    ):
        return ctx.node_text(node)
    if t == "this":
        return "this"
    if t == "member_expression":
        obj_chain = _node_chain(node.child_by_field_name("object"), ctx)
        prop_chain = _node_chain(node.child_by_field_name("property"), ctx)
        if obj_chain and prop_chain:
            return f"{obj_chain}.{prop_chain}"
        return prop_chain or obj_chain
    if t == "field_access":
        obj_chain = _node_chain(node.child_by_field_name("object"), ctx)
        field_chain = _node_chain(node.child_by_field_name("field"), ctx)
        if obj_chain and field_chain:
            return f"{obj_chain}.{field_chain}"
        return field_chain or obj_chain
    if t == "call_expression":
        fn_node = node.child_by_field_name("function")
        if (
            fn_node is not None
            and fn_node.type == "identifier"
            and ctx.node_text(fn_node) in ("require", "import")
        ):
            # Inline `require('child_process').exec(cmd)` / dynamic
            # `import('mod').then(...)` used directly as a member-expression
            # object with no intermediate variable: resolve to the required
            # module's name instead of the literal text "require"/"import",
            # or the sink chain never matches (would otherwise flatten to
            # "require.exec").
            args_node = node.child_by_field_name("arguments")
            if args_node is not None and args_node.named_children:
                first_arg = args_node.named_children[0]
                if first_arg.type == "string":
                    spec = ctx.node_text(first_arg).strip("'\"`")
                    return module_target(spec)
        return _node_chain(fn_node, ctx)
    if t == "method_invocation":
        obj_chain = _node_chain(node.child_by_field_name("object"), ctx)
        name_chain = _node_chain(node.child_by_field_name("name"), ctx)
        if obj_chain and name_chain:
            return f"{obj_chain}.{name_chain}"
        return name_chain
    if t == "object_creation_expression":
        return _node_chain(node.child_by_field_name("type"), ctx)
    if t == "parenthesized_expression" and node.named_children:
        return _node_chain(node.named_children[0], ctx)
    return ""


def _call_args(node) -> List:
    args_node = node.child_by_field_name("arguments")
    if args_node is None:
        return []
    return list(args_node.named_children)


def _find_functions(node, out: List) -> None:
    """Depth-first collection of every function-like node in the tree."""
    if node is None:
        return
    if node.type in _ALL_FUNCTION_TYPES:
        out.append(node)
    for child in node.children:
        _find_functions(child, out)


class CstFunctionTaintVisitor:
    """Tracks taint within one JS/TS function or Java method (CST-backed)."""

    def __init__(
        self,
        file_path: str,
        func_name: str,
        ctx,
        lang: str,
        custom_sources: Optional[Set[str]] = None,
        custom_sinks: Optional[Set[str]] = None,
        custom_sanitizers: Optional[Set[str]] = None,
        extra_source_specs: Sequence[SourceSpec] = (),
        extra_sink_specs: Sequence[SinkSpec] = (),
        is_test_context: bool = False,
        alias_map: Optional[Dict[str, str]] = None,
        call_resolver: Optional[CallResolver] = None,
        alias_origins: Optional[Dict[str, AliasOrigin]] = None,
    ):
        self.file_path = file_path
        self.func_name = func_name
        self.ctx = ctx
        self.lang = lang
        self.env: Dict[str, TaintState] = {}
        self.custom_sources = custom_sources or set()
        self.custom_sinks = custom_sinks or set()
        self.custom_sanitizers = custom_sanitizers or set()
        self.extra_source_specs = tuple(extra_source_specs)
        self.extra_sink_specs = tuple(extra_sink_specs)
        self.is_test_context = is_test_context
        self.alias_map = alias_map or {}
        self.alias_origins = alias_origins or {}
        self.call_resolver = call_resolver
        self.found_flows: List[TaintFlow] = []
        self._visited_calls: Set[int] = set()
        # Inter-procedural summary-mode bookkeeping (populated regardless of
        # mode, mirroring the Python visitor; only consumed when this
        # visitor is invoked from ``cst_summaries.compute_cst_file_summaries``).
        self.param_sink_hits: List[Tuple[int, SinkSpec, int, float]] = []
        self.param_call_edges: List[Tuple[str, Dict[int, int], int]] = []
        self.return_states: List[TaintState] = []
        try:
            self._lines = ctx.source_bytes.decode("utf-8", errors="replace").splitlines()
        except Exception:
            self._lines = []

    # ------------------------------------------------------------------ util

    def _line_text(self, line_number: int) -> str:
        idx = line_number - 1
        if 0 <= idx < len(self._lines):
            return self._lines[idx].strip()
        return ""

    def _make_step(self, line: int, step_type: str, variable_name: str, column: int = 0) -> TaintFlowStep:
        return TaintFlowStep(
            file_path=self.file_path,
            line_number=line,
            column=column,
            function_name=self.func_name,
            step_type=step_type,
            code_snippet=self._line_text(line),
            variable_name=variable_name,
        )

    def _fresh_source_state(self, spec: SourceSpec, line: int, var_name: str) -> TaintState:
        step = self._make_step(line, "source", var_name or spec.pattern)
        return TaintState(source_step=step, source_type=spec.source_type, confidence=spec.confidence)

    @staticmethod
    def _union(a: Optional[TaintState], b: Optional[TaintState]) -> Optional[TaintState]:
        if a is None:
            return b
        if b is None:
            return a
        return a if a.confidence >= b.confidence else b

    def _lookup_source(self, chain: str, is_call: bool) -> Optional[SourceSpec]:
        for spec in self.extra_source_specs:
            if spec.is_call and not is_call:
                continue
            if chain == spec.pattern or chain.startswith(spec.pattern + "."):
                return spec
        return None

    def _lookup_sink(self, chain: str) -> Optional[SinkSpec]:
        for spec in self.extra_sink_specs:
            if chain == spec.pattern:
                return spec
            if spec.match_suffix and chain.endswith("." + spec.pattern):
                return spec
        return None

    # ------------------------------------------------------- expression eval

    def _chain(self, node) -> str:
        """Flattened, alias-resolved dotted chain for a node."""
        return resolve_chain(_node_chain(node, self.ctx), self.alias_map)

    def _eval(self, node) -> Optional[TaintState]:
        if node is None:
            return None
        t = node.type
        if t == "identifier":
            name = self.ctx.node_text(node)
            if name in self.env:
                return self.env[name]
            resolved = resolve_chain(name, self.alias_map)
            return self._match_source_chain(resolved, node, is_call=False)
        if t in ("member_expression", "field_access"):
            chain = self._chain(node)
            state = self._match_source_chain(chain, node, is_call=False)
            if state is not None:
                return state
            return self._eval(node.child_by_field_name("object"))
        if t in ("subscript_expression", "array_access"):
            # Index/member access on a tainted container returns the
            # container's taint (container-granularity over-approximation,
            # same as the Python ast engine) -- covers JS `arr[0]`/`obj['k']`
            # and Java array-index access.
            base = node.child_by_field_name("object") or node.child_by_field_name("array")
            return self._eval(base)
        if t in ("call_expression", "method_invocation", "object_creation_expression"):
            return self._eval_call(node)
        if t == "template_string":
            state: Optional[TaintState] = None
            for child in node.named_children:
                if child.type == "template_substitution" and child.named_children:
                    state = self._union(state, self._eval(child.named_children[0]))
            return state.decayed(PROPAGATOR_DECAY) if state else None
        if t == "binary_expression":
            state = self._union(
                self._eval(node.child_by_field_name("left")),
                self._eval(node.child_by_field_name("right")),
            )
            return state.decayed(PROPAGATOR_DECAY) if state else None
        if t == "parenthesized_expression" and node.named_children:
            return self._eval(node.named_children[0])
        if t == "ternary_expression":
            return self._union(
                self._eval(node.child_by_field_name("consequence")),
                self._eval(node.child_by_field_name("alternative")),
            )
        if t in ("array", "array_initializer", "object"):
            state = None
            for child in node.named_children:
                state = self._union(state, self._eval(child))
            return state
        if t == "pair":
            return self._eval(node.child_by_field_name("value"))
        if t == "cast_expression":
            return self._eval(node.child_by_field_name("value"))
        if t == "unary_expression":
            return self._eval(node.child_by_field_name("argument"))
        if t == "assignment_expression":
            return self._eval(node.child_by_field_name("right"))
        if t == "spread_element" and node.named_children:
            return self._eval(node.named_children[0])
        if t == "await_expression" and node.named_children:
            return self._eval(node.named_children[0])
        return None

    def _match_source_chain(self, chain: str, node, is_call: bool) -> Optional[TaintState]:
        if not chain:
            return None
        spec = self._lookup_source(chain, is_call=is_call)
        if spec is None and chain in self.custom_sources:
            spec = SourceSpec(chain, TaintSourceType.HTTP_PARAMETER, 0.8)
        if spec is None:
            return None
        return self._fresh_source_state(spec, node.start_point[0] + 1, chain)

    def _sanitizer_verified(self, raw_chain: str) -> bool:
        """True only when the call's receiver/name resolves through an
        import/require binding whose ORIGIN is a genuine, allow-listed
        sanitizer package (``cst_alias.JS_SANITIZER_ALLOWED_MODULES`` /
        ``JAVA_SANITIZER_ALLOWED_MODULES``) -- e.g. ``escape-html``,
        ``dompurify``, ``org.owasp.encoder``.

        Alias-map MEMBERSHIP alone is not sufficient evidence: a relative
        import of a local, same-named no-op (``import { escapeHtml } from
        './evil_local_utils'``) also creates an alias-map binding but is NOT
        a real sanitizer -- promoting that to a full clear would mute a real
        flow. Only a resolved binding whose raw specifier is a non-relative,
        allow-listed package name is treated as verified; everything else
        (relative imports, non-allow-listed bare packages, unresolved local
        declarations) stays at the heuristic downgrade."""
        head = raw_chain.split(".", 1)[0]
        origin = self.alias_origins.get(head)
        if origin is None:
            return False
        return is_verified_sanitizer_origin(origin.raw_specifier, origin.is_relative, self.lang)

    def _eval_call(self, node) -> Optional[TaintState]:
        raw_chain = _node_chain(node, self.ctx)
        chain = resolve_chain(raw_chain, self.alias_map)
        args = _call_args(node)
        arg_states: List[Optional[TaintState]] = [self._eval(a) for a in args]
        arg_state: Optional[TaintState] = None
        for st in arg_states:
            arg_state = self._union(arg_state, st)

        sanitizer = classify_sanitizer(raw_chain, tuple(self.custom_sanitizers))
        if sanitizer is None and chain != raw_chain:
            sanitizer = classify_sanitizer(chain, tuple(self.custom_sanitizers))
        if (
            sanitizer is not None
            and sanitizer.kind == "heuristic"
            and self._sanitizer_verified(raw_chain)
        ):
            # Alias/import resolution lets a shadowable "library" sanitizer
            # (JS_LIBRARY_SANITIZERS / JAVA_LIBRARY_SANITIZERS) become a real
            # decision: the name resolves through an actual import binding,
            # not a locally-declared no-op of the same name -- clear taint.
            sanitizer = SanitizerMatch(sanitizer.name, "library-resolved", 0.0)
        if sanitizer is not None and sanitizer.factor == 0.0:
            return None

        mapping = {
            pos: st.param_index
            for pos, st in enumerate(arg_states)
            if st is not None and st.param_index is not None
        }
        if mapping:
            self.param_call_edges.append((chain, mapping, node.start_point[0] + 1))

        spec = self._lookup_source(chain, is_call=True)
        if spec is None:
            for custom in self.custom_sources:
                if chain == custom or chain.endswith(f".{custom}"):
                    spec = SourceSpec(chain, TaintSourceType.HTTP_PARAMETER, 0.8)
                    break
        if spec is not None:
            return self._fresh_source_state(spec, node.start_point[0] + 1, chain)

        method_name = chain.rsplit(".", 1)[-1] if "." in chain else chain
        if method_name in _CONTAINER_READERS:
            obj_node = node.child_by_field_name("object")
            if obj_node is None:
                fn = node.child_by_field_name("function")
                obj_node = fn.child_by_field_name("object") if fn is not None else None
            if obj_node is not None:
                receiver_state = self._eval(obj_node)
                if receiver_state is not None:
                    return receiver_state
        if method_name in _CONTAINER_MUTATORS and arg_state is not None:
            obj_node = node.child_by_field_name("object")
            if obj_node is None:
                fn = node.child_by_field_name("function")
                obj_node = fn.child_by_field_name("object") if fn is not None else None
            if obj_node is not None and obj_node.type == "identifier":
                base_name = self.ctx.node_text(obj_node)
                mutated = arg_state.decayed(1.0)
                mutated.trace.append(self._make_step(node.start_point[0] + 1, "propagation", base_name))
                self.env[base_name] = self._union(self.env.get(base_name), mutated)

        if sanitizer is not None:
            if arg_state is None:
                return None
            downgraded = arg_state.decayed(sanitizer.factor)
            if downgraded.confidence < 0.25:
                downgraded.confidence = 0.25
            downgraded.sanitizers.append(SanitizerRecord(
                name=sanitizer.name, kind=sanitizer.kind,
                factor=sanitizer.factor, line_number=node.start_point[0] + 1,
            ))
            downgraded.trace.append(self._make_step(node.start_point[0] + 1, "sanitizer", chain))
            return downgraded

        # Inter-procedural resolution (cross-function/cross-file summaries):
        # only attempted for calls carrying at least one real (non-param-seed)
        # tainted argument, or a param-forwarding edge already recorded above
        # for summary purposes. A resolved callee is authoritative: a clean
        # return (no param taint reaches a sink, no fresh source returned) is
        # a genuine drop, NOT the x0.5 unknown-call over-approximation.
        if self.call_resolver is not None and any(
            st is not None and st.param_index is None for st in arg_states
        ):
            resolved = self.call_resolver(chain, arg_states, node.start_point[0] + 1)
            if resolved.resolved:
                self.found_flows.extend(resolved.flows)
                return resolved.return_state

        if arg_state is not None:
            return arg_state.decayed(UNKNOWN_CALL_DECAY)
        return None

    # ------------------------------------------------------------ statements

    def _walk(self, node) -> None:
        if node is None:
            return
        t = node.type

        if t in _ALL_FUNCTION_TYPES:
            # Nested/child function bodies are analyzed by their own visitor
            # pass (see scan_js_ts_source/scan_java_source) -- do not
            # descend, mirroring the Python engine's per-scope isolation.
            return

        if t == "variable_declarator":
            value_node = node.child_by_field_name("value")
            name_node = node.child_by_field_name("name")
            if value_node is not None:
                state = self._eval(value_node)
                self._assign(name_node, state, node)
                self._walk(value_node)
            return

        if t == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            state = self._eval(right) if right is not None else None
            self._check_dom_sink_assignment(left, state, node)
            self._assign(left, state, node)
            if right is not None:
                self._walk(right)
            return

        if t in ("call_expression", "method_invocation", "object_creation_expression"):
            self._check_sink(node)
            for child in node.children:
                self._walk(child)
            return

        if t == "return_statement" and node.named_children:
            state = self._eval(node.named_children[0])
            if state is not None:
                self.return_states.append(state)
            self._walk(node.named_children[0])
            return

        for child in node.children:
            self._walk(child)

    def _assign(self, target_node, state: Optional[TaintState], stmt_node) -> None:
        if target_node is None:
            return
        t = target_node.type
        if t in ("array_pattern", "object_pattern"):
            for child in target_node.named_children:
                self._assign(child, state, stmt_node)
            return
        if t in ("member_expression", "field_access", "subscript_expression", "array_access"):
            base = target_node
            while base is not None and base.type in (
                "member_expression", "field_access", "subscript_expression", "array_access",
            ):
                nxt = base.child_by_field_name("object") or base.child_by_field_name("array")
                if nxt is None:
                    break
                base = nxt
            if base is not None and base.type == "identifier" and state is not None:
                name = self.ctx.node_text(base)
                stored = replace(state, trace=list(state.trace), sanitizers=list(state.sanitizers))
                stored.trace.append(self._make_step(stmt_node.start_point[0] + 1, "propagation", name))
                self.env[name] = self._union(self.env.get(name), stored)
            return
        if t != "identifier":
            return
        name = self.ctx.node_text(target_node)
        if state is None:
            # Sticky taint (never-mute mandate): a later assignment of a
            # clean/None value must NOT clear a name that was tainted
            # earlier in the scan (e.g. an if-branch taints `x`, an
            # unconditional else/later assignment sets `x` to a literal --
            # under a linear single-pass walk that would silently kill a
            # real flow). Only an explicit sanitizer call (handled in
            # ``_eval_call`` via ``classify_sanitizer``, which returns a
            # *state*, not None-through-here) clears taint. This is a
            # deliberate over-approximation: `x = tainted; x = "safe";
            # sink(x)` on a straight-line path now also reports (a false
            # positive) -- acceptable per the "muting a real flow is not
            # acceptable" invariant; document at call sites/tests.
            if name in self.env:
                return
            self.env.pop(name, None)
            return
        new_state = replace(state, trace=list(state.trace), sanitizers=list(state.sanitizers))
        new_state.trace.append(self._make_step(stmt_node.start_point[0] + 1, "propagation", name))
        self.env[name] = new_state

    def _check_dom_sink_assignment(self, left, state: Optional[TaintState], node) -> None:
        """``elem.innerHTML = tainted`` (assignment, not call) -- JS/TS only."""
        if left is None or left.type != "member_expression" or state is None:
            return
        prop = left.child_by_field_name("property")
        if prop is None:
            return
        prop_name = self.ctx.node_text(prop)
        if prop_name not in _DOM_SINK_PROPERTIES:
            return
        spec = self._lookup_sink(prop_name)
        if spec is None:
            return
        self._emit_finding(state, spec, node, prop_name)

    # ------------------------------------------------------------------ sinks

    def _check_sink(self, node) -> None:
        # tree-sitter node wrapper objects are re-created per access, so
        # id(node) is NOT a stable identity across traversal steps (a freed
        # wrapper's address can be reused for a different logical node) --
        # key on (start_byte, end_byte, type) instead.
        key = (node.start_byte, node.end_byte, node.type)
        if key in self._visited_calls:
            return
        self._visited_calls.add(key)
        # `_eval_call` also performs container-mutator side effects
        # (`list.add(tainted)` taints the receiver in `self.env`). A bare
        # call-statement like `ids.add(x);` is never routed through
        # `_eval()` (only assignment/declarator RHS positions are), so
        # without this it silently skips the mutation and a later
        # `ids.get(0)` read sees an untainted receiver -- run it here for
        # its env side effects regardless of the return value.
        self._eval_call(node)
        chain = self._chain(node)
        spec = self._lookup_sink(chain)
        custom_hit = False
        if spec is None:
            for custom in self.custom_sinks:
                if chain == custom or chain.endswith(f".{custom}"):
                    spec = SinkSpec(chain, TaintSinkType.SQL_QUERY, "high", 0.8)
                    custom_hit = True
                    break
        if spec is None:
            return

        args = _call_args(node)
        candidate_args = args[:1] if (spec.sink_type in _FIRST_ARG_SINKS and not custom_hit and args) else args
        # Emit a finding for EACH independently-tainted argument, not just
        # the first: `logger.info(a, b)` with both `a` and `b` tainted from
        # distinct sources must report both flows, or one is silently
        # muted -- unacceptable per the never-mute mandate.
        for arg in candidate_args:
            state = self._eval(arg)
            if state is None:
                continue
            if state.param_index is not None and state.source_step.step_type == "param":
                # Summary-computation mode (see cst_summaries.py): a
                # synthetic parameter seed reaching a sink is a
                # param->sink reachability fact for the summary, not a
                # reportable finding in this pass.
                path_factor = state.confidence * spec.confidence
                if path_factor > 0.0:
                    self.param_sink_hits.append(
                        (state.param_index, spec, node.start_point[0] + 1, path_factor)
                    )
                continue
            self._emit_finding(state, spec, node, chain, arg_node=arg)

    def _emit_finding(self, state: TaintState, spec: SinkSpec, node, chain: str, arg_node=None) -> None:
        context = 1.0
        if arg_node is not None and arg_node.type == "identifier":
            name = self.ctx.node_text(arg_node)
            if name.lower().startswith(_MOCK_PREFIXES):
                context *= MOCK_NAME_FACTOR
        final_conf = state.confidence * spec.confidence * context
        if final_conf > 0.0 and final_conf < 0.25 and any(s.kind == "heuristic" for s in state.sanitizers):
            final_conf = 0.25
        if self.is_test_context:
            final_conf = min(final_conf, TEST_PATH_CONFIDENCE_CAP)
        if final_conf <= 0.0:
            return
        final_conf = min(1.0, final_conf)
        # Position the sink step at the tainted ARGUMENT, not the call node
        # itself: two independently-tainted arguments to the same call
        # (e.g. `logger.info(a, b)`) otherwise share one (line, column),
        # which collapses to a single finding under dispatch's
        # (file, line, column, cwe_id) dedup key -- silently muting the
        # second argument's flow.
        pos_node = arg_node if arg_node is not None else node
        line = pos_node.start_point[0] + 1
        col = pos_node.start_point[1]
        sink_step = self._make_step(line, "sink", chain, column=col)
        self.found_flows.append(self._build_flow(state, spec, sink_step, final_conf))

    def _build_flow(self, state: TaintState, spec: SinkSpec, sink_step: TaintFlowStep, confidence: float) -> TaintFlow:
        sink_type = spec.sink_type
        sanitizer_note = ""
        if state.sanitizers:
            sanitizer_note = (
                " A heuristic sanitizer was applied along the flow; the "
                "finding is kept at reduced confidence because its "
                "effectiveness cannot be verified statically."
            )
        return TaintFlow(
            source_type=state.source_type,
            sink_type=sink_type,
            severity=spec.severity,
            source_location=state.source_step,
            sink_location=sink_step,
            intermediate_steps=list(state.trace),
            title=SINK_TITLES.get(sink_type, "Tainted Data Flow"),
            description=(
                f"Tainted data from {state.source_type} source reaches "
                f"{sink_type} sink." + sanitizer_note
            ),
            cwe_id=SINK_CWE.get(sink_type, ""),
            owasp_category=SINK_OWASP.get(sink_type, ""),
            sanitizers_present=bool(state.sanitizers),
            confidence=round(confidence, 4),
            confidence_bucket=confidence_bucket(confidence),
            hop_count=state.hop_count,
            sanitizers_applied=list(state.sanitizers),
        )


# ------------------------------------------------------------- entry points

def _scan_functions(
    file_path: str,
    ctx,
    lang: str,
    extra_source_specs: Sequence[SourceSpec],
    extra_sink_specs: Sequence[SinkSpec],
    custom_sources: Optional[Set[str]],
    custom_sinks: Optional[Set[str]],
    custom_sanitizers: Optional[Set[str]],
    is_test_context: bool,
    alias_map: Optional[Dict[str, str]] = None,
    call_resolver: Optional[CallResolver] = None,
    alias_origins: Optional[Dict[str, AliasOrigin]] = None,
) -> List[TaintFlow]:
    if ctx is None or ctx.root is None:
        return []
    functions: List = []
    _find_functions(ctx.root, functions)
    flows: List[TaintFlow] = []
    for fn in functions:
        body = fn.child_by_field_name("body")
        if body is None:
            continue
        name_node = fn.child_by_field_name("name")
        func_name = ctx.node_text(name_node) if name_node is not None else "<anonymous>"
        visitor = CstFunctionTaintVisitor(
            file_path=file_path,
            func_name=func_name,
            ctx=ctx,
            lang=lang,
            custom_sources=custom_sources,
            custom_sinks=custom_sinks,
            custom_sanitizers=custom_sanitizers,
            extra_source_specs=extra_source_specs,
            extra_sink_specs=extra_sink_specs,
            is_test_context=is_test_context,
            alias_map=alias_map,
            call_resolver=call_resolver,
            alias_origins=alias_origins,
        )
        visitor._walk(body)
        flows.extend(visitor.found_flows)
    return flows


def scan_js_ts_source(
    file_path: str,
    ctx,
    custom_sources: Optional[Set[str]] = None,
    custom_sinks: Optional[Set[str]] = None,
    custom_sanitizers: Optional[Set[str]] = None,
    is_test_context: bool = False,
    alias_map: Optional[Dict[str, str]] = None,
    call_resolver: Optional[CallResolver] = None,
    alias_origins: Optional[Dict[str, AliasOrigin]] = None,
) -> List[TaintFlow]:
    """Scan a parsed JS/TS/TSX ``FileParseContext`` for taint flows."""
    return _scan_functions(
        file_path, ctx, ctx.language if ctx is not None else "javascript",
        JS_SOURCE_SPECS, JS_SINK_SPECS,
        custom_sources, custom_sinks, custom_sanitizers, is_test_context,
        alias_map=alias_map, call_resolver=call_resolver, alias_origins=alias_origins,
    )


def scan_java_source(
    file_path: str,
    ctx,
    custom_sources: Optional[Set[str]] = None,
    custom_sinks: Optional[Set[str]] = None,
    custom_sanitizers: Optional[Set[str]] = None,
    is_test_context: bool = False,
    alias_map: Optional[Dict[str, str]] = None,
    call_resolver: Optional[CallResolver] = None,
    alias_origins: Optional[Dict[str, AliasOrigin]] = None,
) -> List[TaintFlow]:
    """Scan a parsed Java ``FileParseContext`` for taint flows."""
    return _scan_functions(
        file_path, ctx, "java",
        JAVA_SOURCE_SPECS, JAVA_SINK_SPECS,
        custom_sources, custom_sinks, custom_sanitizers, is_test_context,
        alias_map=alias_map, call_resolver=call_resolver, alias_origins=alias_origins,
    )
