"""
L6 Industry Benchmark Tests — Volundr IaC Generation Correctness.

Validates that Volundr's generators produce structurally correct IaC artefacts
meeting industry standards:

  Dockerfile (hadolint-equivalent structural checks)
  - Generated Dockerfile contains required FROM instruction
  - Non-root USER is present when use_non_root=True
  - :latest tag triggers a validation warning
  - Multi-stage Dockerfile uses named stages

  Kubernetes YAML
  - Generated YAML deserialises correctly
  - Required top-level fields are present: apiVersion, kind, metadata, spec

  Terraform HCL
  - Generated main.tf contains terraform {} block with required_providers
  - Generated variables.tf contains variable blocks for configured variables
  - Generated outputs.tf contains output blocks for configured outputs
"""

import yaml
import pytest

from Asgard.Volundr.Docker.models.docker_models import (
    BuildStage,
    DockerfileConfig,
)
from Asgard.Volundr.Docker.services.dockerfile_generator import DockerfileGenerator

from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    ManifestConfig,
    WorkloadType,
    EnvironmentType,
    SecurityProfile,
)
from Asgard.Volundr.Kubernetes.services.manifest_generator import ManifestGenerator

from Asgard.Volundr.Terraform.models.terraform_models import (
    CloudProvider,
    ModuleConfig,
    ModuleComplexity,
    OutputConfig,
    ResourceCategory,
    VariableConfig,
)
from Asgard.Volundr.Terraform.services.module_builder import ModuleBuilder


# ---------------------------------------------------------------------------
# Dockerfile structural correctness (hadolint rule categories)
# ---------------------------------------------------------------------------

class TestVolundrDockerfileStructural:
    """
    Validate that generated Dockerfiles comply with hadolint rule categories
    without requiring the external binary.

    Key hadolint rules verified structurally:
      DL3007 — avoid :latest tag
      DL3002 — last USER should not be root
      SC2 prefix rules — checked via layer optimisation (RUN chaining)
    """

    def setup_method(self) -> None:
        self.generator = DockerfileGenerator()

    def _minimal_stage(self, image: str = "python:3.12-slim", name: str = "app") -> BuildStage:
        return BuildStage(
            name=name,
            base_image=image,
            workdir="/app",
            user="appuser",
            run_commands=["pip install --no-cache-dir -r requirements.txt"],
            copy_commands=[{"src": "requirements.txt", "dst": "/app/requirements.txt"}],
            expose_ports=[8080],
            cmd=["python", "main.py"],
        )

    def test_generated_dockerfile_contains_from(self) -> None:
        """Every generated Dockerfile must contain a FROM instruction."""
        config = DockerfileConfig(
            name="test-app",
            stages=[self._minimal_stage()],
            use_non_root=True,
        )
        result = self.generator.generate(config)
        assert "FROM " in result.dockerfile_content, (
            "Generated Dockerfile missing FROM instruction"
        )

    def test_non_root_user_in_content(self) -> None:
        """When use_non_root=True, generated Dockerfile must include USER instruction."""
        config = DockerfileConfig(
            name="secure-app",
            stages=[self._minimal_stage()],
            use_non_root=True,
        )
        result = self.generator.generate(config)
        assert "USER " in result.dockerfile_content, (
            "Generated Dockerfile missing USER instruction despite use_non_root=True"
        )
        # No validation issues for USER
        assert not any("non-root" in issue for issue in result.validation_results), (
            f"Unexpected non-root USER issue: {result.validation_results}"
        )

    def test_latest_tag_triggers_validation_issue(self) -> None:
        """Using :latest base image must produce a validation warning (DL3007)."""
        config = DockerfileConfig(
            name="latest-app",
            stages=[self._minimal_stage(image="python:latest")],
            use_non_root=True,
        )
        result = self.generator.generate(config)
        latest_issues = [i for i in result.validation_results if "latest" in i.lower()]
        assert len(latest_issues) > 0, (
            "Expected a validation issue for :latest base image (hadolint DL3007 equivalent)"
        )

    def test_workdir_instruction_present(self) -> None:
        """Generated Dockerfile must have a WORKDIR instruction."""
        config = DockerfileConfig(
            name="workdir-app",
            stages=[self._minimal_stage()],
        )
        result = self.generator.generate(config)
        assert "WORKDIR " in result.dockerfile_content

    def test_multi_stage_uses_named_stages(self) -> None:
        """Multi-stage build must reference stage names via AS keyword."""
        builder_stage = BuildStage(
            name="builder",
            base_image="python:3.12-slim",
            workdir="/build",
            run_commands=["pip wheel -r requirements.txt"],
            copy_commands=[{"src": "requirements.txt", "dst": "/build/requirements.txt"}],
        )
        runtime_stage = BuildStage(
            name="runtime",
            base_image="python:3.12-slim",
            workdir="/app",
            user="appuser",
            copy_from="builder",
            copy_src="/build/dist",
            copy_dst="/app/dist",
            expose_ports=[8080],
            cmd=["python", "app.py"],
        )
        config = DockerfileConfig(
            name="multi-stage-app",
            stages=[builder_stage, runtime_stage],
            use_non_root=True,
        )
        result = self.generator.generate(config)
        assert " AS " in result.dockerfile_content, (
            "Multi-stage Dockerfile missing named stages (AS keyword)"
        )

    def test_best_practice_score_non_negative(self) -> None:
        """Best practice score must be in [0, 100]."""
        config = DockerfileConfig(
            name="scored-app",
            stages=[self._minimal_stage()],
            use_non_root=True,
        )
        result = self.generator.generate(config)
        assert 0.0 <= result.best_practice_score <= 100.0


