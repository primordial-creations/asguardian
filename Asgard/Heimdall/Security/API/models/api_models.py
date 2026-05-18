"""Pydantic models for API security scanning."""

from enum import Enum
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class APISecurityCategory(str, Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    MASS_ASSIGNMENT = "mass_assignment"
    RATE_LIMITING = "rate_limiting"
    DATA_EXPOSURE = "data_exposure"
    GRAPHQL = "graphql"
    INPUT_VALIDATION = "input_validation"
    ERROR_HANDLING = "error_handling"
    CORS = "cors"
    VERSIONING = "versioning"
    SECURITY_HEADERS = "security_headers"
    FILE_UPLOAD = "file_upload"


class APISeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class APIFinding(BaseModel):
    file_path: str = Field(..., description="Path to the file containing the issue")
    line_number: int = Field(..., description="Line number of the finding")
    severity: APISeverity
    category: APISecurityCategory
    pattern_type: str = Field(..., description="Specific vulnerability type identifier")
    code_snippet: str = Field("", description="The flagged code snippet")
    description: str = Field(..., description="Description of the vulnerability")
    recommendation: str = Field(..., description="Remediation guidance")


class APIScanConfig(BaseModel):
    scan_path: Path = Field(..., description="Root path to scan")
    recursive: bool = Field(True)
    skip_dirs: List[str] = Field(
        default=[".git", "node_modules", "__pycache__", ".venv", "venv", "vendor"]
    )


class APIScanReport(BaseModel):
    scan_path: str
    total_findings: int = 0
    files_scanned: int = 0
    findings: List[APIFinding] = Field(default_factory=list)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)
