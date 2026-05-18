"""
Heimdall Security LogAnalysis — security event detection in log files.

Scans log files for failed logins, brute force, SQL/XSS/command injection attempts,
path traversal, privilege escalation, and malware indicators.

Usage:
    from Asgard.Heimdall.Security.LogAnalysis import LogAnalyzer

    analyzer = LogAnalyzer()
    report = analyzer.analyze_directory(Path("/var/log"))
    print(f"Security events: {report.total_events}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.LogAnalysis.models.log_models import LogAnalysisReport, LogEvent
from Asgard.Heimdall.Security.LogAnalysis.services.log_analyzer import LogAnalyzer

__all__ = ["LogAnalysisReport", "LogAnalyzer", "LogEvent"]
