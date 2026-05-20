"""
Heimdall Performance - Performance Analysis

This module provides performance analysis tools including:
- Memory profiling (leaks, allocations, inefficiencies)
- CPU profiling (complexity, blocking operations, loops)
- Database analysis (N+1 queries, missing indexes, ORM issues)
- Cache analysis (missing cache, configuration issues)
- Comprehensive static performance analysis

Usage:
    python -m Heimdall performance scan ./src
    python -m Heimdall performance memory ./src
    python -m Heimdall performance cpu ./src
    python -m Heimdall performance database ./src

Example:
    from Heimdall.Performance import StaticPerformanceService

    service = StaticPerformanceService()
    report = service.scan("./src")
    print(f"Performance Score: {report.performance_score}/100")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Bragi.Performance.models import (
    CacheFinding,
    CacheIssueType,
    CacheReport,
    CpuFinding,
    CpuIssueType,
    CpuReport,
    DatabaseFinding,
    DatabaseIssueType,
    DatabaseReport,
    MemoryFinding,
    MemoryIssueType,
    MemoryReport,
    PerformanceReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Bragi.Performance.services import (
    CacheAnalyzerService,
    CachePattern,
    CpuPattern,
    CpuProfilerService,
    DatabaseAnalyzerService,
    DatabasePattern,
    MemoryPattern,
    MemoryProfilerService,
    StaticPerformanceService,
)

__all__ = [
    "CacheAnalyzerService",
    "CacheFinding",
    "CacheIssueType",
    "CachePattern",
    "CacheReport",
    "CpuFinding",
    "CpuIssueType",
    "CpuPattern",
    "CpuProfilerService",
    "CpuReport",
    "DatabaseAnalyzerService",
    "DatabaseFinding",
    "DatabaseIssueType",
    "DatabasePattern",
    "DatabaseReport",
    "MemoryFinding",
    "MemoryIssueType",
    "MemoryPattern",
    "MemoryProfilerService",
    "MemoryReport",
    "PerformanceReport",
    "PerformanceScanConfig",
    "PerformanceSeverity",
    "StaticPerformanceService",
]
