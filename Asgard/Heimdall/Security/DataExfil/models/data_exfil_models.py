"""Pydantic models for data exfiltration detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class ExfilType(str, Enum):
    HTTP_EXFIL = "http_exfil"
    DNS_EXFIL = "dns_exfil"
    EMAIL_EXFIL = "email_exfil"
    FTP_EXFIL = "ftp_exfil"
    CLOUD_EXFIL = "cloud_exfil"
    WEBHOOK_EXFIL = "webhook_exfil"
    DATABASE_DUMP = "database_dump"
    FILE_COLLECTION = "file_collection"
    CLIPBOARD_THEFT = "clipboard_theft"
    SCREENSHOT = "screenshot"
    KEYLOG_EXFIL = "keylog_exfil"
    SENSITIVE_DATA = "sensitive_data"
    ENCODED_EXFIL = "encoded_exfil"
    COVERT_CHANNEL = "covert_channel"
    ENVIRONMENT_EXFIL = "environment_exfil"


class ExfilSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExfilFinding(BaseModel):
    file_path: str
    line_number: int
    exfil_type: ExfilType
    severity: ExfilSeverity
    description: str
    code_snippet: str = ""
    data_type: str = ""


class ExfilScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"])


class ExfilScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[ExfilFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_data_type: Dict[str, int] = Field(default_factory=dict)
