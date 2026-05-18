"""
Heimdall Security SSRF — Server-Side Request Forgery and XXE vulnerability scanner.

Detects user-controlled URLs passed to HTTP clients (requests, urllib, fetch, curl),
and XML parsing without external entity resolution disabled.

Usage:
    from Asgard.Heimdall.Security.SSRF import SSRFXXEScanner, SSRFScanConfig

    scanner = SSRFXXEScanner()
    report = scanner.scan(SSRFScanConfig(scan_path=Path("./src")))
    print(f"SSRF/XXE findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.SSRF.models.ssrf_models import (
    SSRFFinding,
    SSRFScanConfig,
    SSRFScanReport,
    SSRFSeverity,
    SSRFVulnerabilityType,
)
from Asgard.Heimdall.Security.SSRF.services.ssrf_scanner import SSRFXXEScanner

__all__ = [
    "SSRFFinding",
    "SSRFScanConfig",
    "SSRFScanReport",
    "SSRFSeverity",
    "SSRFVulnerabilityType",
    "SSRFXXEScanner",
]
