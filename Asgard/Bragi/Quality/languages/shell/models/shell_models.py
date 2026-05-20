"""
Heimdall Shell Script Analysis Models

Pydantic models for shell script static analysis findings reported by the
regex-based ShellAnalyzer service.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class ShellRuleCategory(str, Enum):
    """Category of a shell script rule finding."""
    SECURITY = "security"
    BUG = "bug"
    STYLE = "style"
    PORTABILITY = "portability"


class ShellSeverity(str, Enum):
    """Severity level for a shell script finding."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ShellFinding(BaseModel):
    """A single finding produced by the ShellAnalyzer."""
    file_path: str = Field(..., description="Absolute path to the file containing the finding")
    line_number: int = Field(..., description="1-based line number of the finding")
    rule_id: str = Field(..., description="Unique rule identifier (e.g. 'shell.eval-injection')")
    category: ShellRuleCategory = Field(..., description="Rule category")
    severity: ShellSeverity = Field(..., description="Severity level")
    title: str = Field(..., description="Short human-readable rule title")
    description: str = Field(..., description="Detailed description of the issue")
    code_snippet: str = Field("", description="The offending line of source code")
    fix_suggestion: str = Field("", description="Suggested remediation")

    class Config:
        use_enum_values = True


class ShellReport(BaseModel):
    """Complete analysis report produced by the ShellAnalyzer."""
    total_findings: int = Field(0, description="Total number of findings")
    error_count: int = Field(0, description="Number of ERROR-severity findings")
    warning_count: int = Field(0, description="Number of WARNING-severity findings")
    info_count: int = Field(0, description="Number of INFO-severity findings")
    findings: List[ShellFinding] = Field(default_factory=list, description="All findings")
    files_analyzed: int = Field(0, description="Number of files analyzed")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan in seconds")
    scanned_at: datetime = Field(default_factory=datetime.now, description="Timestamp of the scan")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: ShellFinding) -> None:
        """Append a finding and update summary counters."""
        self.findings.append(finding)
        self.total_findings += 1
        severity = finding.severity if isinstance(finding.severity, str) else finding.severity.value
        if severity == ShellSeverity.ERROR.value:
            self.error_count += 1
        elif severity == ShellSeverity.WARNING.value:
            self.warning_count += 1
        else:
            self.info_count += 1

    @property
    def has_findings(self) -> bool:
        """Return True when at least one finding exists."""
        return self.total_findings > 0


class ShellAnalysisConfig(BaseModel):
    """Configuration for the ShellAnalyzer."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    include_extensions: List[str] = Field(
        default_factory=lambda: [".sh", ".bash"],
        description="File extensions to include",
    )
    also_check_shebangs: bool = Field(
        True,
        description="Also include files with a shell shebang line regardless of extension",
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "node_modules",
            ".git",
            "__pycache__",
        ],
        description="Glob-style patterns to exclude",
    )
    enabled_rules: Optional[List[str]] = Field(
        None,
        description="Explicit list of rule IDs to run (None means all rules)",
    )
    disabled_rules: List[str] = Field(
        default_factory=list,
        description="Rule IDs to skip",
    )

    class Config:
        use_enum_values = True
