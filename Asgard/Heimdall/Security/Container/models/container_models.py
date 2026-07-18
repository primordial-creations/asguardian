"""
Heimdall Security Container Models

Pydantic models for container security analysis operations and results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class ContainerFindingType(str, Enum):
    """Types of container security findings."""
    ROOT_USER = "root_user"
    LATEST_TAG = "latest_tag"
    SECRETS_IN_IMAGE = "secrets_in_image"
    EXPOSED_PORTS = "exposed_ports"
    PRIVILEGED_MODE = "privileged_mode"
    CHMOD_777 = "chmod_777"
    APT_INSTALL_SUDO = "apt_install_sudo"
    MISSING_HEALTHCHECK = "missing_healthcheck"
    ADD_INSTEAD_OF_COPY = "add_instead_of_copy"
    CURL_PIPE_BASH = "curl_pipe_bash"
    HARDCODED_SECRET = "hardcoded_secret"
    INSECURE_REGISTRY = "insecure_registry"
    HOST_NETWORK = "host_network"
    HOST_PID = "host_pid"
    CAP_SYS_ADMIN = "cap_sys_admin"
    UNRESTRICTED_VOLUME = "unrestricted_volume"
    NO_SECURITY_OPT = "no_security_opt"
    WRITABLE_ROOT_FS = "writable_root_fs"


class ContainerFinding(BaseModel):
    """A detected container security issue."""
    file_path: str = Field(..., description="Path to the file containing the issue")
    line_number: int = Field(..., description="Line number where the issue was found")
    column_start: int = Field(0, description="Column where the issue starts")
    column_end: int = Field(0, description="Column where the issue ends")
    finding_type: ContainerFindingType = Field(..., description="Type of container security issue")
    severity: SecuritySeverity = Field(..., description="Severity of the finding")
    title: str = Field(..., description="Short title describing the issue")
    description: str = Field(..., description="Detailed description of the container security issue")
    code_snippet: str = Field("", description="The problematic code snippet")
    service_name: Optional[str] = Field(None, description="Docker Compose service name if applicable")
    instruction: Optional[str] = Field(None, description="Dockerfile instruction (FROM, RUN, etc.)")
    cwe_id: Optional[str] = Field(None, description="CWE ID if applicable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    remediation: str = Field("", description="Suggested remediation steps")
    references: List[str] = Field(default_factory=list, description="Reference URLs")
    mechanism_id: str = Field("", description="Normalization-engine mechanism id (plan 06).")
    confidence_bucket: str = Field("probable", description="Qualitative confidence bucket (plan 06).")
    cis_docker_benchmark: Optional[str] = Field(
        None, description="CIS Docker Benchmark control id (plan 07.8)."
    )
    nist_800_190: Optional[str] = Field(
        None, description="NIST SP 800-190 control reference (plan 07.8)."
    )

    class Config:
        use_enum_values = True


class ContainerConfig(BaseModel):
    """Configuration for container security scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    check_dockerfile: bool = Field(True, description="Check Dockerfile security")
    check_compose: bool = Field(True, description="Check docker-compose.yml security")
    check_secrets: bool = Field(True, description="Check for secrets in container files")
    check_privileged: bool = Field(True, description="Check for privileged containers")
    check_ports: bool = Field(True, description="Check for exposed sensitive ports")
    min_severity: SecuritySeverity = Field(SecuritySeverity.LOW, description="Minimum severity to report")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            ".next",
            "coverage",
            "*.min.js",
            "*.min.css",
            # Exclude Heimdall's own security detection patterns
            "Heimdall/Security",
            "Heimdall\\Security",
            "Asgard/Heimdall",
            "Asgard\\Heimdall",
            # Exclude test files
            "*_Test",
            "*Test",
            "tests",
            "test_*",
            "Ankh_Test",
            "Asgard_Test",
            "Hercules",
            # Exclude tool prototypes
            "_tool_prototypes",
            # Exclude package lock files
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "ui_dump.xml",
        ],
        description="Patterns to exclude from scanning"
    )
    dockerfile_names: List[str] = Field(
        default_factory=lambda: [
            "Dockerfile",
            "Dockerfile.*",
            "*.dockerfile",
            "dockerfile",
        ],
        description="Dockerfile name patterns to scan"
    )
    compose_names: List[str] = Field(
        default_factory=lambda: [
            "docker-compose.yml",
            "docker-compose.yaml",
            "docker-compose.*.yml",
            "docker-compose.*.yaml",
            "compose.yml",
            "compose.yaml",
        ],
        description="Docker Compose file name patterns to scan"
    )
    sensitive_ports: List[int] = Field(
        default_factory=lambda: [
            22,     # SSH
            23,     # Telnet
            3306,   # MySQL
            5432,   # PostgreSQL
            6379,   # Redis
            27017,  # MongoDB
            11211,  # Memcached
            2375,   # Docker daemon
            2376,   # Docker daemon TLS
            5672,   # RabbitMQ
            15672,  # RabbitMQ Management
            9200,   # Elasticsearch
            9300,   # Elasticsearch cluster
        ],
        description="Ports considered sensitive when exposed"
    )
    secret_env_patterns: List[str] = Field(
        default_factory=lambda: [
            "PASSWORD",
            "SECRET",
            "API_KEY",
            "APIKEY",
            "TOKEN",
            "PRIVATE_KEY",
            "CREDENTIALS",
            "AWS_ACCESS_KEY",
            "AWS_SECRET",
        ],
        description="Environment variable name patterns that indicate secrets"
    )

    class Config:
        use_enum_values = True


