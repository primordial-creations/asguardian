"""
Heimdall Environment Variable Fallback Detection Models

Pydantic models for detecting default/fallback values in environment variable
access which violates the coding standard that prohibits fallback values
for environment variables.

Detected Patterns:
- os.getenv("VAR", "default")
- os.environ.get("VAR", "default")
- os.getenv("VAR") or "default"
- os.environ.get("VAR") or "default"
- config.get("VAR", default="value")
"""

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class EnvFallbackType(str, Enum):
    """Types of environment variable and config fallback patterns."""
    # Environment variable patterns
    GETENV_DEFAULT = "getenv_default"           # os.getenv("VAR", "default")
    ENVIRON_GET_DEFAULT = "environ_get_default" # os.environ.get("VAR", "default")
    GETENV_OR_FALLBACK = "getenv_or_fallback"   # os.getenv("VAR") or "default"
    ENVIRON_GET_OR_FALLBACK = "environ_get_or_fallback"  # os.environ.get("VAR") or "default"
    GENERIC_OR_FALLBACK = "generic_or_fallback"  # any_env_call() or "default"
    # Vault/config patterns
    CONFIG_GET_DEFAULT = "config_get_default"   # config.get("key", default)
    SECRETS_GET_DEFAULT = "secrets_get_default" # secrets.get("key", default)
    VAULT_OR_FALLBACK = "vault_or_fallback"     # vault_result or "default"
    # Enhanced credential-specific patterns
    CREDENTIAL_KEY_GETENV_DEFAULT = "credential_key_getenv_default"        # os.getenv("PASSWORD", ...) - credential key name
    CREDENTIAL_VALUE_ENVIRON_DEFAULT = "credential_value_environ_default"  # os.environ.get(..., "real-secret-value")
    CREDENTIAL_MISSING_NO_FALLBACK = "credential_missing_no_fallback"      # os.environ.get("SECRET") with no default - missing required security config
    HARDCODED_CREDENTIAL_VALUE = "hardcoded_credential_value"              # Fallback value looks like a real credential (long alphanum, base64, hex)


class EnvFallbackSeverity(str, Enum):
    """Severity levels for environment variable fallback violations."""
    CRITICAL = "critical"  # Hardcoded credentials or missing required security config
    HIGH = "high"       # Direct default in getenv/environ.get
    MEDIUM = "medium"   # Fallback via 'or' operator
    LOW = "low"         # Potential fallback (unclear pattern)


class EnvFallbackViolation(BaseModel):
    """Represents a detected environment variable fallback violation."""
    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(..., description="Line where violation is found")
    column: int = Field(0, description="Column offset in the line")
    code_snippet: str = Field(..., description="The code containing the violation")
    variable_name: Optional[str] = Field(None, description="Environment variable name if detected")
    default_value: Optional[str] = Field(None, description="Default/fallback value if detected")
    fallback_type: EnvFallbackType = Field(..., description="Type of fallback pattern")
    severity: EnvFallbackSeverity = Field(..., description="Severity level")
    containing_function: Optional[str] = Field(None, description="Function/method name if applicable")
    containing_class: Optional[str] = Field(None, description="Class name if inside a method")
    context_description: str = Field(..., description="Description of the violation")
    remediation: str = Field(
        "Remove the default value. Environment variables should fail explicitly if not set.",
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


class EnvFallbackReport(BaseModel):
    """Complete environment variable fallback analysis report."""
    total_violations: int = Field(0, description="Total number of fallback violations found")
    violations_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by fallback type")
    violations_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_violations: List[EnvFallbackViolation] = Field(default_factory=list, description="All detected violations")
    most_problematic_files: List[Tuple[str, int]] = Field(default_factory=list, description="Files with most violations")
    files_scanned: int = Field(0, description="Number of files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_violation(self, violation: EnvFallbackViolation) -> None:
        """Add an environment fallback violation to the report."""
        self.detected_violations.append(violation)
        self.total_violations += 1

        # Update type count
        fallback_type = violation.fallback_type if isinstance(violation.fallback_type, str) else violation.fallback_type.value
        self.violations_by_type[fallback_type] = self.violations_by_type.get(fallback_type, 0) + 1

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

    def get_violations_by_type(self, fallback_type: EnvFallbackType) -> List[EnvFallbackViolation]:
        """Get all violations of a specific type."""
        target = fallback_type if isinstance(fallback_type, str) else fallback_type.value
        return [v for v in self.detected_violations if v.fallback_type == target]

    def get_violations_by_severity(self, severity: EnvFallbackSeverity) -> List[EnvFallbackViolation]:
        """Get all violations of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [v for v in self.detected_violations if v.severity == target]


class EnvFallbackConfig(BaseModel):
    """Configuration for environment fallback scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: EnvFallbackSeverity = Field(
        EnvFallbackSeverity.LOW,
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
            "conftest.py",
            "test_*.py",
            "*_test.py",
        ],
        description="Patterns to exclude"
    )
    include_tests: bool = Field(False, description="Include test files (typically excluded)")
    verbose: bool = Field(False, description="Show verbose output")
    # Patterns to skip (e.g., legitimate uses in config loaders)
    skip_functions: List[str] = Field(
        default_factory=lambda: [],
        description="Function names to skip scanning inside"
    )

    class Config:
        use_enum_values = True
