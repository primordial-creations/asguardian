"""
Tests for SBOM v2 (Plan 03 Phase C): transitive installed closure, RECORD
checksums, completeness markers, and CycloneDX 1.5 / SPDX relationship
encoding of the dependency graph.
"""

import json
import tempfile
from pathlib import Path

import pytest

from Asgard.Bragi.Dependencies.models.sbom_models import SBOMConfig, SBOMFormat
from Asgard.Bragi.Dependencies.services.sbom_generator import SBOMGenerator
from Asgard.Bragi.Dependencies.services._sbom_parsers import (
    get_record_checksum,
    get_requires,
    parse_requires_dist,
)


def generate_for(requirements: str, **config_kwargs):
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "requirements.txt").write_text(requirements)
        generator = SBOMGenerator(SBOMConfig(**config_kwargs)
                                  if config_kwargs else None)
        return generator, generator.generate(tmpdir)


class TestTransitiveClosure:
    def test_installed_root_expands_to_closure(self):
        # pytest is installed in the test environment and requires pluggy.
        _, document = generate_for("pytest\n")
        names = {c.name.lower() for c in document.components}
        assert "pluggy" in names
        transitive = [c for c in document.components if c.is_transitive]
        assert transitive, "expected transitive components in the closure"
        assert document.direct_dependencies == 1
        assert document.transitive_dependencies == len(document.components) - 1
        assert document.resolution == "installed-closure"

    def test_closure_edges_recorded(self):
        _, document = generate_for("pytest\n")
        assert document.dependencies, "expected dependency edges"
        root_ref = next(
            c.bom_ref for c in document.components if not c.is_transitive)
        assert any(src == root_ref for src, _ in document.dependencies)

    def test_uninstalled_root_degrades_to_declared_only(self):
        _, document = generate_for("no-such-package-asgard-xyz==1.0\n")
        assert document.resolution == "declared-only"
        assert document.components[0].version_resolution == "declared-only"
        assert document.components[0].checksum_sha256 == ""

    def test_include_transitive_false_stays_declared_only(self):
        _, document = generate_for("pytest\n", include_transitive=False)
        assert document.total_components == 1
        assert document.resolution == "declared-only"
        assert document.dependencies == []

    def test_resolved_component_has_record_checksum(self):
        _, document = generate_for("pytest\n")
        root = document.components[0]
        assert root.version_resolution == "resolved"
        assert len(root.checksum_sha256) == 64
        # Deterministic: same environment, same checksum.
        assert root.checksum_sha256 == get_record_checksum("pytest")


class TestFormats:
    def test_cyclonedx_15_bom_refs_and_dependencies(self):
        generator, document = generate_for(
            "pytest\n", output_format=SBOMFormat.CYCLONEDX)
        cdx = generator.to_cyclonedx_json(document)
        assert cdx["specVersion"] == "1.5"
        assert cdx["serialNumber"].startswith("urn:uuid:")
        assert all("bom-ref" in c for c in cdx["components"])
        assert "dependencies" in cdx
        refs = {c["bom-ref"] for c in cdx["components"]}
        for entry in cdx["dependencies"]:
            assert entry["ref"] in refs
            assert set(entry["dependsOn"]) <= refs
        json.dumps(cdx)  # serializable

    def test_spdx_relationships_encode_graph(self):
        generator, document = generate_for("pytest\n")
        spdx = generator.to_spdx_json(document)
        relationships = spdx["relationships"]
        types = {r["relationshipType"] for r in relationships}
        assert "DESCRIBES" in types
        assert "DEPENDS_ON" in types
        ids = {p["SPDXID"] for p in spdx["packages"]}
        for r in relationships:
            if r["relationshipType"] == "DEPENDS_ON":
                assert r["spdxElementId"] in ids
                assert r["relatedSpdxElement"] in ids

    def test_spdx_checksums_emitted(self):
        generator, document = generate_for("pytest\n")
        spdx = generator.to_spdx_json(document)
        root = spdx["packages"][0]
        assert root["checksums"][0]["algorithm"] == "SHA256"


class TestRequiresParsing:
    def test_extra_gated_requirement_skipped(self):
        assert parse_requires_dist('coverage[toml]>=5.2.1; extra == "testing"') == ""

    def test_plain_requirement_name_extracted(self):
        assert parse_requires_dist("pluggy<2,>=1.5") == "pluggy"

    def test_environment_markers_evaluated(self):
        # Satisfied marker: requirement kept.
        assert parse_requires_dist(
            'tomli>=1; python_version >= "3.0"') == "tomli"
        # Unsatisfied marker: requirement dropped for THIS environment.
        assert parse_requires_dist(
            'tomli>=1; python_version < "3.0"') == ""

    def test_get_requires_for_installed_package(self):
        assert "pluggy" in [n.lower() for n in get_requires("pytest")]

    def test_get_requires_missing_package_empty(self):
        assert get_requires("no-such-package-asgard-xyz") == []
