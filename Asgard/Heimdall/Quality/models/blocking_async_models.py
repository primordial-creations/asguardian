"""
Heimdall Blocking Call in Async Context Analysis Models

Pydantic models for detecting blocking operations inside async functions,
which stall the event loop and degrade application throughput.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class BlockingCallType(str, Enum):
    """Types of blocking calls detected inside async functions."""
    TIME_SLEEP = "time_sleep"
    REQUESTS_HTTP = "requests_http"
    OPEN_FILE_IO = "open_file_io"
    SUBPROCESS_CALL = "subprocess_call"
    URLLIB_CALL = "urllib_call"


class BlockingAsyncSeverity(str, Enum):
    """Severity levels for blocking-in-async violations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BlockingCall(BaseModel):
    """Represents a detected blocking call inside an async function."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where the blocking call appears")
    call_expression: str = Field(..., description="Source text of the blocking call")
    blocking_type: BlockingCallType = Field(..., description="Category of blocking call")
    severity: BlockingAsyncSeverity = Field(
        BlockingAsyncSeverity.HIGH, description="Severity level"
    )
    containing_function: Optional[str] = Field(None, description="Async function/method name")
    containing_class: Optional[str] = Field(None, description="Class name if inside a method")
    context_description: str = Field(..., description="Description of the blocking context")
    remediation: str = Field(..., description="Suggested async-safe alternative")

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


class BlockingAsyncReport(BaseModel):
    """Complete blocking-in-async analysis report."""
    total_violations: int = Field(0, description="Total blocking calls found")
    violations_by_type: Dict[str, int] = Field(
        default_factory=dict, description="Count by blocking call type"
    )
    violations_by_severity: Dict[str, int] = Field(
        default_factory=dict, description="Count by severity"
    )
    detected_calls: List[BlockingCall] = Field(
        default_factory=list, description="All detected blocking calls"
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

    def add_violation(self, call: BlockingCall) -> None:
        """Add a blocking call violation to the report."""
        self.detected_calls.append(call)
        self.total_violations += 1

        blocking_type = call.blocking_type if isinstance(call.blocking_type, str) else call.blocking_type.value
        self.violations_by_type[blocking_type] = self.violations_by_type.get(blocking_type, 0) + 1

        severity = call.severity if isinstance(call.severity, str) else call.severity.value
        self.violations_by_severity[severity] = self.violations_by_severity.get(severity, 0) + 1

    @property
    def has_violations(self) -> bool:
        """Check if any violations were detected."""
        return self.total_violations > 0

    @property
    def is_compliant(self) -> bool:
        """Check if codebase is compliant (no violations)."""
        return self.total_violations == 0

    def get_violations_by_type(self, blocking_type: BlockingCallType) -> List[BlockingCall]:
        """Get all violations of a specific blocking type."""
        target = blocking_type if isinstance(blocking_type, str) else blocking_type.value
        return [v for v in self.detected_calls if v.blocking_type == target]

    def get_violations_by_severity(self, severity: BlockingAsyncSeverity) -> List[BlockingCall]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_calls if v.severity == target]


class BlockingAsyncConfig(BaseModel):
    """Configuration for blocking-in-async scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: BlockingAsyncSeverity = Field(
        BlockingAsyncSeverity.HIGH,
        description="Minimum severity to report",
    )
    output_format: str = Field("text", description="Output format: text, json, markdown")
    include_extensions: Optional[List[str]] = Field(
        default_factory=lambda: [".py", ".pyw", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".rs"],
        description="File extensions to include",
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
        description="Patterns to exclude",
    )
    include_tests: bool = Field(True, description="Include test files")
    verbose: bool = Field(False, description="Show verbose output")

    class Config:
        use_enum_values = True
