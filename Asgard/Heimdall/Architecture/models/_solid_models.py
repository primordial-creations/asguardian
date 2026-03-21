"""
Heimdall Architecture Models - SOLID

Data models for SOLID principle validation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List


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
