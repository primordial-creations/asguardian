"""L3 Contract tests for Volundr (infrastructure generation) models.

Covers Docker, CI/CD, Scaffold, Kubernetes manifest, Helm, and Kustomize models.
"""

import pytest
from pydantic import ValidationError

from Asgard.Volundr import (
    DockerfileConfig,
    PipelineConfig,
    ProjectConfig,
    ScaffoldReport,
    ManifestConfig,
    GeneratedManifest,
    HelmConfig,
    KustomizeConfig,
    CICDPlatform,
)
from Asgard.Volundr.Docker.models.docker_models import BuildStage
from Asgard.Volundr.CICD.models.cicd_models import PipelineStage, CICDPlatform as _CICDPlatform


# ---------------------------------------------------------------------------
# Docker Models
# ---------------------------------------------------------------------------
class TestBuildStageContract:
    def test_requires_name_and_base_image(self):
        with pytest.raises((ValidationError, TypeError)):
            BuildStage()

    def test_instantiates_with_required_fields(self):
        stage = BuildStage(name="builder", base_image="python:3.12-slim")
        assert stage.name == "builder"
        assert stage.base_image == "python:3.12-slim"

    def test_has_run_commands_field(self):
        stage = BuildStage(name="builder", base_image="python:3.12")
        assert hasattr(stage, "run_commands")
        assert isinstance(stage.run_commands, list)

    def test_has_env_vars_field(self):
        stage = BuildStage(name="builder", base_image="python:3.12")
        assert hasattr(stage, "env_vars")


class TestDockerfileConfigContract:
    def test_requires_name_and_stages(self):
        with pytest.raises((ValidationError, TypeError)):
            DockerfileConfig()

    def test_instantiates_with_required_fields(self):
        stage = BuildStage(name="builder", base_image="python:3.12-slim")
        config = DockerfileConfig(name="my-app", stages=[stage])
        assert config.name == "my-app"
        assert len(config.stages) == 1

    def test_has_labels_field(self):
        stage = BuildStage(name="builder", base_image="python:3.12")
        config = DockerfileConfig(name="app", stages=[stage])
        assert hasattr(config, "labels")
        assert isinstance(config.labels, dict)

    def test_has_use_non_root_field(self):
        stage = BuildStage(name="builder", base_image="python:3.12")
        config = DockerfileConfig(name="app", stages=[stage])
        assert hasattr(config, "use_non_root")


# ---------------------------------------------------------------------------
# CI/CD Models
# ---------------------------------------------------------------------------
class TestPipelineStageContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            PipelineStage()

    def test_instantiates_with_required_fields(self):
        stage = PipelineStage(name="test")
        assert stage.name == "test"

    def test_has_steps_field(self):
        stage = PipelineStage(name="build")
        assert hasattr(stage, "steps")
        assert isinstance(stage.steps, list)

    def test_has_needs_field(self):
        stage = PipelineStage(name="deploy")
        assert hasattr(stage, "needs")


class TestPipelineConfigContract:
    def test_requires_name_platform_stages(self):
        with pytest.raises((ValidationError, TypeError)):
            PipelineConfig()

    def test_instantiates_with_required_fields(self):
        stage = PipelineStage(name="test")
        config = PipelineConfig(
            name="my-pipeline",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
        )
        assert config.name == "my-pipeline"
        assert config.platform == CICDPlatform.GITHUB_ACTIONS

    def test_has_triggers_field(self):
        stage = PipelineStage(name="test")
        config = PipelineConfig(
            name="pipeline",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
        )
        assert hasattr(config, "triggers")


# ---------------------------------------------------------------------------
# Scaffold Models
# ---------------------------------------------------------------------------
class TestProjectConfigContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            ProjectConfig()

    def test_instantiates_with_name(self):
        config = ProjectConfig(name="my-service")
        assert config.name == "my-service"

    def test_has_description_field(self):
        config = ProjectConfig(name="my-service")
        assert hasattr(config, "description")

    def test_has_services_field(self):
        config = ProjectConfig(name="my-service")
        assert hasattr(config, "services")


