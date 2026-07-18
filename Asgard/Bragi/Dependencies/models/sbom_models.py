"""
Heimdall SBOM Models

Data models for Software Bill of Materials (SBOM) generation.
Supports SPDX 2.3 and CycloneDX 1.4 formats.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Tuple

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


class VersionResolution(str, Enum):
    """How a component's version field was determined."""
    RESOLVED = "resolved"            # actual installed version from metadata
    DECLARED_ONLY = "declared-only"  # only the declaration spec was available
    UNKNOWN = "unknown"              # no version information at all


class SBOMComponent(BaseModel):
    """A single software component in the SBOM."""
    name: str
    version: str
    version_spec: str = ""
    version_resolution: VersionResolution = VersionResolution.UNKNOWN
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
    # Stable reference for graph edges (CycloneDX bom-ref / SPDX id basis).
    bom_ref: str = ""

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
    # Dependency edges between components as (dependent bom_ref, dependency
    # bom_ref) pairs - the SBOM encodes the graph, not just the set (Plan 03).
    dependencies: List[Tuple[str, str]] = Field(default_factory=list)
    total_components: int = 0
    direct_dependencies: int = 0
    transitive_dependencies: int = 0
    # Honest completeness marker (Plan 03): this SBOM currently covers
    # declared direct dependencies only; a value of "declared-only" says so
    # explicitly instead of silently reporting transitive_dependencies=0.
    resolution: str = Field(
        "declared-only",
        description="SBOM completeness: 'declared-only' (direct declarations) or 'installed-closure'",
    )

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
