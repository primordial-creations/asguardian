"""
Heimdall Security Deserialization — insecure deserialization vulnerability scanner.

Detects unsafe use of pickle, marshal, yaml.load, Java ObjectInputStream,
PHP unserialize, Ruby Marshal.load, and other language-specific deserialization sinks.

Usage:
    from Asgard.Heimdall.Security.Deserialization import DeserializationScanner, DeserializationScanConfig

    scanner = DeserializationScanner()
    report = scanner.scan(DeserializationScanConfig(scan_path=Path("./src")))
    print(f"Deserialization findings: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import (
    DeserializationFinding,
    DeserializationScanConfig,
    DeserializationScanReport,
    DeserializationSeverity,
)
from Asgard.Heimdall.Security.Deserialization.services.deserialization_scanner import DeserializationScanner

__all__ = [
    "DeserializationFinding",
    "DeserializationScanConfig",
    "DeserializationScanReport",
    "DeserializationScanner",
    "DeserializationSeverity",
]
