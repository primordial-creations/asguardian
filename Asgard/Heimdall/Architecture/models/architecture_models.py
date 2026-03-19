"""
Heimdall Architecture Models

Data models for architecture analysis including SOLID validation,
layer compliance, and pattern detection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class SOLIDPrinciple(Enum):
    """SOLID principles."""

    SRP = "single_responsibility"
    OCP = "open_closed"
    LSP = "liskov_substitution"
    ISP = "interface_segregation"
    DIP = "dependency_inversion"


class ViolationSeverity(Enum):
    """Severity levels for violations."""

    INFO = "info"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class HexagonalZone(Enum):
    """Hexagonal architecture zones."""

    DOMAIN = "domain"
    PORT = "port"
    ADAPTER = "adapter"
    INFRASTRUCTURE = "infrastructure"
    UNASSIGNED = "unassigned"


class PortDirection(Enum):
    """Port direction in hexagonal architecture."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class PatternType(Enum):
    """Common design patterns."""

    # Creational
    SINGLETON = "singleton"
    FACTORY = "factory"
    ABSTRACT_FACTORY = "abstract_factory"
    BUILDER = "builder"
    PROTOTYPE = "prototype"

    # Structural
    ADAPTER = "adapter"
    BRIDGE = "bridge"
    COMPOSITE = "composite"
    DECORATOR = "decorator"
    FACADE = "facade"
    FLYWEIGHT = "flyweight"
    PROXY = "proxy"

    # Behavioral
    CHAIN_OF_RESPONSIBILITY = "chain_of_responsibility"
    COMMAND = "command"
    ITERATOR = "iterator"
    MEDIATOR = "mediator"
    MEMENTO = "memento"
    OBSERVER = "observer"
    STATE = "state"
    STRATEGY = "strategy"
    TEMPLATE_METHOD = "template_method"
    VISITOR = "visitor"


