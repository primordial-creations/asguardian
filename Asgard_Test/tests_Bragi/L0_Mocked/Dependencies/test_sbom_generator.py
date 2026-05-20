"""
Tests for Heimdall SBOM Generator Service

Unit tests for SBOM document generation, SPDX and CycloneDX format output,
and SBOMDocument/SBOMComponent model correctness.
"""

import json
import tempfile
from pathlib import Path

import pytest

from Asgard.Bragi.Dependencies.models.sbom_models import (
    SBOMComponent,
    SBOMConfig,
    SBOMDocument,
    SBOMFormat,
    ComponentType,
)
from Asgard.Bragi.Dependencies.services.sbom_generator import SBOMGenerator


class TestSBOMFormat:
    """Tests for SBOMFormat enum."""

    def test_spdx_value(self):
        """Test that SPDX enum has the expected string value."""
        assert SBOMFormat.SPDX == "spdx"

    def test_cyclonedx_value(self):
        """Test that CYCLONEDX enum has the expected string value."""
        assert SBOMFormat.CYCLONEDX == "cyclonedx"

    def test_enum_from_string(self):
        """Test constructing SBOMFormat from a string value."""
        assert SBOMFormat("spdx") == SBOMFormat.SPDX
        assert SBOMFormat("cyclonedx") == SBOMFormat.CYCLONEDX


class TestSBOMComponent:
    """Tests for SBOMComponent model fields."""

    def test_required_fields(self):
        """Test creating a component with required name and version fields."""
        component = SBOMComponent(name="requests", version="2.28.0")
        assert component.name == "requests"
        assert component.version == "2.28.0"

    def test_default_component_type(self):
        """Test that component_type defaults to LIBRARY."""
        component = SBOMComponent(name="flask", version="2.0.0")
        assert component.component_type == ComponentType.LIBRARY.value

    def test_license_id_field(self):
        """Test that license_id can be set and retrieved."""
        component = SBOMComponent(name="pytest", version="7.0.0", license_id="MIT")
        assert component.license_id == "MIT"

    def test_license_id_defaults_to_empty_string(self):
        """Test that license_id defaults to empty string."""
        component = SBOMComponent(name="numpy", version="1.24.0")
        assert component.license_id == ""

    def test_purl_field(self):
        """Test that purl can be set on a component."""
        component = SBOMComponent(
            name="requests",
            version="2.28.0",
            purl="pkg:pypi/requests@2.28.0",
        )
        assert component.purl == "pkg:pypi/requests@2.28.0"

    def test_is_transitive_defaults_false(self):
        """Test that is_transitive defaults to False."""
        component = SBOMComponent(name="click", version="8.0.0")
        assert component.is_transitive is False


