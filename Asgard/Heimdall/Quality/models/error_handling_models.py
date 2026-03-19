"""
Heimdall Error Handling Coverage Analysis Models

Pydantic models for detecting missing error handling around thread targets
and external API calls, where unhandled exceptions can cause silent failures
or process crashes.

Detected Patterns:
- Thread targets (threading.Thread(target=...)) without a top-level try/except
- External calls (requests, urllib, subprocess, aiohttp) not in try/except
- Async functions that await external calls without error handling
"""

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ErrorHandlingType(str, Enum):
    """Types of error handling violations."""
    THREAD_TARGET_NO_EXCEPTION_HANDLING = "thread_target_no_exception_handling"
    UNPROTECTED_EXTERNAL_CALL = "unprotected_external_call"
    ASYNC_EXTERNAL_NO_HANDLING = "async_external_no_handling"


class ErrorHandlingSeverity(str, Enum):
    """Severity levels for error handling violations."""
    HIGH = "high"       # Thread targets without any exception handling
    MEDIUM = "medium"   # External calls not wrapped in try/except
    LOW = "low"         # Minor concern


class ErrorHandlingViolation(BaseModel):
    """Represents a detected error handling violation."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where violation is found")
    column: int = Field(0, description="Column offset in the line")
    code_snippet: str = Field(..., description="The code containing the violation")
    function_name: Optional[str] = Field(None, description="Name of the function with the issue")
    call_expression: Optional[str] = Field(None, description="The external call expression")
    handling_type: ErrorHandlingType = Field(..., description="Type of error handling violation")
    severity: ErrorHandlingSeverity = Field(..., description="Severity level")
    containing_function: Optional[str] = Field(None, description="Function/method name if applicable")
    containing_class: Optional[str] = Field(None, description="Class name if inside a method")
    context_description: str = Field(..., description="Description of the violation context")
    remediation: str = Field(
        "Wrap the call in a try/except block to handle potential exceptions.",
        description="Suggested fix"
    )

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


class ErrorHandlingReport(BaseModel):
    """Complete error handling coverage analysis report."""
    total_violations: int = Field(0, description="Total number of error handling violations found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by violation type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_violations: List[ErrorHandlingViolation] = Field(
        default_factory=list, description="All detected violations"
    )
    most_problematic_files: List[Tuple[str, int]] = Field(
        default_factory=list, description="Files with most violations"
    )
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, violation: ErrorHandlingViolation) -> None:
        """Add an error handling violation to the report."""
        self.detected_violations.append(violation)
        self.total_violations += 1

        handling_type = violation.handling_type if isinstance(violation.handling_type, str) else violation.handling_type.value
        self.violations_by_type[handling_type] = self.violations_by_type.get(handling_type, 0) + 1

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

    def get_violations_by_type(self, handling_type: ErrorHandlingType) -> List[ErrorHandlingViolation]:
        """Get all violations of a specific type."""
        target = handling_type if isinstance(handling_type, str) else handling_type.value
        return [v for v in self.detected_violations if v.handling_type == target]

    def get_violations_by_severity(
        self, severity: ErrorHandlingSeverity
    ) -> List[ErrorHandlingViolation]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_violations if v.severity == target]


class ErrorHandlingConfig(BaseModel):
    """Configuration for error handling coverage scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: ErrorHandlingSeverity = Field(
        ErrorHandlingSeverity.MEDIUM,
        description="Minimum severity to report"
    )
    output_format: str = Field("text", description="Output format: text, json, markdown")
    include_extensions: Optional[List[str]] = Field(
        default_factory=lambda: [".py"],
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
