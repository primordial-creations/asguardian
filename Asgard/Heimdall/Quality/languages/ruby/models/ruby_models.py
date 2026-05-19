"""Models for Ruby quality analysis."""

from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Dict, List


class RubyRuleCategory(str, Enum):
    SECURITY = "security"
    QUALITY = "quality"
    STYLE = "style"
    PERFORMANCE = "performance"
    CORRECTNESS = "correctness"


class RubySeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RubyFinding(BaseModel):
    file_path: str
    line_number: int
    column: int = 0
    rule_id: str
    category: RubyRuleCategory
    severity: RubySeverity
    title: str
    description: str
    code_snippet: str = ""
    fix_suggestion: str = ""


class RubyScanConfig(BaseModel):
    scan_path: Path = Field(default_factory=lambda: Path("."))
    include_extensions: List[str] = Field(default_factory=lambda: [".rb", ".rake", ".gemspec"])
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        "*/test*", "*_test*", "*/vendor/*", "*/node_modules/*",
        "*/.git/*", "*/build/*", "*/dist/*",
    ])
    max_findings: int = Field(default=1000)
    max_file_lines: int = Field(default=10000)
    rules: Dict[str, bool] = Field(default_factory=dict)


class RubyReport(BaseModel):
    findings: List[RubyFinding] = Field(default_factory=list)
    scan_path: str = ""

    @property
    def total_findings(self) -> int:
        return len(self.findings)
