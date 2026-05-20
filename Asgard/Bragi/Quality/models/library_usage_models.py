"""
Heimdall Library Usage Analysis Models

Pydantic models for detecting forbidden library imports that should use
wrapper libraries instead of direct imports.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ForbiddenImportSeverity(str, Enum):
    """Severity levels for forbidden import violations."""
    LOW = "low"           # Import of deprecated but not critical library
    MEDIUM = "medium"     # Import that may cause issues
    HIGH = "high"         # Critical import that must use wrapper


class ForbiddenImportViolation(BaseModel):
    """Represents a detected forbidden import violation."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where import is found")
    column: int = Field(0, description="Column offset of import")
    import_statement: str = Field(..., description="The import statement text")
    module_name: str = Field(..., description="The forbidden module name")
    severity: ForbiddenImportSeverity = Field(..., description="Severity level")
    remediation: str = Field(..., description="Suggested fix/alternative")
    code_snippet: str = Field("", description="Surrounding code context")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line_number}"

    @property
    def qualified_location(self) -> str:
        """Return fully qualified location."""
        return f"{self.relative_path}:{self.line_number}" if self.relative_path else self.location


class ForbiddenImportReport(BaseModel):
    """Complete forbidden import analysis report."""
    total_violations: int = Field(0, description="Total number of forbidden imports found")
    violations_by_module: Dict[str, int] = Field(default_factory=dict, description="Count by module name")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_violations: List[ForbiddenImportViolation] = Field(default_factory=list, description="All detected violations")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most violations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, violation: ForbiddenImportViolation) -> None:
        """Add a forbidden import violation to the report."""
        self.detected_violations.append(violation)
        self.total_violations += 1

        # Update module count
        self.violations_by_module[violation.module_name] = self.violations_by_module.get(violation.module_name, 0) + 1

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

    def get_violations_by_module(self, module_name: str) -> List[ForbiddenImportViolation]:
        """Get all violations for a specific module."""
        return [v for v in self.detected_violations if v.module_name == module_name]

    def get_violations_by_severity(self, severity: ForbiddenImportSeverity) -> List[ForbiddenImportViolation]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_violations if v.severity == target]


class ForbiddenImportConfig(BaseModel):
    """Configuration for forbidden import scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    forbidden_modules: Dict[str, str] = Field(
        default_factory=lambda: {},
        description="Mapping of forbidden module names to remediation messages"
    )
    allowed_paths: List[str] = Field(
        default_factory=lambda: [
            "**/wrappers/**",
        ],
        description="Glob patterns where forbidden imports are allowed"
    )
    severity: ForbiddenImportSeverity = Field(
        ForbiddenImportSeverity.HIGH,
        description="Default severity for violations"
    )
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
    include_tests: bool = Field(True, description="Include test files")
    verbose: bool = Field(False, description="Show verbose output")

    class Config:
        use_enum_values = True
