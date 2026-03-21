"""
Unified Output Formatter - Base Types

Core types used by the output formatter and its helpers.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class OutputFormat(str, Enum):
    """Supported output formats."""
    TEXT = "text"
    JSON = "json"
    GITHUB = "github"
    HTML = "html"
    MARKDOWN = "markdown"


class Severity(str, Enum):
    """Severity levels for issues."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"

    @property
    def github_level(self) -> str:
        """Get GitHub Actions annotation level."""
        if self in (Severity.CRITICAL, Severity.ERROR):
            return "error"
        elif self == Severity.WARNING:
            return "warning"
        else:
            return "notice"

    @property
    def color(self) -> str:
        """Get ANSI color code."""
        colors = {
            Severity.CRITICAL: "\033[1;31m",
            Severity.ERROR: "\033[0;31m",
            Severity.WARNING: "\033[0;33m",
            Severity.INFO: "\033[0;34m",
            Severity.DEBUG: "\033[0;90m",
        }
        return colors.get(self, "")

    @property
    def reset(self) -> str:
        """Get ANSI reset code."""
        return "\033[0m"


@dataclass
class FormattedResult:
    """A single formatted result/issue."""
    message: str
    severity: Severity = Severity.INFO
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None
    category: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> str:
        """Get formatted location string."""
        if not self.file_path:
            return ""
        loc = self.file_path
        if self.line_number:
            loc += f":{self.line_number}"
            if self.column:
                loc += f":{self.column}"
        return loc


@dataclass
class FormattedReport:
    """A validation/analysis report containing multiple issues."""
    title: str = "Report"
    file_path: Optional[str] = None
    total_files: int = 0
    passed: bool = True
    score: float = 100.0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: List[FormattedResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


FormattedIssue = FormattedResult
