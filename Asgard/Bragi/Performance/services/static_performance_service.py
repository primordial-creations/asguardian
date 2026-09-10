"""
Heimdall Static Performance Analysis Service

Service for comprehensive static performance analysis combining multiple
performance checks into a unified analysis.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from Asgard.Bragi.Performance.models.performance_models import (
    AnalyzerOutcome,
    PerformanceReport,
    MemoryReport, CpuReport, DatabaseReport, CacheReport,
    PerformanceScanConfig,
)
from Asgard.Bragi.Performance.services._static_performance_reporter import generate_summary
from Asgard.Bragi.Performance.services.memory_profiler_service import MemoryProfilerService
from Asgard.Bragi.Performance.services.cpu_profiler_service import CpuProfilerService
from Asgard.Bragi.Performance.services.database_analyzer_service import DatabaseAnalyzerService
from Asgard.Bragi.Performance.services.cache_analyzer_service import CacheAnalyzerService


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
        return self._scan(scan_path, self.config)

    def _scan(self, scan_path: Optional[Path], config: PerformanceScanConfig) -> PerformanceReport:
        path = scan_path or config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = PerformanceReport(
            scan_path=str(path),
            scan_config=config,
        )

        for name, expected in (("memory", MemoryReport), ("cpu", CpuReport),
                               ("database", DatabaseReport), ("cache", CacheReport)):
            required = getattr(config, "scan_" + name)
            if not required:
                report.analyzer_outcomes[name] = AnalyzerOutcome(status="skipped", required=False)
                continue
            try:
                result = getattr(self, name + "_service").scan(path)
                if not isinstance(result, expected):
                    raise TypeError("invalid analyzer result")
                setattr(report, name + "_report", result)
                outcome = AnalyzerOutcome(status="succeeded", required=True)
            except (ImportError, FileNotFoundError):
                outcome = AnalyzerOutcome(status="unavailable", required=True,
                                          diagnostic="Required analyzer input or dependency unavailable")
            except Exception:
                # Raw analyzer exceptions can include source text or credentials.
                outcome = AnalyzerOutcome(status="failed", required=True,
                                          diagnostic="Analyzer execution or result validation failed")
            report.analyzer_outcomes[name] = outcome

        report.scan_duration_seconds = time.time() - start_time
        report.scanned_at = datetime.now()

        report.calculate_totals()

        return report

    def _scan_only(self, name: str, scan_path: Optional[Path]) -> PerformanceReport:
        config = self.config.model_copy(update={
            "scan_" + domain: domain == name for domain in ("memory", "cpu", "database", "cache")
        })
        return self._scan(scan_path, config)

    def scan_memory_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """Scan memory with other analyzers explicitly skipped."""
        return self._scan_only("memory", scan_path)

    def scan_cpu_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """Scan cpu with other analyzers explicitly skipped."""
        return self._scan_only("cpu", scan_path)

    def scan_database_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """Scan database with other analyzers explicitly skipped."""
        return self._scan_only("database", scan_path)

    def scan_cache_only(self, scan_path: Optional[Path] = None) -> PerformanceReport:
        """Scan cache with other analyzers explicitly skipped."""
        return self._scan_only("cache", scan_path)

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
        if output_format == "json":
            return report.model_dump_json(indent=2)
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
