"""
Heimdall Lazy Import Analysis Models

Pydantic models for detecting lazy imports (imports inside functions,
methods, or conditional blocks) which violate the coding standard
that ALL imports MUST be at the top of the file.
"""

import os
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from pydantic import BaseModel, Field


class LazyImportType(str, Enum):
    """Types of lazy imports."""
    FUNCTION = "function"           # Import inside a function
    METHOD = "method"               # Import inside a class method
    CONDITIONAL = "conditional"     # Import inside if/else block
    TRY_EXCEPT = "try_except"       # Import inside try/except block
    LOOP = "loop"                   # Import inside a loop
    WITH_BLOCK = "with_block"       # Import inside a with block


class LazyImportSeverity(str, Enum):
    """Severity levels for lazy import violations."""
    LOW = "low"         # Import in rarely-executed code path
    MEDIUM = "medium"   # Import in conditional block
    HIGH = "high"       # Import inside function/method


class LazyImport(BaseModel):
    """Represents a detected lazy import violation."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where import is found")
    import_statement: str = Field(..., description="The import statement text")
    import_type: LazyImportType = Field(..., description="Type of lazy import")
    severity: LazyImportSeverity = Field(..., description="Severity level")
    containing_function: Optional[str] = Field(None, description="Function/method name if applicable")
    containing_class: Optional[str] = Field(None, description="Class name if inside a method")
    context_description: str = Field(..., description="Description of where the import was found")
    remediation: str = Field(
        "Move this import to the top of the file with other module-level imports.",
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


class LazyImportReport(BaseModel):
    """Complete lazy import analysis report."""
    total_violations: int = Field(0, description="Total number of lazy imports found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by import type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_imports: List[LazyImport] = Field(default_factory=list, description="All detected lazy imports")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most violations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, lazy_import: LazyImport) -> None:
        """Add a lazy import violation to the report."""
        self.detected_imports.append(lazy_import)
        self.total_violations += 1

        # Update type count
        import_type = lazy_import.import_type if isinstance(lazy_import.import_type, str) else lazy_import.import_type.value
        self.violations_by_type[import_type] = self.violations_by_type.get(import_type, 0) + 1

        # Update severity count
        severity = lazy_import.severity if isinstance(lazy_import.severity, str) else lazy_import.severity.value
        self.violations_by_severity[severity] = self.violations_by_severity.get(severity, 0) + 1

    @property
    def has_violations(self) -> bool:
        """Check if any violations were detected."""
        return self.total_violations > 0

    @property
    def is_compliant(self) -> bool:
        """Check if codebase is compliant (no violations)."""
        return self.total_violations == 0

    def get_violations_by_type(self, import_type: LazyImportType) -> List[LazyImport]:
        """Get all violations of a specific type."""
        target = import_type if isinstance(import_type, str) else import_type.value
        return [v for v in self.detected_imports if v.import_type == target]

    def get_violations_by_severity(self, severity: LazyImportSeverity) -> List[LazyImport]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_imports if v.severity == target]


class LazyImportConfig(BaseModel):
    """Configuration for lazy import scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: LazyImportSeverity = Field(
        LazyImportSeverity.LOW,
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
