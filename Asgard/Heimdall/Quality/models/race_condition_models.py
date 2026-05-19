"""
Heimdall Race Condition Detection Models

Pydantic models for detecting race condition patterns in Python code:
- Thread start before thread reference is stored (unreliable join)
- Self attribute assignment after thread start (thread reads stale state)
- Check-then-act on shared state without synchronization
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class RaceConditionType(str, Enum):
    """Types of race condition patterns."""
    START_BEFORE_STORE = "start_before_store"    # thread.start() before self._thread = thread
    ASSIGN_AFTER_START = "assign_after_start"    # self.attr = value after thread.start()
    CHECK_THEN_ACT = "check_then_act"            # if self.x: self.x.do() without lock


class RaceConditionSeverity(str, Enum):
    """Severity levels for race condition violations."""
    HIGH = "high"  # All race conditions are high severity


class RaceConditionIssue(BaseModel):
    """Represents a detected race condition pattern."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where issue is found")
    class_name: Optional[str] = Field(None, description="Class containing the issue if applicable")
    method_name: Optional[str] = Field(None, description="Method containing the issue")
    race_type: RaceConditionType = Field(..., description="Type of race condition")
    severity: RaceConditionSeverity = Field(RaceConditionSeverity.HIGH, description="Severity level")
    description: str = Field(..., description="Description of the race condition")
    code_snippet: str = Field("", description="Relevant code snippet")
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


class RaceConditionReport(BaseModel):
    """Complete race condition analysis report."""
    total_violations: int = Field(0, description="Total number of race conditions found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by race type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_issues: List[RaceConditionIssue] = Field(default_factory=list, description="All detected race conditions")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most violations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, issue: RaceConditionIssue) -> None:
        """Add a race condition issue to the report."""
        self.detected_issues.append(issue)
        self.total_violations += 1

        race_type = issue.race_type if isinstance(issue.race_type, str) else issue.race_type.value
        self.violations_by_type[race_type] = self.violations_by_type.get(race_type, 0) + 1

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

    def get_violations_by_type(self, race_type: RaceConditionType) -> List[RaceConditionIssue]:
        """Get all violations of a specific race type."""
        target = race_type if isinstance(race_type, str) else race_type.value
        return [v for v in self.detected_issues if v.race_type == target]

    def get_violations_by_severity(self, severity: RaceConditionSeverity) -> List[RaceConditionIssue]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_issues if v.severity == target]


class RaceConditionConfig(BaseModel):
    """Configuration for race condition scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: RaceConditionSeverity = Field(
        RaceConditionSeverity.HIGH,
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
