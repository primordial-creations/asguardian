"""
Heimdall Dockerfile Data Models

Dataclasses for representing parsed Dockerfile structures.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DockerfileInstruction:
    """Represents a parsed Dockerfile instruction."""
    instruction: str
    arguments: str
    line_number: int
    raw_line: str
    is_continuation: bool = False


@dataclass
class DockerfileStage:
    """Represents a build stage in a multi-stage Dockerfile."""
    name: Optional[str]
    base_image: str
    tag: Optional[str]
    start_line: int
    instructions: List[DockerfileInstruction]
