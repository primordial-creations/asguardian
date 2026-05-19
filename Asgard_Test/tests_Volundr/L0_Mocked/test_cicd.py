"""
Volundr CICD Module Tests

Unit tests for CI/CD pipeline generation.
"""

import pytest
import yaml

from Asgard.Volundr.CICD import (
    PipelineConfig,
    PipelineGenerator,
    GeneratedPipeline,
    CICDPlatform,
)
from Asgard.Volundr.CICD.models.cicd_models import (
    DeploymentStrategy,
    TriggerType,
    StepConfig,
    PipelineStage,
    TriggerConfig,
)


class TestPipelineConfig:
    """Tests for PipelineConfig model validation."""

    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = PipelineConfig(
            name="CI Pipeline",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        assert config.name == "CI Pipeline"
        assert config.platform == CICDPlatform.GITHUB_ACTIONS
        assert len(config.stages) == 1

    def test_full_config(self):
        """Test creating config with all fields."""
        config = PipelineConfig(
            name="CI/CD Pipeline",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[
                TriggerConfig(type=TriggerType.PUSH, branches=["main"]),
                TriggerConfig(type=TriggerType.PULL_REQUEST, branches=["main"]),
            ],
            stages=[
                PipelineStage(
                    name="Build",
                    runs_on="ubuntu-latest",
                    steps=[StepConfig(name="Build", run="make build")],
                ),
                PipelineStage(
                    name="Test",
                    runs_on="ubuntu-latest",
                    needs=["Build"],
                    steps=[StepConfig(name="Test", run="make test")],
                ),
            ],
            env={"NODE_ENV": "production"},
            secrets=["AWS_ACCESS_KEY"],
            deployment_strategy=DeploymentStrategy.ROLLING,
        )
        assert len(config.triggers) == 2
        assert len(config.stages) == 2
        assert config.env["NODE_ENV"] == "production"

    def test_trigger_config(self):
        """Test TriggerConfig model."""
        trigger = TriggerConfig(
            type=TriggerType.PUSH,
            branches=["main", "develop"],
            paths=["src/**"],
            paths_ignore=["docs/**"],
        )
        assert trigger.type == TriggerType.PUSH
        assert "main" in trigger.branches
        assert "src/**" in trigger.paths

    def test_step_config(self):
        """Test StepConfig model."""
        step = StepConfig(
            name="Setup Python",
            uses="actions/setup-python@v5",
            with_params={"python-version": "3.12"},
        )
        assert step.name == "Setup Python"
        assert step.uses == "actions/setup-python@v5"
        assert step.with_params["python-version"] == "3.12"

    def test_step_config_run(self):
        """Test StepConfig with run command."""
        step = StepConfig(
            name="Install dependencies",
            run="pip install -r requirements.txt",
        )
        assert step.run == "pip install -r requirements.txt"

    def test_pipeline_stage(self):
        """Test PipelineStage model."""
        stage = PipelineStage(
            name="Deploy",
            runs_on="ubuntu-latest",
            needs=["Build", "Test"],
            steps=[StepConfig(name="Deploy", run="./deploy.sh")],
            environment="production",
            if_condition="github.ref == 'refs/heads/main'",
            timeout_minutes=30,
        )
        assert stage.name == "Deploy"
        assert stage.needs == ["Build", "Test"]
        assert stage.environment == "production"


class TestCICDPlatform:
    """Tests for CICDPlatform enum."""

    def test_all_platforms(self):
        """Test all CI/CD platforms exist."""
        assert CICDPlatform.GITHUB_ACTIONS.value == "github_actions"
        assert CICDPlatform.GITLAB_CI.value == "gitlab_ci"
        assert CICDPlatform.AZURE_DEVOPS.value == "azure_devops"
        assert CICDPlatform.JENKINS.value == "jenkins"
        assert CICDPlatform.CIRCLECI.value == "circleci"


class TestTriggerType:
    """Tests for TriggerType enum."""

    def test_all_trigger_types(self):
        """Test all trigger types exist."""
        assert TriggerType.PUSH.value == "push"
        assert TriggerType.PULL_REQUEST.value == "pull_request"
        assert TriggerType.TAG.value == "tag"
        assert TriggerType.SCHEDULE.value == "schedule"
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.WORKFLOW_DISPATCH.value == "workflow_dispatch"


class TestDeploymentStrategy:
    """Tests for DeploymentStrategy enum."""

    def test_all_strategies(self):
        """Test all deployment strategies exist."""
        assert DeploymentStrategy.ROLLING.value == "rolling"
        assert DeploymentStrategy.BLUE_GREEN.value == "blue_green"
        assert DeploymentStrategy.CANARY.value == "canary"
        assert DeploymentStrategy.RECREATE.value == "recreate"
        assert DeploymentStrategy.A_B_TESTING.value == "ab_testing"


class TestPipelineGenerator:
    """Tests for PipelineGenerator service."""

    @pytest.fixture
    def generator(self):
        """Create a PipelineGenerator instance."""
        return PipelineGenerator()

    @pytest.fixture
    def basic_config(self):
        """Create a basic pipeline config."""
        return PipelineConfig(
            name="CI Pipeline",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[
                        StepConfig(name="Checkout", uses="actions/checkout@v4"),
                        StepConfig(name="Build", run="make build"),
                    ],
                )
            ],
        )

    def test_generate_returns_pipeline(self, generator, basic_config):
        """Test that generate returns a GeneratedPipeline."""
        result = generator.generate(basic_config)
        assert isinstance(result, GeneratedPipeline)
        assert result.pipeline_content is not None

    def test_generate_github_actions(self, generator):
        """Test generating GitHub Actions workflow."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert "name: CI" in result.pipeline_content
        assert "jobs:" in result.pipeline_content
        assert result.file_path == ".github/workflows/ci.yml"

    def test_generate_github_actions_valid_yaml(self, generator, basic_config):
        """Test that generated GitHub Actions is valid YAML."""
        result = generator.generate(basic_config)
        parsed = yaml.safe_load(result.pipeline_content)
        assert "name" in parsed
        assert "jobs" in parsed

    def test_generate_gitlab_ci(self, generator):
        """Test generating GitLab CI pipeline."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITLAB_CI,
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert "stages:" in result.pipeline_content
        assert result.file_path == ".gitlab-ci.yml"

    def test_generate_azure_devops(self, generator):
        """Test generating Azure DevOps pipeline."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.AZURE_DEVOPS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert "trigger:" in result.pipeline_content
        assert result.file_path == "azure-pipelines.yml"

    def test_generate_jenkins(self, generator):
        """Test generating Jenkinsfile."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.JENKINS,
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert "pipeline {" in result.pipeline_content
        assert "stages {" in result.pipeline_content
        assert result.file_path == "Jenkinsfile"

    def test_generate_with_triggers(self, generator):
        """Test generating pipeline with multiple triggers."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[
                TriggerConfig(type=TriggerType.PUSH, branches=["main", "develop"]),
                TriggerConfig(type=TriggerType.PULL_REQUEST, branches=["main"]),
                TriggerConfig(type=TriggerType.WORKFLOW_DISPATCH),
            ],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert "push:" in result.pipeline_content
        assert "pull_request:" in result.pipeline_content
        assert "workflow_dispatch:" in result.pipeline_content

    def test_generate_with_schedule(self, generator):
        """Test generating pipeline with schedule trigger."""
        config = PipelineConfig(
            name="Nightly",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[
                TriggerConfig(type=TriggerType.SCHEDULE, schedule="0 0 * * *"),
            ],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert "schedule:" in result.pipeline_content
        assert "cron:" in result.pipeline_content

    def test_generate_with_multiple_stages(self, generator):
        """Test generating pipeline with multiple stages."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                ),
                PipelineStage(
                    name="Test",
                    needs=["Build"],
                    steps=[StepConfig(name="Test", run="make test")],
                ),
                PipelineStage(
                    name="Deploy",
                    needs=["Test"],
                    environment="production",
                    steps=[StepConfig(name="Deploy", run="make deploy")],
                ),
            ],
        )
        result = generator.generate(config)
        assert "build:" in result.pipeline_content
        assert "test:" in result.pipeline_content
        assert "deploy:" in result.pipeline_content

    def test_generate_with_needs(self, generator):
        """Test generating pipeline with stage dependencies."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                ),
                PipelineStage(
                    name="Test",
                    needs=["Build"],
                    steps=[StepConfig(name="Test", run="make test")],
                ),
            ],
        )
        result = generator.generate(config)
        assert "needs:" in result.pipeline_content

    def test_generate_with_environment(self, generator):
        """Test generating pipeline with environment."""
        config = PipelineConfig(
            name="Deploy",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Deploy",
                    environment="production",
                    steps=[StepConfig(name="Deploy", run="make deploy")],
                ),
            ],
        )
        result = generator.generate(config)
        assert "environment:" in result.pipeline_content

    def test_generate_with_if_condition(self, generator):
        """Test generating pipeline with conditional execution."""
        config = PipelineConfig(
            name="Deploy",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Deploy",
                    if_condition="github.ref == 'refs/heads/main'",
                    steps=[StepConfig(name="Deploy", run="make deploy")],
                ),
            ],
        )
        result = generator.generate(config)
        assert "if:" in result.pipeline_content

    def test_generate_with_env(self, generator):
        """Test generating pipeline with global environment variables."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                ),
            ],
            env={"NODE_ENV": "production", "CI": "true"},
        )
        result = generator.generate(config)
        assert "env:" in result.pipeline_content
        assert "NODE_ENV" in result.pipeline_content

    def test_generate_with_concurrency(self, generator):
        """Test generating pipeline with concurrency settings."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                ),
            ],
            concurrency={"group": "${{ github.workflow }}", "cancel-in-progress": True},
        )
        result = generator.generate(config)
        assert "concurrency:" in result.pipeline_content

    def test_generate_with_services(self, generator):
        """Test generating pipeline with service containers."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Test",
                    services={
                        "postgres": {
                            "image": "postgres:15",
                            "env": {"POSTGRES_PASSWORD": "test"},
                        }
                    },
                    steps=[StepConfig(name="Test", run="make test")],
                ),
            ],
        )
        result = generator.generate(config)
        assert "services:" in result.pipeline_content

    def test_generate_with_uses_action(self, generator):
        """Test generating pipeline with GitHub Actions."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[
                        StepConfig(name="Checkout", uses="actions/checkout@v4"),
                        StepConfig(
                            name="Setup Python",
                            uses="actions/setup-python@v5",
                            with_params={"python-version": "3.12"},
                        ),
                    ],
                ),
            ],
        )
        result = generator.generate(config)
        assert "uses: actions/checkout@v4" in result.pipeline_content
        assert "uses: actions/setup-python@v5" in result.pipeline_content

    def test_best_practice_score(self, generator):
        """Test that best practice score is calculated."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[TriggerConfig(type=TriggerType.PUSH, branches=["main"])],
            stages=[
                PipelineStage(
                    name="Build",
                    timeout_minutes=30,
                    steps=[StepConfig(name="Build", run="make build")],
                ),
                PipelineStage(
                    name="Test",
                    needs=["Build"],
                    steps=[StepConfig(name="Test", run="make test")],
                ),
            ],
            concurrency={"group": "${{ github.workflow }}"},
            env={"CI": "true"},
        )
        result = generator.generate(config)
        assert result.best_practice_score > 0
        assert result.best_practice_score <= 100

    def test_validation_results(self, generator, basic_config):
        """Test that validation results are included."""
        result = generator.generate(basic_config)
        assert isinstance(result.validation_results, list)

    def test_save_to_file(self, generator, basic_config, temp_output_dir):
        """Test saving pipeline to file."""
        result = generator.generate(basic_config)
        file_path = generator.save_to_file(result, output_dir=str(temp_output_dir))
        assert file_path is not None

    def test_file_path_github_actions(self, generator):
        """Test file path for GitHub Actions."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITHUB_ACTIONS,
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert result.file_path == ".github/workflows/ci.yml"

    def test_file_path_gitlab_ci(self, generator):
        """Test file path for GitLab CI."""
        config = PipelineConfig(
            name="CI",
            platform=CICDPlatform.GITLAB_CI,
            stages=[
                PipelineStage(
                    name="Build",
                    steps=[StepConfig(name="Build", run="make build")],
                )
            ],
        )
        result = generator.generate(config)
        assert result.file_path == ".gitlab-ci.yml"

    def test_config_hash(self, generator, basic_config):
        """Test that config hash is generated."""
        result = generator.generate(basic_config)
        assert result.config_hash is not None
        assert len(result.config_hash) > 0

    def test_pipeline_id(self, generator, basic_config):
        """Test that pipeline ID is generated."""
        result = generator.generate(basic_config)
        assert result.id is not None
        assert basic_config.name in result.id
        assert basic_config.platform.value in result.id
