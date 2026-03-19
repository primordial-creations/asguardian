"""
Heimdall Modularity Analyzer Service

Analyzes module boundaries and organization quality.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Heimdall.Dependencies.models.dependency_models import (
    DependencyConfig,
    ModularityMetrics,
    ModuleDependencies,
)
import networkx as nx

from Asgard.Heimdall.Dependencies.services.import_analyzer import ImportAnalyzer


class ModularityAnalyzer:
    """
    Analyzes module organization and boundary quality.

    Modularity measures how well the codebase is organized into
    cohesive, loosely-coupled modules. High modularity indicates:
    - Good separation of concerns
    - Easy to understand and navigate
    - Changes are localized
    """

    def __init__(self, config: Optional[DependencyConfig] = None):
        """Initialize the modularity analyzer."""
        self.config = config or DependencyConfig()
        self.import_analyzer = ImportAnalyzer(self.config)

    def analyze(self, scan_path: Optional[Path] = None) -> ModularityMetrics:
        """
        Analyze modularity of the codebase.

        Args:
            scan_path: Root path to scan

        Returns:
            ModularityMetrics with analysis results
        """
        path = scan_path or self.config.scan_path
        modules = self.import_analyzer.analyze(path)

        # Calculate coupling metrics
        graph = {m.module_name: m.all_dependencies for m in modules}
        reverse = self._build_reverse_graph(graph)

        # Update modules with afferent coupling
        for module in modules:
            module.afferent_coupling = len(reverse.get(module.module_name, set()))
            if module.afferent_coupling + module.efferent_coupling > 0:
                module.instability = module.efferent_coupling / (
                    module.afferent_coupling + module.efferent_coupling
                )

        # Calculate aggregates
        metrics = ModularityMetrics(
            total_modules=len(modules),
            total_dependencies=sum(len(m.all_dependencies) for m in modules),
        )

        if modules:
            metrics.average_afferent = sum(m.afferent_coupling for m in modules) / len(modules)
            metrics.average_efferent = sum(m.efferent_coupling for m in modules) / len(modules)
            metrics.max_afferent = max(m.afferent_coupling for m in modules)
            metrics.max_efferent = max(m.efferent_coupling for m in modules)

        # Identify stable and unstable modules
        for module in modules:
            if module.instability < 0.2:
                metrics.stable_modules.append(module.module_name)
            elif module.instability > 0.8:
                metrics.unstable_modules.append(module.module_name)

        # Detect communities/clusters
        clusters, modularity_score = self._detect_communities_nx(graph)

        metrics.clusters = clusters
        metrics.modularity_score = modularity_score

        return metrics

    def _build_reverse_graph(
        self, graph: Dict[str, Set[str]]
    ) -> Dict[str, Set[str]]:
        """Build a reverse dependency graph."""
        reverse = {module: set() for module in graph}

        for module, deps in graph.items():
            for dep in deps:
                if dep in reverse:
                    reverse[dep].add(module)

        return reverse

    def _detect_communities_nx(
        self, graph: Dict[str, Set[str]]
    ) -> Tuple[List[Set[str]], float]:
        """Detect communities using NetworkX."""
        nx_graph = nx.DiGraph()

        for module, deps in graph.items():
            for dep in deps:
                if dep in graph:
                    nx_graph.add_edge(module, dep)

        # Convert to undirected for community detection
        undirected = nx_graph.to_undirected()

        try:
            # Use greedy modularity communities
            communities = list(
                nx.algorithms.community.greedy_modularity_communities(undirected)
            )

            # Calculate modularity score
            modularity = nx.algorithms.community.modularity(
                undirected, communities
            )

            return [set(c) for c in communities], modularity
        except Exception:
            # Fallback
            return self._detect_communities_simple(graph), 0.0

    def _detect_communities_simple(
        self, graph: Dict[str, Set[str]]
    ) -> List[Set[str]]:
        """Detect communities using simple connected components."""
        # Build undirected adjacency
        undirected = {module: set() for module in graph}

        for module, deps in graph.items():
            for dep in deps:
                if dep in undirected:
                    undirected[module].add(dep)
                    undirected[dep].add(module)

        # Find connected components
        visited = set()
        components = []

        def dfs(node: str, component: Set[str]) -> None:
            if node in visited:
                return
            visited.add(node)
            component.add(node)
            for neighbor in undirected.get(node, set()):
                dfs(neighbor, component)

        for node in undirected:
            if node not in visited:
                component = set()
                dfs(node, component)
                if component:
                    components.append(component)

        return components

    def get_boundary_violations(
        self, scan_path: Optional[Path] = None
    ) -> List[Dict[str, str]]:
        """
        Detect potential module boundary violations.

        A boundary violation occurs when:
        - A submodule depends on a sibling's internal module
        - A module reaches deeply into another's internals

        Args:
            scan_path: Root path to scan

        Returns:
            List of violation descriptions
        """
        modules = self.import_analyzer.analyze(scan_path)
        violations = []

        for module in modules:
            # Get the top-level package
            parts = module.module_name.split(".")
            if len(parts) < 2:
                continue

            top_level = parts[0]

            for dep in module.all_dependencies:
                dep_parts = dep.split(".")
                if len(dep_parts) < 2:
                    continue

                dep_top = dep_parts[0]

                # Check for deep internal access
                if dep_top != top_level and len(dep_parts) > 2:
                    violations.append({
                        "source": module.module_name,
                        "target": dep,
                        "type": "deep_internal_access",
                        "message": f"Accessing internal module {dep} from {module.module_name}",
                    })

        return violations

    def get_coupling_report(
        self, scan_path: Optional[Path] = None
    ) -> List[Dict]:
        """
        Get a coupling report for all modules.

        Args:
            scan_path: Root path to scan

        Returns:
            List of module coupling information
        """
        path = scan_path or self.config.scan_path
        modules = self.import_analyzer.analyze(path)
        graph = {m.module_name: m.all_dependencies for m in modules}
        reverse = self._build_reverse_graph(graph)

        report = []
        for module in modules:
            afferent = len(reverse.get(module.module_name, set()))
            efferent = len(module.all_dependencies)
            instability = efferent / (afferent + efferent) if (afferent + efferent) > 0 else 0

            report.append({
                "module": module.module_name,
                "afferent_coupling": afferent,
                "efferent_coupling": efferent,
                "instability": round(instability, 2),
                "dependents": list(reverse.get(module.module_name, set())),
                "dependencies": list(module.all_dependencies),
            })

        # Sort by instability (most unstable first)
        report.sort(key=lambda x: x["instability"], reverse=True)

        return report

    def get_layering_analysis(
        self, scan_path: Optional[Path] = None,
        layers: Optional[Dict[str, List[str]]] = None
    ) -> Dict:
        """
        Analyze adherence to a layered architecture.

        Args:
            scan_path: Root path to scan
            layers: Dict mapping layer names to module patterns
                   Higher layers should not depend on lower ones
                   e.g., {"presentation": ["views", "handlers"],
                          "business": ["services"],
                          "data": ["models", "repositories"]}

        Returns:
            Analysis results including violations
        """
        if not layers:
            # Default layers
            layers = {
                "routers": ["routers"],
                "services": ["services"],
                "models": ["models"],
            }

        modules = self.import_analyzer.analyze(scan_path)
        graph = {m.module_name: m.all_dependencies for m in modules}

        # Assign modules to layers
        layer_assignments = {}
        layer_order = list(layers.keys())

        for module_name in graph:
            parts = module_name.split(".")
            for layer_name, patterns in layers.items():
                for pattern in patterns:
                    if pattern in parts:
                        layer_assignments[module_name] = layer_name
                        break
                if module_name in layer_assignments:
                    break

        # Check for violations
        violations = []
        for module_name, deps in graph.items():
            source_layer = layer_assignments.get(module_name)
            if not source_layer:
                continue

            source_idx = layer_order.index(source_layer)

            for dep in deps:
                target_layer = layer_assignments.get(dep)
                if not target_layer:
                    continue

                target_idx = layer_order.index(target_layer)

                # Higher layers (lower index) should not depend on lower layers (higher index)
                if target_idx < source_idx:
                    violations.append({
                        "source": module_name,
                        "source_layer": source_layer,
                        "target": dep,
                        "target_layer": target_layer,
                        "message": f"{source_layer} should not depend on {target_layer}",
                    })

        return {
            "layers": layers,
            "layer_assignments": layer_assignments,
            "violations": violations,
            "is_valid": len(violations) == 0,
        }
