"""
Heimdall Security API — REST and GraphQL API vulnerability scanning.

Detects authentication gaps, IDOR, mass assignment, rate-limiting omissions,
data over-exposure, GraphQL misconfigurations, CORS issues, and unsafe file uploads.

Usage:
    from Asgard.Heimdall.Security.API import APISecurityScanner, APIScanConfig

    scanner = APISecurityScanner()
    report = scanner.scan(APIScanConfig(scan_path=Path("./src")))
    print(f"API findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.API.models.api_models import (
    APIFinding,
    APIScanConfig,
    APIScanReport,
    APISecurityCategory,
    APISeverity,
)
from Asgard.Heimdall.Security.API.services.api_scanner import APISecurityScanner

__all__ = [
    "APIFinding",
    "APIScanConfig",
    "APIScanReport",
    "APISecurityCategory",
    "APISeverity",
    "APISecurityScanner",
]
