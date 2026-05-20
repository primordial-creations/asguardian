"""
Heimdall Architecture Analysis Subpackage

Provides architectural analysis including:
- SOLID principle validation
- Layer architecture compliance
- Design pattern detection
- Architectural smells
"""

from Asgard.Bragi.Architecture.models.architecture_models import (
    ArchitectureConfig,
    SOLIDViolation,
    SOLIDPrinciple,
    SOLIDReport,
    LayerDefinition,
    LayerViolation,
    LayerReport,
    PatternMatch,
    PatternType,
    PatternReport,
    PatternSuggestion,
    PatternSuggestionReport,
    HexagonalZone,
    HexagonalViolation,
    HexagonalReport,
    PortDefinition,
    PortDirection,
    AdapterDefinition,
    ArchitectureReport,
)
from Asgard.Bragi.Architecture.services.solid_validator import SOLIDValidator
from Asgard.Bragi.Architecture.services.layer_analyzer import LayerAnalyzer
from Asgard.Bragi.Architecture.services.pattern_detector import PatternDetector
from Asgard.Bragi.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
from Asgard.Bragi.Architecture.services.pattern_suggester import PatternSuggester
from Asgard.Bragi.Architecture.services.architecture_analyzer import ArchitectureAnalyzer

__all__ = [
    # Models
    "ArchitectureConfig",
    "SOLIDViolation",
    "SOLIDPrinciple",
    "SOLIDReport",
    "LayerDefinition",
    "LayerViolation",
    "LayerReport",
    "PatternMatch",
    "PatternType",
    "PatternReport",
    "PatternSuggestion",
    "PatternSuggestionReport",
    "HexagonalZone",
    "HexagonalViolation",
    "HexagonalReport",
    "PortDefinition",
    "PortDirection",
    "AdapterDefinition",
    "ArchitectureReport",
    # Services
    "SOLIDValidator",
    "LayerAnalyzer",
    "PatternDetector",
    "PatternSuggester",
    "HexagonalAnalyzer",
    "ArchitectureAnalyzer",
]
