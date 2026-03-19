"""
Heimdall Layer Analyzer Service

Analyzes adherence to layered architecture patterns.
"""

import ast
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    ArchitectureConfig,
    LayerDefinition,
    LayerReport,
    LayerViolation,
    ViolationSeverity,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import get_imports
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


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
        try:
            relative = file_path.relative_to(root_path)
            parts = list(relative.parts)

            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]

            if parts[-1] == "__init__":
                parts = parts[:-1]

            if not parts:
                return None

            return ".".join(parts)
        except ValueError:
            return None

    def _analyze_file(
        self,
        file_path: Path,
        root_path: Path,
        module_layers: Dict[str, str],
        layers: List[LayerDefinition]
    ) -> List[LayerViolation]:
        """Analyze a single file for layer violations."""
        violations = []

        source = file_path.read_text(encoding="utf-8", errors="ignore")
        source_module = self._path_to_module(file_path, root_path)

        if not source_module:
            return violations

        source_layer = module_layers.get(source_module)
        if not source_layer:
            return violations

        # Get layer definition
        source_layer_def = next(
            (l for l in layers if l.name == source_layer), None
        )
        if not source_layer_def:
            return violations

        # Parse imports
        imports, from_imports = get_imports(source)

        # Check direct imports
        for imp in imports:
            target_layer = self._get_layer_for_import(imp, module_layers)
            if target_layer:
                violation = self._check_layer_violation(
                    source_module, source_layer, source_layer_def,
                    imp, target_layer,
                    file_path, 0, layers
                )
                if violation:
                    violations.append(violation)

        # Check from imports
        for module, names in from_imports.items():
            target_layer = self._get_layer_for_import(module, module_layers)
            if target_layer:
                violation = self._check_layer_violation(
                    source_module, source_layer, source_layer_def,
                    module, target_layer,
                    file_path, 0, layers
                )
                if violation:
                    violations.append(violation)

        return violations

    def _get_layer_for_import(
        self,
        import_name: str,
        module_layers: Dict[str, str]
    ) -> Optional[str]:
        """Get the layer for an imported module."""
        # Try exact match
        if import_name in module_layers:
            return module_layers[import_name]

        # Try prefix match
        for module, layer in module_layers.items():
            if module.startswith(import_name + ".") or import_name.startswith(module + "."):
                return layer

        return None

    def _check_layer_violation(
        self,
        source_module: str,
        source_layer: str,
        source_layer_def: LayerDefinition,
        target_module: str,
        target_layer: str,
        file_path: Path,
        line_number: int,
        layers: List[LayerDefinition]
    ) -> Optional[LayerViolation]:
        """Check if an import violates layer rules."""
        if source_layer == target_layer:
            return None  # Same layer is OK

        # Check if target is in allowed dependencies
        if target_layer in source_layer_def.allowed_dependencies:
            return None

        # This is a violation
        severity = self._calculate_severity(source_layer, target_layer, layers)

        return LayerViolation(
            source_module=source_module,
            source_layer=source_layer,
            target_module=target_module,
            target_layer=target_layer,
            file_path=str(file_path),
            line_number=line_number,
            message=f"Layer '{source_layer}' should not depend on '{target_layer}'",
            severity=severity,
        )

    def _calculate_severity(
        self,
        source_layer: str,
        target_layer: str,
        layers: List[LayerDefinition]
    ) -> ViolationSeverity:
        """Calculate violation severity based on layer distance."""
        layer_names = [l.name for l in layers]

        if source_layer not in layer_names or target_layer not in layer_names:
            return ViolationSeverity.MODERATE

        source_idx = layer_names.index(source_layer)
        target_idx = layer_names.index(target_layer)

        # Upward dependency (lower layer depending on higher)
        if source_idx > target_idx:
            distance = source_idx - target_idx
            if distance >= 3:
                return ViolationSeverity.CRITICAL
            elif distance >= 2:
                return ViolationSeverity.HIGH
            else:
                return ViolationSeverity.MODERATE

        # Downward but not allowed
        return ViolationSeverity.LOW

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
                    return layer.name

        return None

    def generate_report(self, result: LayerReport, format: str = "text") -> str:
        """
        Generate a formatted report.

        Args:
            result: LayerReport to format
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report string
        """
        if format == "json":
            return self._generate_json_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: LayerReport) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL LAYER ARCHITECTURE REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:        {result.scan_path}")
        lines.append(f"  Total Violations: {result.total_violations}")
        lines.append(f"  Architecture:     {'VALID' if result.is_valid else 'INVALID'}")
        lines.append("")

        # Layer definitions
        lines.append("-" * 70)
        lines.append("  LAYER DEFINITIONS")
        lines.append("-" * 70)
        lines.append("")

        for layer in result.layers:
            lines.append(f"  {layer.name}")
            lines.append(f"    Patterns: {', '.join(layer.patterns)}")
            lines.append(f"    Allowed:  {', '.join(layer.allowed_dependencies) or '(none)'}")
            lines.append("")

        # Violations
        if result.violations:
            lines.append("-" * 70)
            lines.append("  VIOLATIONS")
            lines.append("-" * 70)
            lines.append("")

            for v in result.violations:
                lines.append(f"  [{v.severity.value.upper()}] {v.message}")
                lines.append(f"    Source: {v.source_module} ({v.source_layer})")
                lines.append(f"    Target: {v.target_module} ({v.target_layer})")
                lines.append(f"    File:   {v.file_path}")
                lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, result: LayerReport) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "is_valid": result.is_valid,
            "total_violations": result.total_violations,
            "layers": [
                {
                    "name": l.name,
                    "patterns": l.patterns,
                    "allowed_dependencies": l.allowed_dependencies,
                    "description": l.description,
                }
                for l in result.layers
            ],
            "layer_assignments": result.layer_assignments,
            "violations": [
                {
                    "source_module": v.source_module,
                    "source_layer": v.source_layer,
                    "target_module": v.target_module,
                    "target_layer": v.target_layer,
                    "file_path": v.file_path,
                    "line_number": v.line_number,
                    "message": v.message,
                    "severity": v.severity.value,
                }
                for v in result.violations
            ],
        }

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: LayerReport) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall Layer Architecture Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Architecture Status:** {'Valid' if result.is_valid else 'Invalid'}")
        lines.append(f"- **Total Violations:** {result.total_violations}")
        lines.append("")

        lines.append("## Layer Definitions")
        lines.append("")
        lines.append("| Layer | Patterns | Allowed Dependencies |")
        lines.append("|-------|----------|---------------------|")

        for layer in result.layers:
            lines.append(
                f"| {layer.name} | {', '.join(layer.patterns)} | "
                f"{', '.join(layer.allowed_dependencies) or '(none)'} |"
            )

        lines.append("")

        if result.violations:
            lines.append("## Violations")
            lines.append("")
            lines.append("| Source | Target | Severity | Message |")
            lines.append("|--------|--------|----------|---------|")

            for v in result.violations:
                lines.append(
                    f"| {v.source_module} | {v.target_module} | "
                    f"{v.severity.value.upper()} | {v.message} |"
                )

            lines.append("")

        return "\n".join(lines)
