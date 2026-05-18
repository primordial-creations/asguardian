"""
Heimdall Security Frontend — client-side security vulnerability scanner.

Detects DOM XSS sinks (innerHTML, document.write), prototype pollution, sensitive data
in localStorage, open redirects, eval() usage, React/Angular/Vue-specific risks,
and hardcoded secrets in frontend build code.

Usage:
    from Asgard.Heimdall.Security.Frontend import FrontendSecurityScanner, FrontendScanConfig

    scanner = FrontendSecurityScanner()
    report = scanner.scan(FrontendScanConfig(scan_path=Path("./src")))
    print(f"Frontend findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.Frontend.models.frontend_models import (
    FrontendFinding,
    FrontendScanConfig,
    FrontendScanReport,
    FrontendSeverity,
)
from Asgard.Heimdall.Security.Frontend.services.frontend_scanner import FrontendSecurityScanner

__all__ = [
    "FrontendFinding",
    "FrontendScanConfig",
    "FrontendScanReport",
    "FrontendSecurityScanner",
    "FrontendSeverity",
]
