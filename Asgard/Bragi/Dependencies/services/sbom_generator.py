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
    get_package_meta_fields,
    get_record_checksum,
    get_requires,
    make_purl,
    parse_pyproject_toml,
    parse_requirements_txt,
)


def _canonical(name: str) -> str:
    """PEP 503 canonical package name."""
    import re
    return re.sub(r"[-_.]+", "-", name).lower()


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

        declared: List[tuple] = []
        seen: set = set()

        for filename in self._config.requirements_files:
            candidate = resolved_path / filename
            if not candidate.exists():
                continue

            if filename == "pyproject.toml":
                pairs = parse_pyproject_toml(str(candidate))
            else:
                pairs = parse_requirements_txt(str(candidate))

            for name, version_spec in pairs:
                key = _canonical(name)
                if key in seen:
                    continue
                seen.add(key)
                declared.append((name, version_spec))

        components: List[SBOMComponent] = []
        edges: List[tuple] = []
        roots_resolved = 0

        by_canonical: Dict[str, SBOMComponent] = {}
        for name, version_spec in declared:
            component = self._build_component(name, version_spec,
                                              is_transitive=False)
            components.append(component)
            by_canonical[_canonical(name)] = component
            if component.version_resolution == VersionResolution.RESOLVED.value:
                roots_resolved += 1

        # Transitive resolution (Plan 03 Phase C): walk Requires-Dist from
        # the declared roots through installed metadata to the full closure.
        closure_complete = bool(declared) and roots_resolved == len(declared)
        if self._config.include_transitive:
            queue = [name for name, _ in declared]
            visited = {_canonical(name) for name, _ in declared}
            while queue:
                current = queue.pop(0)
                for requirement in get_requires(current):
                    canonical = _canonical(requirement)
                    source = by_canonical.get(_canonical(current))
                    if canonical not in visited:
                        visited.add(canonical)
                        child = self._build_component(requirement, "",
                                                      is_transitive=True)
                        if child.version_resolution != VersionResolution.RESOLVED.value:
                            closure_complete = False
                        components.append(child)
                        by_canonical[canonical] = child
                        queue.append(requirement)
                    target = by_canonical.get(canonical)
                    if source is not None and target is not None:
                        edge = (source.bom_ref, target.bom_ref)
                        if edge not in edges:
                            edges.append(edge)

        direct_count = len(declared)
        transitive_count = len(components) - direct_count

        # Explicit completeness marker (DEEPTHINK_14 discipline): the SBOM is
        # only an "installed-closure" when every declared root resolved from
        # the environment; otherwise it degrades to an honest declared-only
        # document rather than silently posing as complete.
        if self._config.include_transitive and closure_complete:
            resolution = "installed-closure"
        else:
            resolution = "declared-only"

        fmt = SBOMFormat(self._config.output_format) if isinstance(self._config.output_format, str) else self._config.output_format
        spec_version = "2.3" if fmt == SBOMFormat.SPDX else "1.5"
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
            dependencies=edges,
            total_components=len(components),
            direct_dependencies=direct_count,
            transitive_dependencies=transitive_count,
            resolution=resolution,
        )
        return document

    def _build_component(
        self, name: str, version_spec: str, *, is_transitive: bool
    ) -> SBOMComponent:
        """Build one component with resolved version, hash, and PEP 639 license."""
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
        meta_fields = get_package_meta_fields(name) if resolved else {}

        return SBOMComponent(
            name=name,
            version=version,
            version_spec=version_spec,
            version_resolution=resolution,
            component_type=ComponentType.LIBRARY,
            license_id=license_id,
            purl=purl,
            bom_ref=purl or f"pkg:{name}",
            checksum_sha256=get_record_checksum(name) if resolved else "",
            author=meta_fields.get("author", ""),
            supplier=meta_fields.get("supplier", ""),
            homepage=meta_fields.get("homepage", ""),
            description=meta_fields.get("description", ""),
            is_transitive=is_transitive,
        )

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
