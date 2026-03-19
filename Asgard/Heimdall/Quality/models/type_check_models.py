"""
Heimdall Type Checking Models

Pydantic models for static type checking analysis using Pyright.
Provides Pylance-equivalent type checking across the entire codebase.
"""

import os
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TypeCheckSeverity(str, Enum):
    """Severity levels for type check diagnostics."""
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class TypeCheckCategory(str, Enum):
    """Categories of type checking diagnostics matching Pylance/Pyright rules."""
    TYPE_MISMATCH = "type_mismatch"
    MISSING_IMPORT = "missing_import"
    UNDEFINED_VARIABLE = "undefined_variable"
    ARGUMENT_ERROR = "argument_error"
    RETURN_TYPE = "return_type"
    ATTRIBUTE_ERROR = "attribute_error"
    ASSIGNMENT_ERROR = "assignment_error"
    OPERATOR_ERROR = "operator_error"
    OVERRIDE_ERROR = "override_error"
    GENERIC_ERROR = "generic_error"
    PROTOCOL_ERROR = "protocol_error"
    TYPED_DICT_ERROR = "typed_dict_error"
    OVERLOAD_ERROR = "overload_error"
    UNREACHABLE_CODE = "unreachable_code"
    DEPRECATED = "deprecated"
    GENERAL = "general"


# Map pyright rule names to categories
RULE_CATEGORY_MAP: Dict[str, TypeCheckCategory] = {
    "reportMissingImports": TypeCheckCategory.MISSING_IMPORT,
    "reportMissingModuleSource": TypeCheckCategory.MISSING_IMPORT,
    "reportMissingTypeStubs": TypeCheckCategory.MISSING_IMPORT,
    "reportUndefinedVariable": TypeCheckCategory.UNDEFINED_VARIABLE,
    "reportGeneralClassIssue": TypeCheckCategory.GENERAL,
    "reportArgumentType": TypeCheckCategory.ARGUMENT_ERROR,
    "reportCallIssue": TypeCheckCategory.ARGUMENT_ERROR,
    "reportIndexIssue": TypeCheckCategory.ARGUMENT_ERROR,
    "reportReturnType": TypeCheckCategory.RETURN_TYPE,
    "reportAttributeAccessIssue": TypeCheckCategory.ATTRIBUTE_ERROR,
    "reportAssignmentType": TypeCheckCategory.ASSIGNMENT_ERROR,
    "reportOperatorIssue": TypeCheckCategory.OPERATOR_ERROR,
    "reportOverrideIssue": TypeCheckCategory.OVERRIDE_ERROR,
    "reportIncompatibleMethodOverride": TypeCheckCategory.OVERRIDE_ERROR,
    "reportIncompatibleVariableOverride": TypeCheckCategory.OVERRIDE_ERROR,
    "reportGeneralTypeIssues": TypeCheckCategory.GENERAL,
    "reportOptionalMemberAccess": TypeCheckCategory.ATTRIBUTE_ERROR,
    "reportOptionalCall": TypeCheckCategory.TYPE_MISMATCH,
    "reportOptionalIterable": TypeCheckCategory.TYPE_MISMATCH,
    "reportOptionalSubscript": TypeCheckCategory.TYPE_MISMATCH,
    "reportPrivateUsage": TypeCheckCategory.ATTRIBUTE_ERROR,
    "reportPrivateImportUsage": TypeCheckCategory.MISSING_IMPORT,
    "reportUnusedImport": TypeCheckCategory.MISSING_IMPORT,
    "reportUnusedVariable": TypeCheckCategory.UNDEFINED_VARIABLE,
    "reportUnusedExpression": TypeCheckCategory.GENERAL,
    "reportUnnecessaryIsInstance": TypeCheckCategory.TYPE_MISMATCH,
    "reportUnnecessaryCast": TypeCheckCategory.TYPE_MISMATCH,
    "reportDeprecated": TypeCheckCategory.DEPRECATED,
    "reportUnreachable": TypeCheckCategory.UNREACHABLE_CODE,
    "reportPossiblyUnbound": TypeCheckCategory.UNDEFINED_VARIABLE,
    "reportTypedDictNotRequiredAccess": TypeCheckCategory.TYPED_DICT_ERROR,
    "reportOverlappingOverload": TypeCheckCategory.OVERLOAD_ERROR,
}


class TypeCheckDiagnostic(BaseModel):
    """A single type checking diagnostic (error/warning)."""
    file_path: str = Field(..., description="Absolute path to the file")
    relative_path: str = Field("", description="Relative path from scan root")
    line: int = Field(..., description="Line number (1-based)")
    column: int = Field(0, description="Column number (0-based)")
    end_line: int = Field(0, description="End line number")
    end_column: int = Field(0, description="End column number")
    severity: TypeCheckSeverity = Field(..., description="Diagnostic severity")
    message: str = Field(..., description="Human-readable diagnostic message")
    rule: str = Field("", description="Pyright rule name (e.g. reportMissingImports)")
    category: TypeCheckCategory = Field(TypeCheckCategory.GENERAL, description="Diagnostic category")

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        return f"{os.path.basename(self.file_path)}:{self.line}:{self.column}"

    @property
    def qualified_location(self) -> str:
        """Return full location string with relative path."""
        return f"{self.relative_path}:{self.line}:{self.column}"


