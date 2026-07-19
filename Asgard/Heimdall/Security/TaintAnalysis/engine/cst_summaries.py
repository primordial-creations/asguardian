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

from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import JAVA_SINK_SPECS, JS_SINK_SPECS
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import JAVA_SOURCE_SPECS, JS_SOURCE_SPECS
from Asgard.Heimdall.Security.TaintAnalysis.engine.cst_taint_visitor import (
    CstFunctionTaintVisitor,
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


def _js_param_names(fn, ctx) -> List[str]:
    names: List[str] = []
    params_node = fn.child_by_field_name("parameters")
    if params_node is None:
        # Arrow function with a single unparenthesized identifier param,
        # e.g. `x => x.trim()`.
        single = fn.child_by_field_name("parameter")
        if single is not None and single.type == "identifier":
            return [ctx.node_text(single)]
        return names
    for child in params_node.named_children:
        if child.type == "identifier":
            names.append(ctx.node_text(child))
        elif child.type in _JS_PARAM_WRAPPERS:
            pattern = child.child_by_field_name("pattern") or child.child_by_field_name("name")
            if pattern is not None and pattern.type == "identifier":
                names.append(ctx.node_text(pattern))
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                names.append(ctx.node_text(left))
        # Destructured params (`object_pattern`/`array_pattern`) contribute
        # no single tracked name -- documented gap, matches the Python
        # engine's "no keyword/complex-target param mapping" limitation.
    return names


def _java_param_names(fn, ctx) -> List[str]:
    names: List[str] = []
    params_node = fn.child_by_field_name("parameters")
    if params_node is None:
        return names
    for child in params_node.named_children:
        if child.type in ("formal_parameter", "spread_parameter", "receiver_parameter"):
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                names.append(ctx.node_text(name_node))
    return names


def _param_names(fn, ctx, lang: str) -> List[str]:
    if lang in _JS_LANGS:
        return _js_param_names(fn, ctx)
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
    source_specs = JAVA_SOURCE_SPECS if lang == "java" else JS_SOURCE_SPECS
    sink_specs = JAVA_SINK_SPECS if lang == "java" else JS_SINK_SPECS

    functions: List = []
    _find_functions(ctx.root, functions)
    summaries: Dict[str, FunctionSummary] = {}
    for fn in functions:
        body = fn.child_by_field_name("body")
        if body is None:
            continue
        name_node = fn.child_by_field_name("name")
        func_name = ctx.node_text(name_node) if name_node is not None else "<anonymous>"
        params = _param_names(fn, ctx, lang)

        seed: Dict[str, TaintState] = {}
        for idx, pname in enumerate(params):
            step = TaintFlowStep(
                file_path=file_path,
                line_number=fn.start_point[0] + 1,
                function_name=func_name,
                step_type="param",
                code_snippet="",
                variable_name=pname,
            )
            seed[pname] = TaintState(
                source_step=step,
                source_type=TaintSourceType.HTTP_PARAMETER,  # placeholder; real type from caller
                confidence=1.0,
                param_index=idx,
            )

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
