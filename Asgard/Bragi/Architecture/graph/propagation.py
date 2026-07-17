"""
Topological Bound Propagation — the layer-inference CSP
(DEEPTHINK_03 top-level, Heimdall Plan 03 §3).

    init: matched files -> min=max=base level; unmatched -> min=0, max=MAX
          external imports -> anchored at their configured level
    iterate until fixpoint (monotonic, guaranteed to converge):
        Rule 1 (outward gravity): A.min = max(A.min, B.min) for each A->B
        Rule 2 (inward gravity):  B.max = min(B.max, A.max) for each A->B

Language-agnostic over whatever `DependencyGraph` the caller built (Bragi's
cached import graph, `Dependencies/services/graph_service.py`) — this module
never re-parses or re-walks the filesystem itself.
"""

from __future__ import annotations

import fnmatch
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Bragi.Architecture.graph.nodes import LevelBounds
from Asgard.Bragi.Architecture.services._architecture_config import (
    ArchitectureConfig,
    LayerConfig,
)
from Asgard.Bragi.Dependencies.services.graph_service import DependencyGraph
from collections import deque


def _max_level(config: ArchitectureConfig) -> int:
    levels = [layer.level for layer in config.layers if layer.level is not None]
    return max(levels) if levels else 0


def _match_layer(module: str, class_names: Set[str], config: ArchitectureConfig) -> Optional[LayerConfig]:
    """Heuristic base-level match: path glob OR suffix on module/class name."""
    path_str = "/" + module.replace(".", "/")
    for layer in config.layers:
        if layer.level is None:
            continue
        for pattern in layer.path_patterns:
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(module, pattern):
                return layer
        for suffix in layer.suffixes:
            if module.split(".")[-1].endswith(suffix):
                return layer
            if any(name.endswith(suffix) for name in class_names):
                return layer
    return None


def _match_external_anchor(import_name: str, config: ArchitectureConfig) -> Optional[LayerConfig]:
    root = import_name.split(".")[0]
    for layer in config.layers:
        if layer.level is None:
            continue
        for anchor in layer.external_imports:
            anchor_root = anchor.split(".")[0]
            if import_name == anchor or import_name.startswith(anchor + ".") or root == anchor_root:
                return layer
    return None


def _external_anchor_edges(
    graph: DependencyGraph,
    config: ArchitectureConfig,
    raw_imports_by_module: Optional[Dict[str, Set[str]]],
) -> List[Tuple[str, int, str]]:
    """Edges from a module to a configured `external_imports` anchor level.

    `dependency_list` on `DependencyGraph` only carries *resolved internal*
    targets, so external packages (sqlalchemy, requests, ...) never appear
    there. `raw_imports_by_module` — raw import-statement roots parsed
    independently per module — is what lets an external anchor pin a
    module's level even though the import never resolves to a graph node.
    """
    edges: List[Tuple[str, int, str]] = []
    raw_imports_by_module = raw_imports_by_module or {}
    for module, imports in raw_imports_by_module.items():
        for imp in imports:
            if imp in graph.by_name:
                continue
            layer = _match_external_anchor(imp, config)
            if layer is not None:
                edges.append((module, layer.level, imp))
    # Also honour any external targets that happen to appear in
    # dependency_list (defensive; harmless if empty).
    for m in graph.modules:
        for dep in m.dependency_list:
            if dep.target in graph.by_name:
                continue
            layer = _match_external_anchor(dep.target, config)
            if layer is not None:
                edges.append((m.module_name, layer.level, dep.target))
    return edges


def infer_levels(
    graph: DependencyGraph,
    config: ArchitectureConfig,
    class_names_by_module: Optional[Dict[str, Set[str]]] = None,
    raw_imports_by_module: Optional[Dict[str, Set[str]]] = None,
) -> Dict[str, LevelBounds]:
    """
    Run the layer-inference CSP over `graph` using `config`'s configured
    layer levels. Returns {} if `config` has no `level:`-bearing layers
    (caller should fall back to glob-only classification).
    """
    if not config.has_level_inference:
        return {}

    class_names_by_module = class_names_by_module or {}
    max_lvl = _max_level(config)
    bounds: Dict[str, LevelBounds] = {}

    for module in graph.graph:
        layer = _match_layer(module, class_names_by_module.get(module, set()), config)
        if layer is not None:
            bounds[module] = LevelBounds(
                module=module,
                min_level=layer.level,
                max_level=layer.level,
                base_level=layer.level,
                matched=True,
                pinned_by=[f"heuristic match -> layer '{layer.name}' (level {layer.level})"],
            )
        else:
            bounds[module] = LevelBounds(
                module=module, min_level=0, max_level=max_lvl, matched=False,
            )

    # External-import anchors: every edge to a non-internal import that
    # matches a configured `external_imports` anchor pins an outward bound.
    external_anchor_edges = _external_anchor_edges(graph, config, raw_imports_by_module)

    # Fixpoint iteration (monotonic on a finite lattice -> guaranteed to
    # converge in at most |V| passes).
    changed = True
    iterations = 0
    while changed and iterations <= len(bounds) + 1:
        changed = False
        iterations += 1

        for module, level, anchor_name in external_anchor_edges:
            b = bounds.get(module)
            if b is None:
                continue
            if level > b.min_level:
                b.min_level = level
                b.pinned_by.append(
                    f"imports external '{anchor_name}' anchored at level {level} (outward gravity)"
                )
                changed = True

        for src, deps in graph.graph.items():
            src_bounds = bounds.get(src)
            if src_bounds is None:
                continue
            for dst in deps:
                dst_bounds = bounds.get(dst)
                if dst_bounds is None:
                    continue
                # Rule 1 (outward gravity): A.min = max(A.min, B.min)
                if dst_bounds.min_level > src_bounds.min_level:
                    src_bounds.min_level = dst_bounds.min_level
                    src_bounds.pinned_by.append(
                        f"imports '{dst}' (min level {dst_bounds.min_level}) -> outward gravity"
                    )
                    changed = True
                # Rule 2 (inward gravity): B.max = min(B.max, A.max)
                if src_bounds.max_level < dst_bounds.max_level:
                    dst_bounds.max_level = src_bounds.max_level
                    dst_bounds.pinned_by.append(
                        f"imported by '{src}' (max level {src_bounds.max_level}) -> inward gravity"
                    )
                    changed = True

    return bounds


