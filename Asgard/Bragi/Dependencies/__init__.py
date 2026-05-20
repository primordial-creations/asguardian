"""
Heimdall Dependencies - Dependency Analysis and Cycle Detection

This module provides dependency analysis tools including:
- Import mapping and dependency extraction
- Dependency graph construction with NetworkX
- Circular dependency detection
- Modularity and boundary analysis

Usage:
    python -m Heimdall deps analyze ./src
    python -m Heimdall deps cycles ./src
    python -m Heimdall deps graph ./src --output deps.png
    python -m Heimdall deps modularity ./src

Programmatic Usage:
    from Heimdall.Dependencies import DependencyAnalyzer, DependencyConfig
    from Heimdall.Dependencies import CycleDetector, ImportAnalyzer

    # Full dependency analysis
    config = DependencyConfig(scan_path="./src")
    analyzer = DependencyAnalyzer(config)
    result = analyzer.analyze()

    if result.has_cycles:
        for cycle in result.circular_dependencies:
            print(f"Cycle: {' -> '.join(cycle)}")

    # Just cycle detection
    detector = CycleDetector()
    cycles = detector.detect(Path("./src"))
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Bragi.Dependencies.models.dependency_models import (
    CircularDependency,
    DependencyConfig,
    DependencyInfo,
    DependencyReport,
    DependencySeverity,
    DependencyType,
    ModularityMetrics,
    ModuleDependencies,
)
from Asgard.Bragi.Dependencies.models.sbom_models import (
    ComponentType,
    SBOMComponent,
    SBOMConfig,
    SBOMDocument,
    SBOMFormat,
)
from Asgard.Bragi.Dependencies.services.import_analyzer import ImportAnalyzer
from Asgard.Bragi.Dependencies.services.graph_builder import GraphBuilder
from Asgard.Bragi.Dependencies.services.cycle_detector import CycleDetector
from Asgard.Bragi.Dependencies.services.modularity_analyzer import ModularityAnalyzer
from Asgard.Bragi.Dependencies.services.dependency_analyzer import DependencyAnalyzer
from Asgard.Bragi.Dependencies.services.sbom_generator import SBOMGenerator

__all__ = [
    # Models
    "CircularDependency",
    "DependencyConfig",
    "DependencyInfo",
    "DependencyReport",
    "DependencySeverity",
    "DependencyType",
    "ModularityMetrics",
    "ModuleDependencies",
    # SBOM models
    "ComponentType",
    "SBOMComponent",
    "SBOMConfig",
    "SBOMDocument",
    "SBOMFormat",
    # Services
    "CycleDetector",
    "DependencyAnalyzer",
    "GraphBuilder",
    "ImportAnalyzer",
    "ModularityAnalyzer",
    "SBOMGenerator",
]
