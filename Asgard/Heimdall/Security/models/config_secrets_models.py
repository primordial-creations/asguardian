"""
Heimdall Config Secrets Analysis Models

Pydantic models for detecting hardcoded secrets and credentials in
configuration files (YAML, JSON, TOML, INI). Identifies keys that
commonly hold credentials with real-looking values.

Detected Patterns:
- Keys named token, api_key, password, secret, credential, auth, private_key
  with non-placeholder values
- High-entropy strings (Shannon entropy > 3.5 for strings > 20 chars)
"""

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ConfigSecretType(str, Enum):
    """Types of config secret findings."""
    CREDENTIAL_KEY = "credential_key"       # Key name indicates a credential
    HIGH_ENTROPY_STRING = "high_entropy_string"  # High-entropy value regardless of key name


class ConfigSecretSeverity(str, Enum):
    """Severity levels for config secret findings."""
    CRITICAL = "critical"   # Known credential key with non-placeholder value
    HIGH = "high"           # Credential key with suspicious value
    MEDIUM = "medium"       # High-entropy string that may be a secret
    LOW = "low"             # Low-confidence finding


class ConfigSecretFinding(BaseModel):
    """Represents a detected secret or credential in a config file."""
    file_path: str = Field(..., description="Absolute path to the config file")
    relative_path: str = Field("", description="Relative path from scan root")
    line_number: int = Field(0, description="Line where the secret was found (0 if not applicable)")
    key_name: str = Field(..., description="The configuration key containing the value")
    masked_value: str = Field(..., description="Masked version of the detected value")
    secret_type: ConfigSecretType = Field(..., description="Type of secret finding")
    severity: ConfigSecretSeverity = Field(..., description="Severity level")
    entropy: Optional[float] = Field(None, description="Shannon entropy of the value if calculated")
    context_path: str = Field("", description="Dot-notation path to the key in the config (e.g. 'db.password')")
    context_description: str = Field(..., description="Human-readable description of the finding")
    remediation: str = Field(
        "Move this value to an environment variable or a secrets manager. "
        "Do not hardcode credentials in configuration files.",
        description="Suggested fix"
    )

    class Config:
        use_enum_values = True

    @property
    def location(self) -> str:
        """Return a readable location string."""
        basename = os.path.basename(self.file_path)
        if self.line_number:
            return f"{basename}:{self.line_number}"
        return basename


class ConfigSecretsReport(BaseModel):
    """Complete config secrets analysis report."""
    total_findings: int = Field(0, description="Total number of secret findings")
    findings_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by finding type")
    findings_by_severity: Dict[str, int] = Field(default_factory=dict, description="Count by severity")
    detected_findings: List[ConfigSecretFinding] = Field(
        default_factory=list, description="All detected findings"
    )
    most_problematic_files: List[Tuple[str, int]] = Field(
        default_factory=list, description="Files with most findings"
    )
    files_scanned: int = Field(0, description="Number of config files scanned")
    scan_path: str = Field("", description="Root path that was scanned")
    scan_duration_seconds: float = Field(0.0, description="Time taken for scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When scan was performed")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: ConfigSecretFinding) -> None:
        """Add a config secret finding to the report."""
        self.detected_findings.append(finding)
        self.total_findings += 1

        secret_type = finding.secret_type if isinstance(finding.secret_type, str) else finding.secret_type.value
        self.findings_by_type[secret_type] = self.findings_by_type.get(secret_type, 0) + 1

        severity = finding.severity if isinstance(finding.severity, str) else finding.severity.value
        self.findings_by_severity[severity] = self.findings_by_severity.get(severity, 0) + 1

    @property
    def has_findings(self) -> bool:
        """Check if any findings were detected."""
        return self.total_findings > 0

    @property
    def is_clean(self) -> bool:
        """Check if no secrets were detected."""
        return self.total_findings == 0

    def get_findings_by_type(self, secret_type: ConfigSecretType) -> List[ConfigSecretFinding]:
        """Get all findings of a specific type."""
        target = secret_type if isinstance(secret_type, str) else secret_type.value
        return [f for f in self.detected_findings if f.secret_type == target]

    def get_findings_by_severity(
        self, severity: ConfigSecretSeverity
    ) -> List[ConfigSecretFinding]:
        """Get all findings of a specific severity."""
        target = severity if isinstance(severity, str) else severity.value
        return [f for f in self.detected_findings if f.severity == target]


class ConfigSecretsConfig(BaseModel):
    """Configuration for config secrets scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    severity_filter: ConfigSecretSeverity = Field(
        ConfigSecretSeverity.MEDIUM,
        description="Minimum severity to report"
    )
    output_format: str = Field("text", description="Output format: text, json, markdown")
    include_extensions: List[str] = Field(
        default_factory=lambda: [".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf"],
        description="Config file extensions to scan"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        ],
        description="Patterns to exclude"
    )
    entropy_threshold: float = Field(3.5, description="Shannon entropy threshold for high-entropy detection")
    entropy_min_length: int = Field(20, description="Minimum string length for entropy analysis")
    credential_key_names: List[str] = Field(
        default_factory=lambda: [
            "token", "api_key", "apikey", "password", "passwd", "pwd",
            "secret", "credential", "credentials", "auth", "authorization",
            "private_key", "privatekey", "access_key", "accesskey",
        ],
        description="Key name fragments that indicate credential fields (case-insensitive)"
    )
    verbose: bool = Field(False, description="Show verbose output")

    class Config:
        use_enum_values = True
