"""
Heimdall Taint Analysis Visitor

Forward AST traversal with:
- TaintState carrying a confidence probability and a step trace (not bare
  set membership).
- Branch union: both arms of an ``if`` are analyzed against cloned state and
  the results are unioned (a security tool must over-approximate).
- Assignment kills: assigning a clean RHS removes taint from the target.
- Propagator decay: string mutations (f-string, BinOp concat, %, .format,
  .join) multiply confidence by 0.9 per mutation.
- Sanitizer taxonomy: exact sanitizers drop the flow (factor 0.0); heuristic
  clean_*/sanitize_*/re.sub keep it downgraded (x0.4).
- Sink kwarg semantics: subprocess shell=False drops, shell=True is certain;
  yaml.load with SafeLoader drops.
- Import-alias resolution: chains are canonicalized through the module's
  alias map before matching (``import subprocess as sp`` -> ``sp.run`` is
  ``subprocess.run``).
- Optional call resolver hook for inter-procedural summaries (x0.85 per
  resolved hop); unresolved calls with tainted arguments propagate return
  taint at x0.5 ("unknown third-party call" decay).

What this engine can and cannot conclude: it is a flow-insensitive-across-
branches, path-insensitive, alias-lite forward propagation. It
over-approximates (branch union, unknown-call return taint) and expresses
the residual uncertainty in the confidence value -- it is a shift-left
guardrail (~25-40% recall / ~70% precision class), not a deep SAST replacement.
"""

