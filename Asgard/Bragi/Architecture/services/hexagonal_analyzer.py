"""
Heimdall Hexagonal Architecture Analyzer Service

Analyzes adherence to hexagonal (ports and adapters) architecture patterns.
Validates that domain core has no infrastructure dependencies, ports are
properly defined as abstractions, and adapters implement ports correctly.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from Asgard.Bragi.Architecture.models.architecture_models import (
    AdapterDefinition,
    ArchitectureConfig,
    HexagonalReport,
    HexagonalViolation,
    HexagonalZone,
    PortDefinition,
)
from Asgard.Bragi.Architecture.services._architecture_config import (
    ArchitectureConfig as LayerArchitectureConfig,
    default_architecture_config,
)
from Asgard.Bragi.Quality.utilities.file_utils import scan_directory
from Asgard.Bragi.Architecture.services._hexagonal_reporter import (
    generate_text_report as _gen_text,
    generate_json_report as _gen_json,
    generate_markdown_report as _gen_markdown,
)
from Asgard.Bragi.Architecture.services._generic_hexagonal_checks import (
    check_domain_imports_infrastructure,
    check_missing_port_reference,
)
from Asgard.Bragi.Architecture.services._hexagonal_anti_patterns import (
    detect_anemic_domain_models as _detect_anemic_domain_models,
    detect_infrastructure_leaks as _detect_infrastructure_leaks,
)
from Asgard.Shared.common.language_registry import EXTENSION_TO_LANGUAGE
from Asgard.Bragi.Architecture.services._hexagonal_validators import (
    validate_domain_isolation as _validate_domain,
    validate_dependency_direction as _validate_direction,
    detect_cross_adapter_imports as _detect_cross_adapter,
    detect_ports as _detect_ports_fn,
    detect_adapters as _detect_adapters_fn,
)
from Asgard.Bragi.Architecture.graph.service import ArchGraphService
from Asgard.Bragi.Dependencies.models.dependency_models import DependencyConfig


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

    def __init__(
        self,
        config: Optional[ArchitectureConfig] = None,
        layer_config: Optional[LayerArchitectureConfig] = None,
    ):
        """Initialize the hexagonal analyzer."""
        self.config = config or ArchitectureConfig()
        self.layer_config: LayerArchitectureConfig = layer_config or default_architecture_config()
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

        # Step 6b: Anti-pattern detectors (plan 03 §4) — Anemic Domain
        # Model and Infrastructure Leak, the two gaps left after Missing
        # Ports (already covered by _hexagonal_validators/_generic_hexagonal_checks).
        for v in self._detect_anemic_domain_models(path, zone_assignments):
            report.add_violation(v)
        for v in self._detect_infrastructure_leaks(path, zone_assignments):
            report.add_violation(v)

        # Step 7: Import-graph layer inference (Plan 03) — only when the
        # active architecture.yml (or the zero-config default) declares
        # `level:` on at least one layer; otherwise stays glob-only.
        if self.layer_config.has_level_inference:
            for v in self._analyze_inferred_layers(path):
                report.add_violation(v)

        report.scan_duration_seconds = time.time() - start_time
        return report

    # ------------------------------------------------------------------
    # Import-graph layer inference (Plan 03): CSP level propagation,
    # drift-paradox detection, module-granularity cycles, fan-out.
    # ------------------------------------------------------------------

    def _arch_graph_service(self, root_path: Path) -> ArchGraphService:
        return ArchGraphService(
            config=self.layer_config,
            dep_config=DependencyConfig(scan_path=root_path),
        )

    def _analyze_inferred_layers(self, root_path: Path) -> List[HexagonalViolation]:
        """Layer + drift + module-cycle + fan-out violations from the
        import-graph CSP, expressed as `HexagonalViolation` so they slot
        into the existing report/reporter pipeline without new models."""
        violations: List[HexagonalViolation] = []
        service = self._arch_graph_service(root_path)

        bounds = service.infer(root_path)
        assigned = {m: b.assigned_level for m, b in bounds.items()}
        graph = service.graph_service.build(root_path)

        # Local layer-direction violations: edge A->B requires
        # assigned_level(A) >= assigned_level(B).
        for src, deps in graph.graph.items():
            src_level = assigned.get(src)
            if src_level is None:
                continue
            for dst in deps:
                dst_level = assigned.get(dst)
                if dst_level is None:
                    continue
                if src_level < dst_level:
                    violations.append(HexagonalViolation(
                        file_path=src,
                        line_number=0,
                        source_zone=HexagonalZone.UNASSIGNED,
                        target_zone=HexagonalZone.UNASSIGNED,
                        class_name="",
                        message=(
                            f"Layer violation: '{src}' (level {src_level}) imports "
                            f"'{dst}' (level {dst_level}) — dependencies must point "
                            f"inward/laterally (Level(A) >= Level(B))."
                        ),
                    ))

        for drift in service.drift_violations(root_path):
            violations.append(HexagonalViolation(
                file_path=drift.module,
                line_number=0,
                source_zone=HexagonalZone.UNASSIGNED,
                target_zone=HexagonalZone.UNASSIGNED,
                class_name="",
                message=f"Architecture drift: {drift.message}",
            ))

        for cycle in service.module_cycles(root_path):
            violations.append(HexagonalViolation(
                file_path=cycle.members[0],
                line_number=0,
                source_zone=HexagonalZone.UNASSIGNED,
                target_zone=HexagonalZone.UNASSIGNED,
                class_name="",
                message=f"Module-level cycle: {' -> '.join(cycle.members + [cycle.members[0]])}",
            ))

        for fan_out in service.fan_out_violations(root_path):
            violations.append(HexagonalViolation(
                file_path=fan_out.module,
                line_number=0,
                source_zone=HexagonalZone.UNASSIGNED,
                target_zone=HexagonalZone.UNASSIGNED,
                class_name="",
                message=(
                    f"Module '{fan_out.module}' fans out to {fan_out.fan_out} modules "
                    f"(limit {fan_out.limit}): {', '.join(fan_out.targets)}"
                ),
            ))

        return violations

    def explain_file(self, file_path: str, scan_path: Optional[Path] = None) -> str:
        """`heimdall arch layers <path> --explain <file>`: prints a file's
        inferred bounds and which imports pinned them."""
        path = Path(scan_path or self.config.scan_path).resolve()
        return self._arch_graph_service(path).explain(file_path, path)

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

    def _detect_anemic_domain_models(
        self, root_path: Path, zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Domain-zone classes that hold data but expose no behaviour."""
        return _detect_anemic_domain_models(
            root_path, zone_assignments,
            self.config.exclude_patterns, self.config.include_extensions,
            self._path_to_module,
        )

    def _detect_infrastructure_leaks(
        self, root_path: Path, zone_assignments: Dict[str, str],
    ) -> List[HexagonalViolation]:
        """Domain-zone classes bound to a persistence/web framework via
        base class, decorator, or ORM field declaration."""
        return _detect_infrastructure_leaks(
            root_path, zone_assignments,
            self.config.exclude_patterns, self.config.include_extensions,
            self._path_to_module,
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

    def _get_layer_for_path(self, path_str: str) -> Optional[str]:
        """Return the layer name for a given path string using layer_config patterns."""
        import fnmatch
        for layer in self.layer_config.layers:
            for pattern in layer.path_patterns:
                if fnmatch.fnmatch(path_str, pattern):
                    return layer.name
        return None

    def _check_layer_violations(
        self,
        file_path: str,
        imports: Set[str],
    ) -> List[HexagonalViolation]:
        """Check imports against layer_config forbidden_imports rules."""
        violations: List[HexagonalViolation] = []
        source_layer_name = self._get_layer_for_path(file_path)
        if source_layer_name is None:
            return violations

        layer_map = {lc.name: lc for lc in self.layer_config.layers}
        source_layer = layer_map.get(source_layer_name)
        if source_layer is None:
            return violations

        for imp in imports:
            import_layer_name = self._get_layer_for_path(imp)
            if import_layer_name and import_layer_name in source_layer.forbidden_imports:
                violations.append(
                    HexagonalViolation(
                        file_path=file_path,
                        line_number=0,
                        source_zone=HexagonalZone.UNASSIGNED,
                        target_zone=HexagonalZone.UNASSIGNED,
                        class_name="",
                        message=(
                            f"Layer '{source_layer_name}' must not import "
                            f"from layer '{import_layer_name}' (imported: {imp})"
                        ),
                    )
                )
        return violations

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

    # ------------------------------------------------------------------
    # Multi-language generic analysis
    # ------------------------------------------------------------------

    def analyze_file_generic(
        self,
        file_path: Path,
        language: str,
    ) -> List[HexagonalViolation]:
        """
        Run generic regex-based hexagonal checks on a single non-Python file.

        Args:
            file_path: Path to the source file.
            language: Language identifier (e.g. "java", "go", "typescript").

        Returns:
            List of HexagonalViolation found in the file.
        """
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []

        path_str = str(file_path)
        violations: List[HexagonalViolation] = []
        violations.extend(check_domain_imports_infrastructure(path_str, lines, language))
        violations.extend(check_missing_port_reference(path_str, lines, language))
        return violations

    def analyze_multilang(
        self,
        scan_path: Optional[Path] = None,
        extensions: Optional[List[str]] = None,
    ) -> HexagonalReport:
        """
        Scan non-Python source files for hexagonal architecture violations.

        Args:
            scan_path: Root directory to scan (defaults to config.scan_path).
            extensions: File extensions to include.

        Returns:
            HexagonalReport with all found violations.
        """
        import time as _time
        from Asgard.Bragi.Quality.utilities.file_utils import scan_directory

        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        target_extensions = extensions or [
            ".java", ".cs", ".go", ".rb", ".js", ".ts", ".jsx", ".tsx", ".php", ".kt",
        ]

        start_time = _time.time()
        report = HexagonalReport(scan_path=str(path))

        for file_path in scan_directory(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=target_extensions,
        ):
            language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
            if not language or language == "python":
                continue

            for v in self.analyze_file_generic(file_path, language):
                report.add_violation(v)

        report.scan_duration_seconds = _time.time() - start_time
        return report

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
