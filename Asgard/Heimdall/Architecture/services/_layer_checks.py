"""
Heimdall Layer Analyzer Check Helpers

File analysis and violation check helpers extracted from LayerAnalyzer.
"""

from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Architecture.models.architecture_models import (
    LayerDefinition,
    LayerViolation,
    ViolationSeverity,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import get_imports


def path_to_module(file_path: Path, root_path: Path) -> Optional[str]:
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


def get_layer_for_import(import_name: str, module_layers: Dict[str, str]) -> Optional[str]:
    """Get the layer for an imported module."""
    if import_name in module_layers:
        return module_layers[import_name]
    for module, layer in module_layers.items():
        if module.startswith(import_name + ".") or import_name.startswith(module + "."):
            return layer
    return None


def calculate_severity(
    source_layer: str,
    target_layer: str,
    layers: List[LayerDefinition],
) -> ViolationSeverity:
    """Calculate violation severity based on layer distance."""
    layer_names = [l.name for l in layers]
    if source_layer not in layer_names or target_layer not in layer_names:
        return ViolationSeverity.MODERATE

    source_idx = layer_names.index(source_layer)
    target_idx = layer_names.index(target_layer)

    if source_idx > target_idx:
        distance = source_idx - target_idx
        if distance >= 3:
            return ViolationSeverity.CRITICAL
        elif distance >= 2:
            return ViolationSeverity.HIGH
        else:
            return ViolationSeverity.MODERATE

    return ViolationSeverity.LOW


def check_layer_violation(
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
    if source_layer == target_layer:
        return None
    if target_layer in source_layer_def.allowed_dependencies:
        return None

    severity = calculate_severity(source_layer, target_layer, layers)
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


def analyze_file(
    file_path: Path,
    root_path: Path,
    module_layers: Dict[str, str],
    layers: List[LayerDefinition],
) -> List[LayerViolation]:
    """Analyze a single file for layer violations."""
    violations: List[LayerViolation] = []

    source = file_path.read_text(encoding="utf-8", errors="ignore")
    source_module = path_to_module(file_path, root_path)

    if not source_module:
        return violations

    source_layer = module_layers.get(source_module)
    if not source_layer:
        return violations

    source_layer_def = next((l for l in layers if l.name == source_layer), None)
    if not source_layer_def:
        return violations

    imports, from_imports = get_imports(source)

    for imp in imports:
        target_layer = get_layer_for_import(imp, module_layers)
        if target_layer:
            violation = check_layer_violation(
                source_module, source_layer, source_layer_def,
                imp, target_layer, file_path, 0, layers
            )
            if violation:
                violations.append(violation)

    for module, names in from_imports.items():
        target_layer = get_layer_for_import(module, module_layers)
        if target_layer:
            violation = check_layer_violation(
                source_module, source_layer, source_layer_def,
                module, target_layer, file_path, 0, layers
            )
            if violation:
                violations.append(violation)

    return violations
