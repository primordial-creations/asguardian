"""
Heimdall Daemon Thread Analysis Models

Pydantic models for detecting daemon thread lifecycle issues:
- Daemon threads with no join() call (uncontrolled lifecycle)
- Daemon threads stored only in local variables (reference loss risk)
- Event.wait() patterns where only daemon threads can trigger .set()
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class DaemonThreadIssueType(str, Enum):
    """Types of daemon thread lifecycle issues."""
    NO_JOIN = "no_join"               # daemon=True thread with no join() in scope
    LOCAL_VAR_ONLY = "local_var_only"  # daemon=True thread in local var (reference may be lost)
    EVENT_SET_BY_DAEMON = "event_set_by_daemon"  # Event.wait() only set by daemon threads


class DaemonThreadSeverity(str, Enum):
    """Severity levels for daemon thread violations."""
    MEDIUM = "medium"  # Daemon thread in local var (reference loss risk)
    LOW = "low"        # Daemon thread with no join (lifecycle monitoring risk)


class DaemonThreadIssue(BaseModel):
    """Represents a detected daemon thread lifecycle issue."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where issue is found")
    class_name: Optional[str] = Field(None, description="Class containing the issue if applicable")
    method_name: Optional[str] = Field(None, description="Method containing the issue")
    issue_type: DaemonThreadIssueType = Field(..., description="Type of daemon thread issue")
    severity: DaemonThreadSeverity = Field(..., description="Severity level")
    description: str = Field(..., description="Description of the issue")
    thread_variable: Optional[str] = Field(None, description="Name of the thread variable")
    remediation: str = Field(..., description="Suggested fix")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"

    @property
    def qualified_location(self) -> str:
        """Return fully qualified location with class/method."""
        parts = []
        if self.class_name:
            parts.append(self.class_name)
        if self.method_name:
            parts.append(self.method_name)
        if parts:
            return f"{self.location} ({'.'.join(parts)})"
        return self.location


class DaemonThreadReport(BaseModel):
    """Complete daemon thread analysis report."""
    total_violations: int = Field(0, description="Total number of daemon thread issues found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by issue type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_issues: List[DaemonThreadIssue] = Field(default_factory=list, description="All detected issues")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most violations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, issue: DaemonThreadIssue) -> None:
        """Add a daemon thread issue to the report."""
        self.detected_issues.append(issue)
        self.total_violations += 1

        issue_type = issue.issue_type if isinstance(issue.issue_type, str) else issue.issue_type.value
        self.violations_by_type[issue_type] = self.violations_by_type.get(issue_type, 0) + 1

        severity = issue.severity if isinstance(issue.severity, str) else issue.severity.value
        self.violations_by_severity[severity] = self.violations_by_severity.get(severity, 0) + 1

    @property
    def has_violations(self) -> bool:
        """Check if any violations were detected."""
        return self.total_violations > 0

    @property
    def is_compliant(self) -> bool:
        """Check if codebase is compliant (no violations)."""
        return self.total_violations == 0

    def get_violations_by_severity(self, severity: DaemonThreadSeverity) -> List[DaemonThreadIssue]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_issues if v.severity == target]

    def get_violations_by_type(self, issue_type: DaemonThreadIssueType) -> List[DaemonThreadIssue]:
        """Get all violations of a specific type."""
        target = issue_type if isinstance(issue_type, str) else issue_type.value
        return [v for v in self.detected_issues if v.issue_type == target]


class DaemonThreadConfig(BaseModel):
    """Configuration for daemon thread scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: DaemonThreadSeverity = Field(
        DaemonThreadSeverity.LOW,
        description="Minimum severity to report"
    )
    output_format: str = Field("text", description="Output format: text, json, markdown")
    include_extensions: Optional[List[str]] = Field(
        default_factory=lambda: [".py", ".pyw", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".rs"],
        description="File extensions to include"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "*.pyc",
        ],
        description="Patterns to exclude"
    )
    include_tests: bool = Field(True, description="Include test files")
    verbose: bool = Field(False, description="Show verbose output")

    class Config:
        use_enum_values = True
