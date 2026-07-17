"""
Heimdall Taint Analyzer Service

Confidence-scored intra- and inter-procedural taint analysis on Python
source using the stdlib ``ast`` module.

Pipeline per scan:
1. Parse every file once; build the import-alias map (mandatory -- without
   it ``from requests import get as fetch`` silently bypasses matching).
2. Compute flow-insensitive function summaries per file (optionally cached
   in SQLite keyed by file hash).
3. Analyze module body and every function with the taint visitor, with the
   summary index as inter-procedural call resolver (bounded at
   ``config.max_hops``, default 4).
4. Deduplicate by (file, sink line, sink column, CWE), filter by severity and confidence
   bucket, sort deterministically.

Route-decorated function parameters (Flask/FastAPI/Django stubs) are seeded
as heuristic sources at confidence 0.6.

Honesty note: this is a shift-left guardrail. Expected operating point on
real-world code is roughly 25-40% recall at ~70% precision -- it does NOT
replace a deep SAST engine, and every finding carries a confidence bucket
reflecting exactly how it was derived.
"""

import ast
import fnmatch
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintConfig,
    TaintFlow,
    TaintReport,
)
from Asgard.Heimdall.Security.TaintAnalysis.catalog.sources import (
    ROUTE_PARAM_CONFIDENCE,
)
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintFlowStep,
    TaintSourceType,
)
from Asgard.Heimdall.Security.TaintAnalysis.services._taint_visitor import (
    TaintState,
    _FunctionTaintVisitor,
    _attr_chain,
    _get_code_snippet,
    build_alias_map,
    resolve_chain,
)
from Asgard.Heimdall.Security.TaintAnalysis.stubs import load_framework_stubs
from Asgard.Heimdall.Security.TaintAnalysis.summaries import (
    SummaryCache,
    SummaryIndex,
    collect_imported_module_stems,
    compute_file_summaries,
)

from Asgard.Heimdall.Security.context.test_context import is_test_context

_TEST_PATH_MARKERS = ("test_", "_test.py", "conftest.py")


def _should_exclude(path: Path, exclude_patterns: List[str]) -> bool:
    """Check if a path should be excluded from scanning."""
    path_str = str(path)
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(path.name, pattern):
            return True
        if fnmatch.fnmatch(path_str, f"*{pattern}*"):
            return True
        if pattern in path_str:
            return True
    return False


def _collect_python_files(scan_path: Path, exclude_patterns: List[str]) -> List[Path]:
    """Collect all Python files under scan_path, respecting exclusions."""
    files: List[Path] = []
    if scan_path.is_file():
        return [scan_path]
    for py_file in scan_path.rglob("*.py"):
        if not _should_exclude(py_file, exclude_patterns):
            files.append(py_file)
    return sorted(files)


def _is_test_path(path: Path) -> bool:
    """
    Test-context detection (confidence cap, plan 08).

    Delegates to the Security/context engine: word-boundary directory
    matching AND filename-convention conjunction, plus standalone
    test-infrastructure filenames. This replaces the earlier
    any-'test'-segment heuristic (which false-positived on /ab_testing/
    and false-suppressed prod scripts named test_db_connection.py).
    """
    return is_test_context(str(path))


class _ParsedFile:
    """Single-parse context for one file."""

    def __init__(self, path: Path, source: str, tree: ast.AST):
        self.path = path
        self.source = source
        self.tree = tree
        self.lines = source.splitlines()
        self.alias_map = build_alias_map(tree)
        self.imported_stems = collect_imported_module_stems(tree)
        self.is_test = _is_test_path(path)


