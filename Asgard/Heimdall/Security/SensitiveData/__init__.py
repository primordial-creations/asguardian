"""
Heimdall Security SensitiveData — sensitive data and PII exposure scanner.

Detects hardcoded passwords, API keys, SSNs, credit card numbers, private keys,
AWS/GitHub/Stripe credentials, and JWT tokens embedded in source code.

Usage:
    from Asgard.Heimdall.Security.SensitiveData import SensitiveDataScanner, SensitiveDataScanConfig

    scanner = SensitiveDataScanner()
    report = scanner.scan(SensitiveDataScanConfig(scan_path=Path("./src")))
    print(f"Sensitive data findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.SensitiveData.models.sensitive_data_models import (
    SensitiveDataFinding,
    SensitiveDataScanConfig,
    SensitiveDataScanReport,
    SensitiveDataSeverity,
)
from Asgard.Heimdall.Security.SensitiveData.services.sensitive_data_scanner import SensitiveDataScanner

__all__ = [
    "SensitiveDataFinding",
    "SensitiveDataScanConfig",
    "SensitiveDataScanReport",
    "SensitiveDataScanner",
    "SensitiveDataSeverity",
]
