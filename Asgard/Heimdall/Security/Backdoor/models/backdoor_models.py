"""Pydantic models for backdoor detection."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class BackdoorType(str, Enum):
    PHP_WEBSHELL = "php_webshell"
    JSP_WEBSHELL = "jsp_webshell"
    ASP_WEBSHELL = "asp_webshell"
    PYTHON_BACKDOOR = "python_backdoor"
    BIND_SHELL = "bind_shell"
    REVERSE_SHELL = "reverse_shell"
    HIDDEN_ADMIN = "hidden_admin"
    FILE_MANAGER = "file_manager"
    CODE_EXECUTION = "code_execution"
    CREDENTIAL_HARDCODED = "credential_hardcoded"
    OBFUSCATED = "obfuscated"
    PERSISTENCE = "persistence"
    C2_COMMUNICATION = "c2_communication"
    KNOWN_WEBSHELL = "known_webshell"
    DOUBLE_EXTENSION = "double_extension"


class BackdoorSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BackdoorFinding(BaseModel):
    file_path: str
    line_number: int
    backdoor_type: BackdoorType
    severity: BackdoorSeverity
    description: str
    code_snippet: str = ""
    ioc: str = Field("", description="Indicator of Compromise category")


class BackdoorScanConfig(BaseModel):
    scan_path: Path
    recursive: bool = True
    skip_dirs: List[str] = Field(default=[".git", "node_modules", "__pycache__", ".venv", "venv"])


class BackdoorScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[BackdoorFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_ioc: Dict[str, int] = Field(default_factory=dict)
