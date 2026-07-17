"""
Flow-insensitive, over-approximated function summaries (DEEPTHINK_05).

For every function we record, per parameter index:
- which sinks the parameter reaches inside the function (with the
  accumulated path-confidence factor),
- whether the parameter's taint is returned,
- which callee parameters it is forwarded to (call edges),
plus whether the function returns *fresh* taint (e.g. a helper that returns
``request.args``).

Cross-function/cross-file resolution chains these base summaries at query
time, bounded at ``max_hops`` (default 4) call edges with a x0.85 decay per
resolved hop. Paths beyond the bound are dropped (deeper traversal destroys
precision; >80% of true injection paths span <= 4 hops).

Cache correctness: only *base* summaries (which depend solely on their own
file's content) are cached, keyed by the file's SHA-256. Chaining across
files always happens live at scan time, so editing file B (e.g. removing a
sanitizer) automatically re-derives every flow through B on the next scan --
no reverse-dependency bookkeeping can go stale.

Honest limitations: no type inference -- ``obj.method()`` resolution is
class-hierarchy-style name matching scoped to the current file and its
imports (over-approximated union); returned taint is chained only one level
deep through call results; keyword arguments are not mapped to parameters.
"""

import ast
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from Asgard.Heimdall.Security.normalization.priority import confidence_bucket
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sinks import SinkSpec
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintFlow,
    TaintFlowStep,
    TaintSinkType,
)
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_visitor import (
    RESOLVED_HOP_DECAY,
    ResolvedCall,
    TaintState,
    _FunctionTaintVisitor,
    _get_code_snippet,
)

MAX_HOPS_DEFAULT = 4


@dataclass
class SinkRef:
    """A sink reachable from a function parameter."""
    sink_type: str
    severity: str
    line: int
    path_factor: float      # sink conf x propagator decays inside the callee
    function_name: str
    file_path: str


@dataclass
class FunctionSummary:
    """Base (intra-procedural) summary of one function."""
    qualname: str
    file_path: str
    param_names: List[str] = field(default_factory=list)
    # param index -> sinks it reaches directly inside this function
    param_sinks: Dict[int, List[SinkRef]] = field(default_factory=dict)
    # call edges forwarding params: (callee chain, {callee_pos: param_idx}, line)
    param_calls: List[Tuple[str, Dict[int, int], int]] = field(default_factory=list)
    # param indexes whose taint is returned (with residual factor)
    returns_params: Dict[int, float] = field(default_factory=dict)
    # fresh taint returned: (source_type, confidence, line)
    fresh_return: Optional[Tuple[str, float, int]] = None

    def to_json(self) -> dict:
        d = asdict(self)
        d["param_sinks"] = {
            str(k): [asdict(s) for s in v] for k, v in self.param_sinks.items()
        }
        d["returns_params"] = {str(k): v for k, v in self.returns_params.items()}
        return d

    @classmethod
    def from_json(cls, d: dict) -> "FunctionSummary":
        return cls(
            qualname=d["qualname"],
            file_path=d["file_path"],
            param_names=list(d.get("param_names", [])),
            param_sinks={
                int(k): [SinkRef(**s) for s in v]
                for k, v in d.get("param_sinks", {}).items()
            },
            param_calls=[
                (c[0], {int(a): int(b) for a, b in c[1].items()}, c[2])
                for c in d.get("param_calls", [])
            ],
            returns_params={int(k): v for k, v in d.get("returns_params", {}).items()},
            fresh_return=tuple(d["fresh_return"]) if d.get("fresh_return") else None,
        )


def _param_names(node) -> List[str]:
    args = node.args
    names = [a.arg for a in args.posonlyargs + args.args]
    return [n for n in names if n not in ("self", "cls")]


