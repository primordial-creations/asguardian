"""
Validation Models for Infrastructure Validation

Provides Pydantic models for validation results and reports
across different infrastructure configuration types.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


class ValidationCategory(str, Enum):
    """Validation issue categories."""
    SECURITY = "security"
    BEST_PRACTICE = "best-practice"
    SYNTAX = "syntax"
    SCHEMA = "schema"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    MAINTAINABILITY = "maintainability"


class ValidationRule(BaseModel):
    """Validation rule definition."""
    id: str = Field(description="Rule identifier")
    name: str = Field(description="Rule name")
    description: str = Field(description="Rule description")
    severity: ValidationSeverity = Field(description="Default severity")
    category: ValidationCategory = Field(description="Rule category")
    enabled: bool = Field(default=True, description="Is rule enabled")
    documentation_url: Optional[str] = Field(default=None, description="Documentation URL")
    auto_fix: bool = Field(default=False, description="Can be auto-fixed")


class ValidationResult(BaseModel):
    """Single validation result."""
    rule_id: str = Field(description="Rule that triggered this result")
    message: str = Field(description="Validation message")
    severity: ValidationSeverity = Field(description="Issue severity")
    category: ValidationCategory = Field(description="Issue category")
    file_path: Optional[str] = Field(default=None, description="File path")
    line_number: Optional[int] = Field(default=None, description="Line number")
    column: Optional[int] = Field(default=None, description="Column number")
    resource_kind: Optional[str] = Field(default=None, description="Resource kind (for K8s)")
    resource_name: Optional[str] = Field(default=None, description="Resource name")
    suggestion: Optional[str] = Field(default=None, description="Fix suggestion")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @property
    def location(self) -> str:
        """Get formatted location string."""
        if not self.file_path:
            return ""
        loc = self.file_path
        if self.line_number:
            loc += f":{self.line_number}"
            if self.column:
                loc += f":{self.column}"
        return loc


class ValidationContext(BaseModel):
    """Context for validation operations."""
    strict_mode: bool = Field(default=False, description="Enable strict validation")
    ignore_rules: List[str] = Field(
        default_factory=list,
        description=(
            "DEPRECATED: unscoped, unjustified ignore list. Use reified "
            "suppressions (Suppression/SuppressionSet) instead. Will be "
            "removed in a future minor version."
        ),
    )
    offline: bool = Field(
        default=True, description="Never fetch schemas over the network (default)"
    )
    schema_dir: Optional[str] = Field(
        default=None, description="Directory of user-supplied JSON schema fragments"
    )
    severity_override: Dict[str, ValidationSeverity] = Field(
        default_factory=dict, description="Override rule severities"
    )
    kubernetes_version: str = Field(default="1.29", description="Target K8s version")
    terraform_version: str = Field(default="1.7", description="Target Terraform version")
    custom_rules: List[ValidationRule] = Field(default_factory=list, description="Custom rules")


class FileValidationSummary(BaseModel):
    """Validation summary for a single file."""
    file_path: str = Field(description="File path")
    error_count: int = Field(default=0, description="Number of errors")
    warning_count: int = Field(default=0, description="Number of warnings")
    info_count: int = Field(default=0, description="Number of info messages")
    passed: bool = Field(default=True, description="Passed validation")


class ValidationReport(BaseModel):
    """Complete validation report."""
    id: str = Field(description="Report ID")
    title: str = Field(description="Report title")
    validator: str = Field(description="Validator used")
    results: List[ValidationResult] = Field(default_factory=list, description="Validation results")
    file_summaries: List[FileValidationSummary] = Field(
        default_factory=list, description="Per-file summaries"
    )
    total_files: int = Field(default=0, description="Total files validated")
    total_errors: int = Field(default=0, description="Total errors")
    total_warnings: int = Field(default=0, description="Total warnings")
    total_info: int = Field(default=0, description="Total info messages")
    passed: bool = Field(default=True, description="Overall pass/fail")
    score: float = Field(default=100.0, ge=0, le=100, description="Validation score")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    duration_ms: Optional[int] = Field(default=None, description="Validation duration in ms")
    context: Optional[ValidationContext] = Field(default=None, description="Validation context")

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return self.total_errors > 0

    @property
    def error_results(self) -> List[ValidationResult]:
        """Get only error results."""
        return [r for r in self.results if r.severity == ValidationSeverity.ERROR]

    @property
    def warning_results(self) -> List[ValidationResult]:
        """Get only warning results."""
        return [r for r in self.results if r.severity == ValidationSeverity.WARNING]

    def results_by_file(self) -> Dict[str, List[ValidationResult]]:
        """Group results by file."""
        by_file: Dict[str, List[ValidationResult]] = {}
        for result in self.results:
            file_path = result.file_path or "(no file)"
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(result)
        return by_file

    def results_by_rule(self) -> Dict[str, List[ValidationResult]]:
        """Group results by rule ID."""
        by_rule: Dict[str, List[ValidationResult]] = {}
        for result in self.results:
            if result.rule_id not in by_rule:
                by_rule[result.rule_id] = []
            by_rule[result.rule_id].append(result)
        return by_rule

    def results_by_category(self) -> Dict[ValidationCategory, List[ValidationResult]]:
        """Group results by category."""
        by_category: Dict[ValidationCategory, List[ValidationResult]] = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)
        return by_category
