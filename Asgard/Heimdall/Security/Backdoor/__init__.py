"""
Heimdall Security Backdoor — detects web shells, reverse shells, and persistent access mechanisms.

Combines hash-based known-malware detection with pattern matching for PHP/JSP/ASP
web shells, bind/reverse shells, obfuscated code, C2 beacons, and persistence mechanisms.

Usage:
    from Asgard.Heimdall.Security.Backdoor import BackdoorDetector, BackdoorScanConfig

    detector = BackdoorDetector()
    report = detector.scan(BackdoorScanConfig(scan_path=Path("./src")))
    print(f"Backdoor indicators: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.Backdoor.models.backdoor_models import (
    BackdoorFinding,
    BackdoorScanConfig,
    BackdoorScanReport,
    BackdoorSeverity,
    BackdoorType,
)
from Asgard.Heimdall.Security.Backdoor.services.backdoor_detector import BackdoorDetector

__all__ = [
    "BackdoorDetector",
    "BackdoorFinding",
    "BackdoorScanConfig",
    "BackdoorScanReport",
    "BackdoorSeverity",
    "BackdoorType",
]
