"""
Heimdall Dependency Analyzer Service

Unified analyzer that combines all dependency analysis features.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from Asgard.Heimdall.Dependencies.models.dependency_models import (
    CircularDependency,
    DependencyConfig,
    DependencyReport,
    DependencySeverity,
    ModularityMetrics,
    ModuleDependencies,
)
from Asgard.Heimdall.Dependencies.services._dependency_reporter import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)
from Asgard.Heimdall.Dependencies.services.import_analyzer import ImportAnalyzer
from Asgard.Heimdall.Dependencies.services.graph_builder import GraphBuilder
from Asgard.Heimdall.Dependencies.services.cycle_detector import CycleDetector
from Asgard.Heimdall.Dependencies.services.modularity_analyzer import ModularityAnalyzer


class DependencyAnalyzer:
    """
    Unified dependency analyzer combining all analysis features.

    Provides comprehensive dependency analysis including:
    - Import mapping
    - Dependency graph construction
    - Circular dependency detection
    - Modularity analysis
    """

    def __init__(self, config: Optional[DependencyConfig] = None):
        """Initialize the dependency analyzer."""
        self.config = config or DependencyConfig()

        self.import_analyzer = ImportAnalyzer(self.config)
        self.graph_builder = GraphBuilder(self.config)
        self.cycle_detector = CycleDetector(self.config)
        self.modularity_analyzer = ModularityAnalyzer(self.config)

    def analyze(self, scan_path: Optional[Path] = None) -> DependencyReport:
        """
        Perform complete dependency analysis.

        Args:
            scan_path: Root path to scan

        Returns:
            DependencyReport with all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        modules = self.import_analyzer.analyze(path)
        cycles = self.cycle_detector.detect(path)
        modularity = self.modularity_analyzer.analyze(path)

        graph = {m.module_name: m.all_dependencies for m in modules}
        reverse = self._build_reverse_graph(graph)

        for module in modules:
            module.afferent_coupling = len(reverse.get(module.module_name, set()))
            if module.afferent_coupling + module.efferent_coupling > 0:
                module.instability = module.efferent_coupling / (
                    module.afferent_coupling + module.efferent_coupling
                )

        report = DependencyReport(
            scan_path=str(path),
        )

        for module in modules:
            report.add_module(module)

            if module.efferent_coupling > self.config.max_dependencies:
                module.severity = DependencySeverity.HIGH
                report.high_coupling_modules.append(module)
            elif module.afferent_coupling > self.config.max_dependents:
                module.severity = DependencySeverity.MODERATE
                report.high_coupling_modules.append(module)

        for cycle in cycles:
            report.add_cycle(cycle)

        report.modularity = modularity
        report.scan_duration_seconds = time.time() - start_time

        return report

    def _build_reverse_graph(
        self, graph: Dict[str, set]
    ) -> Dict[str, set]:
        """Build a reverse dependency graph."""
        reverse: Dict[str, set] = {module: set() for module in graph}

        for module, deps in graph.items():
            for dep in deps:
                if dep in reverse:
                    reverse[dep].add(module)

        return reverse

    def analyze_file(self, file_path: Path) -> Optional[ModuleDependencies]:
        """
        Analyze dependencies for a single file.

        Args:
            file_path: Path to the Python file

        Returns:
            ModuleDependencies for the file
        """
        return self.import_analyzer.analyze_file(file_path)

    def get_cycles(self, scan_path: Optional[Path] = None) -> List[CircularDependency]:
        """
        Get circular dependencies only.

        Args:
            scan_path: Root path to scan

        Returns:
            List of circular dependencies
        """
        return cast(list[Any], self.cycle_detector.detect(scan_path))

    def has_cycles(self, scan_path: Optional[Path] = None) -> bool:
        """
        Quick check for circular dependencies.

        Args:
            scan_path: Root path to scan

        Returns:
            True if cycles exist
        """
        return cast(bool, self.cycle_detector.has_cycles(scan_path))

    def get_modularity(self, scan_path: Optional[Path] = None) -> ModularityMetrics:
        """
        Get modularity metrics only.

        Args:
            scan_path: Root path to scan

        Returns:
            ModularityMetrics
        """
        return self.modularity_analyzer.analyze(scan_path)

    def generate_report(self, result: DependencyReport, format: str = "text") -> str:
        """
        Generate a formatted report.

        Args:
            result: DependencyReport to format
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report string
        """
        if format == "json":
            return generate_json_report(result)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
