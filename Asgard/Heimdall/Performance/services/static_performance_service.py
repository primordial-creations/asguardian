"""
Heimdall Static Performance Analysis Service

Service for comprehensive static performance analysis combining multiple
performance checks into a unified analysis.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Heimdall.Performance.models.performance_models import (
    PerformanceReport,
    PerformanceScanConfig,
)
from Asgard.Heimdall.Performance.services._static_performance_reporter import generate_summary
from Asgard.Heimdall.Performance.services.memory_profiler_service import MemoryProfilerService
from Asgard.Heimdall.Performance.services.cpu_profiler_service import CpuProfilerService
from Asgard.Heimdall.Performance.services.database_analyzer_service import DatabaseAnalyzerService
from Asgard.Heimdall.Performance.services.cache_analyzer_service import CacheAnalyzerService


class StaticPerformanceService:
    """
    Comprehensive static performance analysis service.

    Combines multiple performance scanning capabilities:
    - Memory profiling (leaks, allocations, inefficiencies)
    - CPU profiling (complexity, blocking, loops)
    - Database analysis (N+1, missing indexes, ORM issues)
    - Cache analysis (missing cache, configuration issues)

    Provides a unified performance report with aggregated findings
    and an overall performance score.
    """

    def __init__(self, config: Optional[PerformanceScanConfig] = None):
        """
        Initialize the static performance service.

        Args:
            config: Performance scan configuration. Uses defaults if not provided.
        """
        self.config = config or PerformanceScanConfig()

        self.memory_service = MemoryProfilerService(self.config)
        self.cpu_service = CpuProfilerService(self.config)
        self.database_service = DatabaseAnalyzerService(self.config)
        self.cache_service = CacheAnalyzerService(self.config)

    def scan(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """
        Perform comprehensive performance analysis.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            PerformanceReport containing all findings from all services
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = PerformanceReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        if self.config.scan_memory:
            try:
                report.memory_report = self.memory_service.scan(path)
            except Exception:
                pass

        if self.config.scan_cpu:
            try:
                report.cpu_report = self.cpu_service.scan(path)
            except Exception:
                pass

        if self.config.scan_database:
            try:
                report.database_report = self.database_service.scan(path)
            except Exception:
                pass

        if self.config.scan_cache:
            try:
                report.cache_report = self.cache_service.scan(path)
            except Exception:
                pass

        report.scan_duration_seconds = time.time() - start_time
        report.scanned_at = datetime.now()

        report.calculate_totals()

        return report

    def scan_memory_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """
        Scan only for memory issues.

        Args:
            scan_path: Root path to scan

        Returns:
            PerformanceReport with memory findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = PerformanceReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.memory_report = self.memory_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_cpu_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """
        Scan only for CPU/complexity issues.

        Args:
            scan_path: Root path to scan

        Returns:
            PerformanceReport with CPU findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = PerformanceReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.cpu_report = self.cpu_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_database_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """
        Scan only for database issues.

        Args:
            scan_path: Root path to scan

        Returns:
            PerformanceReport with database findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = PerformanceReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.database_report = self.database_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def scan_cache_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """
        Scan only for caching issues.

        Args:
            scan_path: Root path to scan

        Returns:
            PerformanceReport with cache findings only
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        start_time = time.time()

        report = PerformanceReport(
            scan_path=str(path),
            scan_config=self.config,
        )

        report.cache_report = self.cache_service.scan(path)
        report.scan_duration_seconds = time.time() - start_time
        report.calculate_totals()

        return report

    def analyze(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """
        Perform comprehensive performance analysis (delegates to scan()).

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            PerformanceReport containing all findings from all services
        """
        return self.scan(scan_path)

    def generate_report(self, report: PerformanceReport, output_format: str = "text") -> str:
        """
        Generate formatted performance report.

        Args:
            report: The performance report to format
            output_format: Report format - text, json, or markdown

        Returns:
            Formatted report string
        """
        return generate_summary(report)

    def get_summary(self, report: PerformanceReport) -> str:
        """
        Generate a text summary of the performance report.

        Args:
            report: The performance report

        Returns:
            Formatted summary string
        """
        return generate_summary(report)