class TestScaffoldReportContract:
    def test_requires_id_project_name_project_type(self):
        with pytest.raises((ValidationError, TypeError)):
            ScaffoldReport()

    def test_instantiates_with_required_fields(self):
        from Asgard.Volundr import ProjectType
        report = ScaffoldReport(
            id="abc-123",
            project_name="my-service",
            project_type=ProjectType.MICROSERVICE,
        )
        assert report.project_name == "my-service"

    def test_has_files_field(self):
        from Asgard.Volundr import ProjectType
        report = ScaffoldReport(
            id="abc-123",
            project_name="svc",
            project_type=ProjectType.MICROSERVICE,
        )
        assert hasattr(report, "files")

    def test_has_total_files_field(self):
        from Asgard.Volundr import ProjectType
        report = ScaffoldReport(
            id="abc-123",
            project_name="svc",
            project_type=ProjectType.MICROSERVICE,
        )
        assert hasattr(report, "total_files")


# ---------------------------------------------------------------------------
# Kubernetes Manifest Models
# ---------------------------------------------------------------------------
class TestManifestConfigContract:
    def test_requires_name_and_image(self):
        with pytest.raises((ValidationError, TypeError)):
            ManifestConfig()

    def test_instantiates_with_required_fields(self):
        config = ManifestConfig(name="my-app", image="my-app:latest")
        assert config.name == "my-app"
        assert config.image == "my-app:latest"

    def test_has_namespace_field(self):
        config = ManifestConfig(name="my-app", image="my-app:latest")
        assert hasattr(config, "namespace")

    def test_has_replicas_field(self):
        config = ManifestConfig(name="my-app", image="my-app:latest")
        assert hasattr(config, "replicas")


class TestGeneratedManifestContract:
    def test_requires_multiple_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GeneratedManifest()

    def test_instantiates_with_required_fields(self):
        manifest = GeneratedManifest(
            id="gen-001",
            config_hash="abc123",
            manifests={},
            yaml_content="---\n",
            best_practice_score=95.0,
        )
        assert manifest.id == "gen-001"
        assert manifest.best_practice_score == 95.0

    def test_has_validation_results_field(self):
        manifest = GeneratedManifest(
            id="gen-001",
            config_hash="abc123",
            manifests={},
            yaml_content="---\n",
            best_practice_score=80.0,
        )
        assert hasattr(manifest, "validation_results")


# ---------------------------------------------------------------------------
# Helm Models
# ---------------------------------------------------------------------------
class TestHelmConfigContract:
    def test_requires_chart_and_values(self):
        with pytest.raises((ValidationError, TypeError)):
            HelmConfig()

    def test_instantiates_with_required_fields(self):
        from Asgard.Volundr import HelmChart, HelmValues
        chart = HelmChart(name="my-chart")
        values = HelmValues(image_repository="my-repo/my-app")
        config = HelmConfig(chart=chart, values=values)
        assert config.chart.name == "my-chart"

    def test_has_generate_tests_field(self):
        from Asgard.Volundr import HelmChart, HelmValues
        chart = HelmChart(name="my-chart")
        config = HelmConfig(chart=chart, values=HelmValues(image_repository="my-repo/my-app"))
        assert hasattr(config, "generate_tests")


# ---------------------------------------------------------------------------
# Kustomize Models
# ---------------------------------------------------------------------------
class TestKustomizeConfigContract:
    def test_requires_base_and_image(self):
        with pytest.raises((ValidationError, TypeError)):
            KustomizeConfig()

    def test_instantiates_with_required_fields(self):
        from Asgard.Volundr import KustomizeBase
        base = KustomizeBase(name="base")
        config = KustomizeConfig(base=base, image="my-app:latest")
        assert config.image == "my-app:latest"

    def test_has_overlays_field(self):
        from Asgard.Volundr import KustomizeBase
        base = KustomizeBase(name="base")
        config = KustomizeConfig(base=base, image="my-app:latest")
        assert hasattr(config, "overlays")
