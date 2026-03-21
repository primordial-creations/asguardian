"""
Heimdall Dockerfile Security Checks

Re-export shim and RUN pattern check function. All structural checks are in
_dockerfile_structural_checks; pattern definitions are in _dockerfile_patterns.
"""

from typing import List

from Asgard.Heimdall.Security.Container.models.container_models import ContainerFinding
from Asgard.Heimdall.Security.Container.services._dockerfile_patterns import (
    DOCKERFILE_PATTERNS,
    DockerfilePattern,
)
from Asgard.Heimdall.Security.Container.services._dockerfile_structural_checks import (
    check_add_instead_of_copy,
    check_exposed_ports,
    check_latest_tag,
    check_missing_healthcheck,
    check_root_user,
    check_secrets_in_env,
)
from Asgard.Heimdall.Security.Container.utilities.dockerfile_parser import (
    DockerfileInstruction,
    extract_code_snippet,
    find_run_commands,
)


def check_run_patterns(
    instructions: List[DockerfileInstruction],
    lines: List[str],
    file_path: str,
    patterns: List[DockerfilePattern],
) -> List[ContainerFinding]:
    """Check RUN instructions for security patterns."""
    findings: List[ContainerFinding] = []

    run_instructions = find_run_commands(instructions)

    for instr in run_instructions:
        for pattern in patterns:
            if pattern.instruction_filter and pattern.instruction_filter != instr.instruction:
                continue

            match = pattern.pattern.search(instr.arguments)
            if match:
                findings.append(ContainerFinding(
                    file_path=file_path,
                    line_number=instr.line_number,
                    finding_type=pattern.finding_type,
                    severity=pattern.severity,
                    title=pattern.title,
                    description=pattern.description,
                    code_snippet=extract_code_snippet(lines, instr.line_number),
                    instruction="RUN",
                    cwe_id=pattern.cwe_id,
                    confidence=pattern.confidence,
                    remediation=pattern.remediation,
                    references=[
                        f"https://cwe.mitre.org/data/definitions/{pattern.cwe_id.replace('CWE-', '')}.html",
                    ],
                ))

    return findings


__all__ = [
    "DockerfilePattern",
    "DOCKERFILE_PATTERNS",
    "check_root_user",
    "check_latest_tag",
    "check_secrets_in_env",
    "check_exposed_ports",
    "check_add_instead_of_copy",
    "check_missing_healthcheck",
    "check_run_patterns",
]
