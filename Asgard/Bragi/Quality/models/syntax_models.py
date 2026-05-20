"""
Syntax analysis models for Heimdall.

Models for syntax checking, linting violations, and code style issues.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class SyntaxSeverity(Enum):
    """Severity levels for syntax issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    STYLE = "style"


class LinterType(Enum):
    """Supported linter types."""
    FLAKE8 = "flake8"
    PYLINT = "pylint"
    MYPY = "mypy"
    RUFF = "ruff"
    ESLINT = "eslint"
    TSC = "tsc"


@dataclass
class SyntaxIssue:
    """Represents a single syntax or linting issue."""
    file_path: str
    line_number: int
    column: int
    code: str
    message: str
    severity: SyntaxSeverity
    linter: LinterType
    fixable: bool = False
    suggested_fix: Optional[str] = None

    @property
    def location(self) -> str:
        """Human-readable location string."""
        return f"{self.file_path}:{self.line_number}:{self.column}"


@dataclass
class FileAnalysis:
    """Analysis result for a single file."""
    file_path: str
    relative_path: str
    issues: List[SyntaxIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    style_count: int = 0

    @property
    def total_issues(self) -> int:
        """Total number of issues."""
        return len(self.issues)

    @property
    def has_errors(self) -> bool:
        """Whether file has any errors."""
        return self.error_count > 0

    @property
    def has_issues(self) -> bool:
        """Whether file has any issues."""
        return self.total_issues > 0


@dataclass
class SyntaxConfig:
    """Configuration for syntax checking."""
    scan_path: Path
    include_extensions: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    linters: Optional[List[LinterType]] = None
    min_severity: SyntaxSeverity = SyntaxSeverity.WARNING
    include_style: bool = False
    fix_mode: bool = False
    output_format: str = "text"
    verbose: bool = False

    def __post_init__(self):
        """Set defaults after initialization."""
        if self.include_extensions is None:
            self.include_extensions = [".py"]
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                "__pycache__",
                ".git",
                ".venv",
                "venv",
                "node_modules",
                ".mypy_cache",
                ".pytest_cache",
                "*.egg-info",
                "build",
                "dist",
            ]
        if self.linters is None:
            self.linters = [LinterType.RUFF]


@dataclass
class SyntaxResult:
    """Complete syntax analysis result."""
    scan_path: str
    scanned_at: datetime
    scan_duration_seconds: float
    config: SyntaxConfig
    file_analyses: List[FileAnalysis] = field(default_factory=list)

    @property
    def total_files_scanned(self) -> int:
        """Total number of files analyzed."""
        return len(self.file_analyses)

    @property
    def files_with_issues(self) -> int:
        """Number of files with issues."""
        return sum(1 for f in self.file_analyses if f.has_issues)

    @property
    def files_with_errors(self) -> int:
        """Number of files with errors."""
        return sum(1 for f in self.file_analyses if f.has_errors)

    @property
    def total_issues(self) -> int:
        """Total number of issues across all files."""
        return sum(f.total_issues for f in self.file_analyses)

    @property
    def total_errors(self) -> int:
        """Total number of errors across all files."""
        return sum(f.error_count for f in self.file_analyses)

    @property
    def total_warnings(self) -> int:
        """Total number of warnings across all files."""
        return sum(f.warning_count for f in self.file_analyses)

    @property
    def total_info(self) -> int:
        """Total number of info messages."""
        return sum(f.info_count for f in self.file_analyses)

    @property
    def total_style(self) -> int:
        """Total number of style issues."""
        return sum(f.style_count for f in self.file_analyses)

    @property
    def has_issues(self) -> bool:
        """Whether any issues were found."""
        return self.total_issues > 0

    @property
    def has_errors(self) -> bool:
        """Whether any errors were found."""
        return self.total_errors > 0

    @property
    def compliance_rate(self) -> float:
        """Percentage of files without issues."""
        if self.total_files_scanned == 0:
            return 100.0
        return ((self.total_files_scanned - self.files_with_issues) / self.total_files_scanned) * 100

    def get_issues_by_severity(self) -> Dict[str, List[SyntaxIssue]]:
        """Group all issues by severity."""
        result: Dict[str, List[SyntaxIssue]] = {
            SyntaxSeverity.ERROR.value: [],
            SyntaxSeverity.WARNING.value: [],
            SyntaxSeverity.INFO.value: [],
            SyntaxSeverity.STYLE.value: [],
        }
        for fa in self.file_analyses:
            for issue in fa.issues:
                result[issue.severity.value].append(issue)
        return result

    def get_issues_by_code(self) -> Dict[str, List[SyntaxIssue]]:
        """Group all issues by error code."""
        result: Dict[str, List[SyntaxIssue]] = {}
        for fa in self.file_analyses:
            for issue in fa.issues:
                if issue.code not in result:
                    result[issue.code] = []
                result[issue.code].append(issue)
        return result

    def get_fixable_issues(self) -> List[SyntaxIssue]:
        """Get all issues that can be auto-fixed."""
        fixable = []
        for fa in self.file_analyses:
            for issue in fa.issues:
                if issue.fixable:
                    fixable.append(issue)
        return fixable
