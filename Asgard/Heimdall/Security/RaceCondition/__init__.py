"""
Heimdall Security RaceCondition — race condition and TOCTOU pattern detector.

Detects TOCTOU file checks, shared mutable state, non-atomic counter operations,
mktemp() usage, cache check-then-set patterns, and SELECT-then-UPDATE without transactions.

Usage:
    from Asgard.Heimdall.Security.RaceCondition import RaceConditionDetector, RaceConditionScanConfig

    detector = RaceConditionDetector()
    report = detector.scan(RaceConditionScanConfig(scan_path=Path("./src")))
    print(f"Race condition findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.RaceCondition.models.race_condition_models import (
    RaceConditionFinding,
    RaceConditionScanConfig,
    RaceConditionScanReport,
    RaceConditionSeverity,
)
from Asgard.Heimdall.Security.RaceCondition.services.race_condition_detector import RaceConditionDetector

__all__ = [
    "RaceConditionDetector",
    "RaceConditionFinding",
    "RaceConditionScanConfig",
    "RaceConditionScanReport",
    "RaceConditionSeverity",
]
