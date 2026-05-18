"""
Heimdall Security Misconfig — security misconfiguration scanner.

Detects debug mode, default credentials, insecure protocols, disabled SSL verification,
permissive CORS, insecure session cookies, weak secret keys, Docker misconfigurations,
and verbose error handlers.

Usage:
    from Asgard.Heimdall.Security.Misconfig import SecurityMisconfigScanner, MisconfigScanConfig

    scanner = SecurityMisconfigScanner()
    report = scanner.scan(MisconfigScanConfig(scan_path=Path("./src")))
    print(f"Misconfig findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.Misconfig.models.misconfig_models import (
    MisconfigFinding,
    MisconfigScanConfig,
    MisconfigScanReport,
    MisconfigSeverity,
)
from Asgard.Heimdall.Security.Misconfig.services.misconfig_scanner import SecurityMisconfigScanner

__all__ = [
    "MisconfigFinding",
    "MisconfigScanConfig",
    "MisconfigScanReport",
    "MisconfigSeverity",
    "SecurityMisconfigScanner",
]
