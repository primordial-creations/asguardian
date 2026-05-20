"""
Heimdall Dependencies Models

Data models for dependency analysis including:
- Import/dependency tracking
- Circular dependency detection
- Modularity metrics
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class DependencySeverity(str, Enum):
    """Severity levels for dependency issues."""
    CRITICAL = "critical"    # Circular dependency
    HIGH = "high"            # High coupling
    MODERATE = "moderate"    # Notable concern
    LOW = "low"              # Minor issue
    INFO = "info"            # Informational


class DependencyType(str, Enum):
    """Types of dependencies."""
    IMPORT = "import"              # import X
    FROM_IMPORT = "from_import"    # from X import Y
    INHERITANCE = "inheritance"    # class A(B)
    COMPOSITION = "composition"    # self.x = X()
    CALL = "call"                  # X.method()
    TYPE_HINT = "type_hint"        # def f(x: X)


@dataclass
class DependencyConfig:
    """Configuration for dependency analysis."""
    scan_path: Path = field(default_factory=lambda: Path("."))

    # Options
    include_tests: bool = False
    include_external: bool = False  # Include stdlib/third-party
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".pytest_cache", ".mypy_cache", "dist", "build",
    ])
    include_extensions: List[str] = field(default_factory=lambda: [".py"])
    output_format: str = "text"
    verbose: bool = False

    # Thresholds
    max_dependencies: int = 10       # Max outgoing dependencies per module
    max_dependents: int = 15         # Max incoming dependencies per module

    def __post_init__(self):
        if isinstance(self.scan_path, str):
            self.scan_path = Path(self.scan_path)


@dataclass
class DependencyInfo:
    """Information about a single dependency."""
    source: str                      # Module that has the dependency
    target: str                      # Module being depended on
    dependency_type: DependencyType
    line_number: int = 0
    import_name: str = ""            # What was imported (for from imports)

    @property
    def key(self) -> str:
        """Unique key for this dependency."""
        return f"{self.source}->{self.target}"


@dataclass
class ModuleDependencies:
    """Dependencies for a single module/file."""
    module_name: str                 # Module name (dotted path)
    file_path: str
    relative_path: str

    # Dependencies
    imports: Set[str] = field(default_factory=set)           # Direct imports
    from_imports: Dict[str, Set[str]] = field(default_factory=dict)  # from X import Y
    all_dependencies: Set[str] = field(default_factory=set)   # All modules depended on

    # Coupling metrics
    afferent_coupling: int = 0       # Ca - modules that depend on this
    efferent_coupling: int = 0       # Ce - modules this depends on
    instability: float = 0.0         # I = Ce / (Ca + Ce)

    # Dependency details
    dependency_list: List[DependencyInfo] = field(default_factory=list)

    # Issues
    severity: DependencySeverity = DependencySeverity.INFO

    @property
    def total_dependencies(self) -> int:
        """Total number of dependencies."""
        return len(self.all_dependencies)

    def add_dependency(self, dep: DependencyInfo) -> None:
        """Add a dependency."""
        self.dependency_list.append(dep)
        self.all_dependencies.add(dep.target)
        self.efferent_coupling = len(self.all_dependencies)


@dataclass
class CircularDependency:
    """Represents a circular dependency."""
    cycle: List[str]                 # Modules in the cycle
    cycle_length: int = 0
    severity: DependencySeverity = DependencySeverity.CRITICAL

    def __post_init__(self):
        self.cycle_length = len(self.cycle)

    @property
    def as_string(self) -> str:
        """String representation of the cycle."""
        return " -> ".join(self.cycle + [self.cycle[0]])


@dataclass
class ModularityMetrics:
    """Metrics about module boundaries and organization."""
    total_modules: int = 0
    total_dependencies: int = 0

    # Coupling
    average_afferent: float = 0.0
    average_efferent: float = 0.0
    max_afferent: int = 0
    max_efferent: int = 0

    # Clusters (groups of tightly coupled modules)
    clusters: List[Set[str]] = field(default_factory=list)
    modularity_score: float = 0.0    # 0-1, higher is better

    # Stability
    stable_modules: List[str] = field(default_factory=list)    # I < 0.2
    unstable_modules: List[str] = field(default_factory=list)  # I > 0.8


@dataclass
class DependencyReport:
    """Complete dependency analysis report."""
    scan_path: str
    scanned_at: datetime = field(default_factory=datetime.now)
    scan_duration_seconds: float = 0.0

    # Module analyses
    modules: List[ModuleDependencies] = field(default_factory=list)

    # All dependencies
    all_dependencies: List[DependencyInfo] = field(default_factory=list)

    # Circular dependencies
    circular_dependencies: List[CircularDependency] = field(default_factory=list)

    # Modularity
    modularity: ModularityMetrics = field(default_factory=ModularityMetrics)

    # Aggregates
    total_modules: int = 0
    total_dependencies: int = 0
    total_cycles: int = 0

    # Modules with issues
    high_coupling_modules: List[ModuleDependencies] = field(default_factory=list)

    @property
    def has_cycles(self) -> bool:
        """Check if any circular dependencies exist."""
        return len(self.circular_dependencies) > 0

    @property
    def has_issues(self) -> bool:
        """Check if any dependency issues exist."""
        return self.has_cycles or len(self.high_coupling_modules) > 0

    def add_module(self, module: ModuleDependencies) -> None:
        """Add a module analysis."""
        self.modules.append(module)
        self.all_dependencies.extend(module.dependency_list)
        self.total_modules = len(self.modules)
        self.total_dependencies = len(self.all_dependencies)

    def add_cycle(self, cycle: CircularDependency) -> None:
        """Add a circular dependency."""
        self.circular_dependencies.append(cycle)
        self.total_cycles = len(self.circular_dependencies)

    def get_module(self, name: str) -> Optional[ModuleDependencies]:
        """Get a module by name."""
        for m in self.modules:
            if m.module_name == name:
                return m
        return None

    def get_dependents(self, module_name: str) -> List[str]:
        """Get modules that depend on the given module."""
        dependents = []
        for dep in self.all_dependencies:
            if dep.target == module_name:
                if dep.source not in dependents:
                    dependents.append(dep.source)
        return dependents

    def get_dependencies(self, module_name: str) -> List[str]:
        """Get modules that the given module depends on."""
        module = self.get_module(module_name)
        if module:
            return list(module.all_dependencies)
        return []

    def get_dependency_chain(
        self, from_module: str, to_module: str
    ) -> Optional[List[str]]:
        """Find a path from one module to another."""
        # BFS to find shortest path
        if from_module == to_module:
            return [from_module]

        visited = {from_module}
        queue = [[from_module]]

        while queue:
            path = queue.pop(0)
            current = path[-1]

            module = self.get_module(current)
            if not module:
                continue

            for dep in module.all_dependencies:
                if dep == to_module:
                    return path + [dep]

                if dep not in visited:
                    visited.add(dep)
                    queue.append(path + [dep])

        return None
