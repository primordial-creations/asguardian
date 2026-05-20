"""
Heimdall Thread Safety Analysis Models

Pydantic models for detecting thread safety issues in Python code:
- Instance attributes accessed by thread targets but not initialized in __init__
- Shared mutable collections used across threads without synchronization
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class ThreadSafetyIssueType(str, Enum):
    """Types of thread safety issues."""
    UNINITIALIZED_ATTR = "uninitialized_attr"          # Attr used in thread target not set in __init__
    SHARED_MUTABLE_COLLECTION = "shared_mutable_collection"  # list/dict/deque without lock protection
    THREAD_TARGET_ATTR_ACCESS = "thread_target_attr_access"  # Thread target accesses unprotected self attrs


class ThreadSafetySeverity(str, Enum):
    """Severity levels for thread safety violations."""
    HIGH = "high"     # Attribute not initialized in __init__ but accessed by thread target
    MEDIUM = "medium"  # Shared mutable collection without synchronization


class ThreadSafetyIssue(BaseModel):
    """Represents a detected thread safety issue."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where issue is found")
    class_name: str = Field(..., description="Class containing the issue")
    issue_type: ThreadSafetyIssueType = Field(..., description="Type of thread safety issue")
    severity: ThreadSafetySeverity = Field(..., description="Severity level")
    description: str = Field(..., description="Description of the issue")
    attribute_name: Optional[str] = Field(None, description="Attribute involved if applicable")
    thread_target_method: Optional[str] = Field(None, description="Thread target method if applicable")
    remediation: str = Field(..., description="Suggested fix")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"

    @property
    def qualified_location(self) -> str:
        """Return fully qualified location with class name."""
        return f"{self.location} ({self.class_name})"


class ThreadSafetyReport(BaseModel):
    """Complete thread safety analysis report."""
    total_violations: int = Field(0, description="Total number of thread safety issues found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by issue type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_issues: List[ThreadSafetyIssue] = Field(default_factory=list, description="All detected issues")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most violations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, issue: ThreadSafetyIssue) -> None:
        """Add a thread safety issue to the report."""
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

    def get_violations_by_severity(self, severity: ThreadSafetySeverity) -> List[ThreadSafetyIssue]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_issues if v.severity == target]

    def get_violations_by_type(self, issue_type: ThreadSafetyIssueType) -> List[ThreadSafetyIssue]:
        """Get all violations of a specific type."""
        target = issue_type if isinstance(issue_type, str) else issue_type.value
        return [v for v in self.detected_issues if v.issue_type == target]


class ThreadSafetyConfig(BaseModel):
    """Configuration for thread safety scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: ThreadSafetySeverity = Field(
        ThreadSafetySeverity.MEDIUM,
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
