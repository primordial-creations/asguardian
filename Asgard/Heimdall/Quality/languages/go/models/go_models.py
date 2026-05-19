"""Models for Go quality analysis."""

from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Dict, List


class GoRuleCategory(str, Enum):
    SECURITY = "security"
    QUALITY = "quality"
    STYLE = "style"
    PERFORMANCE = "performance"
    CORRECTNESS = "correctness"


class GoSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class GoFinding(BaseModel):
    file_path: str
    line_number: int
    column: int = 0
    rule_id: str
    category: GoRuleCategory
    severity: GoSeverity
    title: str
    description: str
    code_snippet: str = ""
    fix_suggestion: str = ""


class GoScanConfig(BaseModel):
    scan_path: Path = Field(default_factory=lambda: Path("."))
    include_extensions: List[str] = Field(default_factory=lambda: [".go"])
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        "*/test*", "*_test*", "*/vendor/*", "*/node_modules/*",
        "*/.git/*", "*/build/*", "*/dist/*",
    ])
    max_findings: int = Field(default=1000)
    max_file_lines: int = Field(default=10000)
    rules: Dict[str, bool] = Field(default_factory=dict)


class GoReport(BaseModel):
    findings: List[GoFinding] = Field(default_factory=list)
    scan_path: str = ""

    @property
    def total_findings(self) -> int:
        return len(self.findings)
