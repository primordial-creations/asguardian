"""
Heimdall Blocking Call in Async Context Scanner Service

Detects blocking operations used inside async functions, which stall
the event loop and degrade application throughput.

Detects:
- time.sleep() inside async def
- requests.get/post/put/delete/patch/head() inside async def
- open() (file I/O) inside async def without aiofiles
- subprocess.run/call/check_output/check_call() inside async def
- urllib.request.urlopen() inside async def
"""

import ast
import fnmatch
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from Asgard.Heimdall.Quality.models.blocking_async_models import (
    BlockingAsyncConfig,
    BlockingAsyncReport,
    BlockingCall,
)
from Asgard.Heimdall.Quality.services._blocking_async_visitor import BlockingAsyncVisitor
from Asgard.Heimdall.Quality.services._blocking_async_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class BlockingAsyncScanner:
    """
    Scans Python files for blocking calls inside async functions.

    Detects time.sleep, requests HTTP calls, open(), subprocess calls,
    and urllib calls that are used inside async def functions, where they
    block the event loop rather than yielding control.

    Usage:
        scanner = BlockingAsyncScanner()
        report = scanner.analyze(Path("./src"))

        for call in report.detected_calls:
            print(f"{call.location}: {call.call_expression}")
    """

    def __init__(self, config: Optional[BlockingAsyncConfig] = None):
        """
        Initialize the blocking async scanner.

        Args:
            config: Configuration for scanning. If None, uses defaults.
        """
        self.config = config or BlockingAsyncConfig()

    def analyze(self, path: Path) -> BlockingAsyncReport:
        """
        Analyze a file or directory for blocking calls inside async functions.

        Args:
            path: Path to file or directory to analyze

        Returns:
            BlockingAsyncReport with all detected violations

        Raises:
            FileNotFoundError: If path does not exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        start_time = datetime.now()
        report = BlockingAsyncReport(scan_path=str(path))

        if path.is_file():
            violations = self._analyze_file(path, path.parent)
            for violation in violations:
                report.add_violation(violation)
            report.files_scanned = 1
        else:
            self._analyze_directory(path, report)

        report.scan_duration_seconds = (datetime.now() - start_time).total_seconds()

        file_violation_counts: Dict[str, int] = defaultdict(int)
        for call in report.detected_calls:
            file_violation_counts[call.file_path] += 1

        report.most_problematic_files = sorted(
            file_violation_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return report

    def _analyze_file(self, file_path: Path, root_path: Path) -> List[BlockingCall]:
        """
        Analyze a single file for blocking calls in async functions.

        Args:
            file_path: Path to Python file
            root_path: Root path for calculating relative paths

        Returns:
            List of detected BlockingCall violations
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source)

            visitor = BlockingAsyncVisitor(
                file_path=str(file_path.absolute()),
                source_lines=source_lines,
            )
            visitor.visit(tree)

            for violation in visitor.violations:
                try:
                    violation.relative_path = str(file_path.relative_to(root_path))
                except ValueError:
                    violation.relative_path = file_path.name

            return visitor.violations

        except SyntaxError:
            return []
        except Exception:
            return []

    def _analyze_directory(self, directory: Path, report: BlockingAsyncReport) -> None:
        """
        Analyze all Python files in a directory.

        Args:
            directory: Directory to analyze
            report: Report to add violations to
        """
        files_scanned = 0

        for root, dirs, files in os.walk(directory):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not any(self._matches_pattern(d, pattern) for pattern in self.config.exclude_patterns)
            ]

            for file in files:
                if not self._should_analyze_file(file):
                    continue

                if any(self._matches_pattern(file, pattern) for pattern in self.config.exclude_patterns):
                    continue

                if not self.config.include_tests:
                    if file.startswith("test_") or file.endswith("_test.py") or "tests" in str(root_path):
                        continue

                file_path = root_path / file
                violations = self._analyze_file(file_path, directory)
                files_scanned += 1

                for violation in violations:
                    report.add_violation(violation)

        report.files_scanned = files_scanned

    def _should_analyze_file(self, filename: str) -> bool:
        """Check if file should be analyzed based on extension."""
        if self.config.include_extensions:
            return any(filename.endswith(ext) for ext in self.config.include_extensions)
        return filename.endswith(".py")

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches exclude pattern."""
        return fnmatch.fnmatch(name, pattern)

    def generate_report(self, report: BlockingAsyncReport, output_format: str = "text") -> str:
        """
        Generate a formatted blocking-in-async report.

        Args:
            report: BlockingAsyncReport to format
            output_format: Report format (text, json, markdown)

        Returns:
            Formatted report string

        Raises:
            ValueError: If output format is not supported
        """
        format_lower = output_format.lower()
        if format_lower == "json":
            return generate_json_report(report)
        elif format_lower in ("markdown", "md"):
            return generate_markdown_report(report)
        elif format_lower == "text":
            return generate_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {output_format}. Use: text, json, markdown")
