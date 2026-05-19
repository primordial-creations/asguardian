"""
Volundr Docker Module Tests

Unit tests for Dockerfile and docker-compose generation.
"""

import pytest

from Asgard.Volundr.Docker import (
    BaseImage,
    BuildStage,
    DockerfileConfig,
    DockerfileGenerator,
    ComposeServiceConfig,
    ComposeConfig,
    ComposeGenerator,
    GeneratedDockerConfig,
)
from Asgard.Volundr.Docker.models.docker_models import (
    NetworkConfig,
    VolumeConfig,
)


class TestBaseImage:
    """Tests for BaseImage enum."""

    def test_all_base_images(self):
        """Test all base images exist."""
        assert BaseImage.PYTHON_SLIM.value == "python:3.12-slim"
        assert BaseImage.PYTHON_ALPINE.value == "python:3.12-alpine"
        assert BaseImage.NODE_SLIM.value == "node:20-slim"
        assert BaseImage.NODE_ALPINE.value == "node:20-alpine"
        assert BaseImage.GOLANG_ALPINE.value == "golang:1.22-alpine"
        assert BaseImage.RUST_SLIM.value == "rust:1.75-slim"
        assert BaseImage.DISTROLESS_PYTHON.value == "gcr.io/distroless/python3"
        assert BaseImage.DISTROLESS_STATIC.value == "gcr.io/distroless/static-debian12"
        assert BaseImage.UBUNTU.value == "ubuntu:22.04"
        assert BaseImage.ALPINE.value == "alpine:3.19"


class TestBuildStage:
    """Tests for BuildStage model validation."""

    def test_minimal_stage(self):
        """Test creating stage with minimal fields."""
        stage = BuildStage(
            name="builder",
            base_image="python:3.12-slim",
        )
        assert stage.name == "builder"
        assert stage.base_image == "python:3.12-slim"
        assert stage.workdir == "/app"

    def test_full_stage(self):
        """Test creating stage with all fields."""
        stage = BuildStage(
            name="builder",
            base_image="python:3.12",
            workdir="/app",
            user="appuser",
            copy_from="base",
            copy_src="/src",
            copy_dst="/dst",
            run_commands=["pip install poetry", "poetry export -f requirements.txt"],
            copy_commands=[{"src": ".", "dst": "."}],
            env_vars={"PYTHONUNBUFFERED": "1"},
            expose_ports=[8000, 8080],
            entrypoint=["python"],
            cmd=["-m", "myapp"],
        )
        assert stage.name == "builder"
        assert stage.workdir == "/app"
        assert stage.user == "appuser"
        assert len(stage.run_commands) == 2
        assert len(stage.copy_commands) == 1
        assert stage.env_vars["PYTHONUNBUFFERED"] == "1"
        assert 8000 in stage.expose_ports


