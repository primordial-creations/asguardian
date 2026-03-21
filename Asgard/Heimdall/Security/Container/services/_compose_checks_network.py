"""
Heimdall Docker Compose Security Checks - network, PID, and image checks.

Standalone check functions for network_mode, PID namespace, image tags,
and read-only filesystem.
"""

from typing import Any, Dict, List

from Asgard.Heimdall.Security.Container.models.container_models import (
    ContainerFinding,
    ContainerFindingType,
)
from Asgard.Heimdall.Security.Container.utilities.dockerfile_parser import extract_code_snippet
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


def check_network_mode(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for host network mode."""
    findings: List[ContainerFinding] = []

    network_mode = service_config.get("network_mode", "")
    if network_mode == "host":
        findings.append(ContainerFinding(
            file_path=file_path,
            line_number=service_line,
            finding_type=ContainerFindingType.HOST_NETWORK,
            severity=SecuritySeverity.HIGH,
            title="Host Network Mode",
            description=f"Service '{service_name}' uses host network mode, bypassing Docker network isolation.",
            code_snippet=extract_code_snippet(lines, service_line),
            service_name=service_name,
            cwe_id="CWE-653",
            confidence=0.95,
            remediation="Use Docker networks instead of host network mode for better isolation.",
            references=[
                "https://docs.docker.com/network/",
            ],
        ))

    return findings


def check_pid_mode(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for host PID namespace."""
    findings: List[ContainerFinding] = []

    pid_mode = service_config.get("pid", "")
    if pid_mode == "host":
        findings.append(ContainerFinding(
            file_path=file_path,
            line_number=service_line,
            finding_type=ContainerFindingType.HOST_PID,
            severity=SecuritySeverity.HIGH,
            title="Host PID Namespace",
            description=f"Service '{service_name}' shares the host PID namespace, allowing it to see and interact with all host processes.",
            code_snippet=extract_code_snippet(lines, service_line),
            service_name=service_name,
            cwe_id="CWE-653",
            confidence=0.95,
            remediation="Remove pid: host unless absolutely necessary for debugging.",
            references=[
                "https://docs.docker.com/engine/reference/run/#pid-settings---pid",
            ],
        ))

    return findings


def check_image_tag(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for latest tag in images."""
    findings: List[ContainerFinding] = []

    image = service_config.get("image", "")
    if isinstance(image, str):
        if ":" not in image or image.endswith(":latest"):
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=service_line,
                finding_type=ContainerFindingType.LATEST_TAG,
                severity=SecuritySeverity.MEDIUM,
                title="Using :latest Tag",
                description=f"Service '{service_name}' uses :latest tag or no tag for image '{image}'.",
                code_snippet=extract_code_snippet(lines, service_line),
                service_name=service_name,
                cwe_id="CWE-829",
                confidence=0.85,
                remediation="Pin images to specific version tags or digest hashes.",
                references=[
                    "https://docs.docker.com/engine/reference/commandline/tag/",
                ],
            ))

    return findings


def check_read_only(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for writable root filesystem."""
    findings: List[ContainerFinding] = []

    if not service_config.get("read_only", False):
        findings.append(ContainerFinding(
            file_path=file_path,
            line_number=service_line,
            finding_type=ContainerFindingType.WRITABLE_ROOT_FS,
            severity=SecuritySeverity.LOW,
            title="Writable Root Filesystem",
            description=f"Service '{service_name}' has a writable root filesystem.",
            code_snippet=extract_code_snippet(lines, service_line),
            service_name=service_name,
            cwe_id="CWE-732",
            confidence=0.6,
            remediation="Consider adding read_only: true and using volumes for writable paths.",
            references=[
                "https://docs.docker.com/compose/compose-file/05-services/#read_only",
            ],
        ))

    return findings
