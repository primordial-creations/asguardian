"""Pydantic models for git security scanning."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class GitSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class GitFinding(BaseModel):
    file_path: str
    commit: str = ""
    severity: GitSeverity
    issue_type: str
    description: str
    recommendation: str
    details: str = ""


class GitScanReport(BaseModel):
    repo_path: str
    total_findings: int = 0
    findings: List[GitFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