class TestDockerfileConfig:
    """Tests for DockerfileConfig model validation."""

    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(name="main", base_image="python:3.12-slim"),
            ],
        )
        assert config.name == "myapp"
        assert len(config.stages) == 1
        assert config.use_non_root is True
        assert config.optimize_layers is True

    def test_full_config(self):
        """Test creating config with all fields."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="builder",
                    base_image="python:3.12",
                    run_commands=["pip install poetry"],
                ),
                BuildStage(
                    name="runtime",
                    base_image="python:3.12-slim",
                    workdir="/app",
                    user="appuser",
                    expose_ports=[8000],
                    cmd=["python", "-m", "myapp"],
                ),
            ],
            labels={"version": "1.0.0", "maintainer": "team@example.com"},
            args={"PYTHON_VERSION": "3.12"},
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
            use_non_root=True,
            optimize_layers=True,
        )
        assert len(config.stages) == 2
        assert config.labels["version"] == "1.0.0"
        assert config.healthcheck is not None
        assert config.use_non_root is True

    def test_healthcheck_config(self):
        """Test healthcheck in config."""
        config = DockerfileConfig(
            name="myapp",
            stages=[BuildStage(name="main", base_image="python:3.12-slim")],
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
        )
        assert config.healthcheck["interval"] == "30s"
        assert config.healthcheck["retries"] == 3


class TestComposeServiceConfig:
    """Tests for ComposeServiceConfig model validation."""

    def test_minimal_service(self):
        """Test creating service with minimal fields."""
        service = ComposeServiceConfig(name="api", image="myapp:latest")
        assert service.name == "api"
        assert service.image == "myapp:latest"
        assert service.restart == "unless-stopped"

    def test_full_service(self):
        """Test creating service with all fields."""
        service = ComposeServiceConfig(
            name="api",
            image="myapp:latest",
            build={"context": ".", "dockerfile": "Dockerfile"},
            ports=["8000:8000", "8080:8080"],
            environment={"LOG_LEVEL": "debug"},
            env_file=[".env"],
            volumes=["./data:/app/data"],
            depends_on=["db", "redis"],
            networks=["backend"],
            restart="always",
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                "interval": "30s",
            },
            deploy={"replicas": 3},
            labels={"com.example.project": "myapp"},
            command=["python", "-m", "myapp"],
        )
        assert service.name == "api"
        assert service.build["context"] == "."
        assert len(service.depends_on) == 2
        assert service.restart == "always"


class TestNetworkConfig:
    """Tests for NetworkConfig model validation."""

    def test_minimal_network(self):
        """Test creating network with minimal fields."""
        network = NetworkConfig(name="backend")
        assert network.name == "backend"
        assert network.driver == "bridge"
        assert network.external is False

    def test_external_network(self):
        """Test creating external network."""
        network = NetworkConfig(name="external_net", external=True)
        assert network.external is True


class TestVolumeConfig:
    """Tests for VolumeConfig model validation."""

    def test_minimal_volume(self):
        """Test creating volume with minimal fields."""
        volume = VolumeConfig(name="postgres_data")
        assert volume.name == "postgres_data"
        assert volume.driver == "local"
        assert volume.external is False

    def test_volume_with_options(self):
        """Test creating volume with driver options."""
        volume = VolumeConfig(
            name="nfs_data",
            driver="local",
            driver_opts={"type": "nfs", "device": ":/nfs/share"},
        )
        assert volume.driver_opts["type"] == "nfs"


class TestComposeConfig:
    """Tests for ComposeConfig model validation."""

    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = ComposeConfig(
            services=[ComposeServiceConfig(name="api", image="myapp:latest")],
        )
        assert config.version == "3.8"
        assert len(config.services) == 1

    def test_full_config(self):
        """Test creating config with all fields."""
        config = ComposeConfig(
            version="3.8",
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    ports=["8000:8000"],
                    depends_on=["db"],
                ),
                ComposeServiceConfig(
                    name="db",
                    image="postgres:15",
                    volumes=["postgres_data:/var/lib/postgresql/data"],
                ),
            ],
            networks=[NetworkConfig(name="backend", driver="bridge")],
            volumes=[VolumeConfig(name="postgres_data")],
            configs={"app_config": {"file": "./config.yml"}},
            secrets={"db_password": {"file": "./secrets/db_password.txt"}},
        )
        assert config.version == "3.8"
        assert len(config.services) == 2
        assert len(config.networks) == 1
        assert len(config.volumes) == 1


class TestDockerfileGenerator:
    """Tests for DockerfileGenerator service."""

    @pytest.fixture
    def generator(self):
        """Create a DockerfileGenerator instance."""
        return DockerfileGenerator()

    @pytest.fixture
    def basic_config(self):
        """Create a basic Dockerfile config."""
        return DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    workdir="/app",
                ),
            ],
        )

    def test_generate_returns_config(self, generator, basic_config):
        """Test that generate returns a GeneratedDockerConfig."""
        result = generator.generate(basic_config)
        assert isinstance(result, GeneratedDockerConfig)
        assert result.dockerfile_content is not None

    def test_generate_valid_dockerfile(self, generator, basic_config):
        """Test that generated content is a valid Dockerfile."""
        result = generator.generate(basic_config)
        assert "FROM" in result.dockerfile_content
        assert "python:3.12-slim" in result.dockerfile_content

    def test_generate_with_working_dir(self, generator):
        """Test generating Dockerfile with WORKDIR."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(name="main", base_image="python:3.12-slim", workdir="/app"),
            ],
        )
        result = generator.generate(config)
        assert "WORKDIR /app" in result.dockerfile_content

    def test_generate_with_expose(self, generator):
        """Test generating Dockerfile with EXPOSE."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    expose_ports=[8000, 8080],
                ),
            ],
        )
        result = generator.generate(config)
        assert "EXPOSE 8000" in result.dockerfile_content
        assert "EXPOSE 8080" in result.dockerfile_content

    def test_generate_with_user(self, generator):
        """Test generating Dockerfile with USER."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    user="appuser",
                ),
            ],
            use_non_root=True,
        )
        result = generator.generate(config)
        assert "USER appuser" in result.dockerfile_content

    def test_generate_with_env(self, generator):
        """Test generating Dockerfile with ENV."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    env_vars={"PYTHONUNBUFFERED": "1", "APP_ENV": "production"},
                ),
            ],
        )
        result = generator.generate(config)
        assert "ENV" in result.dockerfile_content
        assert "PYTHONUNBUFFERED" in result.dockerfile_content

    def test_generate_with_cmd(self, generator):
        """Test generating Dockerfile with CMD."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    cmd=["python", "-m", "myapp"],
                ),
            ],
        )
        result = generator.generate(config)
        assert "CMD" in result.dockerfile_content

    def test_generate_with_entrypoint(self, generator):
        """Test generating Dockerfile with ENTRYPOINT."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    entrypoint=["python"],
                    cmd=["-m", "myapp"],
                ),
            ],
        )
        result = generator.generate(config)
        assert "ENTRYPOINT" in result.dockerfile_content

    def test_generate_with_labels(self, generator):
        """Test generating Dockerfile with LABEL."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(name="main", base_image="python:3.12-slim"),
            ],
            labels={"version": "1.0.0", "maintainer": "team@example.com"},
        )
        result = generator.generate(config)
        assert "LABEL" in result.dockerfile_content

    def test_generate_with_healthcheck(self, generator):
        """Test generating Dockerfile with HEALTHCHECK."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(name="main", base_image="python:3.12-slim"),
            ],
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
        )
        result = generator.generate(config)
        assert "HEALTHCHECK" in result.dockerfile_content

    def test_generate_multi_stage(self, generator):
        """Test generating multi-stage Dockerfile."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="builder",
                    base_image="python:3.12",
                    run_commands=["pip install poetry"],
                ),
                BuildStage(
                    name="runtime",
                    base_image="python:3.12-slim",
                    copy_from="builder",
                    copy_src="/app/dist",
                    copy_dst="/app/",
                ),
            ],
        )
        result = generator.generate(config)
        assert "AS builder" in result.dockerfile_content
        assert "AS runtime" in result.dockerfile_content

    def test_generate_with_run_commands(self, generator):
        """Test generating Dockerfile with RUN commands."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    run_commands=[
                        "pip install --no-cache-dir -r requirements.txt",
                        "adduser --disabled-password appuser",
                    ],
                ),
            ],
        )
        result = generator.generate(config)
        assert "RUN" in result.dockerfile_content

    def test_generate_with_copy_commands(self, generator):
        """Test generating Dockerfile with COPY instructions."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(
                    name="main",
                    base_image="python:3.12-slim",
                    copy_commands=[
                        {"src": "requirements.txt", "dst": "/app/"},
                        {"src": ".", "dst": "/app"},
                    ],
                ),
            ],
        )
        result = generator.generate(config)
        assert "COPY" in result.dockerfile_content

    def test_generate_with_args(self, generator):
        """Test generating Dockerfile with ARG."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(name="main", base_image="python:3.12-slim"),
            ],
            args={"PYTHON_VERSION": "3.12"},
        )
        result = generator.generate(config)
        assert "ARG PYTHON_VERSION" in result.dockerfile_content

    def test_best_practice_score(self, generator):
        """Test that best practice score is calculated."""
        config = DockerfileConfig(
            name="myapp",
            stages=[
                BuildStage(name="builder", base_image="python:3.12"),
                BuildStage(
                    name="runtime",
                    base_image="python:3.12-slim",
                    user="appuser",
                ),
            ],
            healthcheck={"test": ["CMD", "curl", "localhost"]},
            labels={"version": "1.0"},
            use_non_root=True,
        )
        result = generator.generate(config)
        assert result.best_practice_score > 0
        assert result.best_practice_score <= 100

    def test_validation_results(self, generator, basic_config):
        """Test that validation results are included."""
        result = generator.generate(basic_config)
        assert isinstance(result.validation_results, list)

    def test_has_issues_property(self, generator, basic_config):
        """Test the has_issues property."""
        result = generator.generate(basic_config)
        assert isinstance(result.has_issues, bool)

    def test_config_id_generated(self, generator, basic_config):
        """Test that config ID is generated."""
        result = generator.generate(basic_config)
        assert result.id is not None
        assert "myapp" in result.id

    def test_config_hash_generated(self, generator, basic_config):
        """Test that config hash is generated."""
        result = generator.generate(basic_config)
        assert result.config_hash is not None
        assert len(result.config_hash) > 0

    def test_save_to_file(self, generator, basic_config, temp_output_dir):
        """Test saving Dockerfile to file."""
        result = generator.generate(basic_config)
        file_path = generator.save_to_file(result, output_dir=str(temp_output_dir))
        assert file_path is not None
        assert (temp_output_dir / "Dockerfile").exists()


class TestComposeGenerator:
    """Tests for ComposeGenerator service."""

    @pytest.fixture
    def generator(self):
        """Create a ComposeGenerator instance."""
        return ComposeGenerator()

    @pytest.fixture
    def basic_config(self):
        """Create a basic compose config."""
        return ComposeConfig(
            services=[ComposeServiceConfig(name="api", image="myapp:latest")],
        )

    def test_generate_returns_config(self, generator, basic_config):
        """Test that generate returns a GeneratedDockerConfig."""
        result = generator.generate(basic_config)
        assert isinstance(result, GeneratedDockerConfig)
        assert result.compose_content is not None

    def test_generate_valid_yaml(self, generator, basic_config):
        """Test that generated content is valid YAML."""
        import yaml
        result = generator.generate(basic_config)
        parsed = yaml.safe_load(result.compose_content)
        assert "services" in parsed

    def test_generate_with_multiple_services(self, generator):
        """Test generating compose with multiple services."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(name="api", image="myapp:latest"),
                ComposeServiceConfig(name="db", image="postgres:15"),
                ComposeServiceConfig(name="redis", image="redis:7"),
            ],
        )
        result = generator.generate(config)
        assert "api" in result.compose_content
        assert "db" in result.compose_content
        assert "redis" in result.compose_content

    def test_generate_with_ports(self, generator):
        """Test generating compose with port mappings."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    ports=["8000:8000", "8080:8080"],
                ),
            ],
        )
        result = generator.generate(config)
        assert "8000:8000" in result.compose_content

    def test_generate_with_environment(self, generator):
        """Test generating compose with environment variables."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    environment={"LOG_LEVEL": "debug", "API_URL": "http://api"},
                ),
            ],
        )
        result = generator.generate(config)
        assert "LOG_LEVEL" in result.compose_content

    def test_generate_with_depends_on(self, generator):
        """Test generating compose with dependencies."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    depends_on=["db", "redis"],
                ),
                ComposeServiceConfig(name="db", image="postgres:15"),
                ComposeServiceConfig(name="redis", image="redis:7"),
            ],
        )
        result = generator.generate(config)
        assert "depends_on" in result.compose_content

    def test_generate_with_volumes(self, generator):
        """Test generating compose with volumes."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="db",
                    image="postgres:15",
                    volumes=["postgres_data:/var/lib/postgresql/data"],
                ),
            ],
            volumes=[VolumeConfig(name="postgres_data")],
        )
        result = generator.generate(config)
        assert "volumes" in result.compose_content
        assert "postgres_data" in result.compose_content

    def test_generate_with_networks(self, generator):
        """Test generating compose with networks."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    networks=["backend"],
                ),
            ],
            networks=[NetworkConfig(name="backend", driver="bridge")],
        )
        result = generator.generate(config)
        assert "networks" in result.compose_content
        assert "backend" in result.compose_content

    def test_generate_with_build(self, generator):
        """Test generating compose with build config."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    build={"context": ".", "dockerfile": "Dockerfile"},
                ),
            ],
        )
        result = generator.generate(config)
        assert "build" in result.compose_content

    def test_generate_with_healthcheck(self, generator):
        """Test generating compose with healthcheck."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    healthcheck={
                        "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                        "interval": "30s",
                        "timeout": "10s",
                        "retries": 3,
                    },
                ),
            ],
        )
        result = generator.generate(config)
        assert "healthcheck" in result.compose_content

    def test_generate_with_deploy(self, generator):
        """Test generating compose with deploy config."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    deploy={
                        "replicas": 3,
                        "resources": {"limits": {"cpus": "0.5", "memory": "512M"}},
                    },
                ),
            ],
        )
        result = generator.generate(config)
        assert "deploy" in result.compose_content

    def test_generate_with_external_network(self, generator):
        """Test generating compose with external network."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(name="api", image="myapp:latest"),
            ],
            networks=[NetworkConfig(name="external_net", external=True)],
        )
        result = generator.generate(config)
        assert "external" in result.compose_content

    def test_generate_with_external_volume(self, generator):
        """Test generating compose with external volume."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(name="api", image="myapp:latest"),
            ],
            volumes=[VolumeConfig(name="external_vol", external=True)],
        )
        result = generator.generate(config)
        assert "external" in result.compose_content

    def test_best_practice_score(self, generator):
        """Test that best practice score is calculated."""
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="myapp:latest",
                    healthcheck={"test": ["CMD", "curl", "localhost"]},
                    deploy={"resources": {"limits": {"cpus": "0.5"}}},
                    labels={"com.example.project": "myapp"},
                ),
            ],
            networks=[NetworkConfig(name="backend")],
            volumes=[VolumeConfig(name="data")],
        )
        result = generator.generate(config)
        assert result.best_practice_score > 0
        assert result.best_practice_score <= 100

    def test_validation_results(self, generator, basic_config):
        """Test that validation results are included."""
        result = generator.generate(basic_config)
        assert isinstance(result.validation_results, list)

    def test_config_id_generated(self, generator, basic_config):
        """Test that config ID is generated."""
        result = generator.generate(basic_config)
        assert result.id is not None
        assert "compose" in result.id

    def test_config_hash_generated(self, generator, basic_config):
        """Test that config hash is generated."""
        result = generator.generate(basic_config)
        assert result.config_hash is not None
        assert len(result.config_hash) > 0

    def test_save_to_file(self, generator, basic_config, temp_output_dir):
        """Test saving docker-compose.yml to file."""
        result = generator.generate(basic_config)
        file_path = generator.save_to_file(result, output_dir=str(temp_output_dir))
        assert file_path is not None
        assert (temp_output_dir / "docker-compose.yml").exists()
