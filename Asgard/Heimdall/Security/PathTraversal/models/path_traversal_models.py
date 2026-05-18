"""Pydantic models for path traversal detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class PathTraversalSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PathTraversalFinding(BaseModel):
    file_path: str
    line_number: int
    severity: PathTraversalSeverity
    language: str
    pattern_type: str
    code_snippet: str = ""
    description: str
    recommendation: str


class PathTraversalScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"])


class PathTraversalScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[PathTraversalFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_language: Dict[str, int] = Field(default_factory=dict)
