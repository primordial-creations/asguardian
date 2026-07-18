"""
Verdandi System - System Performance Metrics

This module provides system performance metric calculations including:
- Memory usage and utilization
- CPU usage patterns
- I/O throughput metrics
- Resource utilization

Usage:
    from Asgard.Verdandi.System import MemoryMetricsCalculator

    calc = MemoryMetricsCalculator()
    result = calc.analyze(used_bytes=8000000000, total_bytes=16000000000)
    print(f"Memory Usage: {result.usage_percent}%")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Verdandi.System.models.system_models import (
    CgroupCpuStats,
    CpuMetrics,
    IoMetrics,
    MemoryMetrics,
    PsiReport,
    PsiResource,
    PsiSnapshot,
    ResourceUtilization,
    ThrottleReport,
    UseRedCorrelation,
)
from Asgard.Verdandi.System.services.memory_calculator import MemoryMetricsCalculator
from Asgard.Verdandi.System.services.cpu_calculator import CpuMetricsCalculator
from Asgard.Verdandi.System.services.io_calculator import IoMetricsCalculator
from Asgard.Verdandi.System.services.psi_analyzer import PsiAnalyzer
from Asgard.Verdandi.System.services.cgroup_analyzer import CgroupAnalyzer
from Asgard.Verdandi.System.services.use_red_correlator import UseRedCorrelator

__all__ = [
    "CgroupAnalyzer",
    "CgroupCpuStats",
    "CpuMetrics",
    "CpuMetricsCalculator",
    "IoMetrics",
    "IoMetricsCalculator",
    "MemoryMetrics",
    "MemoryMetricsCalculator",
    "PsiAnalyzer",
    "PsiReport",
    "PsiResource",
    "PsiSnapshot",
    "ResourceUtilization",
    "ThrottleReport",
    "UseRedCorrelator",
    "UseRedCorrelation",
]
