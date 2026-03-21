"""
Heimdall Hexagonal Architecture - Port and Adapter Detection Helpers

Standalone functions for detecting ports (abstract interfaces) and adapter
classes in a hexagonal architecture codebase.
"""

import ast
from pathlib import Path
from typing import Dict, List, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    AdapterDefinition,
    HexagonalZone,
    PortDefinition,
    PortDirection,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    extract_classes,
    get_abstract_methods,
    get_class_bases,
    get_imports,
    is_abstract_class,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


def infer_port_direction(
    class_node: ast.ClassDef,
    file_path: Path,
    root_path: Path,
) -> PortDirection:
    """Infer whether a port is inbound (driving) or outbound (driven)."""
    path_str = str(file_path.relative_to(root_path)).lower()

    if any(kw in path_str for kw in ("inbound", "driving", "input")):
        return PortDirection.INBOUND
    if any(kw in path_str for kw in ("outbound", "driven", "output")):
        return PortDirection.OUTBOUND

    name_lower = class_node.name.lower()
    if any(kw in name_lower for kw in ("repository", "gateway", "client", "sender", "publisher", "store")):
        return PortDirection.OUTBOUND
    if any(kw in name_lower for kw in ("handler", "controller", "command", "query", "usecase", "use_case")):
        return PortDirection.INBOUND

    return PortDirection.OUTBOUND


def detect_ports(
    root_path: Path,
    zone_assignments: Dict[str, str],
    exclude_patterns: List[str],
    include_extensions: List[str],
    path_to_module_fn,
) -> List[PortDefinition]:
    """Detect port interfaces (ABCs) in port and domain zones."""
    ports: List[PortDefinition] = []
    port_zones = {HexagonalZone.PORT.value, HexagonalZone.DOMAIN.value}

    for file_path in scan_directory(
        root_path,
        exclude_patterns=exclude_patterns,
        include_extensions=include_extensions,
    ):
        module_name = path_to_module_fn(file_path, root_path)
        if not module_name:
            continue

        zone = zone_assignments.get(module_name)
        if zone not in port_zones:
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            classes = extract_classes(source)

            for cls in classes:
                if is_abstract_class(cls):
                    abstract_methods = get_abstract_methods(cls)
                    direction = infer_port_direction(cls, file_path, root_path)
                    ports.append(PortDefinition(
                        name=cls.name,
                        file_path=str(file_path),
                        line_number=cls.lineno,
                        direction=direction,
                        abstract_methods=abstract_methods,
                    ))
        except (SyntaxError, Exception):
            continue

    return ports


def detect_adapters(
    root_path: Path,
    zone_assignments: Dict[str, str],
    port_names: Set[str],
    exclude_patterns: List[str],
    include_extensions: List[str],
    find_framework_imports_fn,
    path_to_module_fn,
) -> List[AdapterDefinition]:
    """Detect adapter classes that implement ports."""
    adapters: List[AdapterDefinition] = []
    adapter_zones = {
        HexagonalZone.ADAPTER.value,
        HexagonalZone.INFRASTRUCTURE.value,
    }

    for file_path in scan_directory(
        root_path,
        exclude_patterns=exclude_patterns,
        include_extensions=include_extensions,
    ):
        module_name = path_to_module_fn(file_path, root_path)
        if not module_name:
            continue

        zone = zone_assignments.get(module_name)
        if zone not in adapter_zones:
            continue

        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            classes = extract_classes(source)
            imports, from_imports = get_imports(source)

            framework_hits = find_framework_imports_fn(imports, from_imports)

            for cls in classes:
                bases = get_class_bases(cls)
                for base in bases:
                    base_simple = base.split(".")[-1]
                    if base_simple in port_names:
                        adapters.append(AdapterDefinition(
                            name=cls.name,
                            file_path=str(file_path),
                            line_number=cls.lineno,
                            implements_port=base_simple,
                            zone=HexagonalZone(zone),
                            framework_imports=list(framework_hits),
                        ))
                        break
        except (SyntaxError, Exception):
            continue

    return adapters
