"""
Heimdall Cycle Detector Service

Detects circular dependencies via SCC condensation (Plan 03 Phase B).

`nx.simple_cycles` over the whole graph is exponential on tangled codebases
(DEEPTHINK_09); this detector reduces to strongly connected components first,
enumerates simple cycles only inside small SCCs (display), and reports large
SCCs as a single component with minimum-weight feedback-edge break
suggestions. Severity follows the *reach* of the SCC (member LOC + external
afferent coupling), not cycle length.
"""

from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Bragi.Dependencies.models.dependency_models import (
    CircularDependency,
    DependencyConfig,
)
from Asgard.Bragi.Dependencies.services.graph_service import (
    MAX_SCC_FOR_CYCLE_ENUMERATION,
    DependencyGraphService,
)


class CycleDetector:
    """
    Detects circular dependencies in Python codebases.

    Circular dependencies can cause:
    - Import errors at runtime
    - Difficult to understand code flow
    - Testing difficulties
    - Maintenance headaches

    Public API preserved: detect / has_cycles / suggest_breaks /
    detect_file / get_cycle_graph.
    """

    def __init__(self, config: Optional[DependencyConfig] = None,
                 graph_service: Optional[DependencyGraphService] = None):
        """Initialize the cycle detector (optionally sharing a graph service)."""
        self.config = config or DependencyConfig()
        self.graph_service = graph_service or DependencyGraphService(self.config)
        # Kept for backward compatibility with callers that reached into it.
        self.import_analyzer = self.graph_service.import_analyzer

    def detect(
        self, scan_path: Optional[Path] = None
    ) -> List[CircularDependency]:
        """
        Detect all circular dependencies in the codebase.

        Small SCCs (<= 12 modules) are expanded into their simple cycles for
        display; larger SCCs are reported as one component. Severity is the
        SCC's reach-based severity in both cases.

        Args:
            scan_path: Root path to scan

        Returns:
            List of CircularDependency objects
        """
        path = scan_path or self.config.scan_path
        graph = self.graph_service.build(path)
        sccs = self.graph_service.sccs(path)

        cycles: List[CircularDependency] = []
        for scc in sccs:
            if scc.size <= MAX_SCC_FOR_CYCLE_ENUMERATION:
                enumerated = self.graph_service.enumerate_cycles(graph, scc)
                for cycle in enumerated:
                    cycles.append(CircularDependency(
                        cycle=cycle,
                        severity=scc.severity,
                    ))
                if enumerated:
                    continue
            cycles.append(CircularDependency(
                cycle=list(scc.members),
                severity=scc.severity,
            ))
        return cycles

    def detect_file(self, file_path: Path) -> List[str]:
        """
        Check if a file is part of any circular dependency.

        Args:
            file_path: Path to the Python file

        Returns:
            List of cycle descriptions involving this file
        """
        cycles = self.detect()

        path = Path(file_path).resolve()
        root = self.config.scan_path

        try:
            relative = path.relative_to(root)
            parts = list(relative.parts)
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            if parts[-1] == "__init__":
                parts = parts[:-1]
            module_name = ".".join(parts)
        except ValueError:
            return []

        involved = []
        for cycle in cycles:
            if module_name in cycle.cycle:
                involved.append(cycle.as_string)

        return involved

    def has_cycles(self, scan_path: Optional[Path] = None) -> bool:
        """
        Quick check if any cycles exist (SCC pass only — no enumeration).

        Args:
            scan_path: Root path to scan

        Returns:
            True if cycles exist, False otherwise
        """
        return len(self.graph_service.sccs(scan_path or self.config.scan_path)) > 0

    def get_cycle_graph(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, List[str]]:
        """
        Get a graph of just the modules involved in cycles.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict mapping modules in cycles to their cycle neighbors
        """
        path = scan_path or self.config.scan_path
        graph = self.graph_service.build(path)
        cycle_graph: Dict[str, List[str]] = {}
        for scc in self.graph_service.sccs(path):
            member_set = set(scc.members)
            for module in scc.members:
                neighbors = sorted(
                    dst for dst in graph.graph.get(module, set())
                    if dst in member_set
                )
                if neighbors:
                    cycle_graph.setdefault(module, [])
                    for dst in neighbors:
                        if dst not in cycle_graph[module]:
                            cycle_graph[module].append(dst)
        return cycle_graph

    def suggest_breaks(
        self, scan_path: Optional[Path] = None
    ) -> List[Dict[str, str]]:
        """
        Suggest edges to remove to break cycles.

        Weighted (Plan 03): targets the minimum-weight feedback edge, where
        edge weight = imported-symbol count x (1 + source afferent coupling) —
        never the most-used edge just because its source has few dependencies.

        Args:
            scan_path: Root path to scan

        Returns:
            List of suggested edge breaks {source, target, reason, cycle}
        """
        path = scan_path or self.config.scan_path
        suggestions: List[Dict[str, str]] = []
        for scc in self.graph_service.sccs(path):
            for edge_break in self.graph_service.break_suggestions(scc, path):
                suggestions.append({
                    "source": edge_break.source,
                    "target": edge_break.target,
                    "reason": edge_break.reason,
                    "cycle": " -> ".join(scc.members + [scc.members[0]]),
                })
        return suggestions
