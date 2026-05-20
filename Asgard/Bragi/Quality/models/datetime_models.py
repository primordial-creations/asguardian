"""
Heimdall Datetime Usage Analysis Models

Pydantic models for detecting deprecated and unsafe datetime usage patterns.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class DatetimeIssueType(str, Enum):
    """Types of datetime issues."""
    UTCNOW = "utcnow"                    # datetime.utcnow() - deprecated
    NOW_NO_TZ = "now_no_tz"              # datetime.now() without timezone
    TODAY_NO_TZ = "today_no_tz"          # datetime.today() without timezone
    UTCFROMTIMESTAMP = "utcfromtimestamp"  # datetime.utcfromtimestamp() - deprecated


class DatetimeSeverity(str, Enum):
    """Severity levels for datetime violations."""
    LOW = "low"         # Potentially problematic but may be intentional
    MEDIUM = "medium"   # Should be addressed but not critical
    HIGH = "high"       # Deprecated API or likely to cause timezone bugs


class DatetimeViolation(BaseModel):
    """Represents a detected datetime usage violation."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where issue is found")
    column: int = Field(0, description="Column offset")
    code_snippet: str = Field(..., description="The problematic code")
    issue_type: DatetimeIssueType = Field(..., description="Type of datetime issue")
    severity: DatetimeSeverity = Field(..., description="Severity level")
    remediation: str = Field(..., description="Suggested fix")
    containing_function: Optional[str] = Field(None, description="Function name if applicable")
    containing_class: Optional[str] = Field(None, description="Class name if inside a method")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"

    @property
    def qualified_location(self) -> str:
        """Return fully qualified location with class/function."""
        parts = []
        if self.containing_class:
            parts.append(self.containing_class)
        if self.containing_function:
            parts.append(self.containing_function)
        if parts:
            return f"{self.location} ({'.'.join(parts)})"
        return self.location


# Default remediations for each issue type
DATETIME_REMEDIATIONS = {
    DatetimeIssueType.UTCNOW: "Replace datetime.utcnow() with datetime.now(timezone.utc). The utcnow() method is deprecated in Python 3.12+.",
    DatetimeIssueType.NOW_NO_TZ: "Replace datetime.now() with datetime.now(timezone.utc) or datetime.now(tz) to ensure timezone-aware datetime.",
    DatetimeIssueType.TODAY_NO_TZ: "Replace datetime.today() with datetime.now(timezone.utc).date() or use date.today() if you only need the date.",
    DatetimeIssueType.UTCFROMTIMESTAMP: "Replace datetime.utcfromtimestamp(ts) with datetime.fromtimestamp(ts, tz=timezone.utc). The utcfromtimestamp() method is deprecated.",
}


class DatetimeReport(BaseModel):
    """Complete datetime usage analysis report."""
    total_violations: int = Field(0, description="Total number of datetime issues found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by issue type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_violations: List[DatetimeViolation] = Field(default_factory=list, description="All detected violations")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most violations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, violation: DatetimeViolation) -> None:
        """Add a datetime violation to the report."""
        self.detected_violations.append(violation)
        self.total_violations += 1

        # Update type count
        issue_type = violation.issue_type if isinstance(violation.issue_type, str) else violation.issue_type.value
        self.violations_by_type[issue_type] = self.violations_by_type.get(issue_type, 0) + 1

        # Update severity count
        severity = violation.severity if isinstance(violation.severity, str) else violation.severity.value
        self.violations_by_severity[severity] = self.violations_by_severity.get(severity, 0) + 1

    @property
    def has_violations(self) -> bool:
        """Check if any violations were detected."""
        return self.total_violations > 0

    @property
    def is_compliant(self) -> bool:
        """Check if codebase is compliant (no violations)."""
        return self.total_violations == 0

    def get_violations_by_type(self, issue_type: DatetimeIssueType) -> List[DatetimeViolation]:
        """Get all violations of a specific type."""
        target = issue_type if isinstance(issue_type, str) else issue_type.value
        return [v for v in self.detected_violations if v.issue_type == target]

    def get_violations_by_severity(self, severity: DatetimeSeverity) -> List[DatetimeViolation]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_violations if v.severity == target]


class DatetimeConfig(BaseModel):
    """Configuration for datetime usage scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    check_utcnow: bool = Field(True, description="Check for deprecated datetime.utcnow()")
    check_now_no_tz: bool = Field(True, description="Check for datetime.now() without timezone")
    check_today_no_tz: bool = Field(True, description="Check for datetime.today() without timezone")
    check_utcfromtimestamp: bool = Field(True, description="Check for deprecated datetime.utcfromtimestamp()")
    output_format: str = Field("text", description="Output format: text, json, markdown")
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
    allowed_patterns: List[str] = Field(
        default_factory=list,
        description="File patterns where datetime issues are allowed"
    )
    include_tests: bool = Field(True, description="Include test files")
    verbose: bool = Field(False, description="Show verbose output")

    class Config:
        use_enum_values = True
