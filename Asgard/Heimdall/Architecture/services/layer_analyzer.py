"""
Heimdall Layer Analyzer Service

Analyzes adherence to layered architecture patterns.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, cast

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    LayerDefinition,
    LayerReport,
    LayerViolation,
    ViolationSeverity,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory
from Asgard.Heimdall.Architecture.services._layer_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Heimdall.Architecture.services._layer_checks import (
    path_to_module as _path_to_module_fn,
    get_layer_for_import as _get_layer_for_import,
    calculate_severity as _calculate_severity,
    check_layer_violation as _check_layer_violation,
    analyze_file as _analyze_file_fn,
)


class LayerAnalyzer:
    """
    Analyzes layered architecture compliance.

    Validates that dependencies follow the proper direction
    in layered architectures (e.g., presentation -> business -> data).
    """

    # Default layer definitions
    DEFAULT_LAYERS = [
        LayerDefinition(
            name="routers",
            patterns=["routers", "router", "endpoints", "api"],
            allowed_dependencies=["services", "models", "utilities", "dependencies"],
            description="API layer - handles HTTP requests",
        ),
        LayerDefinition(
            name="services",
            patterns=["services", "service"],
            allowed_dependencies=["models", "utilities", "repositories"],
            description="Business logic layer",
        ),
        LayerDefinition(
            name="repositories",
            patterns=["repositories", "repository", "repos"],
            allowed_dependencies=["models", "utilities"],
            description="Data access layer",
        ),
        LayerDefinition(
            name="models",
            patterns=["models", "model", "schemas", "entities"],
            allowed_dependencies=["utilities"],
            description="Domain models layer",
        ),
        LayerDefinition(
            name="utilities",
            patterns=["utilities", "utils", "helpers", "common"],
            allowed_dependencies=[],
            description="Utility functions layer",
        ),
    ]

    def __init__(self, config: Optional[ArchitectureConfig] = None):
        """Initialize the layer analyzer."""
        self.config = config or ArchitectureConfig()
        self.layers: List[LayerDefinition] = []

    def set_layers(self, layers: List[LayerDefinition]) -> None:
        """
        Set custom layer definitions.

        Args:
            layers: List of layer definitions in order (highest to lowest)
        """
        self.layers = layers

    def analyze(self, scan_path: Optional[Path] = None) -> LayerReport:
        """
        Analyze layer architecture compliance.

        Args:
            scan_path: Root path to scan

        Returns:
            LayerReport with violations
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        # Use custom layers or defaults
        layers = self.layers if self.layers else self.DEFAULT_LAYERS
        report = LayerReport(scan_path=str(path), layers=layers)

        # Build module map
        module_layers = self._assign_layers(path, layers)
        report.layer_assignments = module_layers

        # Analyze each file
        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                violations = self._analyze_file(file_path, path, module_layers, layers)
                for v in violations:
                    report.add_violation(v)
            except (SyntaxError, Exception):
                continue

        report.scan_duration_seconds = time.time() - start_time
        return report

    def _assign_layers(
        self,
        root_path: Path,
        layers: List[LayerDefinition]
    ) -> Dict[str, str]:
        """Assign modules to layers based on patterns."""
        assignments = {}

        for file_path in scan_directory(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            try:
                module_name = self._path_to_module(file_path, root_path)
                if not module_name:
                    continue

                # Check which layer this belongs to
                parts = module_name.lower().split(".")

                for layer in layers:
                    for pattern in layer.patterns:
                        if pattern.lower() in parts:
                            assignments[module_name] = layer.name
                            break
                    if module_name in assignments:
                        break

            except Exception:
                continue

        return assignments

    def _path_to_module(self, file_path: Path, root_path: Path) -> Optional[str]:
        """Convert file path to module name."""
        return _path_to_module_fn(file_path, root_path)

    def _analyze_file(
        self,
        file_path: Path,
        root_path: Path,
        module_layers: Dict[str, str],
        layers: List[LayerDefinition],
    ) -> List[LayerViolation]:
        """Analyze a single file for layer violations."""
        return _analyze_file_fn(file_path, root_path, module_layers, layers)

    def _get_layer_for_import(self, import_name: str, module_layers: Dict[str, str]) -> Optional[str]:
        """Get the layer for an imported module."""
        return _get_layer_for_import(import_name, module_layers)

    def _check_layer_violation(
        self,
        source_module: str,
        source_layer: str,
        source_layer_def: LayerDefinition,
        target_module: str,
        target_layer: str,
        file_path: Path,
        line_number: int,
        layers: List[LayerDefinition],
    ) -> Optional[LayerViolation]:
        """Check if an import violates layer rules."""
        return _check_layer_violation(
            source_module, source_layer, source_layer_def,
            target_module, target_layer, file_path, line_number, layers
        )

    def _calculate_severity(
        self, source_layer: str, target_layer: str, layers: List[LayerDefinition]
    ) -> ViolationSeverity:
        """Calculate violation severity based on layer distance."""
        return _calculate_severity(source_layer, target_layer, layers)

    def get_layer_summary(
        self,
        scan_path: Optional[Path] = None
    ) -> Dict[str, Dict]:
        """
        Get a summary of layer assignments and dependencies.

        Args:
            scan_path: Root path to scan

        Returns:
            Dict with layer information
        """
        path = scan_path or self.config.scan_path
        layers = self.layers if self.layers else self.DEFAULT_LAYERS

        module_layers = self._assign_layers(path, layers)

        summary = {}
        for layer in layers:
            modules_in_layer = [
                m for m, l in module_layers.items()
                if l == layer.name
            ]
            summary[layer.name] = {
                "description": layer.description,
                "patterns": layer.patterns,
                "allowed_dependencies": layer.allowed_dependencies,
                "module_count": len(modules_in_layer),
                "modules": modules_in_layer,
            }

        return summary

    def suggest_layer_assignment(
        self,
        module_name: str
    ) -> Optional[str]:
        """
        Suggest a layer for a module based on patterns.

        Args:
            module_name: Module name to analyze

        Returns:
            Suggested layer name or None
        """
        layers = self.layers if self.layers else self.DEFAULT_LAYERS
        parts = module_name.lower().split(".")

        for layer in layers:
            for pattern in layer.patterns:
                if pattern.lower() in parts:
                    return cast(str, layer.name)

        return None

    def generate_report(self, result: LayerReport, format: str = "text") -> str:
        """Generate a formatted report."""
        if format == "json":
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        else:
            return _gen_text(result)
