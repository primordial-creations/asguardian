"""
Heimdall Hexagonal Architecture - Rule Validation Helpers

Standalone functions for validating hexagonal architecture rules:
domain isolation, dependency direction, and cross-adapter import detection.
"""

from pathlib import Path
from typing import Dict, List, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    HexagonalViolation,
    HexagonalZone,
    ViolationSeverity,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import get_imports
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


def validate_domain_isolation(
    root_path: Path,
    zone_assignments: Dict[str, str],
    exclude_patterns: List[str],
    include_extensions: List[str],
    framework_imports: frozenset,
    find_framework_imports_fn,
    path_to_module_fn,
) -> List[HexagonalViolation]:
    """Validate that domain core has no framework/infrastructure imports."""
    violations: List[HexagonalViolation] = []
    domain_zones = {HexagonalZone.DOMAIN.value, HexagonalZone.PORT.value}

    for file_path in scan_directory(
        root_path,
        exclude_patterns=exclude_patterns,
        include_extensions=include_extensions,
    ):
        module_name = path_to_module_fn(file_path, root_path)
        if not module_name:
            continue

        zone = zone_assignments.get(module_name)
        if zone not in domain_zones:
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            imports, from_imports = get_imports(source)
            framework_hits = find_framework_imports_fn(imports, from_imports)

            for fw_import in framework_hits:
                violations.append(HexagonalViolation(
                    file_path=str(file_path),
                    line_number=0,
                    source_zone=HexagonalZone(zone),
                    target_zone=HexagonalZone.INFRASTRUCTURE,
                    class_name=module_name,
                    message=(
                        f"Domain/port zone imports framework package "
                        f"'{fw_import}' -- domain must remain "
                        f"infrastructure-agnostic"
                    ),
                    severity=ViolationSeverity.CRITICAL,
                ))
        except (SyntaxError, Exception):
            continue

    return violations


def validate_dependency_direction(
    root_path: Path,
    zone_assignments: Dict[str, str],
    exclude_patterns: List[str],
    include_extensions: List[str],
    resolve_import_zone_fn,
    path_to_module_fn,
) -> List[HexagonalViolation]:
    """Validate that dependencies point inward (adapter->port->domain)."""
    violations: List[HexagonalViolation] = []

    zone_rank = {
        HexagonalZone.DOMAIN.value: 0,
        HexagonalZone.PORT.value: 1,
        HexagonalZone.ADAPTER.value: 2,
        HexagonalZone.INFRASTRUCTURE.value: 2,
    }

    for file_path in scan_directory(
        root_path,
        exclude_patterns=exclude_patterns,
        include_extensions=include_extensions,
    ):
        module_name = path_to_module_fn(file_path, root_path)
        if not module_name:
            continue

        source_zone = zone_assignments.get(module_name)
        if not source_zone or source_zone == HexagonalZone.UNASSIGNED.value:
            continue

        source_rank = zone_rank.get(source_zone)
        if source_rank is None:
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            imports, from_imports = get_imports(source)

            all_imports: Set[str] = set(imports)
            all_imports.update(from_imports.keys())

            for imp in all_imports:
                target_zone = resolve_import_zone_fn(imp, zone_assignments)
                if not target_zone or target_zone == HexagonalZone.UNASSIGNED.value:
                    continue
                if target_zone == source_zone:
                    continue

                target_rank = zone_rank.get(target_zone)
                if target_rank is None:
                    continue

                if source_rank < target_rank:
                    violations.append(HexagonalViolation(
                        file_path=str(file_path),
                        line_number=0,
                        source_zone=HexagonalZone(source_zone),
                        target_zone=HexagonalZone(target_zone),
                        class_name=module_name,
                        message=(
                            f"Inner zone '{source_zone}' depends on "
                            f"outer zone '{target_zone}' via import "
                            f"'{imp}' -- dependencies must point inward"
                        ),
                        severity=(
                            ViolationSeverity.CRITICAL
                            if source_zone == HexagonalZone.DOMAIN.value
                            else ViolationSeverity.HIGH
                        ),
                    ))
        except (SyntaxError, Exception):
            continue

    return violations


def detect_cross_adapter_imports(
    root_path: Path,
    zone_assignments: Dict[str, str],
    exclude_patterns: List[str],
    include_extensions: List[str],
    resolve_import_zone_fn,
    path_to_module_fn,
) -> List[HexagonalViolation]:
    """Detect adapters importing directly from other adapters."""
    violations: List[HexagonalViolation] = []
    adapter_zones = {
        HexagonalZone.ADAPTER.value,
        HexagonalZone.INFRASTRUCTURE.value,
    }

    adapter_groups: Dict[str, str] = {}
    for module, zone in zone_assignments.items():
        if zone in adapter_zones:
            parts = module.split(".")
            group = parts[0] if len(parts) <= 2 else ".".join(parts[:2])
            adapter_groups[module] = group

    for file_path in scan_directory(
        root_path,
        exclude_patterns=exclude_patterns,
        include_extensions=include_extensions,
    ):
        module_name = path_to_module_fn(file_path, root_path)
        if not module_name:
            continue

        source_zone = zone_assignments.get(module_name)
        if source_zone not in adapter_zones:
            continue

        source_group = adapter_groups.get(module_name)

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            imports, from_imports = get_imports(source)

            all_imports: Set[str] = set(imports)
            all_imports.update(from_imports.keys())

            for imp in all_imports:
                target_zone = resolve_import_zone_fn(imp, zone_assignments)
                if target_zone not in adapter_zones:
                    continue

                target_group = None
                for mod, grp in adapter_groups.items():
                    if mod.startswith(imp) or imp.startswith(mod):
                        target_group = grp
                        break

                if target_group and source_group and target_group != source_group:
                    violations.append(HexagonalViolation(
                        file_path=str(file_path),
                        line_number=0,
                        source_zone=HexagonalZone(source_zone),
                        target_zone=HexagonalZone(target_zone),
                        class_name=module_name,
                        message=(
                            f"Adapter '{source_group}' imports from "
                            f"adapter '{target_group}' -- adapters "
                            f"must communicate through ports"
                        ),
                        severity=ViolationSeverity.HIGH,
                    ))
        except (SyntaxError, Exception):
            continue

    return violations
