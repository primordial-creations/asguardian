"""
Heimdall Hexagonal Architecture Analyzer Service

Analyzes adherence to hexagonal (ports and adapters) architecture patterns.
Validates that domain core has no infrastructure dependencies, ports are
properly defined as abstractions, and adapters implement ports correctly.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Heimdall.Architecture.models.architecture_models import (
    AdapterDefinition,
    ArchitectureConfig,
    HexagonalReport,
    HexagonalViolation,
    HexagonalZone,
    PortDefinition,
)
from Asgard.Heimdall.Quality.utilities.file_utils import scan_directory
from Asgard.Heimdall.Architecture.services._hexagonal_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Heimdall.Architecture.services._hexagonal_validators import (
    validate_domain_isolation as _validate_domain,
    validate_dependency_direction as _validate_direction,
    detect_cross_adapter_imports as _detect_cross_adapter,
    detect_ports as _detect_ports_fn,
    detect_adapters as _detect_adapters_fn,
)


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
        return _detect_ports_fn(
            root_path, zone_assignments,
            self.config.exclude_patterns, self.config.include_extensions,
            self._path_to_module,
        )

    def _detect_adapters(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
        port_names: Set[str],
    ) -> List[AdapterDefinition]:
        """Detect adapter classes that implement ports."""
        return _detect_adapters_fn(
            root_path, zone_assignments, port_names,
            self.config.exclude_patterns, self.config.include_extensions,
            self._find_framework_imports, self._path_to_module,
        )

    def _validate_domain_isolation(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Validate that domain core has no framework/infrastructure imports."""
        return _validate_domain(
            root_path, zone_assignments,
            self.config.exclude_patterns, self.config.include_extensions,
            FRAMEWORK_IMPORTS, self._find_framework_imports,
            self._path_to_module,
        )

    def _validate_dependency_direction(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Validate that dependencies point inward (adapter->port->domain)."""
        return _validate_direction(
            root_path, zone_assignments,
            self.config.exclude_patterns, self.config.include_extensions,
            self._resolve_import_zone, self._path_to_module,
        )

    def _detect_cross_adapter_imports(
        self,
        root_path: Path,
        zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Detect adapters importing directly from other adapters."""
        return _detect_cross_adapter(
            root_path, zone_assignments,
            self.config.exclude_patterns, self.config.include_extensions,
            self._resolve_import_zone, self._path_to_module,
        )

    def _find_framework_imports(self, imports: Set[str], from_imports: Dict[str, Set[str]]) -> Set[str]:
        """Find framework/infrastructure imports in a set of imports."""
        hits: Set[str] = set()
        for imp in imports:
            if imp.split(".")[0] in FRAMEWORK_IMPORTS or imp in FRAMEWORK_IMPORTS:
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
            return _gen_json(result)
        elif format == "markdown":
            return _gen_markdown(result)
        else:
            return _gen_text(result)
