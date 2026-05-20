"""
Heimdall JavaScript/TypeScript Quality Analysis Models

Pydantic models for JS/TS static analysis findings reported by the
regex-based JavaScript and TypeScript analyzers.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


class JSRuleCategory(str, Enum):
    """Category of a JavaScript/TypeScript rule finding."""
    BUG = "bug"
    CODE_SMELL = "code_smell"
    SECURITY = "security"
    STYLE = "style"
    COMPLEXITY = "complexity"


class JSSeverity(str, Enum):
    """Severity level for a JavaScript/TypeScript finding."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class JSFinding(BaseModel):
    """A single finding produced by the JavaScript or TypeScript analyzer."""
    file_path: str = Field(..., description="Absolute path to the file containing the finding")
    line_number: int = Field(..., description="1-based line number of the finding")
    column: int = Field(0, description="0-based column offset of the finding")
    rule_id: str = Field(..., description="Unique rule identifier (e.g. 'js.no-eval')")
    category: JSRuleCategory = Field(..., description="Rule category")
    severity: JSSeverity = Field(..., description="Severity level")
    title: str = Field(..., description="Short human-readable rule title")
    description: str = Field(..., description="Detailed description of the issue")
    code_snippet: str = Field("", description="The offending line of source code")
    fix_suggestion: str = Field("", description="Suggested remediation")

    class Config:
        use_enum_values = True


class JSReport(BaseModel):
    """Complete analysis report produced by the JavaScript or TypeScript analyzer."""
    total_findings: int = Field(0, description="Total number of findings")
    error_count: int = Field(0, description="Number of ERROR-severity findings")
    warning_count: int = Field(0, description="Number of WARNING-severity findings")
    info_count: int = Field(0, description="Number of INFO-severity findings")
    findings: List[JSFinding] = Field(default_factory=list, description="All findings")
    files_analyzed: int = Field(0, description="Number of files analyzed")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan in seconds")
    scanned_at: datetime = Field(default_factory=datetime.now, description="Timestamp of the scan")
    language: str = Field("javascript", description="Language that was analyzed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: JSFinding) -> None:
        """Append a finding and update summary counters."""
        self.findings.append(finding)
        self.total_findings += 1
        severity = finding.severity if isinstance(finding.severity, str) else finding.severity.value
        if severity == JSSeverity.ERROR.value:
            self.error_count += 1
        elif severity == JSSeverity.WARNING.value:
            self.warning_count += 1
        else:
            self.info_count += 1

    @property
    def has_findings(self) -> bool:
        """Return True when at least one finding exists."""
        return self.total_findings > 0


class JSAnalysisConfig(BaseModel):
    """Configuration for the JavaScript or TypeScript analyzer."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    language: str = Field("javascript", description="Language being analyzed")
    include_extensions: List[str] = Field(
        default_factory=lambda: [".js", ".jsx"],
        description="File extensions to include",
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "node_modules",
            ".git",
            "dist",
            "build",
            "__pycache__",
            "*.min.js",
        ],
        description="Glob-style patterns to exclude",
    )
    enabled_rules: Optional[List[str]] = Field(
        None,
        description="Explicit list of rule IDs to run (None means all rules)",
    )
    disabled_rules: List[str] = Field(
        default_factory=list,
        description="Rule IDs to skip",
    )
    max_complexity: int = Field(10, description="Cyclomatic complexity threshold per function")
    max_function_lines: int = Field(50, description="Maximum lines per function")
    max_file_lines: int = Field(500, description="Maximum lines per file")

    class Config:
        use_enum_values = True