def compute_file_summaries(
    file_path: str,
    tree: ast.AST,
    lines: List[str],
    alias_map: Dict[str, str],
    visitor_kwargs: Optional[dict] = None,
) -> Dict[str, FunctionSummary]:
    """Compute base summaries for every function in a parsed file."""
    summaries: Dict[str, FunctionSummary] = {}
    visitor_kwargs = visitor_kwargs or {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = _param_names(node)
        seed: Dict[str, TaintState] = {}
        for idx, name in enumerate(params):
            step = TaintFlowStep(
                file_path=file_path,
                line_number=node.lineno,
                function_name=node.name,
                step_type="param",
                code_snippet=_get_code_snippet(lines, node.lineno),
                variable_name=name,
            )
            seed[name] = TaintState(
                source_step=step,
                source_type="http_parameter",  # placeholder; real type from caller
                confidence=1.0,
                param_index=idx,
            )
        visitor = _FunctionTaintVisitor(
            file_path=file_path,
            func_name=node.name,
            lines=lines,
            initial_taint=seed,
            alias_map=alias_map,
            **visitor_kwargs,
        )
        for stmt in node.body:
            visitor.visit(stmt)

        summary = FunctionSummary(
            qualname=node.name, file_path=file_path, param_names=params
        )
        for param_idx, spec, line, factor in visitor.param_sink_hits:
            summary.param_sinks.setdefault(param_idx, []).append(SinkRef(
                sink_type=(
                    spec.sink_type.value
                    if hasattr(spec.sink_type, "value") else str(spec.sink_type)
                ),
                severity=spec.severity,
                line=line,
                path_factor=factor,
                function_name=node.name,
                file_path=file_path,
            ))
        summary.param_calls = list(visitor.param_call_edges)
        for state in visitor.return_states:
            if state.param_index is not None and state.source_step.step_type == "param":
                prev = summary.returns_params.get(state.param_index, 0.0)
                summary.returns_params[state.param_index] = max(prev, state.confidence)
            elif state.source_step.step_type == "source":
                src_type = (
                    state.source_type.value
                    if hasattr(state.source_type, "value") else str(state.source_type)
                )
                if (
                    summary.fresh_return is None
                    or state.confidence > summary.fresh_return[1]
                ):
                    summary.fresh_return = (
                        src_type, state.confidence, state.source_step.line_number
                    )
        summaries[node.name] = summary
    return summaries


class SummaryCache:
    """SQLite cache of base summaries keyed by file content hash."""

    def __init__(self, db_path: Path):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS summaries "
            "(file_hash TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        self._conn.commit()

    @staticmethod
    def file_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()

    def get(self, file_hash: str) -> Optional[Dict[str, FunctionSummary]]:
        row = self._conn.execute(
            "SELECT payload FROM summaries WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row[0])
            return {k: FunctionSummary.from_json(v) for k, v in data.items()}
        except (ValueError, KeyError, TypeError):
            return None

    def put(self, file_hash: str, summaries: Dict[str, FunctionSummary]) -> None:
        payload = json.dumps({k: v.to_json() for k, v in summaries.items()})
        self._conn.execute(
            "INSERT OR REPLACE INTO summaries (file_hash, payload) VALUES (?, ?)",
            (file_hash, payload),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class SummaryIndex:
    """
    Cross-file summary resolution with bounded top-down propagation.

    Implements the visitor's ``CallResolver`` protocol.
    """

    def __init__(self, max_hops: int = MAX_HOPS_DEFAULT):
        self.max_hops = max(0, int(max_hops))
        # file -> {func_name -> summary}
        self._by_file: Dict[str, Dict[str, FunctionSummary]] = {}
        # module stem -> file path
        self._module_files: Dict[str, str] = {}
        # file -> set of module stems it imports
        self._file_imports: Dict[str, Set[str]] = {}
        self._current_file: str = ""
        self._lines_by_file: Dict[str, List[str]] = {}

    def add_file(
        self,
        file_path: str,
        summaries: Dict[str, FunctionSummary],
        imported_modules: Set[str],
        lines: List[str],
    ) -> None:
        self._by_file[file_path] = summaries
        self._module_files[Path(file_path).stem] = file_path
        self._file_imports[file_path] = set(imported_modules)
        self._lines_by_file[file_path] = lines

    def set_current_file(self, file_path: str) -> None:
        self._current_file = file_path

    # ------------------------------------------------------------ resolution

    def _candidates(self, chain: str, from_file: str) -> List[FunctionSummary]:
        """Resolve a call chain to candidate function summaries."""
        results: List[FunctionSummary] = []
        parts = chain.split(".")
        tail = parts[-1]
        # module.function (alias-resolved 'from x import f' or 'import x; x.f')
        if len(parts) >= 2:
            module_stem = parts[-2]
            target = self._module_files.get(module_stem)
            if target is not None:
                summary = self._by_file.get(target, {}).get(tail)
                if summary is not None:
                    return [summary]
        # same-file function
        local = self._by_file.get(from_file, {}).get(tail)
        if local is not None:
            return [local]
        # CHA-style method resolution scoped to imported files
        if len(parts) >= 2:
            for stem in self._file_imports.get(from_file, set()):
                target = self._module_files.get(stem)
                if target is None:
                    continue
                summary = self._by_file.get(target, {}).get(tail)
                if summary is not None:
                    results.append(summary)
        return results[:5]  # cap union size to bound over-approximation

    def resolve_call(
        self,
        chain: str,
        arg_states: List[Optional[TaintState]],
        call_line: int,
    ) -> "ResolvedCall":
        """
        CallResolver hook: inter-procedural flows + return taint.

        A resolved callee whose summary shows no returned param taint and no
        fresh-source return has a CLEAN return value (constant, or the param
        passed through an exact sanitizer) -- expressed as
        ``ResolvedCall(resolved=True, return_state=None)``.
        """
        candidates = self._candidates(chain, self._current_file)
        if not candidates:
            return ResolvedCall(resolved=False)
        flows: List[TaintFlow] = []
        ret_state: Optional[TaintState] = None
        for summary in candidates:
            for pos, state in enumerate(arg_states):
                if state is None or state.param_index is not None:
                    continue  # synthetic seeds handled via call edges
                for sink_ref, hops, factor in self._reachable_sinks(
                    summary, pos, depth=1, visited=set()
                ):
                    conf = state.confidence * factor
                    if conf <= 0.0:
                        continue
                    flows.append(self._build_flow(
                        state, sink_ref, hops, min(1.0, conf), chain, call_line
                    ))
                # returned param taint
                ret_factor = summary.returns_params.get(pos)
                if ret_factor:
                    candidate = state.decayed(RESOLVED_HOP_DECAY * ret_factor)
                    candidate.hop_count = state.hop_count + 1
                    if ret_state is None or candidate.confidence > ret_state.confidence:
                        ret_state = candidate
            # fresh taint returned by the callee
            if summary.fresh_return is not None:
                src_type, conf, line = summary.fresh_return
                step = TaintFlowStep(
                    file_path=summary.file_path,
                    line_number=line,
                    function_name=summary.qualname,
                    step_type="source",
                    code_snippet=_get_code_snippet(
                        self._lines_by_file.get(summary.file_path, []), line
                    ),
                    variable_name=summary.qualname,
                )
                candidate = TaintState(
                    source_step=step,
                    source_type=src_type,
                    confidence=conf * RESOLVED_HOP_DECAY,
                    hop_count=1,
                )
                if ret_state is None or candidate.confidence > ret_state.confidence:
                    ret_state = candidate
        return ResolvedCall(resolved=True, return_state=ret_state, flows=flows)

    def _reachable_sinks(
        self,
        summary: FunctionSummary,
        param_idx: int,
        depth: int,
        visited: Set[Tuple[str, str, int]],
    ) -> List[Tuple[SinkRef, int, float]]:
        """
        Sinks reachable from ``param_idx`` of ``summary`` within the hop
        budget. Returns (sink_ref, hops, combined_factor) where factor
        already includes 0.85 per hop and the callee-internal path factor.
        """
        if depth > self.max_hops:
            return []
        key = (summary.file_path, summary.qualname, param_idx)
        if key in visited:
            return []
        visited = visited | {key}
        results: List[Tuple[SinkRef, int, float]] = []
        hop_decay = RESOLVED_HOP_DECAY ** depth
        for sink_ref in summary.param_sinks.get(param_idx, []):
            results.append((sink_ref, depth, hop_decay * sink_ref.path_factor))
        for callee_chain, mapping, _line in summary.param_calls:
            forwarded = [pos for pos, p_idx in mapping.items() if p_idx == param_idx]
            if not forwarded:
                continue
            for callee in self._candidates(callee_chain, summary.file_path):
                for pos in forwarded:
                    results.extend(self._reachable_sinks(
                        callee, pos, depth + 1, visited
                    ))
        return results

    def _build_flow(
        self,
        state: TaintState,
        sink_ref: SinkRef,
        hops: int,
        confidence: float,
        chain: str,
        call_line: int,
    ) -> TaintFlow:
        from Asgard.Heimdall.Security.TaintAnalysis.services._taint_patterns import (
            SINK_CWE, SINK_OWASP, SINK_TITLES,
        )
        sink_type = TaintSinkType(sink_ref.sink_type)
        call_step = TaintFlowStep(
            file_path=self._current_file,
            line_number=call_line,
            function_name=chain,
            step_type="propagation",
            code_snippet=_get_code_snippet(
                self._lines_by_file.get(self._current_file, []), call_line
            ),
            variable_name=chain,
        )
        sink_step = TaintFlowStep(
            file_path=sink_ref.file_path,
            line_number=sink_ref.line,
            function_name=sink_ref.function_name,
            step_type="sink",
            code_snippet=_get_code_snippet(
                self._lines_by_file.get(sink_ref.file_path, []), sink_ref.line
            ),
            variable_name="",
        )
        return TaintFlow(
            source_type=state.source_type,
            sink_type=sink_type,
            severity=sink_ref.severity,
            source_location=state.source_step,
            sink_location=sink_step,
            intermediate_steps=list(state.trace) + [call_step],
            title=SINK_TITLES.get(sink_type, "Tainted Data Flow"),
            description=(
                f"Tainted data from {state.source_type} source reaches "
                f"{sink_ref.sink_type} sink through {hops} function-call "
                f"hop(s) (inter-procedural summary resolution)."
            ),
            cwe_id=SINK_CWE.get(sink_type, ""),
            owasp_category=SINK_OWASP.get(sink_type, ""),
            sanitizers_present=bool(state.sanitizers),
            confidence=round(confidence, 4),
            confidence_bucket=confidence_bucket(confidence),
            hop_count=hops,
            sanitizers_applied=list(state.sanitizers),
        )


def collect_imported_module_stems(tree: ast.AST) -> Set[str]:
    """Module stems a file imports (for scoped CHA-style resolution)."""
    stems: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                stems.add(a.name.split(".")[-1])
                stems.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            stems.add(node.module.split(".")[-1])
            for a in node.names:
                stems.add(a.name)
    return stems
