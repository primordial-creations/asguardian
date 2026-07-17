"""Pydantic models for SSRF and XXE detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class SSRFVulnerabilityType(str, Enum):
    SSRF = "ssrf"
    XXE = "xxe"


class SSRFSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SSRFFinding(BaseModel):
    file_path: str
    line_number: int
    vulnerability_type: SSRFVulnerabilityType
    severity: SSRFSeverity
    language: str
    pattern_type: str
    code_snippet: str = ""
    description: str
    recommendation: str
    # Orthogonal confidence (plan 06/07.1). Defaults preserve legacy
    # regex-only behaviour ("certain") for non-Python languages, which
    # have no AST refinement pass.
    confidence: float = 1.0
    confidence_bucket: str = "certain"
    mechanism_id: str = "ssrf.regex_heuristic"


class SSRFScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"])


class SSRFScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[SSRFFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_vulnerability_type: Dict[str, int] = Field(default_factory=dict)
