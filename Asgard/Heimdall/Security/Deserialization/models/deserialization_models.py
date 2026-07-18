"""Pydantic models for insecure deserialization detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class DeserializationSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DeserializationFinding(BaseModel):
    file_path: str
    line_number: int
    severity: DeserializationSeverity
    language: str
    pattern_type: str
    code_snippet: str = ""
    description: str
    recommendation: str
    # Plan 07.5: taint-integrated provenance classification. A sink is a
    # "finding" (is_hotspot=False) only when the deserialized value can be
    # traced to an untrusted source (network/request/stdin) in a nearby
    # backward window; otherwise it is reported as a "hotspot" -- a
    # data-provenance question for a human, never a confident claim of
    # exploitability (gadget-chain existence is statically unprovable).
    mechanism_id: str = "deserialization.untrusted"
    confidence: float = 0.5
    confidence_bucket: str = "possible"
    is_hotspot: bool = False
    provenance: str = "unknown"


class DeserializationScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"])


class DeserializationScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[DeserializationFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_language: Dict[str, int] = Field(default_factory=dict)