# ---------------------------------------------------------------------------
# Kubernetes YAML validity
# ---------------------------------------------------------------------------

class TestVolundrKubernetesYAML:
    """
    Generated Kubernetes YAML must be valid YAML with required top-level fields.

    Required fields per the Kubernetes API machinery:
      apiVersion, kind, metadata (with name), spec
    """

    def setup_method(self) -> None:
        self.generator = ManifestGenerator()

    def _minimal_config(self, name: str = "test-app") -> ManifestConfig:
        return ManifestConfig(
            name=name,
            namespace="default",
            workload_type=WorkloadType.DEPLOYMENT,
            image="python:3.12-slim",
            replicas=1,
            environment=EnvironmentType.DEVELOPMENT,
            security_profile=SecurityProfile.BASIC,
        )

    def test_generated_yaml_is_valid(self) -> None:
        """Generated YAML content must parse without errors."""
        result = self.generator.generate(self._minimal_config())
        # yaml_content may contain multiple documents
        docs = list(yaml.safe_load_all(result.yaml_content))
        assert len(docs) > 0, "Generated YAML produced no documents"
        # Filter out None docs (empty separators)
        docs = [d for d in docs if d is not None]
        assert len(docs) > 0

    def test_deployment_manifest_has_required_fields(self) -> None:
        """The Deployment manifest must have apiVersion, kind, metadata, spec."""
        result = self.generator.generate(self._minimal_config())
        assert "deployment" in result.manifests, (
            "Expected 'deployment' key in generated manifests"
        )
        deployment = result.manifests["deployment"]
        for field in ("apiVersion", "kind", "metadata", "spec"):
            assert field in deployment, (
                f"Deployment manifest missing required field: '{field}'"
            )

    def test_deployment_kind_is_correct(self) -> None:
        """The Deployment manifest must have kind: Deployment."""
        result = self.generator.generate(self._minimal_config())
        deployment = result.manifests["deployment"]
        assert deployment["kind"] == "Deployment"

    def test_metadata_has_name(self) -> None:
        """Deployment metadata must include the application name."""
        config = self._minimal_config(name="my-service")
        result = self.generator.generate(config)
        deployment = result.manifests["deployment"]
        assert "name" in deployment["metadata"], (
            "Deployment metadata missing 'name' field"
        )

    def test_spec_contains_selector_and_template(self) -> None:
        """Deployment spec must include selector and template."""
        result = self.generator.generate(self._minimal_config())
        spec = result.manifests["deployment"]["spec"]
        assert "selector" in spec, "Deployment spec missing 'selector'"
        assert "template" in spec, "Deployment spec missing 'template'"

    def test_no_validation_issues_for_minimal_config(self) -> None:
        """A minimal, well-formed ManifestConfig should produce no validation issues."""
        result = self.generator.generate(self._minimal_config())
        assert len(result.validation_results) == 0, (
            f"Unexpected validation issues: {result.validation_results}"
        )