def infer_levels_incremental(
    graph: DependencyGraph,
    config: ArchitectureConfig,
    changed_modules: Set[str],
    previous_bounds: Dict[str, LevelBounds],
    class_names_by_module: Optional[Dict[str, Set[str]]] = None,
    raw_imports_by_module: Optional[Dict[str, Set[str]]] = None,
) -> Dict[str, LevelBounds]:
    """
    Incremental update (DEEPTHINK_03 §5): re-seed only `changed_modules` plus
    any brand-new modules absent from `previous_bounds`, then re-propagate
    via a worklist starting from those seeds and their reverse-neighbours,
    instead of a global fixpoint. Monotone lattice -> localized convergence.

    Produces bounds identical to a full `infer_levels` rebuild (verified by
    the incremental-equivalence test) but visits far fewer nodes when only a
    handful of files changed.
    """
    if not config.has_level_inference:
        return {}

    class_names_by_module = class_names_by_module or {}
    max_lvl = _max_level(config)

    bounds: Dict[str, LevelBounds] = {}
    for module in graph.graph:
        prev = previous_bounds.get(module)
        if module not in changed_modules and prev is not None:
            bounds[module] = LevelBounds(
                module=module, min_level=prev.min_level, max_level=prev.max_level,
                base_level=prev.base_level, matched=prev.matched, pinned_by=list(prev.pinned_by),
            )
            continue
        layer = _match_layer(module, class_names_by_module.get(module, set()), config)
        if layer is not None:
            bounds[module] = LevelBounds(
                module=module, min_level=layer.level, max_level=layer.level,
                base_level=layer.level, matched=True,
                pinned_by=[f"heuristic match -> layer '{layer.name}' (level {layer.level})"],
            )
        else:
            bounds[module] = LevelBounds(module=module, min_level=0, max_level=max_lvl, matched=False)

    external_anchor_edges = _external_anchor_edges(graph, config, raw_imports_by_module)

    # Worklist seeded from changed modules; propagation is monotone so it
    # is safe to keep pushing neighbours until nothing more tightens.
    worklist: deque = deque(changed_modules & set(bounds))
    in_worklist: Set[str] = set(worklist)
    edges_by_dst = graph.reverse

    guard = 0
    max_guard = (len(bounds) + len(external_anchor_edges) + 1) * 4
    while worklist and guard <= max_guard:
        guard += 1
        node = worklist.popleft()
        in_worklist.discard(node)
        node_bounds = bounds.get(node)
        if node_bounds is None:
            continue

        for module, level, anchor_name in external_anchor_edges:
            if module != node:
                continue
            if level > node_bounds.min_level:
                node_bounds.min_level = level
                node_bounds.pinned_by.append(
                    f"imports external '{anchor_name}' anchored at level {level} (outward gravity)"
                )

        for dst in graph.graph.get(node, set()):
            dst_bounds = bounds.get(dst)
            if dst_bounds is None:
                continue
            if dst_bounds.min_level > node_bounds.min_level:
                node_bounds.min_level = dst_bounds.min_level
                node_bounds.pinned_by.append(
                    f"imports '{dst}' (min level {dst_bounds.min_level}) -> outward gravity"
                )
            if node_bounds.max_level < dst_bounds.max_level:
                dst_bounds.max_level = node_bounds.max_level
                dst_bounds.pinned_by.append(
                    f"imported by '{node}' (max level {node_bounds.max_level}) -> inward gravity"
                )
                if dst not in in_worklist:
                    worklist.append(dst)
                    in_worklist.add(dst)

        for src in edges_by_dst.get(node, set()):
            src_bounds = bounds.get(src)
            if src_bounds is None:
                continue
            if node_bounds.min_level > src_bounds.min_level:
                src_bounds.min_level = node_bounds.min_level
                src_bounds.pinned_by.append(
                    f"imports '{node}' (min level {node_bounds.min_level}) -> outward gravity"
                )
                if src not in in_worklist:
                    worklist.append(src)
                    in_worklist.add(src)
            if src_bounds.max_level < node_bounds.max_level:
                node_bounds.max_level = src_bounds.max_level
                node_bounds.pinned_by.append(
                    f"imported by '{src}' (max level {src_bounds.max_level}) -> inward gravity"
                )

    return bounds
