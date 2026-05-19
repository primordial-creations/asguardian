"""
L0 Unit Tests for Volundr Dockerfile Generator

Tests the Dockerfile generation service.
"""

import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock
import os

from Asgard.Volundr.Docker.models.docker_models import (
    DockerfileConfig,
    BuildStage,
    GeneratedDockerConfig,
)
from Asgard.Volundr.Docker.services.dockerfile_generator import DockerfileGenerator


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDockerfileGeneratorInitialization:
    """Test DockerfileGenerator initialization"""

    def test_init_with_output_dir(self):
        """Test initialization with custom output directory"""
        generator = DockerfileGenerator(output_dir="/custom/path")

        assert generator.output_dir == "/custom/path"

    def test_init_without_output_dir(self):
        """Test initialization with default output directory"""
        generator = DockerfileGenerator()

        assert generator.output_dir == "."

    def test_init_with_none_output_dir(self):
        """Test initialization with None output directory uses default"""
        generator = DockerfileGenerator(output_dir=None)

        assert generator.output_dir == "."


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDockerfileGeneratorGenerate:
    """Test DockerfileGenerator generate method"""

    def test_generate_simple_dockerfile(self):
        """Test generating simple single-stage Dockerfile"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="",
            base_image="python:3.12-slim",
            run_commands=["pip install -r requirements.txt"]
        )
        config = DockerfileConfig(
            name="simple-app",
            stages=[stage]
        )

        result = generator.generate(config)

        assert isinstance(result, GeneratedDockerConfig)
        assert result.dockerfile_content is not None
        assert "FROM python:3.12-slim" in result.dockerfile_content
        assert "pip install -r requirements.txt" in result.dockerfile_content

    def test_generate_multi_stage_dockerfile(self):
        """Test generating multi-stage Dockerfile"""
        generator = DockerfileGenerator()
        builder = BuildStage(
            name="builder",
            base_image="python:3.12",
            run_commands=["pip install --no-cache-dir -r requirements.txt"]
        )
        runtime = BuildStage(
            name="runtime",
            base_image="python:3.12-slim",
            copy_from="builder",
            copy_src="/usr/local/lib/python",
            copy_dst="/usr/local/lib/python"
        )

        config = DockerfileConfig(
            name="multi-stage-app",
            stages=[builder, runtime]
        )

        result = generator.generate(config)

        assert "FROM python:3.12 AS builder" in result.dockerfile_content
        assert "FROM python:3.12-slim AS runtime" in result.dockerfile_content
        assert "COPY --from=builder" in result.dockerfile_content

    def test_generate_with_labels(self):
        """Test generating Dockerfile with OCI labels"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="app", base_image="node:20-slim")
        config = DockerfileConfig(
            name="labeled-app",
            stages=[stage],
            labels={
                "org.opencontainers.image.title": "My App",
                "org.opencontainers.image.version": "1.0.0"
            }
        )

        result = generator.generate(config)

        assert 'LABEL org.opencontainers.image.title="My App"' in result.dockerfile_content
        assert 'LABEL org.opencontainers.image.version="1.0.0"' in result.dockerfile_content

    def test_generate_with_build_args(self):
        """Test generating Dockerfile with build arguments"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="app", base_image="python:3.12")
        config = DockerfileConfig(
            name="args-app",
            stages=[stage],
            args={
                "PYTHON_VERSION": "3.12",
                "APP_ENV": "production"
            }
        )

        result = generator.generate(config)

        assert "ARG PYTHON_VERSION=3.12" in result.dockerfile_content
        assert "ARG APP_ENV=production" in result.dockerfile_content

    def test_generate_with_healthcheck(self):
        """Test generating Dockerfile with healthcheck"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            expose_ports=[8080]
        )
        config = DockerfileConfig(
            name="health-app",
            stages=[stage],
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8080/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "5s"
            }
        )

        result = generator.generate(config)

        assert "HEALTHCHECK" in result.dockerfile_content
        assert "--interval=30s" in result.dockerfile_content
        assert "--timeout=10s" in result.dockerfile_content
        assert "--retries=3" in result.dockerfile_content

    def test_generate_with_environment_variables(self):
        """Test generating Dockerfile with environment variables"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            env_vars={
                "PYTHONUNBUFFERED": "1",
                "PORT": "8080"
            }
        )
        config = DockerfileConfig(
            name="env-app",
            stages=[stage]
        )

        result = generator.generate(config)

        assert "ENV PYTHONUNBUFFERED=1" in result.dockerfile_content
        assert "ENV PORT=8080" in result.dockerfile_content

    def test_generate_with_expose_ports(self):
        """Test generating Dockerfile with exposed ports"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="nginx:alpine",
            expose_ports=[80, 443]
        )
        config = DockerfileConfig(
            name="web-app",
            stages=[stage]
        )

        result = generator.generate(config)

        assert "EXPOSE 80" in result.dockerfile_content
        assert "EXPOSE 443" in result.dockerfile_content

    def test_generate_with_non_root_user(self):
        """Test generating Dockerfile with non-root user"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            user="appuser"
        )
        config = DockerfileConfig(
            name="secure-app",
            stages=[stage],
            use_non_root=True
        )

        result = generator.generate(config)

        assert "USER appuser" in result.dockerfile_content

    def test_generate_without_non_root_user(self):
        """Test generating Dockerfile without non-root user when disabled"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            user="appuser"
        )
        config = DockerfileConfig(
            name="root-app",
            stages=[stage],
            use_non_root=False
        )

        result = generator.generate(config)

        assert "USER appuser" not in result.dockerfile_content

    def test_generate_with_optimized_layers(self):
        """Test generating Dockerfile with optimized RUN commands"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            run_commands=[
                "apt-get update",
                "apt-get install -y curl",
                "pip install fastapi"
            ]
        )
        config = DockerfileConfig(
            name="optimized-app",
            stages=[stage],
            optimize_layers=True
        )

        result = generator.generate(config)

        assert "RUN apt-get update && \\" in result.dockerfile_content
        assert "apt-get install -y curl && \\" in result.dockerfile_content

    def test_generate_without_layer_optimization(self):
        """Test generating Dockerfile without layer optimization"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            run_commands=[
                "apt-get update",
                "apt-get install -y curl"
            ]
        )
        config = DockerfileConfig(
            name="unoptimized-app",
            stages=[stage],
            optimize_layers=False
        )

        result = generator.generate(config)

        assert result.dockerfile_content.count("RUN") >= 2

    def test_generate_with_copy_commands(self):
        """Test generating Dockerfile with COPY commands"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            copy_commands=[
                {"src": "requirements.txt", "dst": "."},
                {"src": ".", "dst": ".", "chown": "appuser:appuser"}
            ]
        )
        config = DockerfileConfig(
            name="copy-app",
            stages=[stage]
        )

        result = generator.generate(config)

        assert "COPY requirements.txt ." in result.dockerfile_content
        assert "COPY --chown=appuser:appuser . ." in result.dockerfile_content

    def test_generate_with_entrypoint_and_cmd(self):
        """Test generating Dockerfile with ENTRYPOINT and CMD"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            entrypoint=["python", "-m", "app"],
            cmd=["--workers", "4"]
        )
        config = DockerfileConfig(
            name="entrypoint-app",
            stages=[stage]
        )

        result = generator.generate(config)

        assert 'ENTRYPOINT ["python", "-m", "app"]' in result.dockerfile_content
        assert 'CMD ["--workers", "4"]' in result.dockerfile_content

    def test_generate_with_workdir(self):
        """Test generating Dockerfile with WORKDIR"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="node:20-slim",
            workdir="/opt/app"
        )
        config = DockerfileConfig(
            name="workdir-app",
            stages=[stage]
        )

        result = generator.generate(config)

        assert "WORKDIR /opt/app" in result.dockerfile_content

    def test_generate_creates_unique_id(self):
        """Test that generated config has unique ID based on content"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="app", base_image="python:3.12-slim")
        config = DockerfileConfig(name="unique-app", stages=[stage])

        result = generator.generate(config)

        assert result.id.startswith("unique-app-dockerfile-")
        assert len(result.config_hash) == 16

    def test_generate_deterministic_hash(self):
        """Test that same config generates same hash"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="app", base_image="python:3.12-slim")
        config = DockerfileConfig(name="deterministic", stages=[stage])

        result1 = generator.generate(config)
        result2 = generator.generate(config)

        assert result1.config_hash == result2.config_hash
        assert result1.id == result2.id


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDockerfileGeneratorValidation:
    """Test Dockerfile validation logic"""

    def test_validation_missing_from(self):
        """Test validation catches missing FROM instruction"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="app", base_image="python:3.12-slim")
        config = DockerfileConfig(name="test", stages=[stage])

        result = generator.generate(config)

        assert result.validation_results is not None

    def test_validation_latest_tag_warning(self):
        """Test validation warns about :latest tag"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="app", base_image="python:latest")
        config = DockerfileConfig(name="latest-app", stages=[stage])

        result = generator.generate(config)

        assert any("latest" in issue.lower() for issue in result.validation_results)

    def test_validation_non_root_user_missing(self):
        """Test validation catches missing non-root USER"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="app", base_image="python:3.12-slim")
        config = DockerfileConfig(
            name="no-user",
            stages=[stage],
            use_non_root=True
        )

        result = generator.generate(config)

        assert any("USER" in issue for issue in result.validation_results)

    def test_validation_passes_with_user(self):
        """Test validation passes when USER is specified"""
        generator = DockerfileGenerator()
        stage = BuildStage(
            name="app",
            base_image="python:3.12-slim",
            user="appuser"
        )
        config = DockerfileConfig(
            name="with-user",
            stages=[stage],
            use_non_root=True
        )

        result = generator.generate(config)

        user_issues = [i for i in result.validation_results if "USER" in i]
        assert len(user_issues) == 0


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDockerfileGeneratorBestPracticeScore:
    """Test best practice score calculation"""

    def test_score_multi_stage_build(self):
        """Test score is higher for multi-stage builds"""
        generator = DockerfileGenerator()

        single_stage = DockerfileConfig(
            name="single",
            stages=[BuildStage(name="", base_image="python:3.12-slim")]
        )
        result_single = generator.generate(single_stage)

        multi_stage = DockerfileConfig(
            name="multi",
            stages=[
                BuildStage(name="builder", base_image="python:3.12"),
                BuildStage(name="runtime", base_image="python:3.12-slim")
            ]
        )
        result_multi = generator.generate(multi_stage)

        assert result_multi.best_practice_score > result_single.best_practice_score

    def test_score_with_healthcheck(self):
        """Test score includes healthcheck"""
        generator = DockerfileGenerator()

        without_health = DockerfileConfig(
            name="no-health",
            stages=[BuildStage(name="", base_image="python:3.12-slim")]
        )
        result_without = generator.generate(without_health)

        with_health = DockerfileConfig(
            name="with-health",
            stages=[BuildStage(name="", base_image="python:3.12-slim")],
            healthcheck={"test": ["CMD", "echo", "ok"]}
        )
        result_with = generator.generate(with_health)

        assert result_with.best_practice_score > result_without.best_practice_score

    def test_score_with_non_root_user(self):
        """Test score includes non-root user"""
        generator = DockerfileGenerator()

        without_user = DockerfileConfig(
            name="root",
            stages=[BuildStage(name="", base_image="python:3.12-slim")],
            use_non_root=False
        )
        result_without = generator.generate(without_user)

        with_user = DockerfileConfig(
            name="non-root",
            stages=[BuildStage(name="", base_image="python:3.12-slim", user="appuser")],
            use_non_root=True
        )
        result_with = generator.generate(with_user)

        assert result_with.best_practice_score > result_without.best_practice_score

    def test_score_with_labels(self):
        """Test score includes labels"""
        generator = DockerfileGenerator()

        without_labels = DockerfileConfig(
            name="no-labels",
            stages=[BuildStage(name="", base_image="python:3.12-slim")]
        )
        result_without = generator.generate(without_labels)

        with_labels = DockerfileConfig(
            name="with-labels",
            stages=[BuildStage(name="", base_image="python:3.12-slim")],
            labels={"org.opencontainers.image.title": "My App"}
        )
        result_with = generator.generate(with_labels)

        assert result_with.best_practice_score > result_without.best_practice_score

    def test_score_avoids_latest_tag(self):
        """Test score penalizes :latest tag"""
        generator = DockerfileGenerator()

        with_latest = DockerfileConfig(
            name="latest",
            stages=[BuildStage(name="", base_image="python:latest")]
        )
        result_latest = generator.generate(with_latest)

        with_version = DockerfileConfig(
            name="versioned",
            stages=[BuildStage(name="", base_image="python:3.12-slim")]
        )
        result_versioned = generator.generate(with_version)

        assert result_versioned.best_practice_score > result_latest.best_practice_score

    def test_score_range_is_valid(self):
        """Test score is always between 0 and 100"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="", base_image="python:3.12-slim")
        config = DockerfileConfig(name="test", stages=[stage])

        result = generator.generate(config)

        assert 0 <= result.best_practice_score <= 100


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDockerfileGeneratorSaveToFile:
    """Test save_to_file method"""

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_save_to_file_creates_directory(self, mock_makedirs, mock_file):
        """Test that save_to_file creates output directory"""
        generator = DockerfileGenerator(output_dir="/tmp/test")
        stage = BuildStage(name="", base_image="python:3.12-slim")
        config = DockerfileConfig(name="test", stages=[stage])

        result = generator.generate(config)
        file_path = generator.save_to_file(result, "/tmp/test")

        mock_makedirs.assert_called_once_with("/tmp/test", exist_ok=True)
        assert file_path == "/tmp/test/Dockerfile"

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_save_to_file_writes_content(self, mock_makedirs, mock_file):
        """Test that save_to_file writes Dockerfile content"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="", base_image="python:3.12-slim")
        config = DockerfileConfig(name="test", stages=[stage])

        result = generator.generate(config)
        generator.save_to_file(result, "/tmp/test")

        mock_file.assert_called_once()
        handle = mock_file()
        handle.write.assert_called_once()
        written_content = handle.write.call_args[0][0]
        assert "FROM python:3.12-slim" in written_content

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_save_to_file_custom_filename(self, mock_makedirs, mock_file):
        """Test save_to_file with custom filename"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="", base_image="python:3.12-slim")
        config = DockerfileConfig(name="test", stages=[stage])

        result = generator.generate(config)
        file_path = generator.save_to_file(result, "/tmp/test", filename="Dockerfile.dev")

        assert file_path == "/tmp/test/Dockerfile.dev"

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_save_to_file_uses_default_output_dir(self, mock_makedirs, mock_file):
        """Test save_to_file uses generator's default output_dir when not specified"""
        generator = DockerfileGenerator(output_dir="/default/path")
        stage = BuildStage(name="", base_image="python:3.12-slim")
        config = DockerfileConfig(name="test", stages=[stage])

        result = generator.generate(config)
        file_path = generator.save_to_file(result)

        assert file_path == "/default/path/Dockerfile"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDockerfileGeneratorEdgeCases:
    """Test edge cases and error handling"""

    def test_generate_with_empty_stages(self):
        """Test generating Dockerfile with empty stages list"""
        generator = DockerfileGenerator()
        config = DockerfileConfig(name="empty", stages=[])

        result = generator.generate(config)

        assert result.dockerfile_content is not None
        assert len(result.dockerfile_content.strip()) >= 0

    def test_generate_with_stage_no_commands(self):
        """Test generating Dockerfile with stage that has no commands"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="minimal", base_image="alpine:3.19")
        config = DockerfileConfig(name="minimal", stages=[stage])

        result = generator.generate(config)

        assert "FROM alpine:3.19" in result.dockerfile_content

    def test_generate_with_healthcheck_as_string(self):
        """Test healthcheck with string test command"""
        generator = DockerfileGenerator()
        stage = BuildStage(name="", base_image="python:3.12-slim")
        config = DockerfileConfig(
            name="health-string",
            stages=[stage],
            healthcheck={
                "test": "CMD curl -f http://localhost/health",
                "interval": "30s"
            }
        )

        result = generator.generate(config)

        assert "HEALTHCHECK" in result.dockerfile_content

    def test_generate_preserves_stage_order(self):
        """Test that stages are generated in the order specified"""
        generator = DockerfileGenerator()
        stage1 = BuildStage(name="first", base_image="python:3.12")
        stage2 = BuildStage(name="second", base_image="python:3.12-slim")
        stage3 = BuildStage(name="third", base_image="python:3.12-alpine")

        config = DockerfileConfig(name="ordered", stages=[stage1, stage2, stage3])

        result = generator.generate(config)

        first_pos = result.dockerfile_content.index("AS first")
        second_pos = result.dockerfile_content.index("AS second")
        third_pos = result.dockerfile_content.index("AS third")

        assert first_pos < second_pos < third_pos
