"""
Heimdall Documentation Models

Pydantic models for comment density and documentation coverage analysis.

Tracks:
- Comment lines (single-line #, multi-line docstrings)
- Code lines, blank lines, total lines
- Public API documentation coverage (functions and classes without docstrings)
- Per-file and summary-level reporting
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DocumentationConfig(BaseModel):
    """Configuration for documentation and comment density analysis."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    min_comment_density: float = Field(
        10.0,
        description="Minimum acceptable comment density percentage (comment lines / non-blank lines * 100)"
    )
    min_api_coverage: float = Field(
        70.0,
        description="Minimum acceptable public API documentation coverage percentage"
    )
    include_extensions: List[str] = Field(
        default_factory=lambda: [".py", ".pyw", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".rs", ".kt", ".swift", ".scala"],
        description="File extensions to include in analysis"
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
            "migrations",
            "test_*",
            "*_test.py",
        ],
        description="Glob patterns to exclude from scanning"
    )
    include_tests: bool = Field(False, description="Include test files in analysis")
    output_format: str = Field("text", description="Output format: text, json, markdown")
    verbose: bool = Field(False, description="Verbose output")

    class Config:
        use_enum_values = True


class FunctionDocumentation(BaseModel):
    """Documentation status for a single function or method."""
    name: str = Field(..., description="Function or method name")
    line_number: int = Field(1, description="Starting line number")
    has_docstring: bool = Field(False, description="Whether the function has a docstring")
    is_public: bool = Field(True, description="Whether the function is part of the public API")
    docstring_lines: int = Field(0, description="Number of lines in the docstring (0 if none)")

    class Config:
        use_enum_values = True

    @property
    def needs_documentation(self) -> bool:
        """Check if this function requires documentation."""
        return self.is_public and not self.has_docstring


class ClassDocumentation(BaseModel):
    """Documentation status for a single class."""
    name: str = Field(..., description="Class name")
    line_number: int = Field(1, description="Starting line number")
    has_docstring: bool = Field(False, description="Whether the class has a docstring")
    is_public: bool = Field(True, description="Whether the class is part of the public API")
    docstring_lines: int = Field(0, description="Number of lines in the class docstring")
    methods: List[FunctionDocumentation] = Field(
        default_factory=list,
        description="Method documentation statuses within this class"
    )

    class Config:
        use_enum_values = True

    @property
    def needs_documentation(self) -> bool:
        """Check if this class requires documentation."""
        return self.is_public and not self.has_docstring

    @property
    def undocumented_public_methods(self) -> List[FunctionDocumentation]:
        """Return list of public methods lacking docstrings."""
        return [m for m in self.methods if m.is_public and not m.has_docstring]


class FileDocumentation(BaseModel):
    """Documentation analysis for a single file."""
    path: str = Field(..., description="Path to the file")
    total_lines: int = Field(0, description="Total number of lines in the file")
    code_lines: int = Field(0, description="Number of non-blank, non-comment lines")
    comment_lines: int = Field(0, description="Number of comment and docstring lines")
    blank_lines: int = Field(0, description="Number of blank lines")
    comment_density: float = Field(
        0.0,
        description="Comment density: comment_lines / (total_lines - blank_lines) * 100"
    )
    public_api_coverage: float = Field(
        0.0,
        description="Percentage of public API elements (functions and classes) that have docstrings"
    )
    undocumented_count: int = Field(0, description="Number of undocumented public API elements")
    functions: List[FunctionDocumentation] = Field(
        default_factory=list,
        description="Function-level documentation results"
    )
    classes: List[ClassDocumentation] = Field(
        default_factory=list,
        description="Class-level documentation results"
    )

    class Config:
        use_enum_values = True

    @property
    def meets_density_threshold(self) -> bool:
        """Check if this file meets the minimum comment density."""
        return self.comment_density >= 10.0

    @property
    def meets_coverage_threshold(self) -> bool:
        """Check if this file meets the minimum API coverage."""
        return self.public_api_coverage >= 70.0

    @property
    def total_public_apis(self) -> int:
        """Count total number of public API elements in this file."""
        top_level_funcs = sum(1 for f in self.functions if f.is_public)
        class_count = sum(1 for c in self.classes if c.is_public)
        method_count = sum(
            sum(1 for m in c.methods if m.is_public)
            for c in self.classes
        )
        return top_level_funcs + class_count + method_count


class DocumentationReport(BaseModel):
    """Summary documentation analysis report across all scanned files."""
    overall_comment_density: float = Field(
        0.0,
        description="Aggregate comment density across all files"
    )
    overall_api_coverage: float = Field(
        0.0,
        description="Aggregate public API documentation coverage across all files"
    )
    total_files: int = Field(0, description="Total number of files analyzed")
    total_public_apis: int = Field(0, description="Total public API elements across all files")
    undocumented_apis: int = Field(0, description="Total undocumented public API elements")
    file_results: List[FileDocumentation] = Field(
        default_factory=list,
        description="Per-file documentation results"
    )

    # Metadata
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    @property
    def documented_apis(self) -> int:
        """Number of documented public API elements."""
        return self.total_public_apis - self.undocumented_apis

    @property
    def has_density_issues(self) -> bool:
        """Check whether any files fall below the density threshold."""
        return any(f.comment_density < 10.0 for f in self.file_results)

    @property
    def has_coverage_issues(self) -> bool:
        """Check whether any files fall below the coverage threshold."""
        return any(f.public_api_coverage < 70.0 for f in self.file_results)
