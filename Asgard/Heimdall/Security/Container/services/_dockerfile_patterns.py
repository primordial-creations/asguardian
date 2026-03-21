"""
Heimdall Dockerfile Security - Pattern Definitions

DockerfilePattern class and the list of security patterns for use
in RUN instruction analysis.
"""

import re
from typing import List, Optional

from Asgard.Heimdall.Security.Container.models.container_models import ContainerFindingType
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class DockerfilePattern:
    """Defines a pattern for detecting Dockerfile security issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        finding_type: ContainerFindingType,
        severity: SecuritySeverity,
        title: str,
        description: str,
        cwe_id: str,
        remediation: str,
        confidence: float = 0.7,
        instruction_filter: Optional[str] = None,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.finding_type = finding_type
        self.severity = severity
        self.title = title
        self.description = description
        self.cwe_id = cwe_id
        self.remediation = remediation
        self.confidence = confidence
        self.instruction_filter = instruction_filter


DOCKERFILE_PATTERNS: List[DockerfilePattern] = [
    DockerfilePattern(
        name="chmod_777",
        pattern=r"chmod\s+777",
        finding_type=ContainerFindingType.CHMOD_777,
        severity=SecuritySeverity.HIGH,
        title="Chmod 777 Permission",
        description="Setting file permissions to 777 allows any user to read, write, and execute the file.",
        cwe_id="CWE-732",
        remediation="Use more restrictive permissions. For executables, use 755 or 750. For files, use 644 or 640.",
        confidence=0.95,
        instruction_filter="RUN",
    ),
    DockerfilePattern(
        name="apt_install_sudo",
        pattern=r"apt(?:-get)?\s+install\s+.*\bsudo\b",
        finding_type=ContainerFindingType.APT_INSTALL_SUDO,
        severity=SecuritySeverity.MEDIUM,
        title="Sudo Installed in Container",
        description="Installing sudo in a container can enable privilege escalation attacks.",
        cwe_id="CWE-269",
        remediation="Avoid installing sudo. Use multi-stage builds or run commands as the appropriate user directly.",
        confidence=0.85,
        instruction_filter="RUN",
    ),
    DockerfilePattern(
        name="curl_pipe_bash",
        pattern=r"curl\s+[^|]*\|\s*(?:bash|sh)",
        finding_type=ContainerFindingType.CURL_PIPE_BASH,
        severity=SecuritySeverity.HIGH,
        title="Curl Piped to Shell",
        description="Piping curl output directly to a shell is dangerous and can execute malicious code.",
        cwe_id="CWE-94",
        remediation="Download scripts first, verify their contents or checksums, then execute them.",
        confidence=0.9,
        instruction_filter="RUN",
    ),
    DockerfilePattern(
        name="wget_pipe_bash",
        pattern=r"wget\s+[^|]*\|\s*(?:bash|sh)",
        finding_type=ContainerFindingType.CURL_PIPE_BASH,
        severity=SecuritySeverity.HIGH,
        title="Wget Piped to Shell",
        description="Piping wget output directly to a shell is dangerous and can execute malicious code.",
        cwe_id="CWE-94",
        remediation="Download scripts first, verify their contents or checksums, then execute them.",
        confidence=0.9,
        instruction_filter="RUN",
    ),
]