class TaintAnalyzer:
    """
    Confidence-scored taint analysis on Python source code.

    Findings carry orthogonal ``severity`` (impact) and ``confidence``
    (detection certainty, displayed as qualitative buckets).
    """

    def __init__(self, config: Optional[TaintConfig] = None):
        self.config = config or TaintConfig()
        self._custom_sources = set(self.config.custom_sources)
        self._custom_sinks = set(self.config.custom_sinks)
        self._custom_sanitizers = set(self.config.custom_sanitizers)
        self._stubs = load_framework_stubs(self.config.framework_stubs)
        self._all_sanitizers = self._custom_sanitizers | set(self._stubs.sanitizer_names)

    # ------------------------------------------------------------------ scan

    def scan(self, scan_path: Optional[Path] = None) -> TaintReport:
        """Scan the specified path for taint flows."""
        path = Path(scan_path or self.config.scan_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()
        report = TaintReport(scan_path=str(path))

        parsed = self._parse_files(path)
        report.files_analyzed = len(parsed)

        index = self._build_summary_index(parsed)

        all_flows: List[TaintFlow] = []
        for pf in parsed:
            index.set_current_file(str(pf.path))
            all_flows.extend(self._analyze_parsed_file(pf, index))

        for flow in self._dedup(all_flows):
            if not self._severity_meets_threshold(flow.severity):
                continue
            if flow.confidence < self.config.min_confidence:
                continue
            report.add_flow(flow)

        severity_order = {"critical": 0, "high": 1, "medium": 2}
        report.flows.sort(
            key=lambda f: (
                severity_order.get(f.severity, 3),
                f.sink_location.file_path,
                f.sink_location.line_number,
                f.cwe_id,
                -f.confidence,
            )
        )
        report.scan_duration_seconds = time.time() - start_time
        return report

    # --------------------------------------------------------------- parsing

    def _parse_files(self, path: Path) -> List["_ParsedFile"]:
        parsed: List[_ParsedFile] = []
        for file_path in _collect_python_files(path, self.config.exclude_patterns):
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
            except (IOError, OSError):
                continue
            try:
                tree = ast.parse(source, filename=str(file_path))
            except SyntaxError:
                continue
            parsed.append(_ParsedFile(file_path, source, tree))
        return parsed

    # ------------------------------------------------------------- summaries

    def _build_summary_index(self, parsed: List["_ParsedFile"]) -> SummaryIndex:
        index = SummaryIndex(max_hops=self.config.max_hops)
        cache: Optional[SummaryCache] = None
        if self.config.summary_cache_path is not None:
            try:
                cache = SummaryCache(self.config.summary_cache_path)
            except Exception:
                cache = None
        for pf in parsed:
            summaries = None
            file_hash = ""
            if cache is not None:
                file_hash = SummaryCache.file_hash(pf.source)
                summaries = cache.get(file_hash)
            if summaries is None:
                summaries = compute_file_summaries(
                    str(pf.path), pf.tree, pf.lines, pf.alias_map,
                    visitor_kwargs=self._visitor_kwargs(pf, resolver=None),
                )
                if cache is not None:
                    cache.put(file_hash, summaries)
            index.add_file(str(pf.path), summaries, pf.imported_stems, pf.lines)
        if cache is not None:
            cache.close()
        return index

    def _visitor_kwargs(self, pf: "_ParsedFile", resolver) -> dict:
        return {
            "custom_sources": self._custom_sources,
            "custom_sinks": self._custom_sinks,
            "custom_sanitizers": self._all_sanitizers,
            "extra_source_specs": tuple(self._stubs.source_specs),
            "extra_sink_specs": tuple(self._stubs.sink_specs),
            "call_resolver": resolver,
            "is_test_context": pf.is_test,
        }

    # -------------------------------------------------------------- analysis

    def _analyze_parsed_file(
        self, pf: "_ParsedFile", index: SummaryIndex
    ) -> List[TaintFlow]:
        flows: List[TaintFlow] = []
        resolver = index.resolve_call if (
            self.config.track_cross_function or self.config.track_cross_file
        ) else None
        kwargs = self._visitor_kwargs(pf, resolver)
        file_path_str = str(pf.path)

        # Module body (top-level statements).
        module_visitor = _FunctionTaintVisitor(
            file_path=file_path_str,
            func_name="<module>",
            lines=pf.lines,
            initial_taint={},
            alias_map=pf.alias_map,
            **kwargs,
        )
        for stmt in pf.tree.body:
            module_visitor.visit(stmt)
        flows.extend(module_visitor.found_flows)
        module_taint = {
            k: v for k, v in module_visitor.env.items() if v.param_index is None
        }

        # Every function (including methods and nested functions).
        for node in ast.walk(pf.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            initial = dict(module_taint) if self.config.track_cross_function else {}
            initial.update(self._route_param_seed(node, pf, file_path_str))
            visitor = _FunctionTaintVisitor(
                file_path=file_path_str,
                func_name=node.name,
                lines=pf.lines,
                initial_taint=initial,
                alias_map=pf.alias_map,
                **kwargs,
            )
            for stmt in node.body:
                visitor.visit(stmt)
            flows.extend(visitor.found_flows)
        return flows

    def _route_param_seed(
        self, node, pf: "_ParsedFile", file_path_str: str
    ) -> Dict[str, TaintState]:
        """Seed params of route-decorated functions as heuristic sources."""
        if not self._stubs.route_decorators:
            return {}
        decorated = False
        for dec in node.decorator_list:
            chain = resolve_chain(_attr_chain(dec), pf.alias_map)
            for pattern in self._stubs.route_decorators:
                if chain == pattern or chain.endswith("." + pattern) or \
                        chain.startswith(pattern + "."):
                    decorated = True
                    break
            if decorated:
                break
        if not decorated:
            return {}
        seed: Dict[str, TaintState] = {}
        arg_names = [
            a.arg for a in node.args.posonlyargs + node.args.args
            if a.arg not in ("self", "cls", "request")
        ]
        for name in arg_names:
            step = TaintFlowStep(
                file_path=file_path_str,
                line_number=node.lineno,
                function_name=node.name,
                step_type="source",
                code_snippet=_get_code_snippet(pf.lines, node.lineno),
                variable_name=name,
            )
            seed[name] = TaintState(
                source_step=step,
                source_type=TaintSourceType.PATH_PARAMETER,
                confidence=ROUTE_PARAM_CONFIDENCE,
            )
        return seed

    # --------------------------------------------------------------- filters

    @staticmethod
    def _dedup(flows: List[TaintFlow]) -> List[TaintFlow]:
        """Deduplicate by (file, sink line, sink column, CWE); keep highest confidence."""
        best: Dict[tuple, TaintFlow] = {}
        for flow in flows:
            key = (
                flow.sink_location.file_path,
                flow.sink_location.line_number,
                flow.sink_location.column,
                flow.cwe_id,
            )
            existing = best.get(key)
            if existing is None or flow.confidence > existing.confidence:
                best[key] = flow
        return list(best.values())

    def _severity_meets_threshold(self, severity: str) -> bool:
        order = {"critical": 0, "high": 1, "medium": 2}
        min_order = order.get(self.config.min_severity, 2)
        return order.get(severity, 3) <= min_order
