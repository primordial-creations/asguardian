"""
Heimdall Architecture Models - Layer

Data models for layered architecture analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from Asgard.Heimdall.Architecture.models._solid_models import ViolationSeverity


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
