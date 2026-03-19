"""
Heimdall Bug Detector Orchestrator

Orchestrates null dereference detection, unreachable code detection,
and other bug detection services into a unified scan.
"""

import fnmatch
import time
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugReport,
    BugSeverity,
)
from Asgard.Heimdall.Quality.BugDetection.services.null_dereference_detector import NullDereferenceDetector
from Asgard.Heimdall.Quality.BugDetection.services.unreachable_code_detector import UnreachableCodeDetector
from Asgard.Heimdall.Quality.BugDetection.services.assertion_misuse_detector import AssertMisuseDetector
from Asgard.Heimdall.Quality.BugDetection.services.division_by_zero_detector import DivisionByZeroDetector
from Asgard.Heimdall.Quality.BugDetection.services.python_footgun_detector import PythonFootgunDetector
from Asgard.Heimdall.Quality.BugDetection.services.exception_quality_detector import ExceptionQualityDetector
from Asgard.Heimdall.Quality.BugDetection.services.type_erosion_scanner import TypeErosionScanner
from Asgard.Heimdall.Quality.BugDetection.services.dead_code_detector import DeadCodeDetector
from Asgard.Heimdall.Quality.BugDetection.services.magic_numbers_detector import MagicNumbersDetector


def _should_exclude(path: Path, exclude_patterns: List[str]) -> bool:
    """Check if a path should be excluded from scanning."""
    path_str = str(path)
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(path.name, pattern):
            return True
        if fnmatch.fnmatch(path_str, f"*{pattern}*"):
            return True
        if pattern in path_str:
            return True
    return False


def _collect_python_files(scan_path: Path, exclude_patterns: List[str]) -> List[Path]:
    """Collect all Python files under scan_path, respecting exclusions."""
    files: List[Path] = []
    for py_file in scan_path.rglob("*.py"):
        if not _should_exclude(py_file, exclude_patterns):
            files.append(py_file)
    return sorted(files)


class BugDetector:
    """
    Orchestrator for bug detection analysis.

    Runs null dereference detection and unreachable code detection
    across a codebase and combines results into a unified BugReport.
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None):
        """
        Initialize the bug detector orchestrator.

        Args:
            config: Bug detection configuration. Uses defaults if not provided.
        """
        self.config = config or BugDetectionConfig()
        self.null_detector = NullDereferenceDetector(self.config)
        self.unreachable_detector = UnreachableCodeDetector(self.config)
        self.assert_detector = AssertMisuseDetector(self.config)
        self.div_zero_detector = DivisionByZeroDetector(self.config)
        self.footgun_detector = PythonFootgunDetector(self.config)
        self.exception_detector = ExceptionQualityDetector(self.config)
        self.type_erosion_scanner = TypeErosionScanner(self.config)
        self.dead_code_detector = DeadCodeDetector(self.config)
        self.magic_numbers_detector = MagicNumbersDetector(self.config)

    def scan(self, scan_path: Optional[Path] = None) -> BugReport:
        """
        Scan the specified path for bugs.

        Runs all enabled detectors (null dereference, unreachable code)
        and returns a unified BugReport.

        Args:
            scan_path: Root path to scan. Uses config path if not provided.

        Returns:
            BugReport containing all bugs found.

        Raises:
            FileNotFoundError: If the scan path does not exist.
        """
        path = scan_path or self.config.scan_path
        path = Path(path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Scan path does not exist: {path}")

        start_time = time.time()
        report = BugReport(scan_path=str(path))

        python_files = _collect_python_files(path, self.config.exclude_patterns)
        report.files_analyzed = len(python_files)

        for file_path in python_files:
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
            except (IOError, OSError):
                continue

            lines = source.splitlines()
            file_findings: List[BugFinding] = []

            if self.config.detect_null_dereference:
                null_findings = self.null_detector.analyze_file(file_path, lines)
                file_findings.extend(null_findings)

            if self.config.detect_unreachable_code:
                unreachable_findings = self.unreachable_detector.analyze_file(file_path, lines)
                file_findings.extend(unreachable_findings)

            if self.config.detect_division_by_zero:
                file_findings.extend(self.div_zero_detector.analyze_file(file_path, lines))

            if self.config.detect_assertion_misuse:
                file_findings.extend(self.assert_detector.analyze_file(file_path, lines))

            if self.config.detect_python_footguns:
                file_findings.extend(self.footgun_detector.analyze_file(file_path, lines))

            if self.config.detect_exception_quality:
                file_findings.extend(self.exception_detector.analyze_file(file_path, lines))

            if self.config.detect_type_erosion:
                file_findings.extend(self.type_erosion_scanner.analyze_file(file_path, lines))

            if self.config.detect_dead_code:
                file_findings.extend(self.dead_code_detector.analyze_file(file_path, lines))

            if self.config.detect_magic_numbers:
                file_findings.extend(self.magic_numbers_detector.analyze_file(file_path, lines))

            for finding in file_findings:
                report.add_finding(finding)

        # Sort findings: critical first, then by file/line
        severity_order = {
            BugSeverity.CRITICAL.value: 0,
            BugSeverity.HIGH.value: 1,
            BugSeverity.MEDIUM.value: 2,
            BugSeverity.LOW.value: 3,
        }
        report.findings.sort(
            key=lambda f: (
                severity_order.get(
                    f.severity if isinstance(f.severity, str) else f.severity.value, 4
                ),
                f.file_path,
                f.line_number,
            )
        )

        report.scan_duration_seconds = time.time() - start_time
        return report

    def scan_null_dereference_only(self, scan_path: Optional[Path] = None) -> BugReport:
        """
        Scan only for null dereference bugs.

        Args:
            scan_path: Root path to scan.

        Returns:
            BugReport with only null dereference findings.
        """
        original_unreachable = self.config.detect_unreachable_code
        self.config.detect_unreachable_code = False
        try:
            report = self.scan(scan_path)
        finally:
            self.config.detect_unreachable_code = original_unreachable
        return report

    def scan_unreachable_only(self, scan_path: Optional[Path] = None) -> BugReport:
        """
        Scan only for unreachable code bugs.

        Args:
            scan_path: Root path to scan.

        Returns:
            BugReport with only unreachable code findings.
        """
        original_null = self.config.detect_null_dereference
        self.config.detect_null_dereference = False
        try:
            report = self.scan(scan_path)
        finally:
            self.config.detect_null_dereference = original_null
        return report
