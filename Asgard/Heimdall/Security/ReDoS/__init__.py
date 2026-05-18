"""
Heimdall Security ReDoS — Regular Expression Denial of Service scanner.

Extracts regex literals from source code and analyzes them for catastrophic
backtracking patterns: nested quantifiers, overlapping alternations, star height > 1.

Usage:
    from Asgard.Heimdall.Security.ReDoS import ReDoSScanner, ReDoSScanConfig

    scanner = ReDoSScanner()
    report = scanner.scan(ReDoSScanConfig(scan_path=Path("./src")))
    print(f"ReDoS findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.ReDoS.models.redos_models import (
    ReDoSFinding,
    ReDoSScanConfig,
    ReDoSScanReport,
    ReDoSSeverity,
)
from Asgard.Heimdall.Security.ReDoS.services.redos_scanner import ReDoSScanner

__all__ = ["ReDoSFinding", "ReDoSScanConfig", "ReDoSScanReport", "ReDoSScanner", "ReDoSSeverity"]
