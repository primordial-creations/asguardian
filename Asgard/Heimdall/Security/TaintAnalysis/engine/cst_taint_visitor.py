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

import re
from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Set, Tuple

from Asgard.Heimdall.Security.normalization.priority import confidence_bucket
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sanitizers import (
    SanitizerMatch,
    classify_sanitizer,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import (
    C_SINK_SPECS,
    GO_SINK_SPECS,
    JAVA_SINK_SPECS,
    JS_SINK_SPECS,
    SinkSpec,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import (
    C_SOURCE_SPECS,
    GO_SOURCE_SPECS,
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
# NOTE: TaintSinkType.FORMAT_STRING (C printf/fprintf/syslog) is deliberately
# NOT in _FIRST_ARG_SINKS. Instead of a fixed "first arg" position, the
# FORMAT argument's index varies by function (printf's format string is
# arg 0; fprintf's/syslog's is arg 1, after the stream/priority; snprintf's
# is arg 2, after buf/size) -- see _C_FORMAT_ARG_INDEX below, which
# _check_sink uses to scan ONLY the format-string argument itself, not
# every value argument. This means `printf(tainted)` / `printf(userfmt,
# ...)` still flags (the format literal itself is attacker-controlled --
# the real vulnerability class), but `printf("%s", tainted)` /
# `snprintf(buf, sizeof buf, "%s", tainted)` -- a constant format string
# with only a VALUE argument tainted -- correctly does not, since that
# is not a format-string vulnerability (adversarial review MAJOR-3).

# C printf-family functions: index of the FORMAT-STRING argument (0-based).
# Only this argument is taint-checked for TaintSinkType.FORMAT_STRING --
# a tainted value argument under a constant/safe format string is not a
# format-string vulnerability and must not flag.
#
# WS4 generalization: rather than a hand-maintained table of exactly the 4
# original names, the table now also covers the `v*printf` (va_list)
# variants (same argument shape/index as their non-`v` counterpart) and the
# additional libc printf-family members (`dprintf`, wide-char `wprintf`/
# `fwprintf`/`swprintf`) that share the same positional convention: the
# format string sits at the same index as the base family member once you
# account for a leading fd/stream/buffer argument. `_c_format_arg_index`
# below derives the `v`-prefixed variant's index from its base name so a
# future libc member only needs one entry, not two.
_C_FORMAT_ARG_INDEX = {
    "printf": 0,
    "wprintf": 0,
    "fprintf": 1,
    "fwprintf": 1,
    "dprintf": 1,
    "syslog": 1,
    "snprintf": 2,
    "swprintf": 2,
}


def _c_format_arg_index(func_name: str) -> Optional[int]:
    """Resolve the format-string argument index for a C printf-family
    call, including `v`-prefixed va_list variants (`vprintf`, `vfprintf`,
    `vdprintf`, `vsnprintf`, ...) which take the SAME argument shape as
    their non-`v` counterpart (the `va_list` replaces the trailing `...`,
    it does not shift the format-string position)."""
    if func_name in _C_FORMAT_ARG_INDEX:
        return _C_FORMAT_ARG_INDEX[func_name]
    if func_name.startswith("v"):
        base = func_name[1:]
        if base in _C_FORMAT_ARG_INDEX:
            return _C_FORMAT_ARG_INDEX[base]
    return None

# C "mutating source" functions: read untrusted input (stdin/fd/socket)
# INTO a caller-owned output-buffer argument rather than returning it, so
# the CST visitor's normal call-site/return-value source model misses them
# entirely unless handled specially here (adversarial review BLOCKER).
# Maps function name -> tuple of argument indices that receive the tainted
# data, or None for scanf-style variadic `&var` args starting at index 1.
_C_MUTATING_SOURCES = {
    "fgets": (0,),   # fgets(buf, size, stream)
    "gets": (0,),    # gets(buf) -- also inherently unsafe/deprecated
    "read": (1,),    # read(fd, buf, count)
    "recv": (1,),    # recv(fd, buf, len, flags)
    "scanf": None,   # scanf(fmt, &a, &b, ...) -- all args from index 1
}

# Matches a `$1`/`$2`/... positional placeholder in a Go SQL query literal
# (postgres-style; `?` placeholders are checked with a plain substring test).
_RE_DOLLAR_PLACEHOLDER = re.compile(r"\$\d")
_RE_DOLLAR_PLACEHOLDER_NUM = re.compile(r"\$(\d+)")


def _go_sql_placeholder_count(query_text: str) -> int:
    """Count bind-parameter placeholders in a Go SQL query literal (WS4
    precision hardening): postgres-style `$1..$N` count as the number of
    DISTINCT positions referenced (a query can legitimately reuse `$1`
    twice); MySQL/sqlite-style `?` counts as raw occurrences. A literal
    with zero real placeholders returns 0, so any trailing bind-looking
    argument on such a call is treated as suspicious (falls through to
    full scanning) rather than assumed safe."""
    dollar_nums = set(_RE_DOLLAR_PLACEHOLDER_NUM.findall(query_text))
    if dollar_nums:
        return len(dollar_nums)
    return query_text.count("?")

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
_FUNCTION_TYPES_GO = frozenset({
    "function_declaration", "method_declaration", "func_literal",
})
_FUNCTION_TYPES_C = frozenset({"function_definition"})
_ALL_FUNCTION_TYPES = (
    _FUNCTION_TYPES_JS | _FUNCTION_TYPES_JAVA | _FUNCTION_TYPES_GO | _FUNCTION_TYPES_C
)

# C declarator wrapper node types that must be unwrapped to reach the
# identifier they name (`*p` / `p[8]` / `(*fp)()`).
_C_DECLARATOR_WRAPPERS = frozenset({
    "pointer_declarator", "array_declarator", "parenthesized_declarator",
})


def _c_declarator_identifier(node):
    """Unwrap C pointer/array/parenthesized declarator wrappers down to the
    bare ``identifier`` they name, or ``None`` if the shape is unrecognized
    (e.g. a function-pointer declarator -- out of scope for this bounded
    first pass)."""
    while node is not None and node.type in _C_DECLARATOR_WRAPPERS:
        node = node.child_by_field_name("declarator")
    if node is not None and node.type == "identifier":
        return node
    return None

# Go statement/expression node types that wrap a list of comma-separated
# targets/values (`a, b := f()`, `x, y = y, x`, `var a, b = f()`) -- treated
# as a taint union across all members for RHS evaluation.
_GO_LIST_NODE_TYPES = frozenset({"expression_list"})

_DOM_SINK_PROPERTIES = frozenset({"innerHTML", "outerHTML"})

# ------------------------------------------------------- WS5 dynamic-construct
# Class-B gap: reflection / dynamic dispatch / eval / dynamic require-import
# are UNDECIDABLE for static taint -- we cannot prove what code or target
# they resolve to at runtime. Rather than silently staying quiet (a hidden
# blind spot), any of these constructs reached with a non-constant operand
# is surfaced as an explicit TaintSinkType.DYNAMIC_CONSTRUCT / finding_class
# "dynamic_construct" finding at confidence_bucket "needs_review" -- NEVER
# certain, since we cannot prove the flow either way. A statically-constant
# operand (`eval("1+1")`, `Class.forName("com.foo.Bar")`) is not flagged:
# there is nothing dynamic to review.
_JS_DYNAMIC_EVAL_NAMES = frozenset({"eval", "Function"})
_JS_DYNAMIC_IMPORT_NAMES = frozenset({"require", "import"})
_JAVA_DYNAMIC_INVOKE_METHODS = frozenset({"invoke"})
_GO_REFLECT_PREFIX = "reflect."

_CONST_LITERAL_TYPES = frozenset({
    "string", "string_literal", "interpreted_string_literal", "raw_string_literal",
    "number", "number_literal", "int_literal", "float_literal",
    "true", "false", "null", "undefined", "nil", "character_literal",
})


def _is_constant_node(node) -> bool:
    """True only when ``node`` is a compile-time constant (a literal, or a
    concatenation/parenthesization purely of literals) -- everything else
    (identifiers, member/index access, calls) is "dynamic" for WS5 purposes,
    even if the normal taint engine cannot resolve it to a known source."""
    if node is None:
        return True
    t = node.type
    if t in _CONST_LITERAL_TYPES:
        return True
    if t == "template_string":
        return not any(
            c.type == "template_substitution" for c in node.named_children
        )
    if t == "parenthesized_expression" and node.named_children:
        return _is_constant_node(node.named_children[0])
    if t == "binary_expression":
        return (
            _is_constant_node(node.child_by_field_name("left"))
            and _is_constant_node(node.child_by_field_name("right"))
        )
    return False


# ---------------------------------------------------------------- chain util

def _node_chain(node, ctx) -> str:
    """Flatten a member/field access or call target into a dotted chain."""
    if node is None:
        return ""
    t = node.type
    if t in (
        "identifier", "property_identifier", "private_property_identifier",
        "type_identifier", "shorthand_property_identifier",
        "field_identifier", "package_identifier",
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
    if t == "field_expression":
        # C `s.field` / `p->field` (tree-sitter-c's struct-member-access
        # node type; the object is field "argument", not "object"/"field"
        # like the JS/Java equivalents -- WS2 one-level struct-field taint).
        obj_chain = _node_chain(node.child_by_field_name("argument"), ctx)
        field_chain = _node_chain(node.child_by_field_name("field"), ctx)
        if obj_chain and field_chain:
            return f"{obj_chain}.{field_chain}"
        return field_chain or obj_chain
    if t == "selector_expression":
        # Go `pkg.Func` / `receiver.Method` / `a.b.c` chains.
        operand_chain = _node_chain(node.child_by_field_name("operand"), ctx)
        field_chain = _node_chain(node.child_by_field_name("field"), ctx)
        if operand_chain and field_chain:
            return f"{operand_chain}.{field_chain}"
        return field_chain or operand_chain
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
    if t == "new_expression":
        # JS `new Function(taint)` / `new Foo(...)` -- tree-sitter-js's
        # `new_expression` node uses field "constructor" (NOT "type" like
        # Java's `object_creation_expression`, NOT "function" like a plain
        # call) -- BLOCKER-3 (adversarial review): without this branch
        # `new Function(taint)` resolved to chain="" and was invisible to
        # both `_check_sink` and `_check_dynamic_construct`.
        return _node_chain(node.child_by_field_name("constructor"), ctx)
    if t == "import":
        # JS dynamic `import(userVar)` -- tree-sitter-js parses the bare
        # `import` keyword used as a call target (NOT `import ... from`
        # static import syntax) as its own leaf node of type "import"
        # (BLOCKER-4, adversarial review): without this branch the callee
        # chain was "" and never matched `_JS_DYNAMIC_IMPORT_NAMES`.
        return "import"
    if t == "parenthesized_expression" and node.named_children:
        return _node_chain(node.named_children[0], ctx)
    return ""


def _call_args(node) -> List:
    args_node = node.child_by_field_name("arguments")
    if args_node is None:
        return []
    return list(args_node.named_children)


def _is_c_constant_literal(node) -> bool:
    """True for a C literal (string/char/number/concatenated-string/NULL)
    RHS, possibly wrapped in parens -- used by MAJOR-1's strong-update fix
    (`p = "ls";`): a pointer directly reassigned to one of these in
    straight-line code is PROVABLY clean, unlike the general "RHS evaluates
    to no taint" case (a call, a variable, arithmetic) which stays under the
    sticky/over-approximate policy because it isn't provably constant."""
    if node is None:
        return False
    if node.type in (
        "string_literal", "char_literal", "number_literal",
        "concatenated_string", "null",
    ):
        return True
    if node.type == "parenthesized_expression" and node.named_children:
        return _is_c_constant_literal(node.named_children[0])
    return False


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
        # WS2 -- C pointer-aliasing-lite: `self.ptr_aliases[name]` is the
        # SET of all names known to reference the same storage (union-find
        # groups, C-only). `char *p = buf;` / `p = &x;` / `p = arr;` union
        # `p` with the RHS identifier. Lookups are dynamic against `self.env`
        # (not snapshotted at alias-creation time), so taint applied to
        # EITHER member after the alias is formed is visible through the
        # other -- covers both orderings (`p = buf; fgets(buf,...);
        # system(p);` and `fgets(buf,...); p = buf; system(p);`). This is
        # intentionally NOT a full points-to/memory model: intra-procedural
        # only, one flat union-find (no strong/weak updates, no scope exit,
        # no distinguishing `p = buf` from `p = buf + 1`), and does not
        # cross function boundaries -- see the module docstring/WS2 plan
        # note for the honest ceiling.
        self.ptr_aliases: Dict[str, Set[str]] = {}
        # Java-only: variable names of this function's PARAMETERS whose
        # declared type is (simple- or fully-qualified-)
        # HttpServletRequest/HttpServletRequestWrapper. `_lookup_source`
        # previously matched the literal identifier chain
        # "request.getParameter" -- i.e. only worked when the parameter
        # happened to be named `request`. That is a real source-detection
        # gap: `void h(HttpServletRequest r) { ...; r.getParameter(...); }`
        # (or a fully-qualified `javax.servlet.http.HttpServletRequest`
        # parameter type, or any other variable name) was silently NOT
        # recognized as a taint source at all -- a false negative on the
        # most common Java web-input pattern. This set is populated by
        # `_scan_functions` from the enclosing method's formal-parameter
        # list before the walk starts, and is consulted by
        # `_lookup_source` as a type-based fallback alongside the
        # literal "request.getParameter" pattern (kept for receivers that
        # are themselves the result of a call/field access rather than a
        # bare declared parameter).
        self.servlet_request_params: Set[str] = set()
        # Java-only, MINOR (adversarial review): variable name -> declared
        # type's simple name, for every parameter/local whose type is
        # syntactically known. Used to gate the literal `request
        # .getParameter` catalog pattern (catalog/sources.py) -- that
        # pattern matches on the bare name "request" regardless of type, so
        # `void h(String request) { ...; sink(request.getParameter(...)); }`
        # (not real servlet code -- `getParameter` here would be some
        # unrelated method, or wouldn't compile, but the point stands for
        # any non-servlet-typed `request`) was a false positive. Only
        # suppresses the fallback when the type is KNOWN and is NOT a
        # servlet type; an unknown/absent type keeps the literal pattern
        # active (never narrows a genuine `HttpServletRequest request`).
        self.declared_var_types: Dict[str, str] = {}
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
                if self.lang == "java" and "." in spec.pattern:
                    # MINOR (adversarial review): the catalog's literal
                    # `request.getParameter`/`request.getParameterValues`
                    # patterns match on the bare name "request" -- gate them
                    # off when THIS function's `request` is a KNOWN
                    # non-servlet type (e.g. `String request`), now that
                    # type-based servlet detection (below) makes the
                    # name-based fallback unnecessary for genuine servlet
                    # params. An unknown/absent declared type is left alone.
                    head = spec.pattern.split(".", 1)[0]
                    declared = self.declared_var_types.get(head)
                    if declared is not None and declared not in _SERVLET_REQUEST_TYPE_NAMES:
                        continue
                return spec
        # Java type-based fallback: any variable declared as a
        # HttpServletRequest parameter (regardless of its name) reaching
        # `.getParameter(...)` / `.getParameterValues(...)` is the same
        # HTTP_PARAMETER source as the hardcoded `request.getParameter`
        # pattern above -- see `self.servlet_request_params` docstring.
        if self.lang == "java" and is_call and "." in chain:
            receiver, method_name = chain.rsplit(".", 1)
            if receiver in self.servlet_request_params and method_name in (
                "getParameter",
                "getParameterValues",
            ):
                return SourceSpec(
                    f"{receiver}.{method_name}", TaintSourceType.HTTP_PARAMETER, 1.0, is_call=True
                )
        return None

    def _lookup_sink(self, chain: str) -> Optional[SinkSpec]:
        for spec in self.extra_sink_specs:
            if chain == spec.pattern:
                return spec
            if spec.match_suffix and chain.endswith("." + spec.pattern):
                return spec
        return None

    # --------------------------------------------- WS2 C pointer-alias-lite

    def _add_alias(self, a: str, b: str) -> None:
        """Union `a` and `b` into the same pointer-alias group (C only)."""
        if self.lang != "c" or not a or not b or a == b:
            return
        group = self.ptr_aliases.get(a, {a}) | self.ptr_aliases.get(b, {b})
        for member in group:
            self.ptr_aliases[member] = group

    def _alias_state(self, name: str) -> Optional[TaintState]:
        """Taint of any OTHER member of `name`'s pointer-alias group,
        looked up dynamically against the current env (never a snapshot)."""
        if self.lang != "c":
            return None
        group = self.ptr_aliases.get(name)
        if not group:
            return None
        state: Optional[TaintState] = None
        for member in group:
            if member != name and member in self.env:
                state = self._union(state, self.env[member])
        return state

    def _maybe_alias_declaration(self, name: str, value_node) -> None:
        """`T* p = buf;` / `T* p = arr;` / `T* p = &x;` -- C only. Only bare
        single-identifier (or address-of-identifier) RHS shapes are treated
        as an alias; anything else (a call, arithmetic, a cast of a
        non-identifier) is NOT aliased -- honoring the "simple pointer
        aliases only" scope from the WS2 plan note (no offset/arithmetic
        pointer tracking)."""
        if self.lang != "c" or value_node is None:
            return
        target = value_node
        if target.type in ("unary_expression", "pointer_expression"):
            # tree-sitter-c parses `&x` as `pointer_expression` (not
            # `unary_expression`, which is tree-sitter-go's node type for
            # `&x`/`-x`/`!x`) -- both are unwrapped here for the C alias
            # path.
            inner = target.child_by_field_name("argument")
            if inner is None and target.named_children:
                inner = target.named_children[-1]
            target = inner
        if target is not None and target.type == "identifier":
            self._add_alias(name, self.ctx.node_text(target))

    # ------------------------------------------------------- expression eval

    def _chain(self, node) -> str:
        """Flattened, alias-resolved dotted chain for a node."""
        return resolve_chain(_node_chain(node, self.ctx), self.alias_map)

    # --------------------------------------------------- SA1 field/container

    _CHAIN_MEMBER_TYPES = (
        "member_expression", "field_access", "selector_expression", "field_expression",
    )
    _CHAIN_SUBSCRIPT_TYPES = ("subscript_expression", "array_access", "index_expression")

    def _chain_path(self, node) -> Tuple[Optional[str], Optional[List[str]]]:
        """Walk a member/subscript access chain down to its root identifier.

        Returns ``(root_name, prefixes)`` where ``prefixes`` lists exact
        dotted/bracket env-keys, most-specific first. ``prefixes is None``
        means a non-constant subscript sits SOMEWHERE along the chain --
        callers must fall back to the root's whole-value taint (sound
        over-approximation). ``root_name is None`` means the chain isn't
        rooted in a bare identifier (e.g. `f().a`) -- callers fall back to
        plain sub-expression evaluation."""
        if node is None:
            return None, None
        t = node.type
        if t == "identifier":
            return self.ctx.node_text(node), []
        if t in self._CHAIN_MEMBER_TYPES:
            base = (
                node.child_by_field_name("object")
                or node.child_by_field_name("operand")
                or node.child_by_field_name("argument")
            )
            field = (
                node.child_by_field_name("property")
                or node.child_by_field_name("field")
                or node.child_by_field_name("name")
            )
            if base is None or field is None:
                return None, None
            root, prefixes = self._chain_path(base)
            if root is None:
                return None, None
            if prefixes is None:
                return root, None
            parent = prefixes[0] if prefixes else root
            return root, [f"{parent}.{self.ctx.node_text(field)}"] + prefixes
        if t in self._CHAIN_SUBSCRIPT_TYPES:
            base = (
                node.child_by_field_name("object")
                or node.child_by_field_name("array")
                or node.child_by_field_name("operand")
                or node.child_by_field_name("argument")
            )
            if base is None:
                return None, None
            root, prefixes = self._chain_path(base)
            if root is None:
                return None, None
            if prefixes is None:
                return root, None
            index = node.child_by_field_name("index")
            if index is None or index.type not in _CONST_LITERAL_TYPES:
                return root, None  # non-constant index: truncate, sound
            parent = prefixes[0] if prefixes else root
            return root, [f"{parent}[{self.ctx.node_text(index)}]"] + prefixes
        return None, None

    def _family_taint(self, base: str) -> Optional[TaintState]:
        """Union of every field/element taint recorded under ``base`` --
        used ONLY for a bare-identifier read (the whole object, including
        any tainted sub-field, flows out). A specific-field read must stay
        scoped to that field plus the root marker (see ``_read_chain``) to
        avoid a sibling field's taint leaking into an unrelated field."""
        result: Optional[TaintState] = None
        prefixes = (f"{base}.", f"{base}[")
        for key, value in self.env.items():
            if key.startswith(prefixes):
                result = self._union(result, value)
        return result

    def _read_chain(self, node) -> Optional[TaintState]:
        """Field/element-sensitive read for a member/subscript node."""
        root, prefixes = self._chain_path(node)
        if root is None:
            fallback = (
                node.child_by_field_name("object")
                or node.child_by_field_name("array")
                or node.child_by_field_name("operand")
                or node.child_by_field_name("argument")
            )
            return self._eval(fallback)
        if prefixes:
            for path in prefixes:
                if path in self.env:
                    return self.env[path]
        return self.env.get(root)

    def _eval(self, node) -> Optional[TaintState]:
        if node is None:
            return None
        t = node.type
        if t == "identifier":
            name = self.ctx.node_text(node)
            if name in self.env:
                return self.env[name]
            alias_state = self._alias_state(name)
            if alias_state is not None:
                return alias_state
            family = self._family_taint(name)
            if family is not None:
                return family
            resolved = resolve_chain(name, self.alias_map)
            return self._match_source_chain(resolved, node, is_call=False)
        if t in self._CHAIN_MEMBER_TYPES:
            chain = self._chain(node)
            state = self._match_source_chain(chain, node, is_call=False)
            if state is not None:
                return state
            return self._read_chain(node)
        if t in self._CHAIN_SUBSCRIPT_TYPES:
            # Index/member access on a tainted container returns the
            # container's taint (container-granularity over-approximation)
            # UNLESS the index is a constant, in which case field/element
            # -sensitive tracking narrows this to the specific key -- covers
            # JS `arr[0]`/`obj['k']`, Java array-index access, and Go
            # `slice[i]`/`m[k]`.
            base = (
                node.child_by_field_name("object")
                or node.child_by_field_name("array")
                or node.child_by_field_name("operand")
            )
            src = self._match_source_chain(self._chain(base), base, is_call=False) if base is not None else None
            if src is not None:
                return src
            return self._read_chain(node)
        if t == "expression_list":
            # Go comma-separated expression list (`a, b := f()` RHS, `return
            # x, err`) -- union across all members (over-approximation: any
            # tainted member makes the whole list-position "could be
            # tainted" when consumed positionally elsewhere).
            state: Optional[TaintState] = None
            for child in node.named_children:
                state = self._union(state, self._eval(child))
            return state
        if t in ("unary_expression",) and self.lang == "go":
            # Go `&x` (address-of) / `-x` / `!x` -- propagate operand taint;
            # Go unary_expression has no named field, operand is the sole
            # named child.
            if node.named_children:
                return self._eval(node.named_children[0])
            return None
        if t in ("call_expression", "method_invocation", "object_creation_expression", "new_expression"):
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
        if t in ("as_expression", "satisfies_expression"):
            # TypeScript `expr as Type` / `expr satisfies Type` -- the cast
            # is a compile-time-only annotation, not a runtime
            # transformation, so it must NOT launder taint (A3 gap: `req
            # .query.host as string` must stay tainted). The tainted
            # expression is always the first named child; the type
            # annotation is the second and is never evaluated.
            if node.named_children:
                return self._eval(node.named_children[0])
            return None
        if t == "non_null_expression" and node.named_children:
            # TypeScript `expr!` (non-null assertion) -- same rationale as
            # as_expression: purely a compile-time annotation.
            return self._eval(node.named_children[0])
        if t == "type_assertion" and node.named_children:
            # Legacy TypeScript `<Type>expr` cast. tree-sitter-typescript's
            # `type_assertion` node has no named fields -- the type node is
            # the first named child, the tainted expression is the LAST
            # named child. Same rationale as as_expression: a compile-time
            # annotation only, must not launder taint.
            return self._eval(node.named_children[-1])
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
        return is_verified_sanitizer_origin(
            origin.raw_specifier, origin.is_relative, self.lang,
            is_wildcard=getattr(origin, "is_wildcard", False),
        )

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

        if self.lang == "c" and method_name in _C_MUTATING_SOURCES:
            # fgets/gets/read/recv/scanf write untrusted input INTO a
            # caller-owned buffer argument rather than returning it -- taint
            # that argument's identifier directly in self.env so a later
            # `system(buf)` sees it as tainted (adversarial review BLOCKER:
            # this class was previously silently muted entirely).
            buf_indices = _C_MUTATING_SOURCES[method_name]
            if buf_indices is None:
                buf_indices = tuple(range(1, len(args)))
            src_step = self._make_step(node.start_point[0] + 1, "source", method_name)
            fresh = TaintState(
                source_step=src_step, source_type=TaintSourceType.USER_INPUT, confidence=0.9,
            )
            for idx in buf_indices:
                if idx >= len(args):
                    continue
                target = args[idx]
                if target.type in ("unary_expression", "pointer_expression"):
                    # scanf's `&var` -- unwrap the address-of to the named
                    # variable being written into. tree-sitter-c parses
                    # `&var` as `pointer_expression` (WS2 fix: this unwrap
                    # previously only matched `unary_expression`, which C's
                    # grammar never produces for `&x`, so scanf's `&var`
                    # targets were silently never tainted).
                    inner = target.child_by_field_name("argument")
                    if inner is None and target.named_children:
                        inner = target.named_children[-1]
                    target = inner
                if target is not None and target.type in _C_DECLARATOR_WRAPPERS:
                    target = _c_declarator_identifier(target)
                if target is not None and target.type == "identifier":
                    base_name = self.ctx.node_text(target)
                    self.env[base_name] = self._union(self.env.get(base_name), fresh)
            # The call itself has no useful return-value taint for these
            # functions (fgets returns the buffer pointer or NULL, gets/
            # scanf return int) -- fall through to the generic call handling
            # below rather than returning early, so e.g. NULL-check idioms
            # around the call are still walked normally.

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
            if (
                self.lang == "c"
                and left is not None
                and left.type == "identifier"
                and _is_c_constant_literal(right)
            ):
                # MAJOR-1 (adversarial review): `char *p = buf; fgets(buf,
                # ...); p = "ls"; system(p);` was flagging CERTAIN CWE-78
                # even though `p` is PROVABLY reassigned to a constant right
                # before the sink. Unlike the general sticky/never-mute
                # policy in `_assign` (a direct reassignment to a
                # non-constant clean value, e.g. another variable or a call
                # result, stays over-approximate because it ISN'T provably
                # clean), a literal RHS on a plain identifier target is a
                # STRONG update: clear `p`'s own taint AND drop it from its
                # pointer-alias group so it stops transitively inheriting
                # another member's (e.g. `buf`'s) taint. Conditional/aliased
                # cases are untouched -- this only fires for this exact
                # straight-line identifier-assigned-a-literal shape.
                name = self.ctx.node_text(left)
                self.env.pop(name, None)
                group = self.ptr_aliases.pop(name, None)
                if group:
                    remaining = group - {name}
                    for member in remaining:
                        self.ptr_aliases[member] = remaining
            else:
                self._assign(left, state, node)
            if self.lang == "c" and left is not None and left.type == "identifier":
                # `p = buf;` / `p = &x;` (C reassignment, not a fresh
                # declaration) -- also forms a pointer-alias union so a
                # LATER taint of either side is visible through the other.
                # (No-op when the strong-update branch above just fired:
                # `_maybe_alias_declaration` only aliases a bare-identifier/
                # address-of RHS, never a literal.)
                self._maybe_alias_declaration(self.ctx.node_text(left), right)
            if right is not None:
                self._walk(right)
            return

        if t in ("short_var_declaration", "assignment_statement"):
            # Go `a, b := f()` / `x = y`. `left`/`right` are each an
            # `expression_list`; positional pairing when both sides have the
            # same arity, else every target gets the union of all RHS values
            # (over-approximation, never under-taints a multi-assign target).
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            right_state = self._eval(right) if right is not None else None
            if left is not None:
                targets = (
                    left.named_children if left.type == "expression_list" else [left]
                )
                for target in targets:
                    self._assign(target, right_state, node)
            if right is not None:
                self._walk(right)
            return

        if t == "var_declaration":
            # Go `var a, b string = x, y` / `var a = f()` -- one or more
            # `var_spec` children, each with its own name(s)/value.
            for spec in node.named_children:
                if spec.type != "var_spec":
                    continue
                value = spec.child_by_field_name("value")
                value_state = self._eval(value) if value is not None else None
                for name_node in spec.children_by_field_name("name"):
                    self._assign(name_node, value_state, spec)
                if value is not None:
                    self._walk(value)
            return

        if t == "declaration":
            # C `int x = f();` / `char *cmd = getenv(...);` / multi-declarator
            # `int a = 1, b = 2;` -- each comma-separated entry is a repeated
            # `declarator` field, either a bare declarator (`char buf[64];`,
            # nothing to propagate) or an `init_declarator` wrapping
            # `declarator`/`value`. Declarator may be pointer/array-wrapped
            # (`char *cmd = ...`) -- unwrap via `_c_declarator_identifier`.
            for declarator in node.children_by_field_name("declarator"):
                if declarator.type == "init_declarator":
                    value = declarator.child_by_field_name("value")
                    value_state = self._eval(value) if value is not None else None
                    name_node = _c_declarator_identifier(
                        declarator.child_by_field_name("declarator")
                    )
                    self._assign(name_node, value_state, declarator)
                    if name_node is not None:
                        # `char *p = buf;` / `char *p = arr;` / `char *p =
                        # &x;` -- pointer-alias union (WS2), independent of
                        # whether `buf` is ALREADY tainted at this point:
                        # `_alias_state` looks up the group dynamically, so
                        # a later `fgets(buf, ...)` still propagates to `p`.
                        self._maybe_alias_declaration(
                            self.ctx.node_text(name_node), value
                        )
                    if value is not None:
                        self._walk(value)
            return

        if t in ("call_expression", "method_invocation", "object_creation_expression", "new_expression"):
            # MAJOR-2 (adversarial review): a call site that ALREADY
            # produced a concrete taint-flow sink finding (e.g.
            # `eval(taint)` matching the `eval_exec` CWE-95 sink) must NOT
            # also emit a redundant WS5 dynamic_construct finding for the
            # SAME node -- DYNAMIC_CONSTRUCT is for constructs not
            # otherwise caught by a concrete sink. `getattr`/`new
            # Function`/dynamic `import`/reflection calls that have no
            # registered sink still get their needs-review finding.
            flows_before = len(self.found_flows)
            self._check_sink(node)
            sink_hit = len(self.found_flows) > flows_before
            if not sink_hit:
                self._check_dynamic_construct(node)
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
        _LVALUE_CHAIN_TYPES = (
            "member_expression", "field_access", "subscript_expression",
            "array_access", "selector_expression", "index_expression",
            "field_expression",
        )
        if t in _LVALUE_CHAIN_TYPES:
            # SA1 field/container sensitivity: a constant-key chain
            # (`x.a = ...` / `x["a"] = ...`) is a STRONG update at that
            # exact key -- it does not touch sibling fields. A non-constant
            # index anywhere in the chain (`x[i] = ...`) is undecidable --
            # sound over-approximation taints the WHOLE base object (never
            # narrows to "safe"), same as the prior one-level-only
            # behavior, now generalized across chain depth and languages.
            # No CLEAR-on-clean here: the engine's sticky/never-mute policy
            # (see the identifier branch below) applies at field
            # granularity too -- a clean element/field store never removes
            # taint, it just skips adding new taint at that key.
            root, prefixes = self._chain_path(target_node)
            if root is None:
                return
            if prefixes and state is not None:
                path = prefixes[0]
                stored = replace(state, trace=list(state.trace), sanitizers=list(state.sanitizers))
                stored.trace.append(self._make_step(stmt_node.start_point[0] + 1, "propagation", path))
                self.env[path] = self._union(self.env.get(path), stored)
                return
            if prefixes:
                return  # constant-key clean store: sticky, no-op
            # Non-constant index somewhere in the chain: container
            # laundering taints the base container.
            if state is not None:
                stored = replace(state, trace=list(state.trace), sanitizers=list(state.sanitizers))
                stored.trace.append(self._make_step(stmt_node.start_point[0] + 1, "propagation", root))
                self.env[root] = self._union(self.env.get(root), stored)
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
        # Go call shapes commonly put the tainted value AFTER a fixed first
        # argument (`exec.Command("sh", "-c", tainted)`, `db.Query(query,
        # tainted...)` binds param placeholders, not string-concat) -- the
        # JS/Java/Python "the dangerous value is always arg[0]" heuristic
        # would silently mute real Go flows, so Go always scans every
        # argument (over-approximation, never under-detection) EXCEPT for
        # the one case below where that over-approximation is a near-100%
        # FP on idiomatic, safe code: a genuinely parameterized Go SQL call.
        go_sql_parameterized = False
        if self.lang == "go" and spec.sink_type == TaintSinkType.SQL_QUERY and args:
            first = args[0]
            if first.type in ("interpreted_string_literal", "raw_string_literal"):
                query_text = self.ctx.node_text(first)
                placeholder_count = _go_sql_placeholder_count(query_text)
                trailing_count = len(args) - 1
                # WS4 precision: count placeholders vs trailing args rather
                # than a bare substring test. A literal containing a STRAY
                # `?` (decorative text, e.g. inside a quoted sub-string)
                # with MORE trailing args than real placeholders is NOT
                # genuinely parameterized -- something doesn't line up
                # (possibly string-built taint smuggled in via an extra
                # bind-looking argument) -- so it falls through to scanning
                # ALL args below (over-approximate, still flags). Only when
                # the placeholder count covers every trailing arg is the
                # call treated as safely parameterized.
                if placeholder_count > 0 and placeholder_count >= trailing_count:
                    go_sql_parameterized = True
        first_arg_only = (
            spec.sink_type in _FIRST_ARG_SINKS and not custom_hit and args
            and self.lang != "go"
        ) or go_sql_parameterized

        candidate_args = args[:1] if first_arg_only else args

        if self.lang == "c" and spec.sink_type == TaintSinkType.FORMAT_STRING:
            # Only the FORMAT-STRING argument itself is a format-string
            # vulnerability; a tainted VALUE argument under a constant
            # format literal (`printf("%s", tainted)`,
            # `snprintf(buf, sizeof buf, "%s", tainted)`) is not one and
            # must not flag (adversarial review MAJOR-3). `printf(tainted)`
            # / `printf(userfmt, ...)` -- the format literal itself
            # attacker-controlled -- still flags.
            fmt_index = _c_format_arg_index(chain)
            candidate_args = (
                [args[fmt_index]] if fmt_index is not None and fmt_index < len(args) else []
            )
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

    # -------------------------------------------------- WS5 dynamic-construct

    def _check_dynamic_construct(self, node) -> None:
        """Detect eval/reflection/dynamic-dispatch constructs that are
        undecidable for static taint (see the module-level WS5 note) and
        surface them as an explicit needs-review finding when the
        risk-relevant operand is non-constant. This runs INDEPENDENTLY of
        `_check_sink`'s normal source/sink resolution -- it must still fire
        even when the operand cannot be matched to a known taint source, so
        an unresolved dynamic construct is never silently dropped."""
        raw_chain = _node_chain(node, self.ctx)
        chain = resolve_chain(raw_chain, self.alias_map)
        args = _call_args(node)
        method_name = chain.rsplit(".", 1)[-1] if "." in chain else chain

        label = ""
        severity = "high"
        check_arg = None
        always_flag = False

        if self.lang in _JS_LANGS:
            if chain in _JS_DYNAMIC_EVAL_NAMES and args:
                label, severity, check_arg = chain, "critical", args[0]
            elif chain in _JS_DYNAMIC_IMPORT_NAMES and args:
                label, severity, check_arg = f"dynamic {chain}", "high", args[0]
        elif self.lang == "java":
            if method_name in _JAVA_DYNAMIC_INVOKE_METHODS and "invoke" in chain:
                label, severity, always_flag = "Method.invoke", "high", True
            elif method_name == "forName" and args:
                label, severity, check_arg = "Class.forName", "high", args[0]
        elif self.lang == "go":
            if chain.startswith(_GO_REFLECT_PREFIX):
                label, severity = chain, "medium"
                check_arg = args[0] if args else None
                always_flag = check_arg is None

        if not label:
            # `obj[userKey](...)` / computed member call used AS the callee
            # -- the function being invoked is itself dynamic, independent
            # of any named-sink match above.
            fn_node = node.child_by_field_name("function")
            if fn_node is not None and fn_node.type in (
                "subscript_expression", "index_expression",
            ):
                key_node = (
                    fn_node.child_by_field_name("index")
                    or fn_node.child_by_field_name("property")
                )
                if key_node is None and fn_node.named_children:
                    key_node = fn_node.named_children[-1]
                if key_node is not None and not _is_constant_node(key_node):
                    label, severity, check_arg = "dynamic_dispatch", "high", key_node
            if not label:
                return

        if not always_flag and check_arg is not None and _is_constant_node(check_arg):
            return
        self._emit_dynamic_construct(node, label, severity, check_arg)

    def _emit_dynamic_construct(self, node, label: str, severity: str, arg_node) -> None:
        pos_node = arg_node if arg_node is not None else node
        line = pos_node.start_point[0] + 1
        col = pos_node.start_point[1]
        sink_step = self._make_step(line, "sink", label, column=col)
        confidence = 0.3
        tainted = False
        if arg_node is not None:
            state = self._eval(arg_node)
            if state is not None:
                tainted = True
                confidence = max(confidence, min(0.45, 0.25 + state.confidence * 0.2))
        source_step = self._make_step(
            arg_node.start_point[0] + 1 if arg_node is not None else line,
            "source", label,
        )
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
        self.found_flows.append(flow)

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
        if name_node is None and fn.type == "function_definition":
            # C has no `name` field on `function_definition` -- the name
            # lives inside the `declarator` field: `function_declarator`
            # (itself possibly wrapped in `pointer_declarator` for a
            # pointer-returning function) -> its own `declarator` field ->
            # (possibly pointer-wrapped) `identifier`.
            fdecl = fn.child_by_field_name("declarator")
            while fdecl is not None and fdecl.type in _C_DECLARATOR_WRAPPERS:
                fdecl = fdecl.child_by_field_name("declarator")
            if fdecl is not None and fdecl.type == "function_declarator":
                name_node = _c_declarator_identifier(fdecl.child_by_field_name("declarator"))
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
        if lang == "java":
            _populate_servlet_request_params(fn, ctx, visitor)
        visitor._walk(body)
        flows.extend(visitor.found_flows)
    return flows


_SERVLET_REQUEST_TYPE_NAMES = ("HttpServletRequest", "HttpServletRequestWrapper")


def _populate_servlet_request_params(fn, ctx, visitor: "CstFunctionTaintVisitor") -> None:
    """Scan `fn`'s formal-parameter list for parameters declared as
    HttpServletRequest/HttpServletRequestWrapper (simple name, or
    fully-qualified e.g. `javax.servlet.http.HttpServletRequest`) and
    record their variable names in `visitor.servlet_request_params` --
    see that field's docstring for why this type-based recognition is
    needed alongside the literal `request.getParameter` pattern."""
    params_node = fn.child_by_field_name("parameters")
    if params_node is not None:
        for param in params_node.named_children:
            if param.type != "formal_parameter":
                continue
            type_node = param.child_by_field_name("type")
            name_node = param.child_by_field_name("name")
            if type_node is None or name_node is None:
                continue
            type_text = ctx.node_text(type_node)
            simple_type = type_text.rsplit(".", 1)[-1]
            var_name = ctx.node_text(name_node)
            visitor.declared_var_types[var_name] = simple_type
            if simple_type in _SERVLET_REQUEST_TYPE_NAMES:
                visitor.servlet_request_params.add(var_name)
    # MINOR (adversarial review): also record local-variable declared types
    # (`String request = ...;`) so the same non-servlet-type gate in
    # `_lookup_source` applies to a shadowing local, not just parameters.
    body = fn.child_by_field_name("body")
    if body is not None:
        stack = [body]
        while stack:
            n = stack.pop()
            if n.type == "local_variable_declaration":
                type_node = n.child_by_field_name("type")
                if type_node is not None:
                    type_text = ctx.node_text(type_node)
                    simple_type = type_text.rsplit(".", 1)[-1]
                    for declarator in n.named_children:
                        if declarator.type != "variable_declarator":
                            continue
                        name_node = declarator.child_by_field_name("name")
                        if name_node is None:
                            continue
                        var_name = ctx.node_text(name_node)
                        visitor.declared_var_types.setdefault(var_name, simple_type)
                        if simple_type in _SERVLET_REQUEST_TYPE_NAMES:
                            visitor.servlet_request_params.add(var_name)
            stack.extend(n.named_children)


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


def scan_go_source(
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
    """Scan a parsed Go ``FileParseContext`` for taint flows.

    Go has no import-alias ambiguity for taint purposes the way JS/Java do
    (package selectors are unambiguous, no destructured renames of the
    catalog's `pkg.Func` shape are idiomatic) -- ``alias_map``/
    ``alias_origins`` are accepted for interface symmetry with the JS/Java
    entry points (and to keep ``DispatchEngine`` generic) but are typically
    empty for Go call sites; the catalog matches package-qualified chains
    directly (``os.Getenv``, ``exec.Command``, ...).
    """
    return _scan_functions(
        file_path, ctx, "go",
        GO_SOURCE_SPECS, GO_SINK_SPECS,
        custom_sources, custom_sinks, custom_sanitizers, is_test_context,
        alias_map=alias_map, call_resolver=call_resolver, alias_origins=alias_origins,
    )


def scan_c_source(
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
    """Scan a parsed C ``FileParseContext`` for taint flows.

    Bounded first pass, intra-procedural only: no pointer-aliasing or
    memory-layout modeling (a buffer threaded through several pointer hops
    before reaching a sink is not tracked), and "mutating sources"
    (``fgets``/``scanf``/``read``/``recv``/``gets`` tainting an OUTPUT
    ARGUMENT rather than a return value) are not modeled -- see the honest
    gap note above ``C_SOURCE_SPECS`` in ``catalog/sources.py``. C has no
    import/alias ambiguity (``#include`` does not rename symbols), so
    ``alias_map``/``alias_origins`` are accepted only for interface symmetry
    with the other language entry points and are typically empty.
    """
    return _scan_functions(
        file_path, ctx, "c",
        C_SOURCE_SPECS, C_SINK_SPECS,
        custom_sources, custom_sinks, custom_sanitizers, is_test_context,
        alias_map=alias_map, call_resolver=call_resolver, alias_origins=alias_origins,
    )