class ContainerReport(BaseModel):
    """Report from container security analysis."""
    scan_path: str = Field(..., description="Root path that was scanned")
    total_files_scanned: int = Field(0, description="Number of files scanned")
    dockerfiles_analyzed: int = Field(0, description="Number of Dockerfiles analyzed")
    compose_files_analyzed: int = Field(0, description="Number of docker-compose files analyzed")
    total_issues: int = Field(0, description="Total container security issues found")
    critical_issues: int = Field(0, description="Critical severity issues")
    high_issues: int = Field(0, description="High severity issues")
    medium_issues: int = Field(0, description="Medium severity issues")
    low_issues: int = Field(0, description="Low severity issues")
    findings: List[ContainerFinding] = Field(default_factory=list, description="List of findings")
    dockerfile_issues: int = Field(0, description="Issues found in Dockerfiles")
    compose_issues: int = Field(0, description="Issues found in docker-compose files")
    scan_duration_seconds: float = Field(0.0, description="Duration of the scan")
    scanned_at: datetime = Field(default_factory=datetime.now, description="When the scan was performed")
    container_score: float = Field(100.0, ge=0.0, le=100.0, description="Container security score (0-100)")

    class Config:
        use_enum_values = True

    def add_finding(self, finding: ContainerFinding) -> None:
        """Add a container security finding to the report."""
        self.total_issues += 1
        self.findings.append(finding)
        self._increment_severity_count(finding.severity)
        self._calculate_container_score()

    def _increment_severity_count(self, severity: str) -> None:
        """Increment the count for a severity level."""
        if severity == SecuritySeverity.CRITICAL.value:
            self.critical_issues += 1
        elif severity == SecuritySeverity.HIGH.value:
            self.high_issues += 1
        elif severity == SecuritySeverity.MEDIUM.value:
            self.medium_issues += 1
        elif severity == SecuritySeverity.LOW.value:
            self.low_issues += 1

    def _calculate_container_score(self) -> None:
        """Calculate the overall container security score."""
        score = 100.0
        score -= self.critical_issues * 25
        score -= self.high_issues * 10
        score -= self.medium_issues * 5
        score -= self.low_issues * 1
        self.container_score = max(0.0, score)

    @property
    def has_issues(self) -> bool:
        """Check if any container security issues were found."""
        return self.total_issues > 0

    @property
    def is_healthy(self) -> bool:
        """Check if the container security scan is healthy."""
        return self.critical_issues == 0 and self.high_issues == 0

    def get_findings_by_type(self) -> Dict[str, List[ContainerFinding]]:
        """Group findings by type."""
        result: Dict[str, List[ContainerFinding]] = {}
        for finding in self.findings:
            ftype = finding.finding_type
            if ftype not in result:
                result[ftype] = []
            result[ftype].append(finding)
        return result

    def get_findings_by_severity(self) -> Dict[str, List[ContainerFinding]]:
        """Group findings by severity level."""
        result: Dict[str, List[ContainerFinding]] = {
            SecuritySeverity.CRITICAL.value: [],
            SecuritySeverity.HIGH.value: [],
            SecuritySeverity.MEDIUM.value: [],
            SecuritySeverity.LOW.value: [],
            SecuritySeverity.INFO.value: [],
        }
        for finding in self.findings:
            result[finding.severity].append(finding)
        return result
