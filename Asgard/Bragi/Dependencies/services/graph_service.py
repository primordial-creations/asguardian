"""
Bragi Dependency Graph Service (Plan 03 Phase B)

One graph, many consumers: builds the import graph ONCE per scan and serves
cycles (SCC condensation), centrality (Ca/Ce/instability/pagerank/percentile),
and weighted break suggestions to every other Bragi consumer — replacing the
three-full-scans-per-report pattern (DEEPTHINK_09, RESEARCH_15, RESEARCH_02).

Caching (RESEARCH_15):
    - Per-file entries under `.asgard_cache/bragi_dep_graph.json` keyed by
      CONTENT hash (skip re-parsing unchanged files) and carrying an
      INTERFACE hash (sorted export names + import targets).
    - Derived results (SCCs, centrality) are keyed by the combined interface
      hash of all files: a body-only edit re-parses one file but leaves every
      interface hash unchanged, so dependents' cached edges and the derived
      results survive; changing an export list invalidates them.

All outputs are deterministic: modules and results are sorted, and pagerank
uses networkx's deterministic power iteration.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import networkx as nx

from Asgard.Bragi.Dependencies.models.dependency_models import (
    SCC,
    CentralityInfo,
    DependencyConfig,
    DependencySeverity,
    EdgeBreak,
    ModuleDependencies,
)
from Asgard.Bragi.Dependencies.services.import_analyzer import ImportAnalyzer

CACHE_RELATIVE_PATH = Path(".asgard_cache") / "bragi_dep_graph.json"
CACHE_VERSION = "1.0.0"

#: SCCs at or below this size get their simple cycles enumerated for display;
#: larger SCCs are reported as one component with break suggestions instead
#: (DEEPTHINK_09: never run simple_cycles on a dense component).
MAX_SCC_FOR_CYCLE_ENUMERATION = 12

#: Cap on enumerated simple cycles per SCC (display budget).
MAX_CYCLES_PER_SCC = 50

#: Number of minimum-weight feedback edges suggested per large SCC.
TOP_BREAK_SUGGESTIONS = 3


def no_cache_env() -> bool:
    """True when ASGARD_NO_CACHE requests that scans write nothing into
    the scanned path (read-only target safety)."""
    return os.environ.get("ASGARD_NO_CACHE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_exports(source: str) -> List[str]:
    """Top-level exported names: def/class/assignment targets (sorted)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    names: Set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return sorted(names)


def interface_hash(exports: List[str], import_targets: List[str]) -> str:
    """Hash of the file's exported interface + import list (not its body)."""
    payload = "\x00".join(sorted(exports)) + "\x01" + "\x00".join(sorted(import_targets))
    return _sha256(payload)


class DependencyGraph:
    """The single built import graph and its derived indices."""

    def __init__(
        self,
        modules: List[ModuleDependencies],
        scan_path: Path,
    ):
        self.scan_path = scan_path
        self.modules = sorted(modules, key=lambda m: m.module_name)
        self.by_name: Dict[str, ModuleDependencies] = {
            m.module_name: m for m in self.modules
        }
        # Internal edges only (both endpoints are scanned modules).
        self.graph: Dict[str, Set[str]] = {
            m.module_name: {d for d in m.all_dependencies if d in self.by_name}
            for m in self.modules
        }
        self.reverse: Dict[str, Set[str]] = {name: set() for name in self.graph}
        for src, deps in self.graph.items():
            for dst in deps:
                self.reverse[dst].add(src)
        # Edge weight basis: number of imported symbols per (src, dst).
        self.edge_symbols: Dict[Tuple[str, str], int] = {}
        for m in self.modules:
            for dep in m.dependency_list:
                if dep.target in self.by_name:
                    key = (m.module_name, dep.target)
                    self.edge_symbols[key] = self.edge_symbols.get(key, 0) + 1
        self.module_loc: Dict[str, int] = {}
        for m in self.modules:
            try:
                self.module_loc[m.module_name] = sum(
                    1 for _ in open(m.file_path, "r", encoding="utf-8", errors="ignore")
                )
            except OSError:
                self.module_loc[m.module_name] = 0

    def nx_graph(self) -> "nx.DiGraph":
        g = nx.DiGraph()
        g.add_nodes_from(sorted(self.graph))
        for src in sorted(self.graph):
            for dst in sorted(self.graph[src]):
                g.add_edge(src, dst)
        return g

    def edge_weight(self, source: str, target: str) -> float:
        """Break cost of an edge: imported symbols x (1 + source afferent).

        Removing an edge out of a heavily-depended-on module ripples to all
        its dependents, so the same symbol count costs more there.
        """
        symbols = self.edge_symbols.get((source, target), 1)
        return float(symbols) * (1.0 + len(self.reverse.get(source, set())))


