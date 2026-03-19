"""
Heimdall Bug Detection Models

Pydantic models for bug detection operations and results.

Covers symbolic execution subset patterns:
- Null dereference
- Unreachable code
- Always-false / always-true conditions
- Division by zero
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class BugCategory(str, Enum):
    """Categories of bugs detected by the symbolic execution subset."""
    NULL_DEREFERENCE = "null_dereference"       # Accessing attribute/method on potentially None value
    UNREACHABLE_CODE = "unreachable_code"       # Code that can never execute
    ALWAYS_FALSE = "always_false"               # Condition that is always False
    ALWAYS_TRUE = "always_true"                 # Condition that is always True
    DIVISION_BY_ZERO = "division_by_zero"       # Division by a literal zero or zero-assigned variable
    ASSERTION_MISUSE = "assertion_misuse"       # Incorrect/dangerous assert usage
    MUTABLE_DEFAULT_ARG = "mutable_default_arg" # def f(x=[]) — shared mutable default
    LATE_BINDING_CLOSURE = "late_binding_closure" # lambda/nested func in loop captures loop var
    BUILTIN_SHADOWING = "builtin_shadowing"     # list=[], id=1 — shadows built-ins
    IS_LITERAL_COMPARISON = "is_literal_comparison" # x is 1 — identity vs equality
    EXCEPTION_SWALLOWING = "exception_swallowing"   # bare except: pass, or except E: pass
    EXCEPTION_CHAINING = "exception_chaining"   # raise X in except without from e
    TYPE_EROSION = "type_erosion"               # Any annotations, cast(), type: ignore, missing return types
    DEAD_CODE = "dead_code"                     # Unused private methods / module vars
    MAGIC_NUMBER = "magic_number"               # Hard-coded numeric literals


class BugSeverity(str, Enum):
    """Severity levels for detected bugs."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugFinding(BaseModel):
    """A single bug finding detected by the bug detector."""
    file_path: str = Field(..., description="Path to the file containing the bug")
    line_number: int = Field(..., description="Line number where the bug was detected")
    category: BugCategory = Field(..., description="Category of the bug")
    severity: BugSeverity = Field(..., description="Severity of the bug")
    title: str = Field(..., description="Short title describing the bug")
    description: str = Field(..., description="Detailed description of the bug")
    code_snippet: str = Field("", description="The code snippet containing the bug")
    fix_suggestion: str = Field("", description="Suggested fix for the bug")

    class Config:
        use_enum_values = True


class BugReport(BaseModel):
    """Report from a bug detection scan."""
    total_bugs: int = Field(0, description="Total number of bugs found")
    critical_count: int = Field(0, description="Number of critical severity bugs")
    high_count: int = Field(0, description="Number of high severity bugs")
    medium_count: int = Field(0, description="Number of medium severity bugs")
    low_count: int = Field(0, description="Number of low severity bugs")
    findings: List[BugFinding] = Field(default_factory=list, description="All bug findings")
    files_analyzed: int = Field(0, description="Number of files analyzed")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: BugFinding) -> None:
        """Add a bug finding to the report."""
        self.total_bugs += 1
        self.findings.append(finding)
        sev = finding.severity if isinstance(finding.severity, str) else finding.severity.value
        if sev == BugSeverity.CRITICAL.value:
            self.critical_count += 1
        elif sev == BugSeverity.HIGH.value:
            self.high_count += 1
        elif sev == BugSeverity.MEDIUM.value:
            self.medium_count += 1
        elif sev == BugSeverity.LOW.value:
            self.low_count += 1

    @property
    def has_findings(self) -> bool:
        """Check if any bugs were found."""
        return self.total_bugs > 0

    @property
    def is_passing(self) -> bool:
        """Check if the scan passes (no critical or high bugs)."""
        return self.critical_count == 0 and self.high_count == 0

    def get_findings_by_category(self) -> Dict[str, List[BugFinding]]:
        """Group findings by bug category."""
        result: Dict[str, List[BugFinding]] = {}
        for finding in self.findings:
            cat = finding.category if isinstance(finding.category, str) else finding.category
            if cat not in result:
                result[cat] = []
            result[cat].append(finding)
        return result

    def get_findings_by_severity(self) -> Dict[str, List[BugFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[BugFinding]] = {
            BugSeverity.CRITICAL.value: [],
            BugSeverity.HIGH.value: [],
            BugSeverity.MEDIUM.value: [],
            BugSeverity.LOW.value: [],
        }
        for finding in self.findings:
            sev = finding.severity if isinstance(finding.severity, str) else finding.severity
            if sev in result:
                result[sev].append(finding)
        return result


class BugDetectionConfig(BaseModel):
    """Configuration for bug detection analysis."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    detect_null_dereference: bool = Field(True, description="Enable null dereference detection")
    detect_unreachable_code: bool = Field(True, description="Enable unreachable code detection")
    detect_division_by_zero: bool = Field(True, description="Enable division by zero detection")
    detect_assertion_misuse: bool = Field(True, description="Enable assertion misuse detection")
    detect_python_footguns: bool = Field(True, description="Enable mutable defaults, late binding, builtin shadowing")
    detect_exception_quality: bool = Field(True, description="Enable exception swallowing/chaining detection")
    detect_type_erosion: bool = Field(True, description="Enable Any overuse, cast(), type:ignore scanning")
    detect_dead_code: bool = Field(True, description="Enable unused private method/variable detection")
    detect_magic_numbers: bool = Field(True, description="Enable magic number detection")
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
            "tests",
        ],
        description="Patterns to exclude from scanning"
    )

    class Config:
        use_enum_values = True
