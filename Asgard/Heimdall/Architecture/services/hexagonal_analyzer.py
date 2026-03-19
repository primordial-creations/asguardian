"""
Heimdall Hexagonal Architecture Analyzer Service

Analyzes adherence to hexagonal (ports and adapters) architecture patterns.
Validates that domain core has no infrastructure dependencies, ports are
properly defined as abstractions, and adapters implement ports correctly.
"""

import ast
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from Asgard.Heimdall.Architecture.models.architecture_models import (
    AdapterDefinition,
    ArchitectureConfig,
    HexagonalReport,
    HexagonalViolation,
    HexagonalZone,
    PortDefinition,
    PortDirection,
    ViolationSeverity,
)
from Asgard.Heimdall.Architecture.utilities.ast_utils import (
    extract_classes,
    get_abstract_methods,
    get_class_bases,
    get_imports,
    is_abstract_class,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory


# Framework imports that should never appear in the domain core
FRAMEWORK_IMPORTS = frozenset({
    "fastapi", "flask", "django", "starlette",
    "sqlalchemy", "sqlmodel", "databases", "asyncpg", "psycopg2", "pymysql",
    "redis", "aioredis", "celery", "dramatiq",
    "httpx", "aiohttp", "requests",
    "pika", "aio_pika", "kombu",
    "boto3", "botocore",
    "google.cloud", "azure",
    "grpc", "grpcio",
    "websockets", "socketio",
    "uvicorn", "gunicorn", "hypercorn",
})


class HexagonalAnalyzer:
    """
    Analyzes hexagonal (ports and adapters) architecture compliance.

    Validates:
    - Domain core isolation (no framework/infra imports)
    - Ports defined as abstract base classes
    - Adapters implement ports
    - Dependency direction flows inward (adapters -> ports -> domain)
    - No cross-adapter communication
    """

    # Default zone patterns for file/directory matching
    DEFAULT_ZONE_PATTERNS: Dict[HexagonalZone, List[str]] = {
        HexagonalZone.DOMAIN: [
            "domain", "core", "entities", "value_objects",
        ],
        HexagonalZone.PORT: [
            "ports", "interfaces", "abstractions",
        ],
        HexagonalZone.ADAPTER: [
            "adapters", "adapter", "driven", "driving",
        ],
        HexagonalZone.INFRASTRUCTURE: [
            "infrastructure", "infra", "persistence", "external",
            "repositories", "gateways", "clients",
        ],
    }

    def __init__(self, config: Optional[ArchitectureConfig] = None):
        """Initialize the hexagonal analyzer."""
        self.config = config or ArchitectureConfig()
        self.zone_patterns: Dict[HexagonalZone, List[str]] = dict(
            self.DEFAULT_ZONE_PATTERNS
        )

    def set_zone_patterns(
        self, patterns: Dict[HexagonalZone, List[str]]
    ) -> None:
        """Override zone detection patterns."""
        self.zone_patterns = patterns

    def analyze(self, scan_path: Optional[Path] = None) -> HexagonalReport:
        """
        Analyze hexagonal architecture compliance.

        Args:
            scan_path: Root path to scan

        Returns:
            HexagonalReport with violations, ports, and adapters
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = HexagonalReport(scan_path=str(path))

        # Step 1: Assign files to zones
        zone_assignments = self._assign_zones(path)
        report.zone_assignments = zone_assignments

        # Step 2: Detect ports (ABCs in port/domain zones)
        ports = self._detect_ports(path, zone_assignments)
        report.ports = ports
        port_names = {p.name for p in ports}

        # Step 3: Detect adapters (classes implementing ports)
        adapters = self._detect_adapters(path, zone_assignments, port_names)
        report.adapters = adapters

        # Step 4: Validate domain isolation
        domain_violations = self._validate_domain_isolation(
            path, zone_assignments
        )
        for v in domain_violations:
            report.add_violation(v)

        # Step 5: Validate dependency direction
        direction_violations = self._validate_dependency_direction(
            path, zone_assignments
        )
        for v in direction_violations:
            report.add_violation(v)

        # Step 6: Detect cross-adapter imports
        cross_violations = self._detect_cross_adapter_imports(
            path, zone_assignments
        )
        for v in cross_violations:
            report.add_violation(v)

        report.scan_duration_seconds = time.time() - start_time
        return report

    def _assign_zones(self, root_path: Path) -> Dict[str, str]:
        """Assign files to hexagonal zones based on path patterns."""
        assignments: Dict[str, str] = {}

        for file_path in scan_directory(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            module_name = self._path_to_module(file_path, root_path)
            if not module_name:
                continue

            parts = module_name.lower().split(".")

            assigned = False
            for zone, patterns in self.zone_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in parts:
                        assignments[module_name] = zone.value
                        assigned = True
                        break
                if assigned:
                    break

            if not assigned:
                assignments[module_name] = HexagonalZone.UNASSIGNED.value

        return assignments

    def _detect_ports(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
    ) -> List[PortDefinition]:
        """Detect port interfaces (ABCs) in port and domain zones."""
        ports: List[PortDefinition] = []
        port_zones = {HexagonalZone.PORT.value, HexagonalZone.DOMAIN.value}

        for file_path in scan_directory(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            module_name = self._path_to_module(file_path, root_path)
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
                        direction = self._infer_port_direction(
                            cls, file_path, root_path
                        )
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

    def _infer_port_direction(
        self,
        class_node: ast.ClassDef,
        file_path: Path,
        root_path: Path,
    ) -> PortDirection:
        """Infer whether a port is inbound (driving) or outbound (driven)."""
        path_str = str(file_path.relative_to(root_path)).lower()

        # Path-based heuristics
        if any(kw in path_str for kw in ("inbound", "driving", "input")):
            return PortDirection.INBOUND
        if any(kw in path_str for kw in ("outbound", "driven", "output")):
            return PortDirection.OUTBOUND

        # Name-based heuristics
        name_lower = class_node.name.lower()
        if any(kw in name_lower for kw in ("repository", "gateway", "client", "sender", "publisher", "store")):
            return PortDirection.OUTBOUND
        if any(kw in name_lower for kw in ("handler", "controller", "command", "query", "usecase", "use_case")):
            return PortDirection.INBOUND

        return PortDirection.OUTBOUND

    def _detect_adapters(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
        port_names: Set[str],
    ) -> List[AdapterDefinition]:
        """Detect adapter classes that implement ports."""
        adapters: List[AdapterDefinition] = []
        adapter_zones = {
            HexagonalZone.ADAPTER.value,
            HexagonalZone.INFRASTRUCTURE.value,
        }

        for file_path in scan_directory(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            module_name = self._path_to_module(file_path, root_path)
            if not module_name:
                continue

            zone = zone_assignments.get(module_name)
            if zone not in adapter_zones:
                continue

            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                classes = extract_classes(source)
                imports, from_imports = get_imports(source)

                # Collect all framework imports in this file
                framework_hits = self._find_framework_imports(
                    imports, from_imports
                )

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

    def _validate_domain_isolation(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Validate that domain core has no framework/infrastructure imports."""
        violations: List[HexagonalViolation] = []
        domain_zones = {HexagonalZone.DOMAIN.value, HexagonalZone.PORT.value}

        for file_path in scan_directory(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            module_name = self._path_to_module(file_path, root_path)
            if not module_name:
                continue

            zone = zone_assignments.get(module_name)
            if zone not in domain_zones:
                continue

            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                imports, from_imports = get_imports(source)
                framework_hits = self._find_framework_imports(
                    imports, from_imports
                )

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

    def _validate_dependency_direction(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Validate that dependencies point inward (adapter->port->domain)."""
        violations: List[HexagonalViolation] = []

        # Zone hierarchy: domain is innermost, infrastructure outermost
        # Allowed direction: outer -> inner
        zone_rank = {
            HexagonalZone.DOMAIN.value: 0,
            HexagonalZone.PORT.value: 1,
            HexagonalZone.ADAPTER.value: 2,
            HexagonalZone.INFRASTRUCTURE.value: 2,
        }

        for file_path in scan_directory(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            module_name = self._path_to_module(file_path, root_path)
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

                all_imports = set(imports)
                all_imports.update(from_imports.keys())

                for imp in all_imports:
                    target_zone = self._resolve_import_zone(
                        imp, zone_assignments
                    )
                    if not target_zone or target_zone == HexagonalZone.UNASSIGNED.value:
                        continue
                    if target_zone == source_zone:
                        continue

                    target_rank = zone_rank.get(target_zone)
                    if target_rank is None:
                        continue

                    # Inner zone importing from outer zone = violation
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

    def _detect_cross_adapter_imports(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Detect adapters importing directly from other adapters."""
        violations: List[HexagonalViolation] = []
        adapter_zones = {
            HexagonalZone.ADAPTER.value,
            HexagonalZone.INFRASTRUCTURE.value,
        }

        # Group adapter modules by their parent package
        adapter_groups: Dict[str, str] = {}
        for module, zone in zone_assignments.items():
            if zone in adapter_zones:
                # Use the first two segments as the adapter identity
                parts = module.split(".")
                group = parts[0] if len(parts) <= 2 else ".".join(parts[:2])
                adapter_groups[module] = group

        for file_path in scan_directory(
            root_path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            module_name = self._path_to_module(file_path, root_path)
            if not module_name:
                continue

            source_zone = zone_assignments.get(module_name)
            if source_zone not in adapter_zones:
                continue

            source_group = adapter_groups.get(module_name)

            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
                imports, from_imports = get_imports(source)

                all_imports = set(imports)
                all_imports.update(from_imports.keys())

                for imp in all_imports:
                    target_zone = self._resolve_import_zone(
                        imp, zone_assignments
                    )
                    if target_zone not in adapter_zones:
                        continue

                    # Find which adapter group the target belongs to
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

    def _find_framework_imports(
        self,
        imports: Set[str],
        from_imports: Dict[str, Set[str]],
    ) -> Set[str]:
        """Find framework/infrastructure imports in a set of imports."""
        hits: Set[str] = set()

        for imp in imports:
            root_pkg = imp.split(".")[0]
            if root_pkg in FRAMEWORK_IMPORTS or imp in FRAMEWORK_IMPORTS:
                hits.add(imp)

        for module in from_imports:
            root_pkg = module.split(".")[0] if module else ""
            if root_pkg in FRAMEWORK_IMPORTS or module in FRAMEWORK_IMPORTS:
                hits.add(module)

        return hits

    def _resolve_import_zone(
        self,
        import_name: str,
        zone_assignments: Dict[str, str],
    ) -> Optional[str]:
        """Resolve an import to its zone."""
        if import_name in zone_assignments:
            return zone_assignments[import_name]

        for module, zone in zone_assignments.items():
            if module.startswith(import_name + ".") or import_name.startswith(module + "."):
                return zone

        return None

    def _path_to_module(
        self, file_path: Path, root_path: Path
    ) -> Optional[str]:
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

    def generate_report(
        self, result: HexagonalReport, format: str = "text"
    ) -> str:
        """Generate a formatted report."""
        if format == "json":
            return self._generate_json_report(result)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: HexagonalReport) -> str:
        """Generate text format report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  HEIMDALL HEXAGONAL ARCHITECTURE REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  Scan Path:        {result.scan_path}")
        lines.append(f"  Total Violations: {result.total_violations}")
        lines.append(f"  Architecture:     {'VALID' if result.is_valid else 'INVALID'}")
        lines.append(f"  Ports Found:      {len(result.ports)}")
        lines.append(f"  Adapters Found:   {len(result.adapters)}")
        lines.append("")

        # Zone assignments summary
        zone_counts: Dict[str, int] = {}
        for zone in result.zone_assignments.values():
            zone_counts[zone] = zone_counts.get(zone, 0) + 1

        lines.append("-" * 70)
        lines.append("  ZONE ASSIGNMENTS")
        lines.append("-" * 70)
        lines.append("")
        for zone, count in sorted(zone_counts.items()):
            lines.append(f"  {zone:20s} {count} modules")
        lines.append("")

        # Ports
        if result.ports:
            lines.append("-" * 70)
            lines.append("  PORTS (Interfaces)")
            lines.append("-" * 70)
            lines.append("")
            for port in result.ports:
                lines.append(f"  {port.name} [{port.direction.value}]")
                lines.append(f"    File:    {port.file_path}")
                if port.abstract_methods:
                    lines.append(f"    Methods: {', '.join(port.abstract_methods)}")
                lines.append("")

        # Adapters
        if result.adapters:
            lines.append("-" * 70)
            lines.append("  ADAPTERS")
            lines.append("-" * 70)
            lines.append("")
            for adapter in result.adapters:
                lines.append(f"  {adapter.name} -> {adapter.implements_port}")
                lines.append(f"    File: {adapter.file_path}")
                if adapter.framework_imports:
                    lines.append(f"    Frameworks: {', '.join(adapter.framework_imports)}")
                lines.append("")

        # Violations
        if result.violations:
            lines.append("-" * 70)
            lines.append("  VIOLATIONS")
            lines.append("-" * 70)
            lines.append("")
            for v in result.violations:
                lines.append(f"  [{v.severity.value.upper()}] {v.message}")
                lines.append(f"    File:  {v.file_path}")
                lines.append(f"    Zones: {v.source_zone.value} -> {v.target_zone.value}")
                lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def _generate_json_report(self, result: HexagonalReport) -> str:
        """Generate JSON format report."""
        output = {
            "scan_path": result.scan_path,
            "scanned_at": result.scanned_at.isoformat(),
            "is_valid": result.is_valid,
            "total_violations": result.total_violations,
            "ports": [
                {
                    "name": p.name,
                    "file_path": p.file_path,
                    "direction": p.direction.value,
                    "abstract_methods": p.abstract_methods,
                }
                for p in result.ports
            ],
            "adapters": [
                {
                    "name": a.name,
                    "file_path": a.file_path,
                    "implements_port": a.implements_port,
                    "zone": a.zone.value,
                    "framework_imports": a.framework_imports,
                }
                for a in result.adapters
            ],
            "zone_assignments": result.zone_assignments,
            "violations": [
                {
                    "file_path": v.file_path,
                    "source_zone": v.source_zone.value,
                    "target_zone": v.target_zone.value,
                    "class_name": v.class_name,
                    "message": v.message,
                    "severity": v.severity.value,
                }
                for v in result.violations
            ],
        }

        return json.dumps(output, indent=2)

    def _generate_markdown_report(self, result: HexagonalReport) -> str:
        """Generate Markdown format report."""
        lines = []
        lines.append("# Heimdall Hexagonal Architecture Report")
        lines.append("")
        lines.append(f"- **Scan Path:** `{result.scan_path}`")
        lines.append(f"- **Status:** {'Valid' if result.is_valid else 'Invalid'}")
        lines.append(f"- **Total Violations:** {result.total_violations}")
        lines.append(f"- **Ports:** {len(result.ports)}")
        lines.append(f"- **Adapters:** {len(result.adapters)}")
        lines.append("")

        if result.ports:
            lines.append("## Ports")
            lines.append("")
            lines.append("| Name | Direction | Methods | File |")
            lines.append("|------|-----------|---------|------|")
            for p in result.ports:
                methods = ", ".join(p.abstract_methods[:3])
                if len(p.abstract_methods) > 3:
                    methods += f" (+{len(p.abstract_methods) - 3})"
                lines.append(
                    f"| {p.name} | {p.direction.value} | "
                    f"{methods} | {p.file_path} |"
                )
            lines.append("")

        if result.adapters:
            lines.append("## Adapters")
            lines.append("")
            lines.append("| Name | Implements | Zone | Frameworks |")
            lines.append("|------|-----------|------|------------|")
            for a in result.adapters:
                lines.append(
                    f"| {a.name} | {a.implements_port} | "
                    f"{a.zone.value} | "
                    f"{', '.join(a.framework_imports) or '(none)'} |"
                )
            lines.append("")

        if result.violations:
            lines.append("## Violations")
            lines.append("")
            lines.append("| Severity | Source Zone | Target Zone | Message |")
            lines.append("|----------|------------|-------------|---------|")
            for v in result.violations:
                lines.append(
                    f"| {v.severity.value.upper()} | "
                    f"{v.source_zone.value} | {v.target_zone.value} | "
                    f"{v.message} |"
                )
            lines.append("")

        return "\n".join(lines)
