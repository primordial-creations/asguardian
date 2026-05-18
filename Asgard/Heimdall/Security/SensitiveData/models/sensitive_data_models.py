"""Pydantic models for sensitive data exposure detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class SensitiveDataSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SensitiveDataFinding(BaseModel):
    file_path: str
    line_number: int
    severity: SensitiveDataSeverity
    data_type: str
    pattern_type: str
    masked_value: str = ""
    description: str
    recommendation: str


class SensitiveDataScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"])


class SensitiveDataScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[SensitiveDataFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_data_type: Dict[str, int] = Field(default_factory=dict)
