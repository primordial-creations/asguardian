"""Pydantic models for input validation vulnerability detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class InputValidationSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class InputValidationFinding(BaseModel):
    file_path: str
    line_number: int
    severity: InputValidationSeverity
    category: str
    issue_type: str
    code_snippet: str = ""
    description: str
    recommendation: str
    mechanism_id: str = Field("", description="Normalization-engine mechanism id (plan 06).")
    confidence: float = Field(0.6, ge=0.0, le=1.0, description="Confidence score")
    confidence_bucket: str = Field("probable", description="Qualitative confidence bucket (plan 06).")
    is_advisory: bool = Field(
        False,
        description=(
            "Plan 07.12: mass-assignment findings (Pydantic models without "
            "extra='forbid' on update routes) are advisory -- a design "
            "recommendation, not a confirmed vulnerability, since many "
            "APIs intentionally accept partial/extra fields."
        ),
    )
    cwe_id: str = Field("", description="CWE identifier, e.g. CWE-179 for early-validation-before-mutation.")


class InputValidationScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"])


class InputValidationScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[InputValidationFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)
