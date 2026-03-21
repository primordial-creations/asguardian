"""
Heimdall Performance Analysis Models - Report Models

Pydantic report models for memory, CPU, database, cache, and
comprehensive performance scan results.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Heimdall.Performance.models._performance_findings import (
    CacheFinding,
    CpuFinding,
    DatabaseFinding,
    MemoryFinding,
    PerformanceSeverity,
)


class PerformanceScanConfig(BaseModel):
    """Configuration for performance scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    scan_memory: bool = Field(True, description="Enable memory analysis")
    scan_cpu: bool = Field(True, description="Enable CPU analysis")
    scan_database: bool = Field(True, description="Enable database analysis")
    scan_cache: bool = Field(True, description="Enable cache analysis")
    min_severity: PerformanceSeverity = Field(PerformanceSeverity.LOW, description="Minimum severity to report")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "test",
            "tests",
            "*.test.*",
            "*.spec.*",
        ],
        description="Patterns to exclude from scanning"
    )
    include_extensions: Optional[List[str]] = Field(
        None,
        description="File extensions to include (None = all code files)"
    )
    complexity_threshold: int = Field(10, description="Cyclomatic complexity threshold")
    memory_threshold_mb: int = Field(100, description="Memory allocation threshold in MB")

    class Config:
        use_enum_values = True


class MemoryReport(BaseModel):
    """Report from memory profiling analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    issues_found: int = Field(0, description="Total memory issues detected")
    findings: List[MemoryFinding] = Field(default_factory=list, description="List of findings")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: MemoryFinding) -> None:
        """Add a memory finding to the report."""
        self.issues_found += 1
        self.findings.append(finding)

    @property
    def has_findings(self) -> bool:
        """Check if any issues were found."""
        return self.issues_found > 0

    def get_findings_by_severity(self) -> Dict[str, List[MemoryFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[MemoryFinding]] = {
            PerformanceSeverity.CRITICAL.value: [],
            PerformanceSeverity.HIGH.value: [],
            PerformanceSeverity.MEDIUM.value: [],
            PerformanceSeverity.LOW.value: [],
            PerformanceSeverity.INFO.value: [],
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result


class CpuReport(BaseModel):
    """Report from CPU profiling analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    total_functions_analyzed: int = Field(0, description="Number of functions analyzed")
    issues_found: int = Field(0, description="Total CPU issues detected")
    findings: List[CpuFinding] = Field(default_factory=list, description="List of findings")
    average_complexity: float = Field(0.0, description="Average function complexity")
    max_complexity: float = Field(0.0, description="Maximum function complexity")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: CpuFinding) -> None:
        """Add a CPU finding to the report."""
        self.issues_found += 1
        self.findings.append(finding)

    @property
    def has_findings(self) -> bool:
        """Check if any issues were found."""
        return self.issues_found > 0


class DatabaseReport(BaseModel):
    """Report from database performance analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    issues_found: int = Field(0, description="Total database issues detected")
    findings: List[DatabaseFinding] = Field(default_factory=list, description="List of findings")
    orm_detected: Optional[str] = Field(None, description="ORM framework detected")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: DatabaseFinding) -> None:
        """Add a database finding to the report."""
        self.issues_found += 1
        self.findings.append(finding)

    @property
    def has_findings(self) -> bool:
        """Check if any issues were found."""
        return self.issues_found > 0


class CacheReport(BaseModel):
    """Report from cache performance analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    issues_found: int = Field(0, description="Total cache issues detected")
    findings: List[CacheFinding] = Field(default_factory=list, description="List of findings")
    cache_systems_detected: List[str] = Field(default_factory=list, description="Cache systems detected")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: CacheFinding) -> None:
        """Add a cache finding to the report."""
        self.issues_found += 1
        self.findings.append(finding)

    @property
    def has_findings(self) -> bool:
        """Check if any issues were found."""
        return self.issues_found > 0


class PerformanceReport(BaseModel):
    """Comprehensive performance analysis report."""
    scan_path: str = Field(..., description="Root path that was scanned")
    scan_config: PerformanceScanConfig = Field(..., description="Configuration used for the scan")
    memory_report: Optional[MemoryReport] = Field(None, description="Memory profiling report")
    cpu_report: Optional[CpuReport] = Field(None, description="CPU profiling report")
    database_report: Optional[DatabaseReport] = Field(None, description="Database analysis report")
    cache_report: Optional[CacheReport] = Field(None, description="Cache analysis report")
    total_issues: int = Field(0, description="Total performance issues found")
    critical_issues: int = Field(0, description="Critical severity issues")
    high_issues: int = Field(0, description="High severity issues")
    medium_issues: int = Field(0, description="Medium severity issues")
    low_issues: int = Field(0, description="Low severity issues")
    performance_score: float = Field(100.0, ge=0.0, le=100.0, description="Overall performance score (0-100)")
    scan_duration_seconds: float = Field(0.0, description="Total duration of all scans")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def calculate_totals(self) -> None:
        """Calculate total issue counts from all reports."""
        self.total_issues = 0
        self.critical_issues = 0
        self.high_issues = 0
        self.medium_issues = 0
        self.low_issues = 0

        all_findings: List[Any] = []

        if self.memory_report:
            all_findings.extend(self.memory_report.findings)

        if self.cpu_report:
            all_findings.extend(self.cpu_report.findings)

        if self.database_report:
            all_findings.extend(self.database_report.findings)

        if self.cache_report:
            all_findings.extend(self.cache_report.findings)

        for finding in all_findings:
            self.total_issues += 1
            severity = finding.severity
            if severity == PerformanceSeverity.CRITICAL.value:
                self.critical_issues += 1
            elif severity == PerformanceSeverity.HIGH.value:
                self.high_issues += 1
            elif severity == PerformanceSeverity.MEDIUM.value:
                self.medium_issues += 1
            elif severity == PerformanceSeverity.LOW.value:
                self.low_issues += 1

        self._calculate_performance_score()

    def _calculate_performance_score(self) -> None:
        """Calculate the overall performance score."""
        score = 100.0
        score -= self.critical_issues * 20
        score -= self.high_issues * 10
        score -= self.medium_issues * 5
        score -= self.low_issues * 2
        self.performance_score = max(0.0, score)

    @property
    def has_issues(self) -> bool:
        """Check if any performance issues were found."""
        return self.total_issues > 0

    @property
    def is_healthy(self) -> bool:
        """Check if the performance is healthy (no critical or high issues)."""
        return self.critical_issues == 0 and self.high_issues == 0
