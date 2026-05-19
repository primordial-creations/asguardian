"""Models for Csharp quality analysis."""

from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path
from typing import List


class CsharpRuleCategory(str, Enum):
    SECURITY = "security"
    QUALITY = "quality"
    STYLE = "style"
    PERFORMANCE = "performance"
    CORRECTNESS = "correctness"


class CsharpSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class CsharpFinding(BaseModel):
    file_path: str
    line_number: int
    column: int = 0
    rule_id: str
    category: CsharpRuleCategory
    severity: CsharpSeverity
    title: str
    description: str
    code_snippet: str = ""
    fix_suggestion: str = ""


class CsharpScanConfig(BaseModel):
    scan_path: Path = Field(default_factory=lambda: Path("."))
    include_extensions: List[str] = Field(default_factory=lambda: [".cs"])
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        "*/test*", "*_test*", "*/vendor/*", "*/node_modules/*",
        "*/.git/*", "*/build/*", "*/dist/*",
    ])
    max_findings: int = Field(default=1000)