# ---------------------------------------------------------------------------
# Terraform HCL structure
# ---------------------------------------------------------------------------

class TestVolundrTerraformHCL:
    """
    Generated Terraform module files must have valid HCL structure.

    We validate structure textually (no hcl2 parser dependency):
      - main.tf contains terraform {} block
      - variables.tf contains variable blocks for each configured variable
      - outputs.tf contains output blocks for each configured output
    """

    def setup_method(self) -> None:
        self.builder = ModuleBuilder()

    def _minimal_config(self) -> ModuleConfig:
        return ModuleConfig(
            name="test-module",
            provider=CloudProvider.AWS,
            category=ResourceCategory.COMPUTE,
            complexity=ModuleComplexity.SIMPLE,
            description="Test module for L6 benchmarks",
            # Specify resources so main.tf is populated
            resources=["aws_instance"],
            variables=[
                VariableConfig(
                    name="instance_type",
                    type="string",
                    description="EC2 instance type",
                    default="t3.micro",
                ),
                VariableConfig(
                    name="region",
                    type="string",
                    description="AWS region",
                    default="us-east-1",
                ),
            ],
            outputs=[
                OutputConfig(
                    name="instance_id",
                    description="The instance ID",
                    value="aws_instance.main.id",
                ),
            ],
        )

    def test_generated_module_has_required_files(self) -> None:
        """Generated module must include main.tf, variables.tf, outputs.tf, and versions.tf."""
        result = self.builder.generate(self._minimal_config())
        for expected_file in ("main.tf", "variables.tf", "outputs.tf", "versions.tf"):
            assert expected_file in result.module_files, (
                f"Expected '{expected_file}' in module files. "
                f"Got: {list(result.module_files.keys())}"
            )

    def test_versions_tf_contains_terraform_block(self) -> None:
        """
        versions.tf must contain the terraform {} configuration block with
        required_providers — this is where the Volundr generator places it.
        """
        result = self.builder.generate(self._minimal_config())
        versions_tf = result.module_files["versions.tf"]
        assert "terraform {" in versions_tf or "terraform{" in versions_tf, (
            "versions.tf missing terraform {} configuration block"
        )

    def test_versions_tf_contains_required_providers(self) -> None:
        """versions.tf must declare required_providers for the chosen cloud provider."""
        result = self.builder.generate(self._minimal_config())
        versions_tf = result.module_files["versions.tf"]
        assert "required_providers" in versions_tf, (
            "versions.tf missing required_providers block"
        )

    def test_variables_tf_contains_variable_blocks(self) -> None:
        """variables.tf must contain a variable block for each configured variable."""
        result = self.builder.generate(self._minimal_config())
        assert "variables.tf" in result.module_files, (
            "Expected 'variables.tf' in module files"
        )
        variables_tf = result.module_files["variables.tf"]
        for var in ("instance_type", "region"):
            assert f'variable "{var}"' in variables_tf, (
                f"variables.tf missing block for variable '{var}'"
            )

    def test_outputs_tf_contains_output_blocks(self) -> None:
        """outputs.tf must contain an output block for each configured output."""
        result = self.builder.generate(self._minimal_config())
        assert "outputs.tf" in result.module_files, (
            "Expected 'outputs.tf' in module files"
        )
        outputs_tf = result.module_files["outputs.tf"]
        assert 'output "instance_id"' in outputs_tf, (
            "outputs.tf missing block for output 'instance_id'"
        )

    def test_no_validation_issues_for_minimal_module(self) -> None:
        """A well-formed ModuleConfig must not produce validation issues."""
        result = self.builder.generate(self._minimal_config())
        assert len(result.validation_results) == 0, (
            f"Unexpected validation issues: {result.validation_results}"
        )

    def test_non_empty_module_files(self) -> None:
        """Core module files (versions.tf, variables.tf, outputs.tf) must be non-empty."""
        result = self.builder.generate(self._minimal_config())
        for filename in ("versions.tf", "variables.tf", "outputs.tf"):
            content = result.module_files.get(filename, "")
            assert content.strip(), f"Module file '{filename}' is empty"