class FileTypeCheckStats(BaseModel):
    """Type checking statistics for a single file."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    error_count: int = Field(0, description="Number of errors")
    warning_count: int = Field(0, description="Number of warnings")
    info_count: int = Field(0, description="Number of informational diagnostics")
    diagnostics: List[TypeCheckDiagnostic] = Field(default_factory=list, description="All diagnostics for this file")

    class Config:
        use_enum_values = True

    @property
    def total_issues(self) -> int:
        """Total number of issues in this file."""
        return self.error_count + self.warning_count + self.info_count

    @property
    def has_errors(self) -> bool:
        """Check if file has any errors."""
        return self.error_count > 0


class TypeCheckReport(BaseModel):
    """Complete type checking analysis report."""
    total_errors: int = Field(0, description="Total number of errors")
    total_warnings: int = Field(0, description="Total number of warnings")
    total_info: int = Field(0, description="Total number of informational diagnostics")
    errors_by_category: Dict[str, int] = Field(default_factory=dict, description="Error counts by category")
    errors_by_rule: Dict[str, int] = Field(default_factory=dict, description="Error counts by pyright rule")
    files_analyzed: List[FileTypeCheckStats] = Field(default_factory=list, description="Stats per file")
    all_diagnostics: List[TypeCheckDiagnostic] = Field(default_factory=list, description="All diagnostics across all files")
    files_scanned: int = Field(0, description="Number of files scanned by pyright")
    files_with_errors: int = Field(0, description="Number of files with at least one error")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")
    pyright_version: str = Field("", description="Pyright version used")
    type_checking_mode: str = Field("basic", description="Pyright type checking mode used")
    exit_code: int = Field(0, description="Pyright exit code")

    class Config:
        use_enum_values = True

    def add_diagnostic(self, diagnostic: TypeCheckDiagnostic) -> None:
        """Add a diagnostic to the report."""
        self.all_diagnostics.append(diagnostic)

        if diagnostic.severity == TypeCheckSeverity.ERROR.value:
            self.total_errors += 1
        elif diagnostic.severity == TypeCheckSeverity.WARNING.value:
            self.total_warnings += 1
        else:
            self.total_info += 1

        # Track by category
        cat = diagnostic.category
        self.errors_by_category[cat] = self.errors_by_category.get(cat, 0) + 1

        # Track by rule
        if diagnostic.rule:
            self.errors_by_rule[diagnostic.rule] = self.errors_by_rule.get(diagnostic.rule, 0) + 1

    def add_file_stats(self, file_stats: FileTypeCheckStats) -> None:
        """Add file statistics to the report."""
        self.files_analyzed.append(file_stats)
        if file_stats.has_errors:
            self.files_with_errors += 1

    @property
    def total_issues(self) -> int:
        """Total number of all issues."""
        return self.total_errors + self.total_warnings + self.total_info

    @property
    def has_violations(self) -> bool:
        """Check if there are any type errors."""
        return self.total_errors > 0

    @property
    def is_compliant(self) -> bool:
        """Check if codebase passes type checking."""
        return not self.has_violations

    def get_files_with_errors(self) -> List[FileTypeCheckStats]:
        """Get all files that have errors."""
        return [f for f in self.files_analyzed if f.has_errors]

    def get_most_problematic_files(self, limit: int = 20) -> List[FileTypeCheckStats]:
        """Get files sorted by error count (most errors first)."""
        return sorted(
            [f for f in self.files_analyzed if f.total_issues > 0],
            key=lambda f: f.error_count,
            reverse=True,
        )[:limit]

    def get_diagnostics_by_severity(self, severity: str) -> List[TypeCheckDiagnostic]:
        """Get all diagnostics of a given severity."""
        return [d for d in self.all_diagnostics if d.severity == severity]

    def get_diagnostics_by_category(self, category: str) -> List[TypeCheckDiagnostic]:
        """Get all diagnostics of a given category."""
        return [d for d in self.all_diagnostics if d.category == category]


class TypeCheckConfig(BaseModel):
    """Configuration for type checking analysis."""
    engine: str = Field(
        "mypy",
        description="Type checking engine: 'mypy' (default, pure Python) or 'pyright' (Pylance engine, requires Node.js/npx)",
    )
    type_checking_mode: str = Field(
        "basic",
        description="Strictness level. mypy: normal/strict. pyright: off/basic/standard/strict/all",
    )
    python_version: str = Field(
        "",
        description="Python version to target (e.g. 3.12). Empty = auto-detect.",
    )
    python_platform: str = Field(
        "",
        description="Python platform to target (e.g. Linux). Empty = auto-detect.",
    )
    venv_path: str = Field(
        "",
        description="Path to virtual environment for import resolution.",
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
            "assets",
            "*-venv",
            "site-packages",
        ],
        description="Patterns to exclude from analysis",
    )
    include_tests: bool = Field(False, description="Include test files in analysis")
    include_warnings: bool = Field(True, description="Include warnings in output (not just errors)")
    severity_filter: Optional[str] = Field(
        None,
        description="Filter to show only this severity: error, warning, information",
    )
    category_filter: Optional[str] = Field(
        None,
        description="Filter to show only this category",
    )
    output_format: str = Field("text", description="Output format: text, json, markdown")
    verbose: bool = Field(False, description="Show verbose output")
    npx_path: str = Field("npx", description="Path to npx binary for running pyright (engine=pyright only)")
    subprocess_timeout: int = Field(
        300,
        description="Timeout in seconds for the type checker subprocess",
    )

    class Config:
        use_enum_values = True
