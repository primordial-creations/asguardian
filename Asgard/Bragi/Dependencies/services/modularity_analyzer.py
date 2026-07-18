"""
Heimdall Modularity Analyzer Service

Analyzes module boundaries and organization quality.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Bragi.Dependencies.models.dependency_models import (
    CentralityInfo,
    DependencyConfig,
    ModularityMetrics,
)
from Asgard.Bragi.Dependencies.services._modularity_helpers import (
    build_reverse_graph,
    detect_communities_nx,
    get_boundary_violations,
    get_coupling_report,
    get_layering_analysis,
)
from Asgard.Bragi.Dependencies.services.graph_service import DependencyGraphService


class ModularityAnalyzer:
    """
    Analyzes module organization and boundary quality.

    Modularity measures how well the codebase is organized into
    cohesive, loosely-coupled modules. High modularity indicates:
    - Good separation of concerns
    - Easy to understand and navigate
    - Changes are localized

    Consumes the shared DependencyGraphService (Plan 03 Phase B): no second
    codebase scan when the graph is already built.
    """

    def __init__(self, config: Optional[DependencyConfig] = None,
                 graph_service: Optional[DependencyGraphService] = None):
        """Initialize the modularity analyzer."""
        self.config = config or DependencyConfig()
        self.graph_service = graph_service or DependencyGraphService(self.config)
        # Kept for backward compatibility with callers that reached into it.
        self.import_analyzer = self.graph_service.import_analyzer

    def analyze(self, scan_path: Optional[Path] = None) -> ModularityMetrics:
        """
        Analyze modularity of the codebase.

        Args:
            scan_path: Root path to scan

        Returns:
            ModularityMetrics with analysis results
        """
        path = scan_path or self.config.scan_path
        modules = self.graph_service.build(path).modules

        # Calculate coupling metrics
        graph = {m.module_name: m.all_dependencies for m in modules}
        reverse = build_reverse_graph(graph)

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
        clusters, modularity_score = detect_communities_nx(graph)

        metrics.clusters = clusters
        metrics.modularity_score = modularity_score

        return metrics

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
        modules = self.graph_service.build(
            scan_path or self.config.scan_path).modules
        return get_boundary_violations(modules)

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
        modules = self.graph_service.build(path).modules
        graph = {m.module_name: m.all_dependencies for m in modules}
        reverse = build_reverse_graph(graph)
        return get_coupling_report(modules, reverse)

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
        modules = self.graph_service.build(
            scan_path or self.config.scan_path).modules
        return get_layering_analysis(modules, layers)

    def centrality(
        self, scan_path: Optional[Path] = None
    ) -> Dict[str, CentralityInfo]:
        """Centrality passthrough with afferent percentiles (Plan 03)."""
        return self.graph_service.centrality(scan_path or self.config.scan_path)
