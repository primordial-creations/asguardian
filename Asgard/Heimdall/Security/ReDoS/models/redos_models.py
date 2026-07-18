"""Pydantic models for ReDoS vulnerability detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class ReDoSSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReDoSFinding(BaseModel):
    file_path: str
    line_number: int
    severity: ReDoSSeverity
    pattern_type: str
    regex_pattern: str = ""
    description: str
    recommendation: str
    # Orthogonal confidence (plan 06/07): severity is CIA-impact, confidence
    # is "how sure are we this actually blows up". Defaults preserve the
    # legacy regex-heuristic behaviour (always "certain") for any caller
    # still constructing findings without these fields.
    confidence: float = 1.0
    confidence_bucket: str = "certain"
    mechanism_id: str = "redos.heuristic"
    cwe_id: str = "CWE-1333"


class ReDoSScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"])


class ReDoSScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[ReDoSFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
