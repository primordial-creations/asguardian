"""
Heimdall Resource Cleanup Analysis Models

Pydantic models for detecting resource leaks where file handles, streams,
connections, or collections are opened/populated without proper cleanup,
violating resource safety standards.

Detected Patterns:
- open() calls not inside a 'with' block
- Collections (list, deque) appended/extended without being cleared
- Sockets, subprocess.Popen, or other connections not in a 'with' block
"""

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ResourceCleanupType(str, Enum):
    """Types of resource cleanup violations."""
    FILE_OPEN_NO_WITH = "file_open_no_with"               # open() outside with block
    CONNECTION_NO_WITH = "connection_no_with"             # socket/Popen outside with block
    COLLECTION_NO_CLEAR = "collection_no_clear"           # list/deque appended but never cleared


class ResourceCleanupSeverity(str, Enum):
    """Severity levels for resource cleanup violations."""
    HIGH = "high"       # Direct resource leak (file/connection not closed)
    MEDIUM = "medium"   # Potential leak (collection grows unbounded)
    LOW = "low"         # Minor concern


class ResourceCleanupViolation(BaseModel):
    """Represents a detected resource cleanup violation."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where violation is found")
    column: int = Field(0, description="Column offset in the line")
    code_snippet: str = Field(..., description="The code containing the violation")
    resource_name: Optional[str] = Field(None, description="Name of the resource (file, variable, etc.)")
    cleanup_type: ResourceCleanupType = Field(..., description="Type of cleanup violation")
    severity: ResourceCleanupSeverity = Field(..., description="Severity level")
    containing_function: Optional[str] = Field(None, description="Function/method name if applicable")
    containing_class: Optional[str] = Field(None, description="Class name if inside a method")
    context_description: str = Field(..., description="Description of the violation context")
    remediation: str = Field(
        "Use a 'with' statement to ensure the resource is properly closed.",
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


class ResourceCleanupReport(BaseModel):
    """Complete resource cleanup analysis report."""
    total_violations: int = Field(0, description="Total number of cleanup violations found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by violation type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_violations: List[ResourceCleanupViolation] = Field(
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

    def add_violation(self, violation: ResourceCleanupViolation) -> None:
        """Add a resource cleanup violation to the report."""
        self.detected_violations.append(violation)
        self.total_violations += 1

        cleanup_type = violation.cleanup_type if isinstance(violation.cleanup_type, str) else violation.cleanup_type.value
        self.violations_by_type[cleanup_type] = self.violations_by_type.get(cleanup_type, 0) + 1

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

    def get_violations_by_type(self, cleanup_type: ResourceCleanupType) -> List[ResourceCleanupViolation]:
        """Get all violations of a specific type."""
        target = cleanup_type if isinstance(cleanup_type, str) else cleanup_type.value
        return [v for v in self.detected_violations if v.cleanup_type == target]

    def get_violations_by_severity(
        self, severity: ResourceCleanupSeverity
    ) -> List[ResourceCleanupViolation]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_violations if v.severity == target]


class ResourceCleanupConfig(BaseModel):
    """Configuration for resource cleanup scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: ResourceCleanupSeverity = Field(
        ResourceCleanupSeverity.MEDIUM,
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
