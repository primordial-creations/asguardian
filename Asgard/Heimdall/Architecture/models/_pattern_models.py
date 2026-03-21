"""
Heimdall Architecture Models - Patterns

Data models for design pattern detection and suggestions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from Asgard.Heimdall.Architecture.models._solid_models import ViolationSeverity


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
    suggestions: List[PatternSuggestion] = field(default_factory=list)
    scan_duration_seconds: float = 0.0

    @property
    def total_suggestions(self) -> int:
        """Get total suggestion count."""
        return len(self.suggestions)

    @property
    def suggestions_by_pattern(self) -> Dict[PatternType, List[PatternSuggestion]]:
        """Group suggestions by pattern type."""
        result: Dict[PatternType, List[PatternSuggestion]] = {}
        for s in self.suggestions:
            if s.pattern_type not in result:
                result[s.pattern_type] = []
            result[s.pattern_type].append(s)
        return result

    def add_suggestion(self, suggestion: PatternSuggestion) -> None:
        """Add a pattern suggestion to the report."""
        self.suggestions.append(suggestion)
