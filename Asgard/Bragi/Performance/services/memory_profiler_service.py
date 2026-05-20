"""
Heimdall Memory Profiler Service

Service for static analysis of memory-related performance issues
in source code.
"""

import re
import time
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Bragi.Performance.models.performance_models import (
    MemoryFinding,
    MemoryIssueType,
    MemoryReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Bragi.Performance.utilities.performance_utils import (
    extract_code_snippet,
    find_line_column,
    scan_directory_for_performance,
)


class MemoryPattern:
    """Defines a pattern for detecting memory issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        issue_type: MemoryIssueType,
        severity: PerformanceSeverity,
        description: str,
        estimated_impact: str,
        recommendation: str,
        file_types: Optional[Set[str]] = None,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.issue_type = issue_type
        self.severity = severity
        self.description = description
        self.estimated_impact = estimated_impact
        self.recommendation = recommendation
        self.file_types = file_types or {".py", ".js", ".ts", ".java"}


MEMORY_PATTERNS: List[MemoryPattern] = [
    MemoryPattern(
        name="large_file_read",
        pattern=r"""\.read\(\)\s*$""",
        issue_type=MemoryIssueType.HIGH_ALLOCATION,
        severity=PerformanceSeverity.MEDIUM,
        description="Reading entire file into memory at once.",
        estimated_impact="Memory usage proportional to file size",
        recommendation="Use line-by-line iteration or chunked reading for large files.",
        file_types={".py"},
    ),
    MemoryPattern(
        name="readlines_call",
        pattern=r"""\.readlines\(\)""",
        issue_type=MemoryIssueType.HIGH_ALLOCATION,
        severity=PerformanceSeverity.MEDIUM,
        description="readlines() loads entire file into memory as list.",
        estimated_impact="Memory usage proportional to file size",
        recommendation="Iterate over file object directly instead.",
        file_types={".py"},
    ),
    MemoryPattern(
        name="dataframe_copy",
        pattern=r"""\.copy\(\)\s*$""",
        issue_type=MemoryIssueType.HIGH_ALLOCATION,
        severity=PerformanceSeverity.LOW,
        description="DataFrame/object copy may not be necessary.",
        estimated_impact="Memory doubles for each copy operation",
        recommendation="Check if copy is truly needed.",
        file_types={".py"},
    ),
    MemoryPattern(
        name="json_load_read",
        pattern=r"""json\.load\s*\(""",
        issue_type=MemoryIssueType.HIGH_ALLOCATION,
        severity=PerformanceSeverity.MEDIUM,
        description="Loading JSON file into memory.",
        estimated_impact="Memory usage can be 2-10x the file size",
        recommendation="Use ijson for streaming large JSON files.",
        file_types={".py"},
    ),
    MemoryPattern(
        name="lru_cache_unbounded",
        pattern=r"""@lru_cache\s*\(\s*\)""",
        issue_type=MemoryIssueType.UNBOUNDED_GROWTH,
        severity=PerformanceSeverity.MEDIUM,
        description="lru_cache without maxsize can grow indefinitely.",
        estimated_impact="Memory grows with unique inputs",
        recommendation="Use @lru_cache(maxsize=N) to limit cache size.",
        file_types={".py"},
    ),
    MemoryPattern(
        name="event_listener",
        pattern=r"""addEventListener\s*\(""",
        issue_type=MemoryIssueType.MEMORY_LEAK,
        severity=PerformanceSeverity.LOW,
        description="Event listener - ensure corresponding removal exists.",
        estimated_impact="Memory retained until listener is removed",
        recommendation="Always remove event listeners in cleanup/dispose methods.",
        file_types={".js", ".ts", ".jsx", ".tsx"},
    ),
    MemoryPattern(
        name="setinterval_call",
        pattern=r"""setInterval\s*\(""",
        issue_type=MemoryIssueType.MEMORY_LEAK,
        severity=PerformanceSeverity.MEDIUM,
        description="setInterval - ensure clearInterval is called on cleanup.",
        estimated_impact="Callback and closure retained indefinitely",
        recommendation="Store interval ID and call clearInterval in cleanup.",
        file_types={".js", ".ts", ".jsx", ".tsx"},
    ),
    MemoryPattern(
        name="new_array_large",
        pattern=r"""new\s+Array\(\s*\d{6,}\s*\)""",
        issue_type=MemoryIssueType.LARGE_OBJECT,
        severity=PerformanceSeverity.HIGH,
        description="Creating very large pre-sized array.",
        estimated_impact="Immediate allocation of large memory block",
        recommendation="Consider lazy initialization or streaming approach.",
        file_types={".js", ".ts"},
    ),
]


class MemoryProfilerService:
    """
    Static analysis service for memory-related performance issues.

    Detects:
    - Memory leaks
    - Unbounded data structure growth
    - Inefficient memory usage patterns
    - Circular references
    - Large object allocations
    """

    def __init__(self, config: Optional[PerformanceScanConfig] = None):
        """
        Initialize the memory profiler service.

        Args:
            config: Performance scan configuration. Uses defaults if not provided.
        """
        self.config = config or PerformanceScanConfig()
        self.patterns = list(MEMORY_PATTERNS)

    def scan(self, scan_path: Optional[Path] = None) -> MemoryReport:
        """
        Scan the specified path for memory performance issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            MemoryReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = MemoryReport(
            scan_path=str(path),
        )

        for file_path in scan_directory_for_performance(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            report.total_files_scanned += 1
            findings = self._scan_file(file_path, path)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)

        report.scan_duration_seconds = time.time() - start_time

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _scan_file(self, file_path: Path, root_path: Path) -> List[MemoryFinding]:
        """
        Scan a single file for memory issues.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            List of memory findings in the file
        """
        findings: List[MemoryFinding] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings

        lines = content.split("\n")
        file_ext = file_path.suffix.lower()

        for pattern in self.patterns:
            if pattern.file_types and file_ext not in pattern.file_types:
                continue

            for match in pattern.pattern.finditer(content):
                line_number, column = find_line_column(content, match.start())

                if self._is_in_comment(lines, line_number):
                    continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = MemoryFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    issue_type=pattern.issue_type,
                    severity=pattern.severity,
                    description=pattern.description,
                    code_pattern=pattern.name,
                    estimated_impact=pattern.estimated_impact,
                    recommendation=pattern.recommendation,
                    code_snippet=code_snippet,
                )

                findings.append(finding)

        return findings

    def _is_in_comment(self, lines: List[str], line_number: int) -> bool:
        """Check if a line is inside a comment."""
        if line_number < 1 or line_number > len(lines):
            return False

        line = lines[line_number - 1].strip()

        if line.startswith("#") or line.startswith("//") or line.startswith("*"):
            return True

        return False

    def _severity_meets_threshold(self, severity: str) -> bool:
        """Check if a severity level meets the configured threshold."""
        severity_order = {
            PerformanceSeverity.INFO.value: 0,
            PerformanceSeverity.LOW.value: 1,
            PerformanceSeverity.MEDIUM.value: 2,
            PerformanceSeverity.HIGH.value: 3,
            PerformanceSeverity.CRITICAL.value: 4,
        }

        min_level = severity_order.get(self.config.min_severity, 1)
        finding_level = severity_order.get(severity, 1)

        return finding_level >= min_level

    def _severity_order(self, severity: str) -> int:
        """Get sort order for severity (critical first)."""
        order = {
            PerformanceSeverity.CRITICAL.value: 0,
            PerformanceSeverity.HIGH.value: 1,
            PerformanceSeverity.MEDIUM.value: 2,
            PerformanceSeverity.LOW.value: 3,
            PerformanceSeverity.INFO.value: 4,
        }
        return order.get(severity, 5)
