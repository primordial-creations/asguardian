"""
Heimdall Architecture Analysis Subpackage

Provides architectural analysis including:
- SOLID principle validation
- Layer architecture compliance
- Design pattern detection
- Architectural smells
"""

from Asgard.Heimdall.Architecture.models.architecture_models import (
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
from Asgard.Heimdall.Architecture.services.solid_validator import SOLIDValidator
from Asgard.Heimdall.Architecture.services.layer_analyzer import LayerAnalyzer
from Asgard.Heimdall.Architecture.services.pattern_detector import PatternDetector
from Asgard.Heimdall.Architecture.services.hexagonal_analyzer import HexagonalAnalyzer
from Asgard.Heimdall.Architecture.services.pattern_suggester import PatternSuggester
from Asgard.Heimdall.Architecture.services.architecture_analyzer import ArchitectureAnalyzer

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
