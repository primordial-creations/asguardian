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
    mechanism_id: str = Field("", description="Normalization-engine mechanism id (plan 06).")
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Confidence score")
    confidence_bucket: str = Field("probable", description="Qualitative confidence bucket (plan 06).")
    compliance_tags: List[str] = Field(
        default_factory=list,
        description="Plan 07.11: GDPR/PCI/HIPAA tags for compliance reporting.",
    )
    is_hotspot: bool = Field(
        False,
        description=(
            "Plan 07.11: PII-to-log-sink findings where the identifier name "
            "matches the PII lexicon but the value's actual provenance "
            "cannot be confirmed statically are reported as a hotspot "
            "(LOW, capped confidence) rather than a confirmed finding -- "
            "unresolved origin is never treated as safe."
        ),
    )


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
