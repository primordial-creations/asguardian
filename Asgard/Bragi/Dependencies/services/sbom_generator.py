"""
Heimdall SBOM Generator

Generates Software Bill of Materials (SBOM) documents in SPDX 2.3 and
CycloneDX 1.4 formats by scanning dependency declaration files.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from Asgard.Bragi.Dependencies.models.sbom_models import (
    ComponentType,
    SBOMComponent,
    SBOMConfig,
    SBOMDocument,
    SBOMFormat,
)
from Asgard.Bragi.Dependencies.services._sbom_formatters import (
    to_cyclonedx_json,
    to_spdx_json,
)
from Asgard.Bragi.Dependencies.models.sbom_models import VersionResolution
from Asgard.Bragi.Dependencies.services._sbom_parsers import (
    get_installed_version,
    get_license_from_metadata,
    make_purl,
    parse_pyproject_toml,
    parse_requirements_txt,
)


class SBOMGenerator:
    """
    Generates SBOM documents from project dependency files.

    Scans for requirements.txt, pyproject.toml, and other common Python
    dependency declaration files, then produces a structured SBOM document
    in either SPDX 2.3 or CycloneDX 1.4 JSON format.
    """

    def __init__(self, config: Optional[SBOMConfig] = None) -> None:
        self._config = config or SBOMConfig()

    def generate(self, scan_path: Optional[str] = None) -> SBOMDocument:
        """
        Generate an SBOM document by scanning the given path for dependency files.

        Args:
            scan_path: Directory to scan. Overrides config.scan_path when provided.

        Returns:
            A populated SBOMDocument instance.
        """
        resolved_path = Path(scan_path).resolve() if scan_path else Path(self._config.scan_path).resolve()
        project_name = self._config.project_name or resolved_path.name

        components: List[SBOMComponent] = []
        seen: set = set()

        for filename in self._config.requirements_files:
            candidate = resolved_path / filename
            if not candidate.exists():
                continue

            if filename in ("requirements.txt", "requirements-dev.txt"):
                pairs = parse_requirements_txt(str(candidate))
            elif filename == "pyproject.toml":
                pairs = parse_pyproject_toml(str(candidate))
            else:
                pairs = parse_requirements_txt(str(candidate))

            for name, version_spec in pairs:
                key = (name.lower(), version_spec)
                if key in seen:
                    continue
                seen.add(key)

                license_id = get_license_from_metadata(name)

                # Version field carries the RESOLVED installed version when
                # available - never a raw spec string like ">=1.0" (Plan 03).
                resolved = get_installed_version(name)
                if resolved:
                    version = resolved
                    resolution = VersionResolution.RESOLVED
                elif version_spec:
                    version = version_spec
                    resolution = VersionResolution.DECLARED_ONLY
                else:
                    version = ""
                    resolution = VersionResolution.UNKNOWN

                # purl versions must be concrete: a spec range like ">=4.0,<5"
                # is never a valid purl version. Unresolved -> version-less
                # purl, with provenance recorded in version_resolution.
                purl = make_purl(name, resolved)

                component = SBOMComponent(
                    name=name,
                    version=version,
                    version_spec=version_spec,
                    version_resolution=resolution,
                    component_type=ComponentType.LIBRARY,
                    license_id=license_id,
                    purl=purl,
                    is_transitive=False,
                )
                components.append(component)

        fmt = SBOMFormat(self._config.output_format) if isinstance(self._config.output_format, str) else self._config.output_format
        spec_version = "2.3" if fmt == SBOMFormat.SPDX else "1.4"
        document_id = str(uuid.uuid4())
        now = datetime.now()

        document = SBOMDocument(
            format=fmt,
            spec_version=spec_version,
            document_id=document_id,
            document_name=f"SBOM-{project_name}",
            project_name=project_name,
            project_version=self._config.project_version,
            created_at=now,
            components=components,
            total_components=len(components),
            direct_dependencies=len(components),
            # Explicit completeness marker: transitive resolution is not yet
            # performed, and the document says so rather than implying a
            # complete closure with zero transitive dependencies.
            transitive_dependencies=0,
            resolution="declared-only",
        )
        return document

    def to_spdx_json(self, document: SBOMDocument) -> Dict[str, Any]:
        """
        Convert an SBOMDocument to a valid SPDX 2.3 JSON representation.

        Args:
            document: The SBOM document to convert.

        Returns:
            Dictionary conforming to the SPDX 2.3 JSON schema.
        """
        return to_spdx_json(document)

    def to_cyclonedx_json(self, document: SBOMDocument) -> Dict[str, Any]:
        """
        Convert an SBOMDocument to a valid CycloneDX 1.4 JSON representation.

        Args:
            document: The SBOM document to convert.

        Returns:
            Dictionary conforming to the CycloneDX 1.4 JSON schema.
        """
        return to_cyclonedx_json(document)
