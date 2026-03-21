"""
Heimdall Security Container Dockerfile Parser Utilities

Helper functions for parsing and analyzing Dockerfile content.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from Asgard.Heimdall.Security.Container.utilities._dockerfile_models import (
    DockerfileInstruction,
    DockerfileStage,
)
from Asgard.Heimdall.Security.Container.utilities._dockerfile_parse_helpers import (
    parse_env_instruction,
    parse_expose_instruction,
    parse_from_instruction,
    parse_instruction_line,
)


def parse_dockerfile(content: str) -> List[DockerfileInstruction]:
    """
    Parse Dockerfile content into a list of instructions.

    Args:
        content: Raw Dockerfile content

    Returns:
        List of DockerfileInstruction objects
    """
    instructions: List[DockerfileInstruction] = []
    lines = content.split("\n")

    current_instruction = ""
    current_line_number = 0
    is_continuation = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if is_continuation:
            current_instruction += " " + stripped.rstrip("\\").strip()
            if not stripped.endswith("\\"):
                instructions.append(parse_instruction_line(
                    current_instruction,
                    current_line_number,
                    line
                ))
                is_continuation = False
                current_instruction = ""
        else:
            if stripped.endswith("\\"):
                is_continuation = True
                current_instruction = stripped.rstrip("\\").strip()
                current_line_number = i
            else:
                instructions.append(parse_instruction_line(stripped, i, line))

    if current_instruction:
        instructions.append(parse_instruction_line(
            current_instruction,
            current_line_number,
            current_instruction
        ))

    return instructions


def parse_stages(content: str) -> List[DockerfileStage]:
    """
    Parse multi-stage Dockerfile into stages.

    Args:
        content: Raw Dockerfile content

    Returns:
        List of DockerfileStage objects
    """
    instructions = parse_dockerfile(content)
    stages: List[DockerfileStage] = []
    current_stage: Optional[DockerfileStage] = None

    for instr in instructions:
        if instr.instruction == "FROM":
            if current_stage:
                stages.append(current_stage)

            base_image, tag, name = parse_from_instruction(instr.arguments)
            current_stage = DockerfileStage(
                name=name,
                base_image=base_image,
                tag=tag,
                start_line=instr.line_number,
                instructions=[instr],
            )
        elif current_stage:
            current_stage.instructions.append(instr)

    if current_stage:
        stages.append(current_stage)

    return stages


def extract_env_vars(instructions: List[DockerfileInstruction]) -> Dict[str, str]:
    """
    Extract environment variables from Dockerfile instructions.

    Args:
        instructions: List of parsed instructions

    Returns:
        Dictionary of environment variable names to values
    """
    env_vars: Dict[str, str] = {}

    for instr in instructions:
        if instr.instruction == "ENV":
            env_pairs = parse_env_instruction(instr.arguments)
            env_vars.update(env_pairs)

    return env_vars


def extract_exposed_ports(instructions: List[DockerfileInstruction]) -> List[Tuple[int, int]]:
    """
    Extract exposed ports from Dockerfile instructions.

    Args:
        instructions: List of parsed instructions

    Returns:
        List of (port, line_number) tuples
    """
    ports: List[Tuple[int, int]] = []

    for instr in instructions:
        if instr.instruction == "EXPOSE":
            port_numbers = parse_expose_instruction(instr.arguments)
            for port in port_numbers:
                ports.append((port, instr.line_number))

    return ports


def has_user_instruction(instructions: List[DockerfileInstruction]) -> bool:
    """
    Check if Dockerfile has a USER instruction (not running as root).

    Args:
        instructions: List of parsed instructions

    Returns:
        True if USER instruction is present
    """
    for instr in instructions:
        if instr.instruction == "USER":
            user = instr.arguments.strip().lower()
            if user and user != "root" and user != "0":
                return True
    return False


def has_healthcheck(instructions: List[DockerfileInstruction]) -> bool:
    """
    Check if Dockerfile has a HEALTHCHECK instruction.

    Args:
        instructions: List of parsed instructions

    Returns:
        True if HEALTHCHECK instruction is present
    """
    for instr in instructions:
        if instr.instruction == "HEALTHCHECK":
            if instr.arguments.strip().upper() != "NONE":
                return True
    return False


def find_run_commands(instructions: List[DockerfileInstruction]) -> List[DockerfileInstruction]:
    """
    Find all RUN instructions in the Dockerfile.

    Args:
        instructions: List of parsed instructions

    Returns:
        List of RUN instructions
    """
    return [instr for instr in instructions if instr.instruction == "RUN"]


def find_copy_add_instructions(
    instructions: List[DockerfileInstruction]
) -> List[DockerfileInstruction]:
    """
    Find all COPY and ADD instructions in the Dockerfile.

    Args:
        instructions: List of parsed instructions

    Returns:
        List of COPY and ADD instructions
    """
    return [instr for instr in instructions if instr.instruction in ("COPY", "ADD")]


def extract_code_snippet(lines: List[str], line_number: int, context_lines: int = 2) -> str:
    """
    Extract a code snippet around a specific line.

    Args:
        lines: List of file lines
        line_number: Line number (1-indexed)
        context_lines: Number of context lines before and after

    Returns:
        Code snippet with context
    """
    if not lines or line_number < 1:
        return ""

    start_idx = max(0, line_number - 1 - context_lines)
    end_idx = min(len(lines), line_number + context_lines)

    snippet_lines = []
    for i in range(start_idx, end_idx):
        line_num = i + 1
        marker = ">>> " if line_num == line_number else "    "
        line_content = lines[i] if i < len(lines) else ""
        snippet_lines.append(f"{marker}{line_num}: {line_content.rstrip()}")

    return "\n".join(snippet_lines)