class TestSBOMGenerator:
    """Tests for SBOMGenerator class."""

    def test_generate_with_requirements_txt(self):
        """Test generating an SBOM from a directory with a requirements.txt file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\nflask>=2.0.0\npytest==7.1.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert isinstance(document, SBOMDocument)
            assert document.total_components == 3
            assert document.direct_dependencies == 3

    def test_generate_returns_sbom_document(self):
        """Test that generate() returns an SBOMDocument instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            assert isinstance(document, SBOMDocument)

    def test_generate_empty_project(self):
        """Test generating an SBOM for a project with no requirements file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert document.total_components == 0
            assert len(document.components) == 0

    def test_generate_project_name_from_directory(self):
        """Test that project name is derived from the directory name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            assert document.project_name == Path(tmpdir).name

    def test_generate_custom_project_name(self):
        """Test that config project_name overrides the directory name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SBOMConfig(project_name="my-custom-project")
            generator = SBOMGenerator(config)
            document = generator.generate(tmpdir)
            assert document.project_name == "my-custom-project"

    def test_generate_component_count_matches_requirements(self):
        """Test that component count matches the number of entries in requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text(
                "requests==2.28.0\n"
                "flask>=2.0.0\n"
                "click~=8.0\n"
                "pytest!=7.0.0\n"
            )

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert len(document.components) == 4
            assert document.total_components == 4

    def test_generate_skips_comments_and_blank_lines(self):
        """Test that comment lines and blank lines are not parsed as dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text(
                "# This is a comment\n"
                "\n"
                "requests==2.28.0\n"
                "# Another comment\n"
                "\n"
                "flask>=2.0.0\n"
            )

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert document.total_components == 2

    def test_generate_deduplicates_components(self):
        """Test that duplicate entries are deduplicated based on name and version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\nrequests==2.28.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert document.total_components == 1

    def test_generate_component_has_purl(self):
        """Test that generated components have a purl field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert len(document.components) == 1
            component = document.components[0]
            assert "requests" in component.purl
            assert "pypi" in component.purl

    def test_to_spdx_json_is_valid_json_structure(self):
        """Test that to_spdx_json() returns a dict with required SPDX fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            spdx = generator.to_spdx_json(document)

            assert isinstance(spdx, dict)
            serialized = json.dumps(spdx)
            parsed = json.loads(serialized)

            assert "spdxVersion" in parsed
            assert "SPDXID" in parsed
            assert "name" in parsed

    def test_to_spdx_json_required_fields(self):
        """Test that SPDX JSON output contains all required top-level fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\nflask>=2.0.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            spdx = generator.to_spdx_json(document)

            assert spdx["spdxVersion"] == "SPDX-2.3"
            assert spdx["SPDXID"] == "SPDXRef-DOCUMENT"
            assert "packages" in spdx
            assert "creationInfo" in spdx
            assert "dataLicense" in spdx
            assert "documentNamespace" in spdx

    def test_to_spdx_json_packages_count(self):
        """Test that SPDX JSON packages list length matches component count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\nflask>=2.0.0\npytest==7.1.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            spdx = generator.to_spdx_json(document)

            assert len(spdx["packages"]) == 3

    def test_to_cyclonedx_json_required_fields(self):
        """Test that CycloneDX JSON output contains all required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\nflask>=2.0.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            cdx = generator.to_cyclonedx_json(document)

            assert isinstance(cdx, dict)
            assert cdx["bomFormat"] == "CycloneDX"
            assert "specVersion" in cdx
            assert "components" in cdx

    def test_to_cyclonedx_json_is_valid_json(self):
        """Test that CycloneDX output can be serialized to valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            cdx = generator.to_cyclonedx_json(document)

            serialized = json.dumps(cdx)
            parsed = json.loads(serialized)

            assert parsed["bomFormat"] == "CycloneDX"
            assert "specVersion" in parsed
            assert "components" in parsed

    def test_to_cyclonedx_json_components_count(self):
        """Test that CycloneDX components list matches the document component count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\nflask>=2.0.0\npytest==7.1.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            cdx = generator.to_cyclonedx_json(document)

            assert len(cdx["components"]) == 3

    def test_to_cyclonedx_json_empty_components(self):
        """Test CycloneDX output for a project with no dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            cdx = generator.to_cyclonedx_json(document)

            assert cdx["bomFormat"] == "CycloneDX"
            assert cdx["components"] == []

    def test_to_spdx_json_empty_project(self):
        """Test SPDX output for a project with no dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            spdx = generator.to_spdx_json(document)

            assert spdx["spdxVersion"] == "SPDX-2.3"
            assert spdx["packages"] == []

    def test_generate_with_spdx_format_config(self):
        """Test that SPDX format config is reflected in the document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\n")

            config = SBOMConfig(output_format=SBOMFormat.SPDX)
            generator = SBOMGenerator(config)
            document = generator.generate(tmpdir)

            assert document.spec_version == "2.3"

    def test_generate_with_cyclonedx_format_config(self):
        """Test that CycloneDX format config is reflected in the document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("requests==2.28.0\n")

            config = SBOMConfig(output_format=SBOMFormat.CYCLONEDX)
            generator = SBOMGenerator(config)
            document = generator.generate(tmpdir)

            assert document.spec_version == "1.4"

    def test_generate_with_requirements_dev_txt(self):
        """Test that requirements-dev.txt entries are parsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_dev_file = Path(tmpdir) / "requirements-dev.txt"
            req_dev_file.write_text("black==23.1.0\nmypy>=1.0.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert document.total_components == 2

    def test_generate_skips_editable_installs(self):
        """Test that -e editable install lines are not parsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("-e .\nrequests==2.28.0\n")

            generator = SBOMGenerator()
            document = generator.generate(tmpdir)

            assert document.total_components == 1

    def test_sbom_document_has_document_id(self):
        """Test that a generated SBOMDocument has a non-empty document_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            assert document.document_id != ""

    def test_sbom_document_has_created_at(self):
        """Test that a generated SBOMDocument has a created_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SBOMGenerator()
            document = generator.generate(tmpdir)
            assert document.created_at is not None
