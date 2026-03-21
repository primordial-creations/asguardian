"""
Heimdall CPU Profiler Service

Service for static analysis of CPU-related performance issues
in source code, including complexity analysis.
"""

import re
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Performance.models.performance_models import (
    CpuFinding,
    CpuIssueType,
    CpuReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Heimdall.Performance.services._cpu_patterns import (
    CPU_PATTERNS,
    CpuPattern,
)
from Asgard.Heimdall.Performance.utilities.performance_utils import (
    calculate_complexity,
    extract_code_snippet,
    find_line_column,
    scan_directory_for_performance,
)


class CpuProfilerService:
    """
    Static analysis service for CPU-related performance issues.

    Detects:
    - High algorithmic complexity (nested loops)
    - Inefficient loop patterns
    - Blocking operations
    - Redundant computations
    - Recursive function issues
    """

    def __init__(self, config: Optional[PerformanceScanConfig] = None):
        """
        Initialize the CPU profiler service.

        Args:
            config: Performance scan configuration. Uses defaults if not provided.
        """
        self.config = config or PerformanceScanConfig()
        self.patterns = list(CPU_PATTERNS)

    def scan(self, scan_path: Optional[Path] = None) -> CpuReport:
        """
        Scan the specified path for CPU performance issues.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            CpuReport containing all findings
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()

        report = CpuReport(
            scan_path=str(path),
        )

        all_complexities: List[float] = []

        for file_path in scan_directory_for_performance(
            path,
            exclude_patterns=self.config.exclude_patterns,
            include_extensions=self.config.include_extensions,
        ):
            report.total_files_scanned += 1
            findings, complexities = self._scan_file(file_path, path)

            all_complexities.extend(complexities)
            report.total_functions_analyzed += len(complexities)

            for finding in findings:
                if self._severity_meets_threshold(finding.severity):
                    report.add_finding(finding)

        report.scan_duration_seconds = time.time() - start_time

        if all_complexities:
            report.average_complexity = sum(all_complexities) / len(all_complexities)
            report.max_complexity = max(all_complexities)

        report.findings.sort(
            key=lambda f: (
                self._severity_order(f.severity),
                f.file_path,
                f.line_number,
            )
        )

        return report

    def _scan_file(self, file_path: Path, root_path: Path) -> tuple:
        """
        Scan a single file for CPU issues and calculate complexity.

        Args:
            file_path: Path to the file to scan
            root_path: Root path for relative path calculation

        Returns:
            Tuple of (findings list, complexity scores list)
        """
        findings: List[CpuFinding] = []
        complexities: List[float] = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (IOError, OSError):
            return findings, complexities

        lines = content.split("\n")
        file_ext = file_path.suffix.lower()

        if file_ext == ".py":
            complexity_scores = calculate_complexity(content)
            complexities = list(complexity_scores.values())

            for func_name, complexity in complexity_scores.items():
                if complexity > self.config.complexity_threshold:
                    func_info = self._find_function_line(content, func_name)

                    finding = CpuFinding(
                        file_path=str(file_path.relative_to(root_path)),
                        line_number=func_info.get("line", 1),
                        function_name=func_name,
                        issue_type=CpuIssueType.HIGH_COMPLEXITY,
                        severity=self._complexity_to_severity(complexity),
                        description=f"Function has cyclomatic complexity of {complexity}.",
                        complexity_score=float(complexity),
                        estimated_impact="Harder to test, maintain, and may indicate performance issues",
                        recommendation="Break down into smaller functions, reduce branching.",
                        code_snippet=extract_code_snippet(lines, func_info.get("line", 1)),
                    )
                    findings.append(finding)

        for pattern in self.patterns:
            if pattern.file_types and file_ext not in pattern.file_types:
                continue

            for match in pattern.pattern.finditer(content):
                line_number, column = find_line_column(content, match.start())

                if self._is_in_comment(lines, line_number):
                    continue

                code_snippet = extract_code_snippet(lines, line_number)

                finding = CpuFinding(
                    file_path=str(file_path.relative_to(root_path)),
                    line_number=line_number,
                    function_name="",
                    issue_type=pattern.issue_type,
                    severity=pattern.severity,
                    description=pattern.description,
                    complexity_score=None,
                    estimated_impact=pattern.estimated_impact,
                    recommendation=pattern.recommendation,
                    code_snippet=code_snippet,
                )

                findings.append(finding)

        return findings, complexities

    def _find_function_line(self, content: str, func_name: str) -> dict:
        """Find the line number where a function is defined."""
        pattern = rf"def\s+{re.escape(func_name)}\s*\("
        match = re.search(pattern, content)
        if match:
            line_number, _ = find_line_column(content, match.start())
            return {"line": line_number}
        return {"line": 1}

    def _complexity_to_severity(self, complexity: int) -> PerformanceSeverity:
        """Convert complexity score to severity level."""
        if complexity > 30:
            return PerformanceSeverity.CRITICAL
        elif complexity > 20:
            return PerformanceSeverity.HIGH
        elif complexity > 15:
            return PerformanceSeverity.MEDIUM
        else:
            return PerformanceSeverity.LOW

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
