"""
Heimdall Future/Promise Leak Analysis Models

Pydantic models for detecting futures, asyncio tasks, and threads that
are created but never properly resolved, awaited, or joined.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class FutureLeakType(str, Enum):
    """Types of future/promise leaks."""
    ASYNCIO_TASK = "asyncio_task"
    EXECUTOR_SUBMIT = "executor_submit"
    CONCURRENT_FUTURE = "concurrent_future"
    THREAD_NOT_JOINED = "thread_not_joined"


class FutureLeakSeverity(str, Enum):
    """Severity levels for future leak violations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FutureLeak(BaseModel):
    """Represents a detected future/promise leak."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where the future or thread is created")
    variable_name: str = Field(..., description="Variable holding the future or thread")
    leak_type: FutureLeakType = Field(..., description="Type of future leak")
    severity: FutureLeakSeverity = Field(..., description="Severity level")
    containing_function: Optional[str] = Field(None, description="Function/method name")
    containing_class: Optional[str] = Field(None, description="Class name if inside a method")
    context_description: str = Field(..., description="Description of the leak context")
    remediation: str = Field(..., description="Suggested fix")

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


class FutureLeakReport(BaseModel):
    """Complete future/promise leak analysis report."""
    total_violations: int = Field(0, description="Total number of leaks found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by leak type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_leaks: List[FutureLeak] = Field(default_factory=list, description="All detected leaks")
    most_problematic_files: List[Tuple[str, int]] = Field(
        default_factory=list, description="Files with most violations"
    )
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, leak: FutureLeak) -> None:
        """Add a future leak violation to the report."""
        self.detected_leaks.append(leak)
        self.total_violations += 1

        leak_type = leak.leak_type if isinstance(leak.leak_type, str) else leak.leak_type.value
        self.violations_by_type[leak_type] = self.violations_by_type.get(leak_type, 0) + 1

        severity = leak.severity if isinstance(leak.severity, str) else leak.severity.value
        self.violations_by_severity[severity] = self.violations_by_severity.get(severity, 0) + 1

    @property
    def has_violations(self) -> bool:
        """Check if any violations were detected."""
        return self.total_violations > 0

    @property
    def is_compliant(self) -> bool:
        """Check if codebase is compliant (no violations)."""
        return self.total_violations == 0

    def get_violations_by_type(self, leak_type: FutureLeakType) -> List[FutureLeak]:
        """Get all violations of a specific type."""
        target = leak_type if isinstance(leak_type, str) else leak_type.value
        return [v for v in self.detected_leaks if v.leak_type == target]

    def get_violations_by_severity(self, severity: FutureLeakSeverity) -> List[FutureLeak]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_leaks if v.severity == target]


class FutureLeakConfig(BaseModel):
    """Configuration for future/promise leak scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: FutureLeakSeverity = Field(
        FutureLeakSeverity.MEDIUM,
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
