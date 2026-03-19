"""
Heimdall Cycle Detector Service

Detects circular dependencies in the codebase.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Dependencies.models.dependency_models import (
    CircularDependency,
    DependencyConfig,
    DependencySeverity,
)
import networkx as nx

from Asgard.Heimdall.Dependencies.services.import_analyzer import ImportAnalyzer


class CycleDetector:
    """
    Detects circular dependencies in Python codebases.

    Circular dependencies can cause:
    - Import errors at runtime
    - Difficult to understand code flow
    - Testing difficulties
    - Maintenance headaches
    """

    def __init__(self, config: Optional[DependencyConfig] = None):
        """Initialize the cycle detector."""
        self.config = config or DependencyConfig()
        self.import_analyzer = ImportAnalyzer(self.config)

    def detect(
        self, scan_path: Optional[Path] = None
    ) -> List[CircularDependency]:
        """
        Detect all circular dependencies in the codebase.

        Args:
            scan_path: Root path to scan

        Returns:
            List of CircularDependency objects
        """
        path = scan_path or self.config.scan_path
        modules = self.import_analyzer.analyze(path)

        # Build dependency graph
        graph = {m.module_name: m.all_dependencies for m in modules}

        return self._detect_with_networkx(graph)

    def _detect_with_networkx(
        self, graph: Dict[str, Set[str]]
    ) -> List[CircularDependency]:
        """Detect cycles using NetworkX."""
        nx_graph = nx.DiGraph()

        for module, deps in graph.items():
            for dep in deps:
                if dep in graph:  # Only internal dependencies
                    nx_graph.add_edge(module, dep)

        cycles = []

        # Find simple cycles
        try:
            simple_cycles = list(nx.simple_cycles(nx_graph))

            for cycle in simple_cycles:
                cycles.append(CircularDependency(
                    cycle=cycle,
                    severity=self._calculate_severity(len(cycle)),
                ))
        except Exception:
            # Fall back to SCC detection
            sccs = list(nx.strongly_connected_components(nx_graph))
            for scc in sccs:
                if len(scc) > 1:
                    cycles.append(CircularDependency(
                        cycle=list(scc),
                        severity=self._calculate_severity(len(scc)),
                    ))

        return cycles

    def _detect_with_dfs(
        self, graph: Dict[str, Set[str]]
    ) -> List[CircularDependency]:
        """Detect cycles using DFS (fallback when NetworkX unavailable)."""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                cycles.append(CircularDependency(
                    cycle=cycle,
                    severity=self._calculate_severity(len(cycle)),
                ))
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor in graph:  # Only internal deps
                    dfs(neighbor, path.copy())

            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        # Deduplicate cycles (same cycle can be found starting from different nodes)
        unique_cycles = []
        seen = set()

        for cycle in cycles:
            # Normalize: rotate to start with smallest element
            min_idx = cycle.cycle.index(min(cycle.cycle))
            normalized = tuple(cycle.cycle[min_idx:] + cycle.cycle[:min_idx])

            if normalized not in seen:
                seen.add(normalized)
                unique_cycles.append(cycle)

        return unique_cycles

    def _calculate_severity(self, cycle_length: int) -> DependencySeverity:
        """Calculate severity based on cycle length."""
        if cycle_length <= 2:
            return DependencySeverity.HIGH
        else:
            return DependencySeverity.CRITICAL

    def detect_file(self, file_path: Path) -> List[str]:
        """
        Check if a file is part of any circular dependency.

        Args:
            file_path: Path to the Python file

        Returns:
            List of cycle descriptions involving this file
        """
        cycles = self.detect()

        # Get module name for the file
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
        Quick check if any cycles exist.

        Args:
            scan_path: Root path to scan

        Returns:
            True if cycles exist, False otherwise
        """
        cycles = self.detect(scan_path)
        return len(cycles) > 0

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
        cycles = self.detect(scan_path)

        cycle_graph = {}

        for cycle in cycles:
            for i, module in enumerate(cycle.cycle):
                if module not in cycle_graph:
                    cycle_graph[module] = []

                # Add next module in cycle
                next_idx = (i + 1) % len(cycle.cycle)
                next_module = cycle.cycle[next_idx]
                if next_module not in cycle_graph[module]:
                    cycle_graph[module].append(next_module)

        return cycle_graph

    def suggest_breaks(
        self, scan_path: Optional[Path] = None
    ) -> List[Dict[str, str]]:
        """
        Suggest edges to remove to break cycles.

        Uses a heuristic: prefer breaking edges where the source
        has fewer dependencies.

        Args:
            scan_path: Root path to scan

        Returns:
            List of suggested edge breaks {source, target, reason}
        """
        cycles = self.detect(scan_path)
        modules = self.import_analyzer.analyze(scan_path)

        # Build dependency counts
        dep_counts = {m.module_name: len(m.all_dependencies) for m in modules}

        suggestions = []

        for cycle in cycles:
            # Find the edge with the source having fewest dependencies
            best_edge = None
            best_score = float("inf")

            for i, source in enumerate(cycle.cycle):
                target = cycle.cycle[(i + 1) % len(cycle.cycle)]
                score = dep_counts.get(source, 0)

                if score < best_score:
                    best_score = score
                    best_edge = (source, target)

            if best_edge:
                suggestions.append({
                    "source": best_edge[0],
                    "target": best_edge[1],
                    "reason": f"Source has only {best_score} dependencies",
                    "cycle": cycle.as_string,
                })

        return suggestions
