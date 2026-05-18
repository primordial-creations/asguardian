"""
Heimdall Security DataExfil — data exfiltration pattern detection.

Identifies HTTP/DNS/email/FTP/cloud exfiltration, database dumps, keyloggers,
covert channels, and sensitive PII being transmitted from application code.

Usage:
    from Asgard.Heimdall.Security.DataExfil import DataExfiltrationDetector, ExfilScanConfig

    detector = DataExfiltrationDetector()
    report = detector.scan(ExfilScanConfig(scan_path=Path("./src")))
    print(f"Exfiltration indicators: {report.total_findings}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.DataExfil.models.data_exfil_models import (
    ExfilFinding,
    ExfilScanConfig,
    ExfilScanReport,
    ExfilSeverity,
    ExfilType,
)
from Asgard.Heimdall.Security.DataExfil.services.data_exfil_detector import DataExfiltrationDetector

__all__ = [
    "DataExfiltrationDetector",
    "ExfilFinding",
    "ExfilScanConfig",
    "ExfilScanReport",
    "ExfilSeverity",
    "ExfilType",
]
