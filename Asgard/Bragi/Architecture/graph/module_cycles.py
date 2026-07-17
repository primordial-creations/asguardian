"""
Module-granularity cycle detection (DEEPTHINK_03 §4B, Heimdall Plan 03).

File-level cycles are noisy: mutually recursive types living in the same
directory are benign. Architectural cycles live at *module* (directory)
granularity. This collapses the file-level import graph already built by
`Dependencies/services/graph_service.py` down to directories and runs
Tarjan SCC (via networkx) on the condensed graph — no re-parsing, no edit
to `graph_service.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

import networkx as nx

from Asgard.Bragi.Dependencies.services.graph_service import DependencyGraph


@dataclass
class ModuleCycle:
    """A strongly-connected component of directories (size >= 2)."""

    members: List[str]                    # directory ("module_id") names
    file_members: Dict[str, List[str]] = field(default_factory=dict)  # module_id -> files in it
    internal_edges: int = 0

    @property
    def size(self) -> int:
        return len(self.members)


def module_id(dotted_module: str) -> str:
    """Directory-granularity module id: the dotted path minus its last
    segment (the file/leaf module). Top-level modules collapse to ''."""
    parts = dotted_module.split(".")
    return ".".join(parts[:-1])


def detect_module_cycles(graph: DependencyGraph) -> List[ModuleCycle]:
    """Collapse the file graph to directories and run Tarjan SCC.

    A directory-level self-loop (two files in the same directory importing
    each other) is NOT reported — that is the "mutually recursive types in
    one directory are benign" case Plan 03 explicitly excludes.
    """
    dir_of: Dict[str, str] = {m: module_id(m) for m in graph.graph}
    condensed = nx.DiGraph()
    condensed.add_nodes_from(sorted(set(dir_of.values())))

    for src, deps in graph.graph.items():
        src_dir = dir_of[src]
        for dst in deps:
            dst_dir = dir_of.get(dst)
            if dst_dir is None or dst_dir == src_dir:
                continue
            condensed.add_edge(src_dir, dst_dir)

    cycles: List[ModuleCycle] = []
    for component in nx.strongly_connected_components(condensed):
        if len(component) < 2:
            continue
        members = sorted(component)
        file_members: Dict[str, List[str]] = {mid: [] for mid in members}
        for module, mid in dir_of.items():
            if mid in file_members:
                file_members[mid].append(module)
        for mid in file_members:
            file_members[mid].sort()
        internal_edges = sum(
            1 for u, v in condensed.edges(members) if u in component and v in component
        )
        cycles.append(ModuleCycle(
            members=members, file_members=file_members, internal_edges=internal_edges,
        ))

    cycles.sort(key=lambda c: (-c.size, c.members))
    return cycles