import ast
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from Asgard.Heimdall.Security.normalization.priority import confidence_bucket
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sanitizers import (
    SanitizerMatch,
    classify_sanitizer,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import (
    SUBPROCESS_NO_SHELL_FACTOR,
    SinkSpec,
    lookup_sink,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import (
    SourceSpec,
    lookup_source,
)
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    SanitizerRecord,
    TaintFlow,
    TaintFlowStep,
    TaintSinkType,
    TaintSourceType,
)

PROPAGATOR_DECAY = 0.9      # per string-mutation step
RESOLVED_HOP_DECAY = 0.85   # per resolved inter-procedural hop
UNKNOWN_CALL_DECAY = 0.5    # through an unresolved / third-party call
MOCK_NAME_FACTOR = 0.3      # variable named mock_/test_/dummy_/fake_
TEST_PATH_CONFIDENCE_CAP = 0.1

_MOCK_PREFIXES = ("mock_", "test_", "dummy_", "fake_", "sample_", "example_")

# Sink types where only the first positional argument is injectable; the
# remaining arguments are driver-bound parameters (the parameterized-call
# sanitizer: execute(sql, params) with a constant sql is safe).
_FIRST_ARG_SINKS = {
    TaintSinkType.SQL_QUERY,
    TaintSinkType.SHELL_COMMAND,
    TaintSinkType.EVAL_EXEC,
    TaintSinkType.FILE_PATH,
    TaintSinkType.TEMPLATE_RENDER,
    TaintSinkType.REDIRECT,
}


@dataclass
class TaintState:
    """Taint of a single value: provenance, confidence, and trace."""
    source_step: TaintFlowStep
    source_type: TaintSourceType
    confidence: float
    trace: List[TaintFlowStep] = field(default_factory=list)
    sanitizers: List[SanitizerRecord] = field(default_factory=list)
    hop_count: int = 0
    param_index: Optional[int] = None  # set when seeded from a function param

    def decayed(self, factor: float) -> "TaintState":
        return replace(
            self,
            confidence=self.confidence * factor,
            trace=list(self.trace),
            sanitizers=list(self.sanitizers),
        )


@dataclass
class ResolvedCall:
    """Outcome of inter-procedural call resolution.

    ``resolved=True`` means the callee was found in the scanned project and
    its summary is authoritative: ``returns_clean`` (no param taint returned,
    no fresh taint) is a taint-DROP, and the x0.5 unknown-call decay must NOT
    be applied. ``resolved=False`` means genuinely unknown/third-party.
    """
    resolved: bool = False
    return_state: Optional[TaintState] = None
    flows: List[TaintFlow] = field(default_factory=list)

    @property
    def returns_clean(self) -> bool:
        return self.resolved and self.return_state is None


# Inter-procedural resolver contract (implemented by summaries.SummaryIndex):
# resolve_call(resolved_chain, arg_states, call_line) -> ResolvedCall
CallResolver = Callable[[str, List[Optional[TaintState]], int], ResolvedCall]

# Container mutator methods: a call like x.append(tainted) taints x.
_CONTAINER_MUTATORS = frozenset({
    "append", "insert", "extend", "add", "update", "setdefault", "appendleft",
})

# Sentinel stored in `env` for a field/container key that was explicitly
# strong-updated to a KNOWN-CLEAN value (`x.a = "literal"`) -- distinct from
# "key absent" (no info recorded, defer to the base/root marker). Using a
# distinct sentinel (rather than popping the key) lets an explicit clean
# override at field granularity coexist with an unrelated whole-object taint
# marker set earlier (`x = source(); x.a = "safe"; sink(x.a)` clears,
# `sink(x.b)` still flags via the root fallback) -- SA1 field sensitivity.
_CLEARED = object()


def _attr_chain(node: ast.AST) -> str:
    """Flatten an attribute access chain into a dotted string."""
    if isinstance(node, ast.Attribute):
        parent = _attr_chain(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _attr_chain(node.func)
    return ""


def _is_constant_ast(node: ast.AST) -> bool:
    """True only when ``node`` is a compile-time constant (a literal, or an
    f-string/BinOp concatenation purely of literals) -- WS5's "eval('1+1')
    must not flag" carve-out. Anything else (names, attribute/subscript
    access, calls) is dynamic."""
    if node is None:
        return True
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.JoinedStr):
        return all(
            not isinstance(part, ast.FormattedValue) or _is_constant_ast(part.value)
            for part in node.values
        )
    if isinstance(node, ast.BinOp):
        return _is_constant_ast(node.left) and _is_constant_ast(node.right)
    return False


def _get_code_snippet(lines: List[str], line_number: int) -> str:
    idx = line_number - 1
    if 0 <= idx < len(lines):
        return lines[idx].strip()
    return ""


def build_alias_map(tree: ast.AST) -> Dict[str, str]:
    """
    Resolve import aliases for canonical chain matching.

    ``import subprocess as sp``          -> {"sp": "subprocess"}
    ``from requests import get as fetch``-> {"fetch": "requests.get"}
    ``from os import system``            -> {"system": "os.system"}
    """
    aliases: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                if a.name == "*":
                    continue
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"
    return aliases


def resolve_chain(chain: str, alias_map: Dict[str, str]) -> str:
    """Canonicalize the leading segment of a chain through the alias map."""
    if not chain:
        return chain
    head, sep, rest = chain.partition(".")
    resolved = alias_map.get(head)
    if resolved is None or resolved == head:
        return chain
    return f"{resolved}.{rest}" if sep else resolved


class _FunctionTaintVisitor(ast.NodeVisitor):
    """Tracks taint within one function (or the module body)."""

    def __init__(
        self,
        file_path: str,
        func_name: str,
        lines: List[str],
        initial_taint: Optional[Dict[str, TaintState]] = None,
        custom_sources: Optional[Set[str]] = None,
        custom_sinks: Optional[Set[str]] = None,
        custom_sanitizers: Optional[Set[str]] = None,
        alias_map: Optional[Dict[str, str]] = None,
        extra_source_specs: Sequence[SourceSpec] = (),
        extra_sink_specs: Sequence[SinkSpec] = (),
        call_resolver: Optional[CallResolver] = None,
        is_test_context: bool = False,
    ):
        self.file_path = file_path
        self.func_name = func_name
        self.lines = lines
        self.env: Dict[str, TaintState] = dict(initial_taint or {})
        # SA2 constant/string propagation: best-effort literal value of a
        # Name binding, tracked so `eval`/`__import__`/`require`-style
        # dynamic constructs and `getattr`/`setattr` field names can be
        # resolved when they reference a locally-bound constant, not just a
        # literal spelled inline. Branch-sensitive (see visit_If).
        self.const_env: Dict[str, str] = {}
        self.custom_sources = custom_sources or set()
        self.custom_sinks = custom_sinks or set()
        self.custom_sanitizers = custom_sanitizers or set()
        self.alias_map = alias_map or {}
        self.extra_source_specs = tuple(extra_source_specs)
        self.extra_sink_specs = tuple(extra_sink_specs)
        self.call_resolver = call_resolver
        self.is_test_context = is_test_context
        self.found_flows: List[TaintFlow] = []
        # Sink hits whose taint came from a synthetic parameter seed --
        # these feed function summaries and are NOT reported as findings.
        # Entries: (param_index, SinkSpec, sink_line, path_confidence_factor)
        self.param_sink_hits: List[Tuple[int, SinkSpec, int, float]] = []
        # Return-taint observations, for function-summary computation.
        self.return_states: List[TaintState] = []
        # Call edges with param-tainted args: (resolved_chain, {callee_arg_pos: param_index}, line)
        self.param_call_edges: List[Tuple[str, Dict[int, int], int]] = []

    # ------------------------------------------------------------------ util

    def _resolve(self, node: ast.AST) -> str:
        return resolve_chain(_attr_chain(node), self.alias_map)

    def _make_step(
        self, line_number: int, step_type: str, variable_name: str, column: int = 0
    ) -> TaintFlowStep:
        return TaintFlowStep(
            file_path=self.file_path,
            line_number=line_number,
            column=column,
            function_name=self.func_name,
            step_type=step_type,
            code_snippet=_get_code_snippet(self.lines, line_number),
            variable_name=variable_name,
        )

    def _fresh_source_state(
        self, spec: SourceSpec, line: int, var_name: str
    ) -> TaintState:
        step = self._make_step(line, "source", var_name or spec.pattern)
        return TaintState(
            source_step=step,
            source_type=spec.source_type,
            confidence=spec.confidence,
        )

    @staticmethod
    def _union(a: Optional[TaintState], b: Optional[TaintState]) -> Optional[TaintState]:
        """Union two taint states: keep the higher-confidence provenance."""
        if a is None:
            return b
        if b is None:
            return a
        return a if a.confidence >= b.confidence else b

    # --------------------------------------------------- SA1 field/container

    @staticmethod
    def _constant_key_repr(slice_node: Optional[ast.AST]) -> Optional[str]:
        """Repr of a subscript's index IFF it is a compile-time constant
        (str/int/bool literal) -- the sound gate for field/key-granularity
        tracking. A non-constant index (a Name, call, expression, ...)
        returns None, which callers MUST treat as "whole container tainted"
        (never as "this key is safe to ignore")."""
        s = slice_node
        if s is not None and hasattr(ast, "Index") and isinstance(s, ast.Index):
            s = s.value  # pragma: no cover - py<3.9 compat
        if isinstance(s, ast.Constant) and isinstance(s.value, (str, int, bool)):
            return repr(s.value)
        return None

    def _chain_info(
        self, node: ast.AST
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        """Walk an Attribute/Subscript chain down to its root Name.

        Returns ``(root_name, prefixes)`` where ``prefixes`` lists exact
        dotted/bracket env-keys for this chain, longest (most specific)
        first. ``prefixes is None`` means the chain contains a non-constant
        subscript SOMEWHERE along it -- callers must fall back to the root's
        whole-value taint (sound over-approximation), never treat any
        segment as a precise key. ``root_name is None`` means the chain
        isn't rooted in a bare local Name (e.g. `f().a`) -- callers fall
        back to plain sub-expression evaluation.
        """
        if isinstance(node, ast.Name):
            return node.id, []
        if isinstance(node, ast.Attribute):
            root, prefixes = self._chain_info(node.value)
            if root is None:
                return None, None
            if prefixes is None:
                return root, None
            parent = prefixes[0] if prefixes else root
            return root, [f"{parent}.{node.attr}"] + prefixes
        if isinstance(node, ast.Subscript):
            root, prefixes = self._chain_info(node.value)
            if root is None:
                return None, None
            if prefixes is None:
                return root, None
            key = self._constant_key_repr(node.slice)
            if key is None:
                return root, None  # non-constant index: truncate, sound
            parent = prefixes[0] if prefixes else root
            return root, [f"{parent}[{key}]"] + prefixes
        return None, None

    def _family_taint(self, base: str) -> Optional[TaintState]:
        """Union of every field/element taint recorded under ``base`` --
        used ONLY for a bare-name read (`sink(x)`), where the whole object
        (including any tainted sub-field) flows out. Must NOT be used for a
        specific-field read (`x.b`), which must stay scoped to that field
        plus the root marker -- otherwise a sibling field's taint would
        wrongly leak into an unrelated field read (muting the SA1
        precision gain would be fine; the reverse -- inventing cross-field
        contamination -- is a correctness bug, not a soundness necessity)."""
        result: Optional[TaintState] = None
        prefixes = (f"{base}.", f"{base}[")
        for key, value in self.env.items():
            if value is _CLEARED:
                continue
            if key.startswith(prefixes):
                result = self._union(result, value)
        return result

    def _read_chain(self, node: ast.AST) -> Optional[TaintState]:
        """Field/element-sensitive read for an Attribute/Subscript node.

        A ``_CLEARED`` marker at the specific key only suppresses the
        root's *default-inherited* taint -- it must NOT override taint the
        root independently acquired via a non-constant-index write
        elsewhere (e.g. ``m[dyn] = tainted`` taints ``env[root]`` for real,
        and a later ``m["known"] = "safe"`` cannot prove ``dyn != "known"``).
        So on a ``_CLEARED`` hit we fall back to (union with) the root's
        own non-``_CLEARED`` taint rather than returning None outright.
        """
        root, prefixes = self._chain_info(node)
        if root is None:
            return self._eval(node.value)
        root_value = self.env.get(root)
        root_state = None if root_value is _CLEARED else root_value
        if prefixes:
            for path in prefixes:
                if path in self.env:
                    value = self.env[path]
                    if value is _CLEARED:
                        return root_state
                    return value
        return root_state

    # ------------------------------------------------------- expression eval

    def _eval(self, node: ast.AST) -> Optional[TaintState]:
        """Taint state of an expression, with propagator decay applied."""
        if isinstance(node, ast.Name):
            state = self.env.get(node.id)
            if state is not None:
                return None if state is _CLEARED else state
            family = self._family_taint(node.id)
            if family is not None:
                return family
            return self._match_source_chain(node)
        if isinstance(node, ast.Attribute):
            src = self._match_source_chain(node)
            if src is not None:
                return src
            return self._read_chain(node)
        if isinstance(node, ast.Subscript):
            # Preserve source-detection precedence: `request.args['q']`
            # must still match the `request.args` dict-like source spec
            # (checked on the base expression) BEFORE falling to
            # field/element-key container tracking.
            src = self._match_source_chain(node.value)
            if src is not None:
                return src
            return self._read_chain(node)
        if isinstance(node, ast.Starred):
            return self._eval(node.value)
        if isinstance(node, ast.Call):
            return self._eval_call(node)
        if isinstance(node, ast.JoinedStr):
            state: Optional[TaintState] = None
            for part in node.values:
                if isinstance(part, ast.FormattedValue):
                    state = self._union(state, self._eval(part.value))
            return state.decayed(PROPAGATOR_DECAY) if state else None
        if isinstance(node, ast.BinOp):
            state = self._union(self._eval(node.left), self._eval(node.right))
            return state.decayed(PROPAGATOR_DECAY) if state else None
        if isinstance(node, ast.BoolOp):
            state = None
            for v in node.values:
                state = self._union(state, self._eval(v))
            return state
        if isinstance(node, ast.IfExp):
            return self._union(self._eval(node.body), self._eval(node.orelse))
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            state = None
            for elt in node.elts:
                state = self._union(state, self._eval(elt))
            return state
        if isinstance(node, ast.Dict):
            state = None
            for v in list(node.keys) + list(node.values):
                if v is not None:
                    state = self._union(state, self._eval(v))
            return state
        if isinstance(node, ast.NamedExpr):
            return self._eval(node.value)
        if isinstance(node, ast.Await):
            return self._eval(node.value)
        return None

    def _match_source_chain(self, node: ast.AST) -> Optional[TaintState]:
        chain = self._resolve(node)
        if not chain:
            return None
        spec = lookup_source(chain, is_call=False, extra_specs=self.extra_source_specs)
        if spec is None and chain in self.custom_sources:
            spec = SourceSpec(chain, TaintSourceType.HTTP_PARAMETER, 0.8)
        if spec is None:
            return None
        return self._fresh_source_state(spec, getattr(node, "lineno", 1), chain)

    def _getattr_field_name(self, name_node: ast.AST) -> Optional[str]:
        """String value of a `getattr`/`setattr` name argument IFF it is
        statically determinable (literal or tracked const binding)."""
        value = self._const_str_value(name_node)
        return value

    def _eval_getattr(self, node: ast.Call) -> Optional[TaintState]:
        """`getattr(o, "name"[, default])` with a determinable name ->
        treat exactly as `o.name` (field-sensitive read); the optional
        default is unioned in (either could be the runtime value)."""
        field = self._getattr_field_name(node.args[1])
        if field is None:
            return None
        base_node = node.args[0]
        state: Optional[TaintState] = None
        if isinstance(base_node, ast.Name):
            root, _ = self._chain_info(base_node)
            bv = self.env.get(root)
            root_state = None if bv is _CLEARED else bv
            path = f"{root}.{field}"
            if path in self.env:
                v = self.env[path]
                # A _CLEARED marker at the specific field must not override
                # taint the root independently acquired (e.g. via
                # setattr(o, dyn_name, tainted)) -- fall back to root state
                # instead of asserting safety (never mute a real flow).
                state = root_state if v is _CLEARED else v
            else:
                state = root_state
        else:
            state = self._eval(base_node)
        if len(node.args) >= 3:
            state = self._union(state, self._eval(node.args[2]))
        return state

    def _eval_setattr(self, node: ast.Call) -> bool:
        """`setattr(o, "name", value)` with a determinable name -> treat
        exactly as `o.name = value` (field-sensitive strong update).
        Returns True when handled.

        A NON-determinable name is also handled here (not left to fall
        through to the generic unresolved-call path, which would drop the
        side effect on ``o`` entirely): mirroring `_assign_target`'s
        non-constant-index container laundering, the value taints the
        WHOLE base object -- sound over-approximation, since the actual
        field cannot be ruled out to be any specific known field (never
        mute a real flow by silently forgetting the write happened)."""
        base_node = node.args[0]
        value_state = self._eval(node.args[2])
        field = self._getattr_field_name(node.args[1])
        if field is None:
            if isinstance(base_node, ast.Name) and value_state is not None:
                stored = replace(
                    value_state, trace=list(value_state.trace),
                    sanitizers=list(value_state.sanitizers),
                )
                stored.trace.append(
                    self._make_step(node.lineno, "propagation", base_node.id)
                )
                existing = self.env.get(base_node.id)
                existing = None if existing is _CLEARED else existing
                self.env[base_node.id] = self._union(existing, stored)
            return True
        if not isinstance(base_node, ast.Name):
            return True  # determinable name, but no trackable base: no-op
        path = f"{base_node.id}.{field}"
        if value_state is None:
            self.env[path] = _CLEARED
        else:
            stored = replace(
                value_state, trace=list(value_state.trace),
                sanitizers=list(value_state.sanitizers),
            )
            stored.trace.append(self._make_step(node.lineno, "propagation", path))
            self.env[path] = stored
        return True

    def _eval_call(self, node: ast.Call) -> Optional[TaintState]:
        chain = self._resolve(node.func)
        arg_nodes = list(node.args) + [kw.value for kw in node.keywords]
        arg_state: Optional[TaintState] = None
        for arg in arg_nodes:
            arg_state = self._union(arg_state, self._eval(arg))

        # 0. SA2: `getattr(o, "name")` / `setattr(o, "name", v)` with a
        #    LITERAL/CONST attribute name resolve to plain attribute
        #    access/assignment (`o.name`) at full field-sensitive fidelity
        #    -- no artificial decay, no dynamic-construct finding (that
        #    residue is reserved for a genuinely non-constant name, handled
        #    separately by `_check_dynamic_construct`'s getattr-dispatch
        #    check). A non-constant name falls through unchanged to the
        #    normal unresolved-call handling below.
        if chain == "getattr" and len(node.args) >= 2:
            resolved = self._eval_getattr(node)
            if resolved is not None or self._is_determinable(node.args[1]):
                return resolved
        if chain == "setattr" and len(node.args) >= 3:
            handled = self._eval_setattr(node)
            if handled:
                return None

        # 1. Exact sanitizer (known-complete neutralizer): taint dropped.
        #    Heuristic (name-based) matches are held back: if the callee
        #    resolves to an in-project function, its summary is authoritative
        #    (a no-op `sanitize_*` wrapper must NOT mute the finding).
        sanitizer = classify_sanitizer(chain, tuple(self.custom_sanitizers))
        if sanitizer is not None and sanitizer.factor == 0.0:
            return None

        # 2. Source call (input(), request.args.get(...), custom sources)?
        spec = lookup_source(chain, is_call=True, extra_specs=self.extra_source_specs)
        if spec is None:
            for custom in self.custom_sources:
                if chain == custom or chain.endswith(f".{custom}"):
                    spec = SourceSpec(chain, TaintSourceType.HTTP_PARAMETER, 0.8)
                    break
        if spec is not None:
            return self._fresh_source_state(spec, node.lineno, chain)

        # 3. Method call on a receiver: container mutators taint the
        #    receiver (x.append(tainted)); tainted receivers propagate
        #    through string-mutation methods (s.format(...)).
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in _CONTAINER_MUTATORS and arg_state is not None:
                base = node.func.value
                if isinstance(base, ast.Name):
                    mutated = arg_state.decayed(1.0)
                    mutated.trace.append(
                        self._make_step(node.lineno, "propagation", base.id)
                    )
                    self.env[base.id] = self._union(
                        self.env.get(base.id), mutated
                    )
            recv_state = self._eval(node.func.value)
            if recv_state is not None:
                combined = self._union(recv_state, arg_state) or recv_state
                return combined.decayed(PROPAGATOR_DECAY)

        # 4. Inter-procedural: record param-forwarding call edges (used by
        #    summary computation) and consult the resolver when available.
        #    A RESOLVED callee's summary is authoritative: returns-clean
        #    drops taint; the x0.5 unknown-call decay never applies.
        positional_states = [self._eval(a) for a in node.args]
        self._record_param_call_edge(chain, positional_states, node.lineno)
        if self.call_resolver is not None:
            resolution = self.call_resolver(chain, positional_states, node.lineno)
            for flow in resolution.flows:
                self._record_flow(flow)
            if resolution.resolved:
                return resolution.return_state  # None == returns clean

        # 5. Unresolved call: heuristic-named sanitizers downgrade (x0.4)
        #    but may never push a flow below the visible 'possible' bucket
        #    (0.25) -- an unverified name must not make a finding vanish.
        if sanitizer is not None:
            if arg_state is None:
                return None
            downgraded = arg_state.decayed(sanitizer.factor)
            if downgraded.confidence < 0.25:
                downgraded.confidence = 0.25
            downgraded.sanitizers.append(SanitizerRecord(
                name=sanitizer.name, kind=sanitizer.kind,
                factor=sanitizer.factor, line_number=node.lineno,
            ))
            downgraded.trace.append(
                self._make_step(node.lineno, "sanitizer", chain)
            )
            return downgraded

        # 6. Unknown call with tainted arguments: over-approximate return
        #    taint through a third-party/unresolved call at x0.5.
        if arg_state is not None:
            return arg_state.decayed(UNKNOWN_CALL_DECAY)
        return None

    def _record_param_call_edge(
        self, chain: str, arg_states: List[Optional[TaintState]], line: int
    ) -> None:
        mapping = {
            pos: st.param_index
            for pos, st in enumerate(arg_states)
            if st is not None and st.param_index is not None
        }
        if mapping:
            self.param_call_edges.append((chain, mapping, line))

    # ------------------------------------------------------------ statements

    def visit_Assign(self, node: ast.Assign) -> None:
        state = self._eval(node.value)
        for target in node.targets:
            self._assign_target(target, state, node.lineno)
        # SA2 constant/string propagation: remember simple Name bindings to
        # a compile-time-foldable string/literal value so a later
        # `eval`/`__import__`/`getattr` reference to that Name can be
        # resolved instead of staying an undecidable "needs review".
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            const_value = self._const_str_value(node.value)
            if const_value is not None:
                self.const_env[node.targets[0].id] = const_value
            else:
                self.const_env.pop(node.targets[0].id, None)
        self.generic_visit(node)

    def _const_str_value(self, node: ast.AST) -> Optional[str]:
        """Best-effort compile-time constant-fold to a string, else None.
        Covers literal concatenation (`"a" + "b"`), f-strings/JoinedStr of
        constants, and references to a Name already known-constant in
        ``const_env`` (simple const-binding propagation)."""
        if node is None:
            return ""
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else str(node.value)
        if isinstance(node, ast.Name):
            return self.const_env.get(node.id)
        if isinstance(node, ast.JoinedStr):
            parts: List[str] = []
            for part in node.values:
                value = self._const_str_value(
                    part.value if isinstance(part, ast.FormattedValue) else part
                )
                if value is None:
                    return None
                parts.append(value)
            return "".join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._const_str_value(node.left)
            right = self._const_str_value(node.right)
            if left is None or right is None:
                return None
            return left + right
        return None

    def _is_determinable(self, node: Optional[ast.AST]) -> bool:
        """True when ``node`` is statically resolvable to a known value --
        either a pure-literal constant (``_is_constant_ast``) or a
        constant-foldable expression through tracked const bindings
        (``const_env``). Used to gate SA2 dynamic-construct resolution:
        only a genuinely NON-determinable operand stays needs-review."""
        return _is_constant_ast(node) or self._const_str_value(node) is not None

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._assign_target(node.target, self._eval(node.value), node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        rhs = self._eval(node.value)
        if isinstance(node.target, ast.Name):
            existing = self.env.get(node.target.id)
            combined = self._union(existing, rhs)
            if combined is not None:
                combined = combined.decayed(PROPAGATOR_DECAY)
                self.env[node.target.id] = combined
        self.generic_visit(node)

    def _clear_family(self, base: str) -> None:
        """A fresh whole-value reassignment (`x = ...`) invalidates every
        previously-recorded field/element key for ``x`` -- it now refers to
        a brand-new value, so stale `x.a`/`x["k"]` entries from the old
        value must not linger and produce stale findings/stale clears."""
        prefixes = (f"{base}.", f"{base}[")
        for key in [k for k in self.env if k.startswith(prefixes)]:
            del self.env[key]

    def _assign_target(
        self, target: ast.AST, state: Optional[TaintState], line: int
    ) -> None:
        if isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._assign_target(elt, state, line)
            return
        if isinstance(target, (ast.Subscript, ast.Attribute)):
            # SA1 field/container sensitivity: a constant-key chain
            # (`x.a = ...` / `x["a"] = ...`) is a STRONG update at that
            # exact key -- it does not touch sibling fields, and an
            # explicit clean store records a CLEARED override so a stale
            # whole-object taint marker doesn't leak into this one known
            # field. A non-constant index anywhere in the chain (`x[i] = `)
            # is undecidable -- sound over-approximation taints the WHOLE
            # base object (never narrows to "safe"), matching the prior
            # one-level behavior generalized across chain depth.
            root, prefixes = self._chain_info(target)
            if root is None:
                return
            if prefixes:
                path = prefixes[0]
                if state is None:
                    self.env[path] = _CLEARED
                else:
                    stored = replace(
                        state, trace=list(state.trace),
                        sanitizers=list(state.sanitizers),
                    )
                    stored.trace.append(self._make_step(line, "propagation", path))
                    self.env[path] = stored
                return
            # Non-constant index somewhere in the chain: container laundering
            # taints the base container. A clean element store does NOT
            # clear the container (other elements may still be tainted).
            if state is not None:
                stored = replace(
                    state, trace=list(state.trace),
                    sanitizers=list(state.sanitizers),
                )
                stored.trace.append(self._make_step(line, "propagation", root))
                existing = self.env.get(root)
                existing = None if existing is _CLEARED else existing
                self.env[root] = self._union(existing, stored)
            return
        if not isinstance(target, ast.Name):
            return
        # Whole-variable reassignment: the name now refers to a fresh value,
        # so any previously-tracked field/element sub-state is stale.
        self._clear_family(target.id)
        if state is None:
            # Assignment kills taint when the RHS is clean.
            self.env.pop(target.id, None)
            self.const_env.pop(target.id, None)
            return
        new_state = replace(
            state, trace=list(state.trace), sanitizers=list(state.sanitizers)
        )
        if new_state.source_step.variable_name in ("", new_state.source_step.code_snippet):
            new_state.source_step = replace_variable_name(new_state.source_step, target.id)
        new_state.trace.append(self._make_step(line, "propagation", target.id))
        self.env[target.id] = new_state

    # ------------------------------------------------- SA4 path-sensitivity

    # Cross-language-consistent (mirrors the CST engine's Number.isInteger/
    # isFinite choice), GENUINE value-domain predicates: a string for which
    # one of these returns True is PROVABLY restricted to a character class
    # that cannot carry an injection payload (SQL/shell/HTML/path special
    # characters are all excluded from digit/alnum/numeric/decimal charsets).
    # This is NOT a new "semantic validator" invention -- it is the same
    # kind of value-domain proof already used for the `int()`/`float()`
    # EXACT_SANITIZERS entries in catalog/sanitizers.py, just expressed as a
    # boolean predicate instead of a transform. Anything not in this set
    # (isValid, is_safe, custom validators, `x != None`, `x is not None`,
    # truthiness checks, ...) is deliberately NOT recognized here -- an
    # unverified/heuristic guard must never clear taint (never mute).
    _VALIDATOR_STR_METHODS = frozenset({"isdigit", "isalnum", "isnumeric", "isdecimal"})
    _VALIDATOR_ISINSTANCE_SAFE_TYPES = frozenset({"int", "float"})

    def _classify_guard(self, test: ast.AST) -> Optional[Tuple[str, bool]]:
        """Detect `if <validator>(x):` / `if not <validator>(x):` where
        <validator> is one of the whitelisted, provably value-domain-
        restricting predicates above, with a single bare-Name argument.

        Returns ``(var_name, body_is_validated_arm)`` -- the SENSE tells the
        caller which branch (test-True/body, or test-False/else) is the one
        where ``var_name`` is PROVEN restricted. Returns ``None`` for any
        other test shape, including calls to functions this engine cannot
        verify (a non-whitelisted call must not clear taint on either arm --
        both `visit_If` arms are then processed with the ordinary sound
        union, so an unguarded/unverified-guard path still flags).
        """
        negated = False
        inner = test
        if isinstance(inner, ast.UnaryOp) and isinstance(inner.op, ast.Not):
            negated = True
            inner = inner.operand
        if not isinstance(inner, ast.Call):
            return None
        if (
            isinstance(inner.func, ast.Attribute)
            and inner.func.attr in self._VALIDATOR_STR_METHODS
            and not inner.args
            and isinstance(inner.func.value, ast.Name)
        ):
            return inner.func.value.id, not negated
        chain = self._resolve(inner.func)
        if chain == "isinstance" and len(inner.args) == 2:
            target, type_arg = inner.args
            if not isinstance(target, ast.Name):
                return None
            if isinstance(type_arg, ast.Name):
                type_names = [type_arg.id]
            elif isinstance(type_arg, ast.Tuple):
                type_names = [t.id for t in type_arg.elts if isinstance(t, ast.Name)]
            else:
                return None
            if type_names and all(
                t in self._VALIDATOR_ISINSTANCE_SAFE_TYPES for t in type_names
            ):
                return target.id, not negated
        return None

    @staticmethod
    def _is_terminal_block(stmts: List[ast.stmt]) -> bool:
        """Conservative check: does this block ALWAYS exit the enclosing
        function/loop (so control never falls through to code after the
        ``if``)? Used ONLY to decide which arm's env feeds post-if code on
        a branch join -- never to clear taint by itself. Anything not
        recognized as certainly terminal (a bare last-statement Return/
        Raise/Continue/Break, or a nested if/else whose BOTH arms are
        terminal) is treated as non-terminal, i.e. the normal sound union
        merge still applies -- this can only gain precision, never mute a
        flow that the union would otherwise have kept."""
        if not stmts:
            return False
        last = stmts[-1]
        if isinstance(last, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
            return True
        if isinstance(last, ast.If) and last.orelse:
            return (
                _FunctionTaintVisitor._is_terminal_block(last.body)
                and _FunctionTaintVisitor._is_terminal_block(last.orelse)
            )
        return False

    def visit_If(self, node: ast.If) -> None:
        self._eval(node.test)
        # Context-coverage fix (adversarial review): `_eval` only computes
        # a taint STATE for the test expression -- it never dispatches to
        # `visit_Call`, so a dynamic construct used directly as (or nested
        # in) an `if`/`while` TEST, e.g. `if eval(req.query.x):`, was
        # silently never checked for a sink/dynamic-construct finding.
        # `self.visit(node.test)` re-walks just the test expression: if it
        # IS a Call, this dispatches straight to `visit_Call`; otherwise
        # (BoolOp/Compare/...) `generic_visit` recurses into it and reaches
        # any nested Call the same way `visit_Expr`/`visit_Assign` already
        # do for their own RHS expressions.
        self.visit(node.test)

        # SA4 path-sensitivity: a test that is (or negates) a call to one of
        # the whitelisted value-domain predicates PROVES the guarded
        # variable's value-domain on exactly the arm indicated by
        # `_classify_guard`'s sense. Only that specific variable, only in
        # that specific arm, is cleared before the arm's own statements are
        # visited -- an unrecognized/unverified guard (e.g. `if is_valid(x)`
        # where `is_valid` is not a catalog-verified predicate, or
        # `if x != None`) returns None and nothing is cleared, so the
        # ordinary union-only merge below still applies and an unguarded
        # path still flags.
        guard = self._classify_guard(node.test)

        saved = dict(self.env)
        saved_const = dict(self.const_env)
        if guard is not None:
            var, body_validated = guard
            if body_validated:
                self.env[var] = _CLEARED
        for stmt in node.body:
            self.visit(stmt)
        body_env = self.env
        body_const = self.const_env

        self.env = dict(saved)
        self.const_env = dict(saved_const)
        if guard is not None:
            var, body_validated = guard
            if not body_validated:
                self.env[var] = _CLEARED
        for stmt in node.orelse:
            self.visit(stmt)
        else_env = self.env
        else_const = self.const_env

        # SA4 branch-join generalization: when one arm ALWAYS exits the
        # enclosing function/loop (early-return / guard-clause / raise),
        # code after the `if` is only ever reached via the OTHER arm --
        # feed the merge from that arm alone instead of unioning in the
        # terminal arm's (irrelevant-to-what-follows) env. This is what
        # makes the classic `if not is_valid(x): return` guard-clause
        # pattern actually clear x for the code that follows: the
        # terminating body arm is excluded, and the else arm (empty when
        # there's no explicit `else`, i.e. `saved` with the guard applied)
        # is what the merge is built from. When NEITHER arm is (verifiably)
        # terminal, this makes no assumption and falls through to the
        # ordinary sound union -- an unguarded path (no early return, both
        # arms fall through) still gets its taint unioned in, still flags.
        body_terminal = self._is_terminal_block(node.body)
        else_terminal = self._is_terminal_block(node.orelse) if node.orelse else False
        if body_terminal and not else_terminal:
            merged = dict(else_env)
            merged_const = dict(else_const)
        elif else_terminal and not body_terminal:
            merged = dict(body_env)
            merged_const = dict(body_const)
        else:
            # Branch union: over-approximate by keeping taint from either arm.
            merged = {}
            for name in set(body_env) | set(else_env):
                merged_value = self._merge_branch_value(body_env.get(name), else_env.get(name))
                if merged_value is not None:
                    merged[name] = merged_value
            # Const bindings only survive the merge when BOTH arms agree on
            # the exact same value -- a branch-dependent constant is not
            # safely "the" constant post-merge (would risk wrongly
            # resolving/clearing a dynamic-construct finding on the other
            # path).
            merged_const = {}
            for name in set(body_const) & set(else_const):
                if body_const[name] == else_const[name]:
                    merged_const[name] = body_const[name]
        self.env = merged
        self.const_env = merged_const

    @staticmethod
    def _merge_branch_value(a, b):
        """3-state branch-merge for an env entry: a real TaintState, the
        ``_CLEARED`` sentinel (explicit known-clean strong update), or
        absent (no info -- defers to the root/base marker elsewhere).
        Sound rule: a real taint from EITHER arm always survives (never
        mute a real flow); an explicit clean override only survives when
        BOTH arms agree; a clean override facing "no info" from the other
        arm is dropped back to absent rather than promoted to CLEARED,
        since the other arm's true status is unknown and must not be
        asserted safe."""
        a_state = None if a is _CLEARED else a
        b_state = None if b is _CLEARED else b
        if a_state is not None or b_state is not None:
            return _FunctionTaintVisitor._union(a_state, b_state)
        if a is _CLEARED and b is _CLEARED:
            return _CLEARED
        return None

    def visit_For(self, node: ast.For) -> None:
        iter_state = self._eval(node.iter)
        # Context-coverage fix (adversarial review): same rationale as
        # visit_If's `self.visit(node.test)` -- a dynamic construct in the
        # loop's ITER expression (`for x in getattr(o, v)():`) must still
        # reach `visit_Call`.
        self.visit(node.iter)
        if iter_state is not None:
            self._assign_target(node.target, iter_state, node.lineno)
        saved = dict(self.env)
        saved_const = dict(self.const_env)
        for stmt in list(node.body) + list(node.orelse):
            self.visit(stmt)
        for name, st in saved.items():
            if name not in self.env:
                self.env[name] = st
            else:
                self.env[name] = self._merge_branch_value(self.env[name], st)
        # Const bindings set/mutated inside a loop body may vary across
        # iterations -- conservative: only a const known BEFORE the loop
        # and left untouched (or reaffirmed identically) survives.
        self.const_env = {
            k: v for k, v in saved_const.items()
            if self.const_env.get(k, v) == v
        }

    def visit_While(self, node: ast.While) -> None:
        self._eval(node.test)
        # Context-coverage fix (adversarial review): same rationale as
        # visit_If's `self.visit(node.test)`.
        self.visit(node.test)
        saved = dict(self.env)
        saved_const = dict(self.const_env)
        for stmt in list(node.body) + list(node.orelse):
            self.visit(stmt)
        for name, st in saved.items():
            if name not in self.env:
                self.env[name] = st
            else:
                self.env[name] = self._merge_branch_value(self.env[name], st)
        self.const_env = {
            k: v for k, v in saved_const.items()
            if self.const_env.get(k, v) == v
        }

    def visit_Expr(self, node: ast.Expr) -> None:
        self._eval(node.value)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            state = self._eval(node.value)
            if state is not None:
                self.return_states.append(state)
            # Context-coverage fix (adversarial review): `_eval` only
            # computes a taint STATE -- it never dispatches to `visit_Call`,
            # so `return eval(x)` / `return getattr(o, v)()` / `return
            # __import__(v)` were silently never checked for a sink/
            # dynamic-construct finding (only assignment-RHS, bare-Expr-
            # statement, and call-argument positions were covered). Same
            # `self.visit(...)` re-walk as visit_If/visit_While/visit_For.
            self.visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Nested/child function bodies are analyzed separately by the
        # analyzer; do not descend (avoids duplicate flows).
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    # ------------------------------------------------------------------ sinks

    def visit_Call(self, node: ast.Call) -> None:
        # MAJOR-2 (adversarial review): a call site that already produced
        # a concrete taint-flow sink finding (e.g. `eval(taint)` matching
        # the `eval_exec` CWE-95 sink) must not ALSO emit a redundant WS5
        # dynamic_construct finding for the same node -- DYNAMIC_CONSTRUCT
        # is reserved for constructs with no concrete sink match (getattr
        # dispatch, __import__, ...).
        flows_before = len(self.found_flows)
        self._check_sink(node)
        sink_hit = len(self.found_flows) > flows_before
        if not sink_hit:
            self._check_dynamic_construct(node)
        self.generic_visit(node)

    # -------------------------------------------------- WS5 dynamic-construct

    def _check_dynamic_construct(self, node: ast.Call) -> None:
        """Surface eval/exec/getattr-dispatch/__import__ constructs reached
        with a non-constant operand as an explicit needs-review finding,
        independent of whether the operand resolves to a known taint
        source (see the CST engine's mirror of this in
        ``engine/cst_taint_visitor.py`` for the full WS5 rationale)."""
        chain = self._resolve(node.func)
        label = ""
        severity = "high"
        check_arg = None
        always_flag = False

        if chain in ("eval", "exec") and node.args:
            label, severity, check_arg = chain, "critical", node.args[0]
        elif chain == "__import__" and node.args:
            label, severity, check_arg = "dynamic __import__", "high", node.args[0]
        elif isinstance(node.func, ast.Call):
            # `getattr(obj, user_input)(...)` -- the callee itself is a
            # getattr() call whose attribute-name argument is dynamic.
            inner = node.func
            inner_chain = self._resolve(inner.func)
            if inner_chain == "getattr" and len(inner.args) >= 2:
                label, severity = "getattr-dispatch", "high"
                check_arg = inner.args[1]
                # NOT always_flag: a statically-constant attribute name
                # (`getattr(obj, "create")(...)`) is ordinary, decidable
                # code and must not flag (WS5 "constant arg must not
                # flag" requirement) -- only a non-constant attribute
                # name makes the dispatch target undecidable.

        if not label:
            return
        if not always_flag and check_arg is not None and self._is_determinable(check_arg):
            return
        self._emit_dynamic_construct(node, label, severity, check_arg)

    def _emit_dynamic_construct(
        self, node: ast.Call, label: str, severity: str, arg_node: Optional[ast.AST]
    ) -> None:
        pos_node = arg_node if arg_node is not None else node
        line = getattr(pos_node, "lineno", node.lineno)
        col = getattr(pos_node, "col_offset", node.col_offset)
        sink_step = self._make_step(line, "sink", label, column=col)
        confidence = 0.3
        tainted = False
        if arg_node is not None:
            state = self._eval(arg_node)
            if state is not None:
                tainted = True
                confidence = max(confidence, min(0.45, 0.25 + state.confidence * 0.2))
        source_step = self._make_step(line, "source", label)
        flow = TaintFlow(
            source_type=TaintSourceType.USER_INPUT,
            sink_type=TaintSinkType.DYNAMIC_CONSTRUCT,
            severity=severity,
            source_location=source_step,
            sink_location=sink_step,
            intermediate_steps=[],
            title=f"Dynamic construct reached: {label} (needs review)",
            description=(
                f"A dynamic/reflective construct ({label}) was reached with "
                "a non-constant operand"
                + (" that may itself be tainted" if tainted else "")
                + ". Static analysis cannot prove what code path or target "
                "this resolves to at runtime -- this is surfaced as an "
                "explicit needs-review finding rather than silently "
                "skipped. Confidence is deliberately kept low/needs-review: "
                "this is neither a confirmed vulnerability nor confirmed "
                "safe."
            ),
            cwe_id="CWE-470",
            owasp_category="A03:2021",
            sanitizers_present=False,
            confidence=confidence,
            confidence_bucket="needs_review",
            hop_count=0,
            sanitizers_applied=[],
            finding_class="dynamic_construct",
        )
        self._record_flow(flow)

    def _check_sink(self, node: ast.Call) -> None:
        chain = self._resolve(node.func)
        spec = lookup_sink(chain, extra_specs=self.extra_sink_specs)
        custom_hit = False
        if spec is None:
            for custom in self.custom_sinks:
                if chain == custom or chain.endswith(f".{custom}"):
                    spec = SinkSpec(chain, TaintSinkType.SQL_QUERY, "high", 0.8)
                    custom_hit = True
                    break
        if spec is None:
            return

        kwarg_factor = self._kwarg_factor(spec, node)
        if kwarg_factor <= 0.0:
            return

        sink_type = spec.sink_type
        if sink_type in _FIRST_ARG_SINKS and not custom_hit:
            candidate_args = node.args[:1]
        else:
            candidate_args = list(node.args) + [kw.value for kw in node.keywords]

        for arg in candidate_args:
            state = self._eval(arg)
            if state is None:
                continue
            if (
                state.param_index is not None
                and state.source_step.step_type == "param"
            ):
                # Synthetic parameter seed (summary mode): record the
                # param->sink reachability, do not report a finding.
                path_factor = state.confidence * spec.confidence * kwarg_factor
                if path_factor > 0.0:
                    self.param_sink_hits.append(
                        (state.param_index, spec, node.lineno, path_factor)
                    )
                continue
            context = 1.0
            if isinstance(arg, ast.Name) and arg.id.lower().startswith(_MOCK_PREFIXES):
                context *= MOCK_NAME_FACTOR
            final_conf = state.confidence * spec.confidence * kwarg_factor * context
            if final_conf > 0.0 and final_conf < 0.25 and any(
                s.kind == "heuristic" for s in state.sanitizers
            ):
                # A heuristic (name-based, unverified) sanitizer downgrade
                # must never make a finding vanish below the visible
                # 'possible' bucket.
                final_conf = 0.25
            if self.is_test_context:
                final_conf = min(final_conf, TEST_PATH_CONFIDENCE_CAP)
            if final_conf <= 0.0:
                continue
            final_conf = min(1.0, final_conf)
            sink_step = self._make_step(
                node.lineno, "sink", chain, column=node.col_offset
            )
            var_name = arg.id if isinstance(arg, ast.Name) else ""
            self._record_flow(self._build_flow(
                state, spec, sink_step, final_conf, var_name
            ))
            break

    @staticmethod
    def _kwarg_factor(spec: SinkSpec, node: ast.Call) -> float:
        """Evaluate the sink's keyword-argument semantics."""
        if spec.kwarg_rule == "subprocess_shell":
            for kw in node.keywords:
                if kw.arg == "shell":
                    if isinstance(kw.value, ast.Constant):
                        return 1.0 if kw.value.value else 0.0
                    return 1.0  # dynamic shell= value: over-approximate
            return SUBPROCESS_NO_SHELL_FACTOR
        if spec.kwarg_rule == "yaml_safe_loader":
            for kw in node.keywords:
                if kw.arg == "Loader" and "Safe" in _attr_chain(kw.value):
                    return 0.0
            return 1.0
        return 1.0

    def _build_flow(
        self,
        state: TaintState,
        spec: SinkSpec,
        sink_step: TaintFlowStep,
        confidence: float,
        var_name: str,
    ) -> TaintFlow:
        from Asgard.Heimdall.Security.TaintAnalysis.services._taint_patterns import (
            SINK_CWE, SINK_OWASP, SINK_TITLES,
        )
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

    def _record_flow(self, flow: TaintFlow) -> None:
        self.found_flows.append(flow)


def replace_variable_name(step: TaintFlowStep, var_name: str) -> TaintFlowStep:
    """Return a copy of a step with the variable name filled in."""
    data = step.model_dump() if hasattr(step, "model_dump") else step.dict()
    data["variable_name"] = var_name
    return TaintFlowStep(**data)


# --------------------------------------------------------------------------
# Legacy helper facade (kept for backwards compatibility with older imports)
# --------------------------------------------------------------------------

def _is_sanitizer_call(node: ast.AST, custom_sanitizers: Set[str]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    match = classify_sanitizer(_attr_chain(node.func), tuple(custom_sanitizers))
    return match is not None and match.factor == 0.0


def _get_source_type_for_node(node: ast.AST, custom_sources: Set[str]):
    chain = _attr_chain(node)
    spec = lookup_source(chain, is_call=isinstance(node, ast.Call))
    if spec is not None:
        return spec.source_type
    if isinstance(node, ast.Call):
        func_name = _attr_chain(node.func)
        spec = lookup_source(func_name, is_call=True)
        if spec is not None:
            return spec.source_type
        for custom in custom_sources:
            if func_name == custom or func_name.endswith(f".{custom}"):
                return TaintSourceType.HTTP_PARAMETER
    return None


def _get_sink_type_for_call(func_chain: str, custom_sinks: Set[str]):
    spec = lookup_sink(func_chain)
    if spec is not None:
        return spec.sink_type, spec.severity
    for custom in custom_sinks:
        if func_chain == custom or func_chain.endswith(f".{custom}"):
            return TaintSinkType.SQL_QUERY, "high"
    return None
