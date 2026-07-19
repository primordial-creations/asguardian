"""
Flow-insensitive, over-approximated function summaries for the JS/TS/Java
CST taint engine (plan 04 gap: "inter-procedural summaries for JS/TS/Java").

Mirrors ``Security/TaintAnalysis/summaries.py`` (the Python ``ast`` design)
almost verbatim -- ``FunctionSummary``, ``SinkRef``, ``SummaryCache`` and the
bounded ``SummaryIndex`` (k<=4 hops, x0.85 decay/hop) are language-agnostic
by construction (they operate on dotted chains and dataclasses, never on
``ast`` nodes), so they are imported and reused as-is rather than
reimplemented. Only two things are language-specific and live here:

1. ``compute_cst_file_summaries`` -- walks the tree-sitter CST (via
   ``CstFunctionTaintVisitor`` in param-seeded "summary mode") instead of
   ``ast``.
2. Parameter-name extraction for JS/TS (``formal_parameters`` /
   single-identifier arrow params) and Java (``formal_parameter`` nodes).

Cross-file resolution scope (honest limitation): a ``SummaryIndex`` is built
per scan by ``Security/engine/dispatch.py`` over the sibling files that
share this file's extension group in the same directory (bounded, capped),
not a whole-project import graph -- this covers same-directory modules
(the overwhelming majority of small util/helper splits, and all of this
plan's benchmark fixtures) without the cost/complexity of a full resolver.
Calls into files outside that directory over-approximate via the x0.5
unknown-call decay, same as an unresolved call.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import (
    C_SINK_SPECS,
    GO_SINK_SPECS,
    JAVA_SINK_SPECS,
    JS_SINK_SPECS,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import (
    C_SOURCE_SPECS,
    GO_SOURCE_SPECS,
    JAVA_SOURCE_SPECS,
    JS_SOURCE_SPECS,
)
from Asgard.Heimdall.Security.TaintAnalysis.engine.cst_taint_visitor import (
    _C_DECLARATOR_WRAPPERS,
    CstFunctionTaintVisitor,
    _c_declarator_identifier,
    _find_functions,
)
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import TaintFlowStep, TaintSourceType
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_visitor import TaintState
from Asgard.Heimdall.Security.TaintAnalysis.summaries import FunctionSummary, SinkRef, SummaryIndex

# Re-exported for callers (dispatch.py) so they don't need to import from
# two modules for one concept.
__all__ = [
    "compute_cst_file_summaries",
    "collect_cst_imported_module_stems",
    "SummaryIndex",
    "FunctionSummary",
]

_JS_LANGS = frozenset({"javascript", "typescript", "tsx"})

_JS_PARAM_WRAPPERS = frozenset({"required_parameter", "optional_parameter"})


def _js_destructure_names(pattern, ctx) -> List[str]:
    """Extract bound identifier names from a JS/TS destructuring pattern:
    ``{a, b}`` / ``{a: renamed}`` / ``[x, y]`` (nested/rest patterns are
    walked recursively; over-approximate by collecting every leaf
    identifier rather than trying to model partial binding)."""
    names: List[str] = []
    if pattern is None:
        return names
    t = pattern.type
    if t == "identifier":
        names.append(ctx.node_text(pattern))
        return names
    if t == "object_pattern":
        for child in pattern.named_children:
            if child.type == "shorthand_property_identifier_pattern":
                names.append(ctx.node_text(child))
            elif child.type == "pair_pattern":
                value = child.child_by_field_name("value")
                names.extend(_js_destructure_names(value, ctx))
            elif child.type == "rest_pattern":
                inner = child.named_children[0] if child.named_children else None
                names.extend(_js_destructure_names(inner, ctx))
            elif child.type in ("object_pattern", "array_pattern"):
                names.extend(_js_destructure_names(child, ctx))
        return names
    if t == "array_pattern":
        for child in pattern.named_children:
            if child.type == "assignment_pattern":
                left = child.child_by_field_name("left")
                names.extend(_js_destructure_names(left, ctx))
            elif child.type == "rest_pattern":
                inner = child.named_children[0] if child.named_children else None
                names.extend(_js_destructure_names(inner, ctx))
            else:
                names.extend(_js_destructure_names(child, ctx))
        return names
    return names


def _js_param_names(fn, ctx) -> List[List[str]]:
    """Returns one group of bound names per parameter POSITION -- normally
    a singleton (``[["req"], ["res"]]``), but destructured params
    (``{a, b}`` / ``[x, y]``) contribute multiple names at the SAME
    position so a tainted positional argument taints all of them."""
    groups: List[List[str]] = []
    params_node = fn.child_by_field_name("parameters")
    if params_node is None:
        # Arrow function with a single unparenthesized identifier param,
        # e.g. `x => x.trim()`.
        single = fn.child_by_field_name("parameter")
        if single is not None and single.type == "identifier":
            return [[ctx.node_text(single)]]
        return groups
    for child in params_node.named_children:
        if child.type == "identifier":
            groups.append([ctx.node_text(child)])
        elif child.type in _JS_PARAM_WRAPPERS:
            pattern = child.child_by_field_name("pattern") or child.child_by_field_name("name")
            if pattern is not None:
                names = _js_destructure_names(pattern, ctx)
                if names:
                    groups.append(names)
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            names = _js_destructure_names(left, ctx)
            if names:
                groups.append(names)
        elif child.type in ("object_pattern", "array_pattern"):
            names = _js_destructure_names(child, ctx)
            if names:
                groups.append(names)
    return groups


def _java_param_names(fn, ctx) -> List[List[str]]:
    groups: List[List[str]] = []
    params_node = fn.child_by_field_name("parameters")
    if params_node is None:
        return groups
    for child in params_node.named_children:
        if child.type in ("formal_parameter", "spread_parameter", "receiver_parameter"):
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                groups.append([ctx.node_text(name_node)])
    return groups


def _go_param_names(fn, ctx) -> List[List[str]]:
    """Go ``parameter_list``: each ``parameter_declaration`` may carry
    MULTIPLE ``name`` fields (``func f(a, b string)``) sharing one type --
    each still gets its own POSITION for summary purposes."""
    groups: List[List[str]] = []
    params_node = fn.child_by_field_name("parameters")
    if params_node is None:
        return groups
    for child in params_node.named_children:
        if child.type == "parameter_declaration":
            for name_node in child.children_by_field_name("name"):
                groups.append([ctx.node_text(name_node)])
    return groups


def _c_param_names(fn, ctx) -> List[List[str]]:
    """C ``parameter_list``: each ``parameter_declaration`` names one
    parameter via its (possibly pointer/array-wrapped) ``declarator`` field.
    Bare types with no name (``void f(int)`` prototypes) contribute nothing."""
    groups: List[List[str]] = []
    params_node = fn.child_by_field_name("parameters")
    if params_node is None:
        return groups
    for child in params_node.named_children:
        if child.type != "parameter_declaration":
            continue
        declarator = child.child_by_field_name("declarator")
        name_node = _c_declarator_identifier(declarator)
        if name_node is not None:
            groups.append([ctx.node_text(name_node)])
    return groups


def _c_function_name(fn, ctx) -> Optional[str]:
    """C ``function_definition`` has no ``name`` field -- unwrap
    ``declarator`` -> (possibly pointer-wrapped) ``function_declarator`` ->
    its own ``declarator`` field -> (possibly pointer-wrapped) identifier."""
    fdecl = fn.child_by_field_name("declarator")
    while fdecl is not None and fdecl.type in _C_DECLARATOR_WRAPPERS:
        fdecl = fdecl.child_by_field_name("declarator")
    if fdecl is None or fdecl.type != "function_declarator":
        return None
    name_node = _c_declarator_identifier(fdecl.child_by_field_name("declarator"))
    return ctx.node_text(name_node) if name_node is not None else None


def _param_names(fn, ctx, lang: str) -> List[List[str]]:
    if lang in _JS_LANGS:
        return _js_param_names(fn, ctx)
    if lang == "go":
        return _go_param_names(fn, ctx)
    if lang == "c":
        return _c_param_names(fn, ctx)
    return _java_param_names(fn, ctx)


def compute_cst_file_summaries(
    file_path: str,
    ctx,
    lang: str,
    alias_map: Dict[str, str],
    custom_sanitizers: Optional[Set[str]] = None,
) -> Dict[str, FunctionSummary]:
    """Compute base (intra-file) summaries for every function in one parsed
    JS/TS/Java file. Mirrors ``summaries.compute_file_summaries``."""
    if ctx is None or ctx.root is None:
        return {}
    if lang == "java":
        source_specs, sink_specs = JAVA_SOURCE_SPECS, JAVA_SINK_SPECS
    elif lang == "go":
        source_specs, sink_specs = GO_SOURCE_SPECS, GO_SINK_SPECS
    elif lang == "c":
        source_specs, sink_specs = C_SOURCE_SPECS, C_SINK_SPECS
    else:
        source_specs, sink_specs = JS_SOURCE_SPECS, JS_SINK_SPECS

    functions: List = []
    _find_functions(ctx.root, functions)
    summaries: Dict[str, FunctionSummary] = {}
    for fn in functions:
        body = fn.child_by_field_name("body")
        if body is None:
            continue
        name_node = fn.child_by_field_name("name")
        if name_node is not None:
            func_name = ctx.node_text(name_node)
        elif fn.type == "function_definition":
            func_name = _c_function_name(fn, ctx) or "<anonymous>"
        else:
            func_name = "<anonymous>"
        param_groups = _param_names(fn, ctx, lang)

        seed: Dict[str, TaintState] = {}
        for idx, names in enumerate(param_groups):
            for pname in names:
                step = TaintFlowStep(
                    file_path=file_path,
                    line_number=fn.start_point[0] + 1,
                    function_name=func_name,
                    step_type="param",
                    code_snippet="",
                    variable_name=pname,
                )
                # Destructured params (`{a, b}` / `[x, y]`) bind MULTIPLE
                # names at the SAME positional index -- a tainted positional
                # argument taints every bound name (over-approximate: does
                # not distinguish which destructured key was actually
                # tainted, matches the plan's "no reassignment tracking"
                # scope).
                seed[pname] = TaintState(
                    source_step=step,
                    source_type=TaintSourceType.HTTP_PARAMETER,  # placeholder; real type from caller
                    confidence=1.0,
                    param_index=idx,
                )
        params = [pname for names in param_groups for pname in names]

        visitor = CstFunctionTaintVisitor(
            file_path=file_path,
            func_name=func_name,
            ctx=ctx,
            lang=lang,
            custom_sanitizers=custom_sanitizers,
            extra_source_specs=source_specs,
            extra_sink_specs=sink_specs,
            alias_map=alias_map,
        )
        visitor.env.update(seed)
        visitor._walk(body)

        summary = FunctionSummary(qualname=func_name, file_path=file_path, param_names=params)
        for param_idx, spec, line, factor in visitor.param_sink_hits:
            summary.param_sinks.setdefault(param_idx, []).append(SinkRef(
                sink_type=(
                    spec.sink_type.value if hasattr(spec.sink_type, "value") else str(spec.sink_type)
                ),
                severity=spec.severity,
                line=line,
                path_factor=factor,
                function_name=func_name,
                file_path=file_path,
            ))
        summary.param_calls = list(visitor.param_call_edges)
        for state in visitor.return_states:
            if state.param_index is not None and state.source_step.step_type == "param":
                prev = summary.returns_params.get(state.param_index, 0.0)
                summary.returns_params[state.param_index] = max(prev, state.confidence)
            elif state.source_step.step_type == "source":
                src_type = (
                    state.source_type.value if hasattr(state.source_type, "value") else str(state.source_type)
                )
                if summary.fresh_return is None or state.confidence > summary.fresh_return[1]:
                    summary.fresh_return = (src_type, state.confidence, state.source_step.line_number)
        summaries[func_name] = summary
    return summaries


def collect_cst_imported_module_stems(alias_map: Dict[str, str]) -> Set[str]:
    """Module stems a file imports (for scoped CHA-style resolution),
    derived from the already-built alias map rather than re-walking the
    tree (``cst_alias.build_cst_alias_map`` already normalized relative
    specifiers to their basename)."""
    stems: Set[str] = set()
    for target in alias_map.values():
        head = target.split(".", 1)[0]
        if head:
            stems.add(head)
    return stems
