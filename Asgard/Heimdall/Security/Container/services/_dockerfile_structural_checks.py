"""
Heimdall Dockerfile Security - Structural Check Functions

Standalone check functions for Dockerfile structural security issues:
root user, latest tag, secrets in ENV, exposed ports, ADD vs COPY,
and missing HEALTHCHECK.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Container.models.container_models import (
    ContainerFinding,
    ContainerFindingType,
)
from Asgard.Heimdall.Security.Container.utilities.dockerfile_parser import (
    DockerfileInstruction,
    extract_code_snippet,
    extract_env_vars,
    extract_exposed_ports,
    has_healthcheck,
    has_user_instruction,
)
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


def check_root_user(
    instructions: List[DockerfileInstruction],
    lines: List[str],
    file_path: str,
) -> List[ContainerFinding]:
    """Check if container runs as root."""
    findings: List[ContainerFinding] = []

    if not has_user_instruction(instructions):
        last_from = None
        for instr in instructions:
            if instr.instruction == "FROM":
                last_from = instr

        if last_from:
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=last_from.line_number,
                finding_type=ContainerFindingType.ROOT_USER,
                severity=SecuritySeverity.HIGH,
                title="Container Running as Root",
                description="Container runs as root user. This increases the attack surface and potential damage from container escape.",
                code_snippet=extract_code_snippet(lines, last_from.line_number),
                instruction="FROM",
                cwe_id="CWE-250",
                confidence=0.85,
                remediation="Add a USER instruction to run the container as a non-root user.",
                references=[
                    "https://docs.docker.com/engine/security/rootless/",
                    "https://cwe.mitre.org/data/definitions/250.html",
                ],
            ))

    return findings


def check_latest_tag(
    stages: List,
    lines: List[str],
    file_path: str,
) -> List[ContainerFinding]:
    """Check for usage of :latest tag."""
    findings: List[ContainerFinding] = []

    for stage in stages:
        if stage.tag is None or stage.tag.lower() == "latest":
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=stage.start_line,
                finding_type=ContainerFindingType.LATEST_TAG,
                severity=SecuritySeverity.MEDIUM,
                title="Using :latest Tag",
                description=f"Image '{stage.base_image}' uses :latest tag or no tag. This makes builds non-reproducible and may introduce unexpected changes.",
                code_snippet=extract_code_snippet(lines, stage.start_line),
                instruction="FROM",
                cwe_id="CWE-829",
                confidence=0.9,
                remediation="Pin images to specific version tags or digest hashes for reproducible builds.",
                references=[
                    "https://docs.docker.com/engine/reference/builder/#from",
                ],
            ))

    return findings


def check_secrets_in_env(
    instructions: List[DockerfileInstruction],
    lines: List[str],
    file_path: str,
    secret_env_patterns: List[str],
) -> List[ContainerFinding]:
    """Check for secrets in ENV instructions."""
    findings: List[ContainerFinding] = []

    extract_env_vars(instructions)

    for instr in instructions:
        if instr.instruction == "ENV":
            for pattern in secret_env_patterns:
                if re.search(pattern, instr.arguments, re.IGNORECASE):
                    if "=" in instr.arguments:
                        findings.append(ContainerFinding(
                            file_path=file_path,
                            line_number=instr.line_number,
                            finding_type=ContainerFindingType.SECRETS_IN_IMAGE,
                            severity=SecuritySeverity.CRITICAL,
                            title="Secret in ENV Instruction",
                            description="Hardcoded secret found in ENV instruction. Secrets are visible in image history and layers.",
                            code_snippet=extract_code_snippet(lines, instr.line_number),
                            instruction="ENV",
                            cwe_id="CWE-798",
                            confidence=0.85,
                            remediation="Use build arguments with --build-arg, Docker secrets, or environment variables at runtime instead.",
                            references=[
                                "https://docs.docker.com/engine/swarm/secrets/",
                                "https://cwe.mitre.org/data/definitions/798.html",
                            ],
                        ))
                    break

    return findings


def check_exposed_ports(
    instructions: List[DockerfileInstruction],
    lines: List[str],
    file_path: str,
    check_ports: bool,
    sensitive_ports: List[int],
) -> List[ContainerFinding]:
    """Check for exposed sensitive ports."""
    findings: List[ContainerFinding] = []

    if not check_ports:
        return findings

    ports = extract_exposed_ports(instructions)

    for port, line_number in ports:
        if port in sensitive_ports:
            findings.append(ContainerFinding(
                file_path=file_path,
                line_number=line_number,
                finding_type=ContainerFindingType.EXPOSED_PORTS,
                severity=SecuritySeverity.MEDIUM,
                title=f"Sensitive Port {port} Exposed",
                description=f"Port {port} is exposed. This port is commonly associated with sensitive services.",
                code_snippet=extract_code_snippet(lines, line_number),
                instruction="EXPOSE",
                cwe_id="CWE-200",
                confidence=0.7,
                remediation="Consider if this port needs to be exposed. Use Docker networks for internal communication.",
                references=[
                    "https://docs.docker.com/network/",
                ],
            ))

    return findings


def check_add_instead_of_copy(
    instructions: List[DockerfileInstruction],
    lines: List[str],
    file_path: str,
) -> List[ContainerFinding]:
    """Check for ADD used instead of COPY."""
    findings: List[ContainerFinding] = []

    for instr in instructions:
        if instr.instruction == "ADD":
            args = instr.arguments.lower()
            if not (args.startswith("http://") or args.startswith("https://") or ".tar" in args):
                findings.append(ContainerFinding(
                    file_path=file_path,
                    line_number=instr.line_number,
                    finding_type=ContainerFindingType.ADD_INSTEAD_OF_COPY,
                    severity=SecuritySeverity.LOW,
                    title="ADD Used Instead of COPY",
                    description="ADD has extra features (URL download, tar extraction) that make it less predictable. Use COPY for simple file copies.",
                    code_snippet=extract_code_snippet(lines, instr.line_number),
                    instruction="ADD",
                    cwe_id="CWE-829",
                    confidence=0.8,
                    remediation="Use COPY instead of ADD for copying local files. ADD is only needed for URL downloads or tar extraction.",
                    references=[
                        "https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#add-or-copy",
                    ],
                ))

    return findings


def check_missing_healthcheck(
    instructions: List[DockerfileInstruction],
    lines: List[str],
    file_path: str,
) -> List[ContainerFinding]:
    """Check for missing HEALTHCHECK instruction."""
    findings: List[ContainerFinding] = []

    if not has_healthcheck(instructions):
        last_line = len(lines)
        findings.append(ContainerFinding(
            file_path=file_path,
            line_number=last_line,
            finding_type=ContainerFindingType.MISSING_HEALTHCHECK,
            severity=SecuritySeverity.LOW,
            title="Missing HEALTHCHECK Instruction",
            description="No HEALTHCHECK instruction found. Health checks help Docker detect when a container is unhealthy.",
            code_snippet="",
            instruction=None,
            cwe_id="CWE-693",
            confidence=0.7,
            remediation="Add a HEALTHCHECK instruction to verify the container is functioning correctly.",
            references=[
                "https://docs.docker.com/engine/reference/builder/#healthcheck",
            ],
        ))

    return findings
