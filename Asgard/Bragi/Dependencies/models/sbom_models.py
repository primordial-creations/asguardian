"""
Heimdall SBOM Models

Data models for Software Bill of Materials (SBOM) generation.
Supports SPDX 2.3 and CycloneDX 1.4 formats.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class SBOMFormat(str, Enum):
    """Supported SBOM output formats."""
    SPDX = "spdx"
    CYCLONEDX = "cyclonedx"


class ComponentType(str, Enum):
    """SBOM component classification types."""
    LIBRARY = "library"
    FRAMEWORK = "framework"
    APPLICATION = "application"
    CONTAINER = "container"
    DEVICE = "device"
    FIRMWARE = "firmware"


class SBOMComponent(BaseModel):
    """A single software component in the SBOM."""
    name: str
    version: str
    component_type: ComponentType = ComponentType.LIBRARY
    license_id: str = ""
    purl: str = ""
    cpe: str = ""
    description: str = ""
    homepage: str = ""
    download_url: str = ""
    checksum_sha256: str = ""
    supplier: str = ""
    author: str = ""
    is_transitive: bool = False

    class Config:
        use_enum_values = True


class SBOMDocument(BaseModel):
    """A complete SBOM document in the chosen format."""
    format: SBOMFormat
    spec_version: str
    document_id: str
    document_name: str
    project_name: str
    project_version: str = ""
    created_at: datetime
    creator_tool: str = "Asgard Heimdall SBOM Generator"
    creator_organization: str = ""
    components: List[SBOMComponent] = Field(default_factory=list)
    total_components: int = 0
    direct_dependencies: int = 0
    transitive_dependencies: int = 0

    class Config:
        use_enum_values = True


class SBOMConfig(BaseModel):
    """Configuration for SBOM generation."""
    scan_path: Path = Field(default_factory=lambda: Path("."))
    output_format: SBOMFormat = SBOMFormat.SPDX
    project_name: str = ""
    project_version: str = ""
    include_transitive: bool = True
    requirements_files: List[str] = Field(
        default_factory=lambda: [
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "Pipfile",
        ]
    )

    class Config:
        use_enum_values = True