@dataclass
class ArchitectureConfig:
    """Configuration for architecture analysis."""

    scan_path: Path = field(default_factory=lambda: Path("."))
    exclude_patterns: List[str] = field(
        default_factory=lambda: [
            "__pycache__", ".git", ".venv", "venv", "env", ".env",
            "node_modules", "build", "dist", "*.egg-info",
            ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
            "site-packages", "*-venv",
            ".next", ".nuxt", "coverage", "htmlcov",
            "vendor", "third_party",
        ]
    )
    include_extensions: List[str] = field(default_factory=lambda: [".py"])

    # SOLID thresholds
    max_class_responsibilities: int = 3
    max_method_count: int = 20
    max_public_methods: int = 10
    max_dependencies: int = 7

    # Layer configuration
    layers: Dict[str, List[str]] = field(default_factory=dict)

    # Pattern detection
    detect_patterns: List[PatternType] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure scan_path is a Path."""
        if isinstance(self.scan_path, str):
            self.scan_path = Path(self.scan_path)


@dataclass
class SOLIDViolation:
    """A SOLID principle violation."""

    principle: SOLIDPrinciple
    class_name: str
    file_path: str
    line_number: int
    message: str
    severity: ViolationSeverity = ViolationSeverity.MODERATE
    suggestion: str = ""

    @property
    def principle_name(self) -> str:
        """Get full principle name."""
        names = {
            SOLIDPrinciple.SRP: "Single Responsibility Principle",
            SOLIDPrinciple.OCP: "Open/Closed Principle",
            SOLIDPrinciple.LSP: "Liskov Substitution Principle",
            SOLIDPrinciple.ISP: "Interface Segregation Principle",
            SOLIDPrinciple.DIP: "Dependency Inversion Principle",
        }
        return names.get(self.principle, self.principle.value)


@dataclass
class SOLIDReport:
    """Report of SOLID principle analysis."""

    scan_path: str = ""
    scanned_at: datetime = field(default_factory=datetime.now)
    total_classes: int = 0
    violations: List[SOLIDViolation] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    @property
    def total_violations(self) -> int:
        """Get total violation count."""
        return len(self.violations)

    @property
    def violations_by_principle(self) -> Dict[SOLIDPrinciple, List[SOLIDViolation]]:
        """Group violations by principle."""
        result: Dict[SOLIDPrinciple, List[SOLIDViolation]] = {
            p: [] for p in SOLIDPrinciple
        }
        for v in self.violations:
            result[v.principle].append(v)
        return result

    @property
    def has_violations(self) -> bool:
        """Check if any violations exist."""
        return len(self.violations) > 0

    def add_violation(self, violation: SOLIDViolation) -> None:
        """Add a violation to the report."""
        self.violations.append(violation)


@dataclass
class LayerDefinition:
    """Definition of an architectural layer."""

    name: str
    patterns: List[str] = field(default_factory=list)
    allowed_dependencies: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class LayerViolation:
    """A layer architecture violation."""

    source_module: str
    source_layer: str
    target_module: str
    target_layer: str
    file_path: str
    line_number: int
    message: str
    severity: ViolationSeverity = ViolationSeverity.MODERATE


@dataclass
class LayerReport:
    """Report of layer architecture analysis."""

    scan_path: str = ""
    scanned_at: datetime = field(default_factory=datetime.now)
    layers: List[LayerDefinition] = field(default_factory=list)
    layer_assignments: Dict[str, str] = field(default_factory=dict)
    violations: List[LayerViolation] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    @property
    def total_violations(self) -> int:
        """Get total violation count."""
        return len(self.violations)

    @property
    def is_valid(self) -> bool:
        """Check if architecture is valid (no violations)."""
        return len(self.violations) == 0

    def add_violation(self, violation: LayerViolation) -> None:
        """Add a violation to the report."""
        self.violations.append(violation)


@dataclass
class PatternMatch:
    """A detected design pattern."""

    pattern_type: PatternType
    class_name: str
    file_path: str
    line_number: int
    confidence: float = 1.0
    participants: List[str] = field(default_factory=list)
    details: str = ""


@dataclass
class PatternReport:
    """Report of design pattern detection."""

    scan_path: str = ""
    scanned_at: datetime = field(default_factory=datetime.now)
    patterns: List[PatternMatch] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    @property
    def total_patterns(self) -> int:
        """Get total pattern count."""
        return len(self.patterns)

    @property
    def patterns_by_type(self) -> Dict[PatternType, List[PatternMatch]]:
        """Group patterns by type."""
        result: Dict[PatternType, List[PatternMatch]] = {}
        for p in self.patterns:
            if p.pattern_type not in result:
                result[p.pattern_type] = []
            result[p.pattern_type].append(p)
        return result

    def add_pattern(self, pattern: PatternMatch) -> None:
        """Add a pattern match to the report."""
        self.patterns.append(pattern)


@dataclass
class PortDefinition:
    """A detected port (interface/ABC) in the hexagonal architecture."""

    name: str
    file_path: str
    line_number: int
    direction: PortDirection
    abstract_methods: List[str] = field(default_factory=list)


@dataclass
class AdapterDefinition:
    """A detected adapter implementing a port."""

    name: str
    file_path: str
    line_number: int
    implements_port: str
    zone: HexagonalZone = HexagonalZone.ADAPTER
    framework_imports: List[str] = field(default_factory=list)


@dataclass
class HexagonalViolation:
    """A violation of hexagonal architecture rules."""

    file_path: str
    line_number: int
    source_zone: HexagonalZone
    target_zone: HexagonalZone
    class_name: str
    message: str
    severity: ViolationSeverity = ViolationSeverity.MODERATE


@dataclass
class HexagonalReport:
    """Report of hexagonal architecture analysis."""

    scan_path: str = ""
    scanned_at: datetime = field(default_factory=datetime.now)
    ports: List[PortDefinition] = field(default_factory=list)
    adapters: List[AdapterDefinition] = field(default_factory=list)
    zone_assignments: Dict[str, str] = field(default_factory=dict)
    violations: List[HexagonalViolation] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    @property
    def total_violations(self) -> int:
        """Get total violation count."""
        return len(self.violations)

    @property
    def is_valid(self) -> bool:
        """Check if hexagonal architecture is valid (no violations)."""
        return len(self.violations) == 0

    def add_violation(self, violation: HexagonalViolation) -> None:
        """Add a violation to the report."""
        self.violations.append(violation)


@dataclass
class PatternSuggestion:
    """A suggested design pattern for a class or code region."""

    pattern_type: PatternType
    class_name: str
    file_path: str
    line_number: int
    rationale: str
    signals: List[str] = field(default_factory=list)
    confidence: float = 0.6
    benefit: str = ""


@dataclass
class PatternSuggestionReport:
    """Report of pattern candidate suggestions from code smell analysis."""

    scan_path: str = ""
    scanned_at: datetime = field(default_factory=datetime.now)
    suggestions: List["PatternSuggestion"] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    @property
    def total_suggestions(self) -> int:
        """Get total suggestion count."""
        return len(self.suggestions)

    @property
    def suggestions_by_pattern(self) -> Dict[PatternType, List["PatternSuggestion"]]:
        """Group suggestions by pattern type."""
        result: Dict[PatternType, List[PatternSuggestion]] = {}
        for s in self.suggestions:
            if s.pattern_type not in result:
                result[s.pattern_type] = []
            result[s.pattern_type].append(s)
        return result

    def add_suggestion(self, suggestion: "PatternSuggestion") -> None:
        """Add a pattern suggestion to the report."""
        self.suggestions.append(suggestion)


@dataclass
class ArchitectureReport:
    """Combined architecture analysis report."""

    scan_path: str = ""
    scanned_at: datetime = field(default_factory=datetime.now)
    solid_report: Optional[SOLIDReport] = None
    layer_report: Optional[LayerReport] = None
    pattern_report: Optional[PatternReport] = None
    hexagonal_report: Optional[HexagonalReport] = None
    suggestion_report: Optional[PatternSuggestionReport] = None
    scan_duration_seconds: float = 0.0

    @property
    def total_violations(self) -> int:
        """Get total violations across all reports."""
        total = 0
        if self.solid_report:
            total += self.solid_report.total_violations
        if self.layer_report:
            total += self.layer_report.total_violations
        if self.hexagonal_report:
            total += self.hexagonal_report.total_violations
        return total

    @property
    def is_healthy(self) -> bool:
        """Check if architecture is healthy (no violations)."""
        return self.total_violations == 0

    @property
    def total_patterns(self) -> int:
        """Get total detected patterns."""
        if self.pattern_report:
            return self.pattern_report.total_patterns
        return 0
