"""
Heimdall Naming Convention Models

Pydantic models for Python PEP 8 naming convention enforcement.

Checks:
- Functions/methods: snake_case
- Variables (module-level assignments): snake_case
- Classes: PascalCase (CapWords)
- Constants (ALL_CAPS module-level): UPPER_CASE_WITH_UNDERSCORES
- Private members: allowed _ prefix variants of their type rules
- Dunder methods: exempt
- Type aliases (single uppercase letters like T, K, V): exempt
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NamingConvention(str, Enum):
    """Supported naming convention styles."""
    SNAKE_CASE = "snake_case"
    PASCAL_CASE = "pascal_case"
    UPPER_CASE = "upper_case"
    CAMEL_CASE = "camel_case"


class NamingViolation(BaseModel):
    """A single naming convention violation."""
    file_path: str = Field(..., description="Path to the file containing the violation")
    line_number: int = Field(..., description="Line number of the violation")
    element_type: str = Field(
        ...,
        description="Type of code element: function, class, variable, constant, method"
    )
    element_name: str = Field(..., description="The actual name found in the code")
    expected_convention: NamingConvention = Field(
        ...,
        description="The expected naming convention for this element type"
    )
    description: str = Field("", description="Human-readable description of the violation")

    class Config:
        use_enum_values = True


class NamingConfig(BaseModel):
    """Configuration for naming convention scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    check_functions: bool = Field(True, description="Check function and method names")
    check_classes: bool = Field(True, description="Check class names")
    check_variables: bool = Field(True, description="Check module-level variable names")
    check_constants: bool = Field(True, description="Check module-level constant names")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "migrations",
        ],
        description="Glob patterns to exclude from scanning"
    )
    allow_list: List[str] = Field(
        default_factory=list,
        description="Names to exclude from convention checking (exact matches)"
    )
    include_extensions: List[str] = Field(
        default_factory=lambda: [".py"],
        description="File extensions to include"
    )
    include_tests: bool = Field(True, description="Include test files in analysis")
    output_format: str = Field("text", description="Output format: text, json, markdown")
    verbose: bool = Field(False, description="Verbose output")

    class Config:
        use_enum_values = True


class NamingReport(BaseModel):
    """Summary of naming convention violations across all scanned files."""
    total_violations: int = Field(0, description="Total number of naming violations found")
    violations_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of violations grouped by element type"
    )
    file_results: Dict[str, List[NamingViolation]] = Field(
        default_factory=dict,
        description="Violations grouped by file path"
    )

    # Metadata
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    @property
    def files_with_violations(self) -> int:
        """Number of files that have at least one violation."""
        return sum(1 for violations in self.file_results.values() if violations)

    @property
    def has_violations(self) -> bool:
        """Check if any violations were found."""
        return self.total_violations > 0

    def add_violation(self, violation: NamingViolation) -> None:
        """Add a violation to the report."""
        file_path = violation.file_path
        if file_path not in self.file_results:
            self.file_results[file_path] = []
        self.file_results[file_path].append(violation)

        self.total_violations += 1

        element_type = violation.element_type
        self.violations_by_type[element_type] = (
            self.violations_by_type.get(element_type, 0) + 1
        )
