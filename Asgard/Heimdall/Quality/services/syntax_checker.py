"""
Syntax checker service for Heimdall.

Runs syntax and linting checks using external tools like ruff, flake8, pylint, and mypy.
"""

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from Asgard.Heimdall.Quality.models.syntax_models import (
    FileAnalysis,
    LinterType,
    SyntaxConfig,
    SyntaxIssue,
    SyntaxResult,
    SyntaxSeverity,
)
from Asgard.Heimdall.Quality.services._syntax_linters import (
    run_flake8,
    run_mypy,
    run_pylint,
    run_ruff,
    run_ruff_fix,
)
from Asgard.Heimdall.Quality.services._syntax_report import (
    generate_json_report,
    generate_markdown_report,
    generate_text_report,
)


class SyntaxChecker:
    """
    Syntax and linting checker service.

    Uses external linters (ruff, flake8, pylint, mypy) to check code for
    syntax errors, linting violations, and style issues.
    """

    def __init__(self, config: SyntaxConfig):
        """Initialize the syntax checker."""
        self.config = config
        self._available_linters: Optional[List[LinterType]] = None

    def get_available_linters(self) -> List[LinterType]:
        """Check which linters are available on the system."""
        if self._available_linters is not None:
            return self._available_linters

        available = []
        linter_commands = {
            LinterType.RUFF: ["ruff", "--version"],
            LinterType.FLAKE8: ["flake8", "--version"],
            LinterType.PYLINT: ["pylint", "--version"],
            LinterType.MYPY: ["mypy", "--version"],
        }

        for linter, cmd in linter_commands.items():
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                available.append(linter)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        self._available_linters = available
        return available

    def analyze(self) -> SyntaxResult:
        """
        Run syntax analysis on the configured path.

        Returns:
            SyntaxResult with all findings
        """
        start_time = time.time()
        scan_path = Path(self.config.scan_path).resolve()

        if not scan_path.exists():
            raise FileNotFoundError(f"Path not found: {scan_path}")

        files = self._get_files_to_scan(scan_path)

        linters = self._get_linters_to_run()

        all_issues: List[SyntaxIssue] = []
        for linter in linters:
            issues = self._run_linter(linter, scan_path)
            all_issues.extend(issues)

        file_analyses = self._group_issues_by_file(all_issues, files, scan_path)

        file_analyses = self._filter_by_severity(file_analyses)

        duration = time.time() - start_time

        return SyntaxResult(
            scan_path=str(scan_path),
            scanned_at=datetime.now(),
            scan_duration_seconds=duration,
            config=self.config,
            file_analyses=file_analyses,
        )

    def fix(self) -> Tuple[SyntaxResult, int]:
        """
        Run syntax analysis and fix auto-fixable issues.

        Returns:
            Tuple of (SyntaxResult after fixing, number of fixes applied)
        """
        scan_path = Path(self.config.scan_path).resolve()
        fixes_applied = 0

        if LinterType.RUFF in self.get_available_linters():
            fixes_applied = run_ruff_fix(scan_path, self.config)

        result = self.analyze()

        return result, fixes_applied

    def _get_files_to_scan(self, scan_path: Path) -> List[Path]:
        """Get list of files to scan based on config."""
        files = []

        if scan_path.is_file():
            if self._should_include_file(scan_path):
                files.append(scan_path)
        else:
            for ext in self.config.include_extensions:
                pattern = f"**/*{ext}"
                for file_path in scan_path.glob(pattern):
                    if self._should_include_file(file_path):
                        files.append(file_path)

        return sorted(files)

    def _should_include_file(self, file_path: Path) -> bool:
        """Check if a file should be included in analysis."""
        path_str = str(file_path)

        for pattern in self.config.exclude_patterns:
            if pattern in path_str:
                return False

        return True

    def _get_linters_to_run(self) -> List[LinterType]:
        """Determine which linters to run."""
        requested = self.config.linters or [LinterType.RUFF]
        available = self.get_available_linters()

        linters = [l for l in requested if l in available]

        if not linters:
            if LinterType.RUFF in available:
                linters = [LinterType.RUFF]
            elif LinterType.FLAKE8 in available:
                linters = [LinterType.FLAKE8]

        return linters

    def _run_linter(self, linter: LinterType, scan_path: Path) -> List[SyntaxIssue]:
        """Run a specific linter and parse its output."""
        if linter == LinterType.RUFF:
            return run_ruff(scan_path, self.config)
        elif linter == LinterType.FLAKE8:
            return run_flake8(scan_path, self.config)
        elif linter == LinterType.PYLINT:
            return run_pylint(scan_path, self.config)
        elif linter == LinterType.MYPY:
            return run_mypy(scan_path, self.config)
        return []

    def _group_issues_by_file(
        self,
        issues: List[SyntaxIssue],
        files: List[Path],
        scan_path: Path
    ) -> List[FileAnalysis]:
        """Group issues by file and create FileAnalysis objects."""
        issues_by_file: dict[str, List[SyntaxIssue]] = {}
        for issue in issues:
            abs_path = str(Path(issue.file_path).resolve())
            if abs_path not in issues_by_file:
                issues_by_file[abs_path] = []
            issues_by_file[abs_path].append(issue)

        file_analyses = []
        all_files = set(str(f.resolve()) for f in files)

        for file_path_str in all_files:
            file_path = Path(file_path_str)
            try:
                rel_path = str(file_path.relative_to(scan_path))
            except ValueError:
                rel_path = str(file_path)

            file_issues = issues_by_file.get(file_path_str, [])

            fa = FileAnalysis(
                file_path=file_path_str,
                relative_path=rel_path,
                issues=file_issues,
                error_count=sum(1 for i in file_issues if i.severity == SyntaxSeverity.ERROR),
                warning_count=sum(1 for i in file_issues if i.severity == SyntaxSeverity.WARNING),
                info_count=sum(1 for i in file_issues if i.severity == SyntaxSeverity.INFO),
                style_count=sum(1 for i in file_issues if i.severity == SyntaxSeverity.STYLE),
            )
            file_analyses.append(fa)

        file_analyses.sort(key=lambda x: x.relative_path)

        return file_analyses

    def _filter_by_severity(self, file_analyses: List[FileAnalysis]) -> List[FileAnalysis]:
        """Filter issues by minimum severity."""
        severity_order = [
            SyntaxSeverity.ERROR,
            SyntaxSeverity.WARNING,
            SyntaxSeverity.INFO,
            SyntaxSeverity.STYLE,
        ]

        min_index = severity_order.index(self.config.min_severity)
        allowed_severities = set(severity_order[:min_index + 1])

        if not self.config.include_style:
            allowed_severities.discard(SyntaxSeverity.STYLE)

        for fa in file_analyses:
            fa.issues = [i for i in fa.issues if i.severity in allowed_severities]
            fa.error_count = sum(1 for i in fa.issues if i.severity == SyntaxSeverity.ERROR)
            fa.warning_count = sum(1 for i in fa.issues if i.severity == SyntaxSeverity.WARNING)
            fa.info_count = sum(1 for i in fa.issues if i.severity == SyntaxSeverity.INFO)
            fa.style_count = sum(1 for i in fa.issues if i.severity == SyntaxSeverity.STYLE)

        return file_analyses

    def generate_report(self, result: SyntaxResult, output_format: str = "text") -> str:
        """Generate a formatted report."""
        linters_used = self._get_linters_to_run()
        if output_format == "json":
            return generate_json_report(result, linters_used)
        elif output_format == "markdown":
            return generate_markdown_report(result, linters_used)
        else:
            return generate_text_report(result, linters_used)
