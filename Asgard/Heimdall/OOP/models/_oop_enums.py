"""
Heimdall OOP Models - Enumerations and Configuration

Severity/level enums and OOPConfig.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List


class OOPSeverity(str, Enum):
    """Severity levels for OOP metric violations."""
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFO = "info"


class CouplingLevel(str, Enum):
    """Classification of coupling levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class CohesionLevel(str, Enum):
    """Classification of cohesion levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    LOW = "low"
    CRITICAL = "critical"


@dataclass
class OOPConfig:
    """Configuration for OOP analysis."""
    scan_path: Path = field(default_factory=lambda: Path("."))

    cbo_threshold: int = 10
    dit_threshold: int = 5
    noc_threshold: int = 10
    lcom_threshold: float = 0.8
    rfc_threshold: int = 50
    wmc_threshold: int = 50

    include_tests: bool = False
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".pytest_cache", ".mypy_cache", "dist", "build",
    ])
    include_extensions: List[str] = field(default_factory=lambda: [".py"])
    output_format: str = "text"
    verbose: bool = False

    def __post_init__(self):
        if isinstance(self.scan_path, str):
            self.scan_path = Path(self.scan_path)
