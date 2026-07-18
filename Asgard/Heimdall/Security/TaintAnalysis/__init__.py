"""
Heimdall Security - Taint Analysis

Tracks untrusted user input (sources) through code execution paths to
dangerous sinks (SQL queries, shell commands, etc.) to detect injection
vulnerabilities using intra-function and cross-function taint tracking.

Usage:
    python -m Heimdall security taint ./src

Programmatic Usage:
    from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer, TaintConfig

    config = TaintConfig(scan_path=Path("./src"))
    analyzer = TaintAnalyzer(config)
    report = analyzer.scan(Path("./src"))
    print(f"Taint flows found: {report.total_flows}")
"""

from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    SanitizerRecord,
    TaintConfig,
    TaintFlow,
    TaintFlowStep,
    TaintReport,
    TaintSinkType,
    TaintSourceType,
)
from Asgard.Heimdall.Security.TaintAnalysis.services.taint_analyzer import TaintAnalyzer

__all__ = [
    "SanitizerRecord",
    "TaintAnalyzer",
    "TaintConfig",
    "TaintFlow",
    "TaintFlowStep",
    "TaintReport",
    "TaintSinkType",
    "TaintSourceType",
]
