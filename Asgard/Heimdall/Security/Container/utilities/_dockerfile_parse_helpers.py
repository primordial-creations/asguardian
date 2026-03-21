"""
Heimdall Dockerfile Parse Helpers

Private helper functions for parsing individual Dockerfile instruction lines.
"""

import re
from typing import Dict, List, Optional, Tuple

from Asgard.Heimdall.Security.Container.utilities._dockerfile_models import DockerfileInstruction


def parse_instruction_line(line: str, line_number: int, raw_line: str) -> DockerfileInstruction:
    """
    Parse a single Dockerfile instruction line.

    Args:
        line: The instruction line (without continuation)
        line_number: Line number in the file
        raw_line: The raw line content

    Returns:
        DockerfileInstruction object
    """
    parts = line.split(None, 1)
    instruction = parts[0].upper() if parts else ""
    arguments = parts[1] if len(parts) > 1 else ""

    return DockerfileInstruction(
        instruction=instruction,
        arguments=arguments,
        line_number=line_number,
        raw_line=raw_line.strip(),
    )


def parse_from_instruction(arguments: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Parse FROM instruction arguments.

    Args:
        arguments: FROM instruction arguments

    Returns:
        Tuple of (base_image, tag, stage_name)
    """
    as_match = re.search(r"\s+[Aa][Ss]\s+(\S+)", arguments)
    stage_name = as_match.group(1) if as_match else None

    if as_match:
        arguments = arguments[:as_match.start()]

    arguments = arguments.strip()

    if ":" in arguments:
        parts = arguments.split(":", 1)
        base_image = parts[0]
        tag = parts[1].split()[0] if parts[1] else None
    else:
        base_image = arguments.split()[0] if arguments else ""
        tag = None

    return base_image, tag, stage_name


def parse_env_instruction(arguments: str) -> Dict[str, str]:
    """
    Parse ENV instruction arguments.

    Args:
        arguments: ENV instruction arguments

    Returns:
        Dictionary of environment variable names to values
    """
    env_vars: Dict[str, str] = {}

    key_value_pattern = r'(\w+)=(?:"([^"]*)"|\'([^\']*)\'|(\S+))'
    matches = re.findall(key_value_pattern, arguments)

    for match in matches:
        key = match[0]
        value = match[1] or match[2] or match[3]
        env_vars[key] = value

    if not matches:
        parts = arguments.split(None, 1)
        if len(parts) == 2:
            env_vars[parts[0]] = parts[1]

    return env_vars


def parse_expose_instruction(arguments: str) -> List[int]:
    """
    Parse EXPOSE instruction arguments.

    Args:
        arguments: EXPOSE instruction arguments

    Returns:
        List of port numbers
    """
    ports: List[int] = []

    port_pattern = r"(\d+)(?:/(?:tcp|udp))?"
    matches = re.findall(port_pattern, arguments)

    for match in matches:
        try:
            ports.append(int(match))
        except ValueError:
            pass

    return ports
