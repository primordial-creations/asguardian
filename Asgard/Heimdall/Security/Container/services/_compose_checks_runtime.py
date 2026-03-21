"""
Heimdall Docker Compose Security Checks - runtime privilege checks.

Standalone check functions for privileged mode, capabilities, security options,
volumes, environment secrets, and exposed ports.
"""

import re
from typing import Any, Dict, List

from Asgard.Heimdall.Security.Container.models.container_models import (
    ContainerFinding,
    ContainerFindingType,
)
from Asgard.Heimdall.Security.Container.utilities.dockerfile_parser import extract_code_snippet
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


def check_privileged(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for privileged containers."""
    findings: List[ContainerFinding] = []

    if service_config.get("privileged", False):
        findings.append(ContainerFinding(
            file_path=file_path,
            line_number=service_line,
            finding_type=ContainerFindingType.PRIVILEGED_MODE,
            severity=SecuritySeverity.CRITICAL,
            title="Privileged Container",
            description=f"Service '{service_name}' runs in privileged mode, giving it full access to the host.",
            code_snippet=extract_code_snippet(lines, service_line),
            service_name=service_name,
            cwe_id="CWE-250",
            confidence=0.95,
            remediation="Remove privileged: true. Use specific capabilities instead if needed.",
            references=[
                "https://docs.docker.com/engine/reference/run/#runtime-privilege-and-linux-capabilities",
                "https://cwe.mitre.org/data/definitions/250.html",
            ],
        ))

    return findings


def check_capabilities(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for dangerous capabilities."""
    findings: List[ContainerFinding] = []

    dangerous_caps = {
        "SYS_ADMIN": "Allows mounting filesystems, loading kernel modules, and more",
        "NET_ADMIN": "Allows full network administration",
        "SYS_PTRACE": "Allows process tracing and debugging",
        "DAC_READ_SEARCH": "Allows bypassing file read permission checks",
        "ALL": "Grants all capabilities",
    }

    cap_add = service_config.get("cap_add", [])
    if isinstance(cap_add, list):
        for cap in cap_add:
            cap_upper = str(cap).upper()
            if cap_upper in dangerous_caps:
                findings.append(ContainerFinding(
                    file_path=file_path,
                    line_number=service_line,
                    finding_type=ContainerFindingType.CAP_SYS_ADMIN,
                    severity=SecuritySeverity.HIGH,
                    title=f"Dangerous Capability: {cap_upper}",
                    description=f"Service '{service_name}' has {cap_upper} capability. {dangerous_caps[cap_upper]}.",
                    code_snippet=extract_code_snippet(lines, service_line),
                    service_name=service_name,
                    cwe_id="CWE-250",
                    confidence=0.9,
                    remediation="Remove this capability and use more specific, less privileged alternatives.",
                    references=[
                        "https://docs.docker.com/engine/reference/run/#runtime-privilege-and-linux-capabilities",
                    ],
                ))

    return findings


def check_security_opt(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for disabled security options."""
    findings: List[ContainerFinding] = []

    security_opt = service_config.get("security_opt", [])
    if isinstance(security_opt, list):
        for opt in security_opt:
            opt_str = str(opt).lower()

            if "apparmor:unconfined" in opt_str:
                findings.append(ContainerFinding(
                    file_path=file_path,
                    line_number=service_line,
                    finding_type=ContainerFindingType.NO_SECURITY_OPT,
                    severity=SecuritySeverity.HIGH,
                    title="AppArmor Disabled",
                    description=f"Service '{service_name}' runs with AppArmor disabled.",
                    code_snippet=extract_code_snippet(lines, service_line),
                    service_name=service_name,
                    cwe_id="CWE-693",
                    confidence=0.9,
                    remediation="Use the default AppArmor profile or create a custom profile.",
                    references=[
                        "https://docs.docker.com/engine/security/apparmor/",
                    ],
                ))

            if "seccomp:unconfined" in opt_str:
                findings.append(ContainerFinding(
                    file_path=file_path,
                    line_number=service_line,
                    finding_type=ContainerFindingType.NO_SECURITY_OPT,
                    severity=SecuritySeverity.HIGH,
                    title="Seccomp Disabled",
                    description=f"Service '{service_name}' runs with seccomp disabled.",
                    code_snippet=extract_code_snippet(lines, service_line),
                    service_name=service_name,
                    cwe_id="CWE-693",
                    confidence=0.9,
                    remediation="Use the default seccomp profile or create a custom profile.",
                    references=[
                        "https://docs.docker.com/engine/security/seccomp/",
                    ],
                ))

    return findings


def check_environment_secrets(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
    secret_env_patterns: List[str],
) -> List[ContainerFinding]:
    """Check for secrets in environment variables."""
    findings: List[ContainerFinding] = []

    environment = service_config.get("environment", {})

    env_list: List[str] = []
    if isinstance(environment, dict):
        env_list = [f"{k}={v}" for k, v in environment.items() if v is not None]
    elif isinstance(environment, list):
        env_list = [str(e) for e in environment]

    for env_entry in env_list:
        if "=" not in env_entry:
            continue

        key, value = env_entry.split("=", 1)

        for pattern in secret_env_patterns:
            if re.search(pattern, key, re.IGNORECASE):
                if value and not value.startswith("${") and not value.startswith("$"):
                    findings.append(ContainerFinding(
                        file_path=file_path,
                        line_number=service_line,
                        finding_type=ContainerFindingType.HARDCODED_SECRET,
                        severity=SecuritySeverity.CRITICAL,
                        title="Hardcoded Secret in Environment",
                        description=f"Service '{service_name}' has a hardcoded secret in environment variable '{key}'.",
                        code_snippet=extract_code_snippet(lines, service_line),
                        service_name=service_name,
                        cwe_id="CWE-798",
                        confidence=0.85,
                        remediation="Use Docker secrets, environment files, or external secret management.",
                        references=[
                            "https://docs.docker.com/compose/use-secrets/",
                            "https://cwe.mitre.org/data/definitions/798.html",
                        ],
                    ))
                break

    return findings


def check_volumes(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
) -> List[ContainerFinding]:
    """Check for dangerous volume mounts."""
    findings: List[ContainerFinding] = []

    dangerous_mounts = {
        "/": "Root filesystem",
        "/etc": "System configuration",
        "/var/run/docker.sock": "Docker socket",
        "/proc": "Process information",
        "/sys": "System information",
    }

    volumes = service_config.get("volumes", [])
    if isinstance(volumes, list):
        for volume in volumes:
            volume_str = str(volume)

            if ":" in volume_str:
                parts = volume_str.split(":")
                host_path = parts[0]
            else:
                host_path = volume_str

            for dangerous_path, description in dangerous_mounts.items():
                if host_path == dangerous_path or host_path.startswith(dangerous_path + "/"):
                    findings.append(ContainerFinding(
                        file_path=file_path,
                        line_number=service_line,
                        finding_type=ContainerFindingType.UNRESTRICTED_VOLUME,
                        severity=SecuritySeverity.HIGH,
                        title=f"Dangerous Volume Mount: {dangerous_path}",
                        description=f"Service '{service_name}' mounts {dangerous_path} ({description}) from the host.",
                        code_snippet=extract_code_snippet(lines, service_line),
                        service_name=service_name,
                        cwe_id="CWE-250",
                        confidence=0.9,
                        remediation="Avoid mounting sensitive host paths. Use named volumes or specific subdirectories.",
                        references=[
                            "https://docs.docker.com/storage/volumes/",
                        ],
                    ))
                    break

    return findings


def check_exposed_ports(
    service_name: str,
    service_config: Dict[str, Any],
    lines: List[str],
    file_path: str,
    service_line: int,
    check_ports: bool,
    sensitive_ports: List[int],
) -> List[ContainerFinding]:
    """Check for exposed sensitive ports."""
    findings: List[ContainerFinding] = []

    if not check_ports:
        return findings

    ports = service_config.get("ports", [])
    if isinstance(ports, list):
        for port_mapping in ports:
            port_str = str(port_mapping)

            port_match = re.search(r":(\d+)(?:/|$)", port_str)
            if port_match:
                container_port = int(port_match.group(1))
                if container_port in sensitive_ports:
                    findings.append(ContainerFinding(
                        file_path=file_path,
                        line_number=service_line,
                        finding_type=ContainerFindingType.EXPOSED_PORTS,
                        severity=SecuritySeverity.MEDIUM,
                        title=f"Sensitive Port {container_port} Exposed",
                        description=f"Service '{service_name}' exposes port {container_port}.",
                        code_snippet=extract_code_snippet(lines, service_line),
                        service_name=service_name,
                        cwe_id="CWE-200",
                        confidence=0.7,
                        remediation="Consider if this port needs to be exposed publicly.",
                        references=[
                            "https://docs.docker.com/compose/compose-file/05-services/#ports",
                        ],
                    ))

    return findings
