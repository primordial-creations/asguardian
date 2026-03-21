"""
Heimdall Architecture Models

Data models for architecture analysis including SOLID validation,
layer compliance, and pattern detection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Architecture.models._solid_models import (
    SOLIDPrinciple,
    SOLIDReport,
    SOLIDViolation,
    ViolationSeverity,
)
from Asgard.Heimdall.Architecture.models._layer_models import (
    LayerDefinition,
    LayerReport,
    LayerViolation,
)
from Asgard.Heimdall.Architecture.models._pattern_models import (
    AdapterDefinition,
    HexagonalReport,
    HexagonalViolation,
    HexagonalZone,
    PatternMatch,
    PatternReport,
    PatternSuggestion,
    PatternSuggestionReport,
    PatternType,
    PortDefinition,
    PortDirection,
)


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


__all__ = [
    "ArchitectureConfig",
    "ArchitectureReport",
    "SOLIDPrinciple",
    "SOLIDViolation",
    "SOLIDReport",
    "ViolationSeverity",
    "LayerDefinition",
    "LayerViolation",
    "LayerReport",
    "PatternType",
    "PatternMatch",
    "PatternReport",
    "PortDirection",
    "PortDefinition",
    "AdapterDefinition",
    "HexagonalZone",
    "HexagonalViolation",
    "HexagonalReport",
    "PatternSuggestion",
    "PatternSuggestionReport",
]
