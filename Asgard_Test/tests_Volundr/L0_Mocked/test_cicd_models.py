"""
L0 Unit Tests for Volundr CICD Models

Tests Pydantic models for CI/CD pipeline configuration.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from Asgard.Volundr.CICD.models.cicd_models import (
    CICDPlatform,
    DeploymentStrategy,
    TriggerType,
    StepConfig,
    PipelineStage,
    TriggerConfig,
    PipelineConfig,
    GeneratedPipeline,
)


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestCICDPlatform:
    """Test CICDPlatform enum"""

    def test_cicd_platform_values(self):
        """Test all CICD platform values are accessible"""
        assert CICDPlatform.GITHUB_ACTIONS == "github_actions"
        assert CICDPlatform.GITLAB_CI == "gitlab_ci"
        assert CICDPlatform.AZURE_DEVOPS == "azure_devops"
        assert CICDPlatform.JENKINS == "jenkins"
        assert CICDPlatform.CIRCLECI == "circleci"

    def test_cicd_platform_from_string(self):
        """Test creating CICDPlatform from string"""
        assert CICDPlatform("github_actions") == CICDPlatform.GITHUB_ACTIONS
        assert CICDPlatform("gitlab_ci") == CICDPlatform.GITLAB_CI


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDeploymentStrategy:
    """Test DeploymentStrategy enum"""

    def test_deployment_strategy_values(self):
        """Test all deployment strategy values are accessible"""
        assert DeploymentStrategy.ROLLING == "rolling"
        assert DeploymentStrategy.BLUE_GREEN == "blue_green"
        assert DeploymentStrategy.CANARY == "canary"
        assert DeploymentStrategy.RECREATE == "recreate"
        assert DeploymentStrategy.A_B_TESTING == "ab_testing"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestTriggerType:
    """Test TriggerType enum"""

    def test_trigger_type_values(self):
        """Test all trigger type values are accessible"""
        assert TriggerType.PUSH == "push"
        assert TriggerType.PULL_REQUEST == "pull_request"
        assert TriggerType.TAG == "tag"
        assert TriggerType.SCHEDULE == "schedule"
        assert TriggerType.MANUAL == "manual"
        assert TriggerType.WORKFLOW_DISPATCH == "workflow_dispatch"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestStepConfig:
    """Test StepConfig model"""

    def test_step_config_minimal(self):
        """Test StepConfig with minimal required fields"""
        step = StepConfig(name="Checkout code")

        assert step.name == "Checkout code"
        assert step.run is None
        assert step.uses is None
        assert step.with_params == {}
        assert step.env == {}
        assert step.if_condition is None
        assert step.continue_on_error is False
        assert step.timeout_minutes is None

    def test_step_config_with_run(self):
        """Test StepConfig with run command"""
        step = StepConfig(
            name="Run tests",
            run="pytest tests/"
        )

        assert step.name == "Run tests"
        assert step.run == "pytest tests/"

    def test_step_config_with_uses(self):
        """Test StepConfig with uses action"""
        step = StepConfig(
            name="Setup Python",
            uses="actions/setup-python@v5",
            with_params={"python-version": "3.12"}
        )

        assert step.uses == "actions/setup-python@v5"
        assert step.with_params["python-version"] == "3.12"

    def test_step_config_with_environment(self):
        """Test StepConfig with environment variables"""
        step = StepConfig(
            name="Deploy",
            run="./deploy.sh",
            env={
                "ENVIRONMENT": "production",
                "API_KEY": "${{ secrets.API_KEY }}"
            }
        )

        assert len(step.env) == 2
        assert step.env["ENVIRONMENT"] == "production"

    def test_step_config_with_conditional(self):
        """Test StepConfig with conditional execution"""
        step = StepConfig(
            name="Deploy to production",
            run="./deploy.sh",
            if_condition="github.ref == 'refs/heads/main'"
        )

        assert step.if_condition == "github.ref == 'refs/heads/main'"

    def test_step_config_with_error_handling(self):
        """Test StepConfig with continue on error"""
        step = StepConfig(
            name="Lint code",
            run="flake8 .",
            continue_on_error=True
        )

        assert step.continue_on_error is True

    def test_step_config_with_timeout(self):
        """Test StepConfig with timeout"""
        step = StepConfig(
            name="Long running task",
            run="./long-task.sh",
            timeout_minutes=120
        )

        assert step.timeout_minutes == 120


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestPipelineStage:
    """Test PipelineStage model"""

    def test_pipeline_stage_minimal(self):
        """Test PipelineStage with minimal required fields"""
        stage = PipelineStage(name="build")

        assert stage.name == "build"
        assert stage.runs_on == "ubuntu-latest"
        assert stage.needs == []
        assert stage.steps == []
        assert stage.env == {}
        assert stage.services == {}
        assert stage.strategy is None
        assert stage.if_condition is None
        assert stage.timeout_minutes == 60
        assert stage.continue_on_error is False
        assert stage.environment is None

    def test_pipeline_stage_with_steps(self):
        """Test PipelineStage with steps"""
        steps = [
            StepConfig(name="Checkout", uses="actions/checkout@v4"),
            StepConfig(name="Build", run="make build")
        ]

        stage = PipelineStage(
            name="build",
            steps=steps
        )

        assert len(stage.steps) == 2
        assert stage.steps[0].name == "Checkout"
        assert stage.steps[1].run == "make build"

    def test_pipeline_stage_with_dependencies(self):
        """Test PipelineStage with dependencies on other stages"""
        stage = PipelineStage(
            name="deploy",
            needs=["build", "test"]
        )

        assert len(stage.needs) == 2
        assert "build" in stage.needs
        assert "test" in stage.needs

    def test_pipeline_stage_with_custom_runner(self):
        """Test PipelineStage with custom runner"""
        stage = PipelineStage(
            name="build",
            runs_on="self-hosted"
        )

        assert stage.runs_on == "self-hosted"

    def test_pipeline_stage_with_services(self):
        """Test PipelineStage with service containers"""
        stage = PipelineStage(
            name="test",
            services={
                "postgres": {
                    "image": "postgres:15",
                    "env": {"POSTGRES_PASSWORD": "test"}
                }
            }
        )

        assert "postgres" in stage.services
        assert stage.services["postgres"]["image"] == "postgres:15"

    def test_pipeline_stage_with_matrix_strategy(self):
        """Test PipelineStage with matrix strategy"""
        stage = PipelineStage(
            name="test",
            strategy={
                "matrix": {
                    "python-version": ["3.10", "3.11", "3.12"],
                    "os": ["ubuntu-latest", "windows-latest"]
                }
            }
        )

        assert stage.strategy is not None
        assert "matrix" in stage.strategy
        assert len(stage.strategy["matrix"]["python-version"]) == 3

    def test_pipeline_stage_with_environment(self):
        """Test PipelineStage with deployment environment"""
        stage = PipelineStage(
            name="deploy",
            environment="production"
        )

        assert stage.environment == "production"

    def test_pipeline_stage_with_timeout(self):
        """Test PipelineStage with custom timeout"""
        stage = PipelineStage(
            name="long-build",
            timeout_minutes=180
        )

        assert stage.timeout_minutes == 180


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestTriggerConfig:
    """Test TriggerConfig model"""

    def test_trigger_config_minimal(self):
        """Test TriggerConfig with minimal required fields"""
        trigger = TriggerConfig(type=TriggerType.PUSH)

        assert trigger.type == TriggerType.PUSH
        assert trigger.branches == []
        assert trigger.paths == []
        assert trigger.paths_ignore == []
        assert trigger.tags == []
        assert trigger.schedule is None

    def test_trigger_config_push_with_branches(self):
        """Test TriggerConfig for push with branch filters"""
        trigger = TriggerConfig(
            type=TriggerType.PUSH,
            branches=["main", "develop"]
        )

        assert trigger.type == TriggerType.PUSH
        assert len(trigger.branches) == 2
        assert "main" in trigger.branches

    def test_trigger_config_with_paths(self):
        """Test TriggerConfig with path filters"""
        trigger = TriggerConfig(
            type=TriggerType.PUSH,
            paths=["src/**", "tests/**"],
            paths_ignore=["docs/**", "*.md"]
        )

        assert len(trigger.paths) == 2
        assert len(trigger.paths_ignore) == 2
        assert "src/**" in trigger.paths
        assert "*.md" in trigger.paths_ignore

    def test_trigger_config_tag_trigger(self):
        """Test TriggerConfig for tag triggers"""
        trigger = TriggerConfig(
            type=TriggerType.TAG,
            tags=["v*", "release-*"]
        )

        assert trigger.type == TriggerType.TAG
        assert len(trigger.tags) == 2

    def test_trigger_config_schedule(self):
        """Test TriggerConfig for scheduled triggers"""
        trigger = TriggerConfig(
            type=TriggerType.SCHEDULE,
            schedule="0 0 * * *"
        )

        assert trigger.type == TriggerType.SCHEDULE
        assert trigger.schedule == "0 0 * * *"

    def test_trigger_config_pull_request(self):
        """Test TriggerConfig for pull request triggers"""
        trigger = TriggerConfig(
            type=TriggerType.PULL_REQUEST,
            branches=["main"]
        )

        assert trigger.type == TriggerType.PULL_REQUEST


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestPipelineConfig:
    """Test PipelineConfig model"""

    def test_pipeline_config_minimal(self):
        """Test PipelineConfig with minimal required fields"""
        stage = PipelineStage(name="build")
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage]
        )

        assert config.name == "CI"
        assert config.platform == CICDPlatform.GITHUB_ACTIONS
        assert len(config.stages) == 1
        assert config.triggers == []
        assert config.env == {}
        assert config.secrets == []
        assert config.concurrency is None
        assert config.deployment_strategy == DeploymentStrategy.ROLLING
        assert config.docker_registry is None
        assert config.kubernetes_cluster is None

    def test_pipeline_config_with_triggers(self):
        """Test PipelineConfig with multiple triggers"""
        stage = PipelineStage(name="build")
        triggers = [
            TriggerConfig(type=TriggerType.PUSH, branches=["main"]),
            TriggerConfig(type=TriggerType.PULL_REQUEST, branches=["main"]),
            TriggerConfig(type=TriggerType.SCHEDULE, schedule="0 2 * * *")
        ]

        config = PipelineConfig(
            name="CI/CD",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            triggers=triggers
        )

        assert len(config.triggers) == 3
        assert config.triggers[0].type == TriggerType.PUSH
        assert config.triggers[2].schedule == "0 2 * * *"

    def test_pipeline_config_with_multiple_stages(self):
        """Test PipelineConfig with multiple stages"""
        stages = [
            PipelineStage(name="build"),
            PipelineStage(name="test", needs=["build"]),
            PipelineStage(name="deploy", needs=["test"])
        ]

        config = PipelineConfig(
            name="Pipeline",
            platform=CICDPlatform.GITLAB_CI,
            stages=stages
        )

        assert len(config.stages) == 3
        assert config.stages[1].needs == ["build"]
        assert config.stages[2].needs == ["test"]

    def test_pipeline_config_with_environment(self):
        """Test PipelineConfig with global environment variables"""
        stage = PipelineStage(name="build")
        config = PipelineConfig(
            name="Build",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            env={
                "NODE_ENV": "production",
                "CI": "true"
            }
        )

        assert len(config.env) == 2
        assert config.env["NODE_ENV"] == "production"

    def test_pipeline_config_with_secrets(self):
        """Test PipelineConfig with required secrets"""
        stage = PipelineStage(name="deploy")
        config = PipelineConfig(
            name="Deploy",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            secrets=["DOCKER_PASSWORD", "KUBE_CONFIG", "API_KEY"]
        )

        assert len(config.secrets) == 3
        assert "DOCKER_PASSWORD" in config.secrets

    def test_pipeline_config_with_concurrency(self):
        """Test PipelineConfig with concurrency settings"""
        stage = PipelineStage(name="build")
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            concurrency={
                "group": "${{ github.workflow }}-${{ github.ref }}",
                "cancel-in-progress": True
            }
        )

        assert config.concurrency is not None
        assert config.concurrency["cancel-in-progress"] is True

    def test_pipeline_config_deployment_strategies(self):
        """Test PipelineConfig with different deployment strategies"""
        stage = PipelineStage(name="deploy")

        config1 = PipelineConfig(
            name="Rolling",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            deployment_strategy=DeploymentStrategy.ROLLING
        )
        assert config1.deployment_strategy == DeploymentStrategy.ROLLING

        config2 = PipelineConfig(
            name="BlueGreen",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            deployment_strategy=DeploymentStrategy.BLUE_GREEN
        )
        assert config2.deployment_strategy == DeploymentStrategy.BLUE_GREEN

        config3 = PipelineConfig(
            name="Canary",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            deployment_strategy=DeploymentStrategy.CANARY
        )
        assert config3.deployment_strategy == DeploymentStrategy.CANARY

    def test_pipeline_config_with_docker_registry(self):
        """Test PipelineConfig with Docker registry"""
        stage = PipelineStage(name="build")
        config = PipelineConfig(
            name="Docker Build",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            docker_registry="ghcr.io"
        )

        assert config.docker_registry == "ghcr.io"

    def test_pipeline_config_with_kubernetes(self):
        """Test PipelineConfig with Kubernetes cluster"""
        stage = PipelineStage(name="deploy")
        config = PipelineConfig(
            name="K8s Deploy",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[stage],
            kubernetes_cluster="production-cluster"
        )

        assert config.kubernetes_cluster == "production-cluster"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestGeneratedPipeline:
    """Test GeneratedPipeline model"""

    def test_generated_pipeline_minimal(self):
        """Test GeneratedPipeline with minimal required fields"""
        pipeline = GeneratedPipeline(
            id="pipeline-123",
            config_hash="abc123",
            platform=CICDPlatform.GITHUB_ACTIONS,
            pipeline_content="name: CI\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n",
            file_path=".github/workflows/ci.yml",
            best_practice_score=90.0
        )

        assert pipeline.id == "pipeline-123"
        assert pipeline.config_hash == "abc123"
        assert pipeline.platform == CICDPlatform.GITHUB_ACTIONS
        assert "name: CI" in pipeline.pipeline_content
        assert pipeline.file_path == ".github/workflows/ci.yml"
        assert pipeline.validation_results == []
        assert pipeline.best_practice_score == 90.0
        assert isinstance(pipeline.created_at, datetime)

    def test_generated_pipeline_with_validation_results(self):
        """Test GeneratedPipeline with validation issues"""
        pipeline = GeneratedPipeline(
            id="pipeline-456",
            config_hash="def456",
            platform=CICDPlatform.GITLAB_CI,
            pipeline_content="stages:\n  - build\n",
            file_path=".gitlab-ci.yml",
            validation_results=[
                "Missing test stage",
                "No caching configured",
                "Secrets hardcoded"
            ],
            best_practice_score=65.0
        )

        assert len(pipeline.validation_results) == 3
        assert "Missing test stage" in pipeline.validation_results
        assert pipeline.best_practice_score == 65.0

    def test_generated_pipeline_has_issues_property(self):
        """Test GeneratedPipeline has_issues property"""
        pipeline1 = GeneratedPipeline(
            id="clean",
            config_hash="clean123",
            platform=CICDPlatform.GITHUB_ACTIONS,
            pipeline_content="content",
            file_path="file.yml",
            validation_results=[],
            best_practice_score=100.0
        )
        assert pipeline1.has_issues is False

        pipeline2 = GeneratedPipeline(
            id="issues",
            config_hash="issues123",
            platform=CICDPlatform.GITHUB_ACTIONS,
            pipeline_content="content",
            file_path="file.yml",
            validation_results=["Issue 1"],
            best_practice_score=80.0
        )
        assert pipeline2.has_issues is True

    def test_generated_pipeline_score_validation(self):
        """Test GeneratedPipeline score must be 0-100"""
        with pytest.raises(ValidationError):
            GeneratedPipeline(
                id="invalid",
                config_hash="invalid",
                platform=CICDPlatform.GITHUB_ACTIONS,
                pipeline_content="content",
                file_path="file.yml",
                best_practice_score=150.0
            )

        with pytest.raises(ValidationError):
            GeneratedPipeline(
                id="invalid",
                config_hash="invalid",
                platform=CICDPlatform.GITHUB_ACTIONS,
                pipeline_content="content",
                file_path="file.yml",
                best_practice_score=-10.0
            )

    def test_generated_pipeline_created_at_default(self):
        """Test GeneratedPipeline created_at defaults to current time"""
        before = datetime.now()
        pipeline = GeneratedPipeline(
            id="time-test",
            config_hash="time123",
            platform=CICDPlatform.JENKINS,
            pipeline_content="pipeline {}",
            file_path="Jenkinsfile",
            best_practice_score=85.0
        )
        after = datetime.now()

        assert before <= pipeline.created_at <= after

    def test_generated_pipeline_different_platforms(self):
        """Test GeneratedPipeline for different platforms"""
        github = GeneratedPipeline(
            id="gh",
            config_hash="gh123",
            platform=CICDPlatform.GITHUB_ACTIONS,
            pipeline_content="yaml",
            file_path=".github/workflows/ci.yml",
            best_practice_score=90.0
        )
        assert github.platform == CICDPlatform.GITHUB_ACTIONS

        gitlab = GeneratedPipeline(
            id="gl",
            config_hash="gl123",
            platform=CICDPlatform.GITLAB_CI,
            pipeline_content="yaml",
            file_path=".gitlab-ci.yml",
            best_practice_score=90.0
        )
        assert gitlab.platform == CICDPlatform.GITLAB_CI

        jenkins = GeneratedPipeline(
            id="jk",
            config_hash="jk123",
            platform=CICDPlatform.JENKINS,
            pipeline_content="groovy",
            file_path="Jenkinsfile",
            best_practice_score=90.0
        )
        assert jenkins.platform == CICDPlatform.JENKINS