class DependencyGraphService:
    """
    Builds the import graph once and serves cycles/centrality/breaks.

    Usage:
        service = DependencyGraphService(config)
        graph = service.build(scan_path)
        sccs = service.sccs(scan_path)
        centrality = service.centrality(scan_path)
        provider = service.centrality_provider(scan_path)   # Plan 02 exposure
    """

    def __init__(self, config: Optional[DependencyConfig] = None,
                 use_disk_cache: bool = True):
        self.config = config or DependencyConfig()
        # ASGARD_NO_CACHE=1 forces the disk cache off (read-only targets).
        self.use_disk_cache = use_disk_cache and not no_cache_env()
        self.import_analyzer = ImportAnalyzer(self.config)
        self._graphs: Dict[str, DependencyGraph] = {}
        self._derived: Dict[str, dict] = {}
        # Cache observability (tested properties, RESEARCH_15):
        self.last_parse_count = 0          # files parsed on the last build
        self.last_file_cache_hits = 0      # files served from content cache
        self.derived_cache_hit = False     # SCC/centrality reused via interface hash

    # ------------------------------------------------------------------ build

    def build(self, scan_path: Optional[Path] = None) -> DependencyGraph:
        """Build (or return the memoized) dependency graph for a path."""
        path = Path(scan_path or self.config.scan_path).resolve()
        key = str(path)
        if key in self._graphs:
            return self._graphs[key]

        cache = self._load_cache(path)
        cached_files: Dict[str, dict] = cache.get("files", {})

        modules = self.import_analyzer.analyze(path)
        self.last_parse_count = len(modules)
        self.last_file_cache_hits = 0

        new_files: Dict[str, dict] = {}
        for m in sorted(modules, key=lambda m: m.relative_path):
            try:
                source = Path(m.file_path).read_text(
                    encoding="utf-8", errors="ignore")
            except OSError:
                source = ""
            content_hash = _sha256(source)
            entry = cached_files.get(m.relative_path)
            if entry is not None and entry.get("content_hash") == content_hash:
                self.last_file_cache_hits += 1
                new_files[m.relative_path] = entry
                continue
            exports = _extract_exports(source)
            targets = sorted({d.target for d in m.dependency_list})
            new_files[m.relative_path] = {
                "content_hash": content_hash,
                "interface_hash": interface_hash(exports, targets),
                "module": m.module_name,
                "imports": targets,
                "exports": exports,
            }

        graph = DependencyGraph(modules, path)
        self._graphs[key] = graph

        graph_key = self._graph_key(new_files)
        derived = cache.get("derived", {})
        self.derived_cache_hit = derived.get("graph_key") == graph_key
        if not self.derived_cache_hit:
            derived = {
                "graph_key": graph_key,
                "sccs": [self._scc_payload(s) for s in self._compute_sccs(graph)],
                "centrality": {
                    name: info.__dict__
                    for name, info in self._compute_centrality(graph).items()
                },
            }
        self._derived[key] = derived

        if self.use_disk_cache:
            self._save_cache(path, {"version": CACHE_VERSION,
                                    "files": new_files,
                                    "derived": derived})
        return graph

    def invalidate(self, scan_path: Optional[Path] = None) -> None:
        """Drop the in-memory memo for a path (or all paths)."""
        if scan_path is None:
            self._graphs.clear()
            self._derived.clear()
        else:
            key = str(Path(scan_path).resolve())
            self._graphs.pop(key, None)
            self._derived.pop(key, None)

    @staticmethod
    def _graph_key(files: Dict[str, dict]) -> str:
        """Combined interface hash: unchanged under body-only edits."""
        payload = "\x00".join(
            f"{rel}={entry.get('interface_hash', '')}"
            for rel, entry in sorted(files.items())
        )
        return _sha256(payload)

    def _cache_path(self, scan_path: Path) -> Path:
        return scan_path / CACHE_RELATIVE_PATH

    def _load_cache(self, scan_path: Path) -> dict:
        if not self.use_disk_cache:
            return {}
        cache_file = self._cache_path(scan_path)
        if not cache_file.exists():
            return {}
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != CACHE_VERSION:
                return {}
            return data
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_cache(self, scan_path: Path, payload: dict) -> None:
        try:
            cache_file = self._cache_path(scan_path)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=1, sort_keys=True)
        except OSError:
            pass  # caching is best-effort, never fatal

    # ------------------------------------------------------------------- SCCs

    def sccs(self, scan_path: Optional[Path] = None) -> List[SCC]:
        """Strongly connected components of size >= 2, reach-ranked."""
        graph = self.build(scan_path)
        return self._compute_sccs(graph)

    def _compute_sccs(self, graph: DependencyGraph) -> List[SCC]:
        g = graph.nx_graph()
        result: List[SCC] = []
        for component in nx.strongly_connected_components(g):
            if len(component) < 2:
                continue
            members = sorted(component)
            member_loc = sum(graph.module_loc.get(m, 0) for m in members)
            external_afferent = sum(
                1
                for m in members
                for src in graph.reverse.get(m, set())
                if src not in component
            )
            internal_edges = sum(
                1
                for m in members
                for dst in graph.graph.get(m, set())
                if dst in component
            )
            scc = SCC(
                members=members,
                member_loc=member_loc,
                external_afferent=external_afferent,
                internal_edges=internal_edges,
            )
            scc.severity = self._scc_severity(scc)
            result.append(scc)
        # Deterministic: biggest reach first, then members.
        result.sort(key=lambda s: (-s.reach, s.members))
        return result

    @staticmethod
    def _scc_severity(scc: SCC) -> DependencySeverity:
        """Severity = f(reach), not f(length) (RESEARCH_02/15).

        A 2-cycle between two 1000-line, heavily-imported modules is CRITICAL;
        a 5-cycle between five 30-line leaf helpers is MODERATE.
        """
        if scc.reach >= 1000 or scc.external_afferent >= 10 or scc.size >= 8:
            return DependencySeverity.CRITICAL
        if scc.reach >= 300 or scc.external_afferent >= 3:
            return DependencySeverity.HIGH
        return DependencySeverity.MODERATE

    @staticmethod
    def _scc_payload(scc: SCC) -> dict:
        return {
            "members": scc.members,
            "member_loc": scc.member_loc,
            "external_afferent": scc.external_afferent,
            "internal_edges": scc.internal_edges,
            "severity": scc.severity.value,
        }

    def enumerate_cycles(self, graph: DependencyGraph, scc: SCC) -> List[List[str]]:
        """Simple cycles for display — only inside a small SCC (bounded)."""
        if scc.size > MAX_SCC_FOR_CYCLE_ENUMERATION:
            return []
        sub = graph.nx_graph().subgraph(scc.members)
        cycles: List[List[str]] = []
        for cycle in nx.simple_cycles(sub):
            min_idx = cycle.index(min(cycle))
            cycles.append(cycle[min_idx:] + cycle[:min_idx])
            if len(cycles) >= MAX_CYCLES_PER_SCC:
                break
        cycles.sort(key=lambda c: (len(c), c))
        return cycles

    # ------------------------------------------------------------ break edges

    def break_suggestions(
        self, scc: SCC, scan_path: Optional[Path] = None
    ) -> List[EdgeBreak]:
        """Minimum-weight feedback edges that would break the SCC.

        Greedy: repeatedly remove the cheapest intra-SCC edge (weight =
        imported symbols x (1 + source afferent)) until the component is
        acyclic; report the removals (top TOP_BREAK_SUGGESTIONS).
        """
        graph = self.build(scan_path)
        sub = nx.DiGraph()
        member_set = set(scc.members)
        for m in scc.members:
            for dst in graph.graph.get(m, set()):
                if dst in member_set:
                    sub.add_edge(m, dst, weight=graph.edge_weight(m, dst))
        suggestions: List[EdgeBreak] = []
        working = sub.copy()
        while True:
            cyclic_nodes = [
                c for c in nx.strongly_connected_components(working) if len(c) > 1
            ]
            if not cyclic_nodes:
                break
            candidates = sorted(
                (
                    (data["weight"], src, dst)
                    for src, dst, data in working.edges(data=True)
                    if any(src in c and dst in c for c in cyclic_nodes)
                ),
            )
            if not candidates:
                break
            weight, src, dst = candidates[0]
            working.remove_edge(src, dst)
            suggestions.append(EdgeBreak(
                source=src,
                target=dst,
                weight=weight,
                symbol_count=graph.edge_symbols.get((src, dst), 1),
                reason=(
                    f"Minimum-weight feedback edge: {graph.edge_symbols.get((src, dst), 1)} "
                    f"imported symbol(s), source has "
                    f"{len(graph.reverse.get(src, set()))} dependent(s)"
                ),
            ))
        return suggestions[:TOP_BREAK_SUGGESTIONS]

    # ------------------------------------------------------------- centrality

    def centrality(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, CentralityInfo]:
        """Ca/Ce/instability/pagerank + afferent percentile per module."""
        graph = self.build(scan_path)
        return self._compute_centrality(graph)

    def _compute_centrality(
        self, graph: DependencyGraph
    ) -> Dict[str, CentralityInfo]:
        names = sorted(graph.graph)
        if not names:
            return {}
        afferents = {n: len(graph.reverse.get(n, set())) for n in names}
        efferents = {n: len(graph.graph.get(n, set())) for n in names}
        g = graph.nx_graph()
        try:
            pagerank = nx.pagerank(g, alpha=0.85)
        except Exception:
            pagerank = {n: 0.0 for n in names}
        total = len(names)
        result: Dict[str, CentralityInfo] = {}
        for name in names:
            ca, ce = afferents[name], efferents[name]
            below = sum(1 for other in names if afferents[other] < ca)
            result[name] = CentralityInfo(
                module=name,
                afferent=ca,
                efferent=ce,
                instability=(ce / (ca + ce)) if (ca + ce) else 0.0,
                pagerank=round(float(pagerank.get(name, 0.0)), 10),
                afferent_percentile=below / total if total > 1 else 0.0,
            )
        return result

    def centrality_provider(
        self, scan_path: Optional[Path] = None
    ) -> Callable[[str], Optional[float]]:
        """
        A `CentralityProvider` for Plan 02's Exposure Factor: maps a module
        name, absolute file path, or relative path to its afferent-coupling
        percentile in [0, 1]. Returns None for unknown paths.
        """
        graph = self.build(scan_path)
        centrality = self._compute_centrality(graph)
        by_key: Dict[str, float] = {}
        for m in graph.modules:
            info = centrality.get(m.module_name)
            if info is None:
                continue
            by_key[m.module_name] = info.afferent_percentile
            by_key[str(Path(m.file_path))] = info.afferent_percentile
            by_key[m.relative_path] = info.afferent_percentile

        def provider(path_or_module: str) -> Optional[float]:
            key = str(path_or_module)
            if key in by_key:
                return by_key[key]
            try:
                resolved = str(Path(key).resolve())
            except (OSError, ValueError):
                return None
            return by_key.get(resolved)

        return provider

    # ------------------------------------------------------- import frequency

    def import_frequencies(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, int]:
        """
        Import-site count per imported module across the codebase (Plan 03
        §3.4): the fact feed for Quality's lazy-import scanner, which needs
        RESEARCH_18's dual heuristic (import cost x call-site frequency)
        instead of import cost alone.
        """
        graph = self.build(scan_path)
        frequencies: Dict[str, int] = {}
        for m in graph.modules:
            for dep in m.dependency_list:
                frequencies[dep.target] = frequencies.get(dep.target, 0) + 1
        return dict(sorted(frequencies.items()))
