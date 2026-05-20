"""
Heimdall Quality - Bug Detection

Detects potential runtime bugs using symbolic execution subsets:
- Null dereference: accessing attributes/methods on potentially None values
- Unreachable code: code blocks that can never execute
- Always-false/always-true conditions
- Division by zero

Usage:
    python -m Heimdall quality bugs ./src
    python -m Heimdall quality bugs ./src --null-only
    python -m Heimdall quality bugs ./src --unreachable-only

Programmatic Usage:
    from Asgard.Bragi.Quality.BugDetection import BugDetector, BugDetectionConfig
    from pathlib import Path

    config = BugDetectionConfig(scan_path=Path("./src"))
    detector = BugDetector(config)
    report = detector.scan(Path("./src"))
    print(f"Bugs found: {report.total_bugs}")
"""

from Asgard.Bragi.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugReport,
    BugSeverity,
)
from Asgard.Bragi.Quality.BugDetection.services.null_dereference_detector import NullDereferenceDetector
from Asgard.Bragi.Quality.BugDetection.services.unreachable_code_detector import UnreachableCodeDetector
from Asgard.Bragi.Quality.BugDetection.services.assertion_misuse_detector import AssertMisuseDetector
from Asgard.Bragi.Quality.BugDetection.services.division_by_zero_detector import DivisionByZeroDetector
from Asgard.Bragi.Quality.BugDetection.services.python_footgun_detector import PythonFootgunDetector
from Asgard.Bragi.Quality.BugDetection.services.exception_quality_detector import ExceptionQualityDetector
from Asgard.Bragi.Quality.BugDetection.services.type_erosion_scanner import TypeErosionScanner
from Asgard.Bragi.Quality.BugDetection.services.dead_code_detector import DeadCodeDetector
from Asgard.Bragi.Quality.BugDetection.services.magic_numbers_detector import MagicNumbersDetector
from Asgard.Bragi.Quality.BugDetection.services.bug_detector import BugDetector

__all__ = [
    "BugCategory",
    "BugDetectionConfig",
    "BugDetector",
    "BugFinding",
    "BugReport",
    "BugSeverity",
    "NullDereferenceDetector",
    "UnreachableCodeDetector",
    "AssertMisuseDetector",
    "DivisionByZeroDetector",
    "PythonFootgunDetector",
    "ExceptionQualityDetector",
    "TypeErosionScanner",
    "DeadCodeDetector",
    "MagicNumbersDetector",
]
