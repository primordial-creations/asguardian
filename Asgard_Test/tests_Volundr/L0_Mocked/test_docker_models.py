"""
L0 Unit Tests for Volundr Docker Models

Tests Pydantic models for Docker configuration generation.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from Asgard.Volundr.Docker.models.docker_models import (
    BaseImage,
    BuildStage,
    DockerfileConfig,
    ComposeServiceConfig,
    NetworkConfig,
    VolumeConfig,
    ComposeConfig,
    GeneratedDockerConfig,
)


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestBaseImage:
    """Test BaseImage enum"""

    def test_base_image_values(self):
        """Test all base image values are accessible"""
        assert BaseImage.PYTHON_SLIM == "python:3.12-slim"
        assert BaseImage.PYTHON_ALPINE == "python:3.12-alpine"
        assert BaseImage.NODE_SLIM == "node:20-slim"
        assert BaseImage.NODE_ALPINE == "node:20-alpine"
        assert BaseImage.GOLANG_ALPINE == "golang:1.22-alpine"
        assert BaseImage.RUST_SLIM == "rust:1.75-slim"
        assert BaseImage.DISTROLESS_PYTHON == "gcr.io/distroless/python3"
        assert BaseImage.DISTROLESS_STATIC == "gcr.io/distroless/static-debian12"
        assert BaseImage.UBUNTU == "ubuntu:22.04"
        assert BaseImage.ALPINE == "alpine:3.19"

    def test_base_image_from_string(self):
        """Test creating BaseImage from string"""
        assert BaseImage("python:3.12-slim") == BaseImage.PYTHON_SLIM
        assert BaseImage("alpine:3.19") == BaseImage.ALPINE


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestBuildStage:
    """Test BuildStage model"""

    def test_build_stage_minimal(self):
        """Test BuildStage with minimal required fields"""
        stage = BuildStage(
            name="builder",
            base_image="python:3.12-slim"
        )

        assert stage.name == "builder"
        assert stage.base_image == "python:3.12-slim"
        assert stage.workdir == "/app"
        assert stage.user is None
        assert stage.copy_from is None
        assert stage.copy_src is None
        assert stage.copy_dst is None
        assert stage.run_commands == []
        assert stage.copy_commands == []
        assert stage.env_vars == {}
        assert stage.expose_ports == []
        assert stage.entrypoint is None
        assert stage.cmd is None

    def test_build_stage_full(self):
        """Test BuildStage with all fields populated"""
        stage = BuildStage(
            name="runtime",
            base_image="python:3.12-alpine",
            workdir="/opt/app",
            user="appuser",
            copy_from="builder",
            copy_src="/build/dist",
            copy_dst="/opt/app",
            run_commands=[
                "apk add --no-cache curl",
                "pip install --no-cache-dir -r requirements.txt"
            ],
            copy_commands=[
                {"src": ".", "dst": ".", "chown": "appuser:appuser"}
            ],
            env_vars={"PYTHONUNBUFFERED": "1", "PORT": "8080"},
            expose_ports=[8080, 9090],
            entrypoint=["python", "-m", "app"],
            cmd=["--workers", "4"]
        )

        assert stage.name == "runtime"
        assert stage.base_image == "python:3.12-alpine"
        assert stage.workdir == "/opt/app"
        assert stage.user == "appuser"
        assert stage.copy_from == "builder"
        assert stage.copy_src == "/build/dist"
        assert stage.copy_dst == "/opt/app"
        assert len(stage.run_commands) == 2
        assert len(stage.copy_commands) == 1
        assert stage.env_vars["PYTHONUNBUFFERED"] == "1"
        assert 8080 in stage.expose_ports
        assert stage.entrypoint == ["python", "-m", "app"]
        assert stage.cmd == ["--workers", "4"]

    def test_build_stage_multi_stage_copy(self):
        """Test BuildStage configured for multi-stage COPY"""
        stage = BuildStage(
            name="final",
            base_image="gcr.io/distroless/python3",
            copy_from="builder",
            copy_src="/usr/local/lib/python3.12",
            copy_dst="/usr/local/lib/python3.12"
        )

        assert stage.copy_from == "builder"
        assert stage.copy_src is not None
        assert stage.copy_dst is not None


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestDockerfileConfig:
    """Test DockerfileConfig model"""

    def test_dockerfile_config_minimal(self):
        """Test DockerfileConfig with minimal required fields"""
        stage = BuildStage(name="app", base_image="python:3.12-slim")
        config = DockerfileConfig(
            name="test-app",
            stages=[stage]
        )

        assert config.name == "test-app"
        assert len(config.stages) == 1
        assert config.labels == {}
        assert config.args == {}
        assert config.healthcheck is None
        assert config.use_non_root is True
        assert config.optimize_layers is True

    def test_dockerfile_config_multi_stage(self):
        """Test DockerfileConfig with multiple stages"""
        builder = BuildStage(name="builder", base_image="python:3.12")
        runtime = BuildStage(name="runtime", base_image="python:3.12-slim")

        config = DockerfileConfig(
            name="multi-stage-app",
            stages=[builder, runtime]
        )

        assert len(config.stages) == 2
        assert config.stages[0].name == "builder"
        assert config.stages[1].name == "runtime"

    def test_dockerfile_config_with_labels(self):
        """Test DockerfileConfig with OCI labels"""
        stage = BuildStage(name="app", base_image="node:20-slim")
        config = DockerfileConfig(
            name="labeled-app",
            stages=[stage],
            labels={
                "org.opencontainers.image.title": "My App",
                "org.opencontainers.image.version": "1.0.0",
                "org.opencontainers.image.source": "https://github.com/org/repo"
            }
        )

        assert len(config.labels) == 3
        assert "org.opencontainers.image.title" in config.labels
        assert config.labels["org.opencontainers.image.version"] == "1.0.0"

    def test_dockerfile_config_with_healthcheck(self):
        """Test DockerfileConfig with healthcheck"""
        stage = BuildStage(name="app", base_image="python:3.12-slim")
        config = DockerfileConfig(
            name="health-app",
            stages=[stage],
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8080/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "40s"
            }
        )

        assert config.healthcheck is not None
        assert config.healthcheck["test"] == ["CMD", "curl", "-f", "http://localhost:8080/health"]
        assert config.healthcheck["interval"] == "30s"
        assert config.healthcheck["retries"] == 3

    def test_dockerfile_config_with_build_args(self):
        """Test DockerfileConfig with build arguments"""
        stage = BuildStage(name="app", base_image="python:3.12")
        config = DockerfileConfig(
            name="args-app",
            stages=[stage],
            args={
                "PYTHON_VERSION": "3.12",
                "APP_ENV": "production"
            }
        )

        assert len(config.args) == 2
        assert config.args["PYTHON_VERSION"] == "3.12"
        assert config.args["APP_ENV"] == "production"

    def test_dockerfile_config_optimization_flags(self):
        """Test DockerfileConfig optimization flags"""
        stage = BuildStage(name="app", base_image="alpine:3.19")

        config1 = DockerfileConfig(
            name="optimized",
            stages=[stage],
            optimize_layers=True
        )
        assert config1.optimize_layers is True

        config2 = DockerfileConfig(
            name="unoptimized",
            stages=[stage],
            optimize_layers=False
        )
        assert config2.optimize_layers is False

    def test_dockerfile_config_non_root_user(self):
        """Test DockerfileConfig non-root user flag"""
        stage = BuildStage(name="app", base_image="python:3.12-slim")

        config1 = DockerfileConfig(
            name="secure",
            stages=[stage],
            use_non_root=True
        )
        assert config1.use_non_root is True

        config2 = DockerfileConfig(
            name="root",
            stages=[stage],
            use_non_root=False
        )
        assert config2.use_non_root is False


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestComposeServiceConfig:
    """Test ComposeServiceConfig model"""

    def test_compose_service_minimal(self):
        """Test ComposeServiceConfig with minimal required fields"""
        svc = ComposeServiceConfig(name="web")

        assert svc.name == "web"
        assert svc.image is None
        assert svc.build is None
        assert svc.ports == []
        assert svc.environment == {}
        assert svc.env_file == []
        assert svc.volumes == []
        assert svc.depends_on == []
        assert svc.networks == []
        assert svc.restart == "unless-stopped"
        assert svc.healthcheck is None
        assert svc.deploy is None
        assert svc.labels == {}
        assert svc.command is None

    def test_compose_service_with_image(self):
        """Test ComposeServiceConfig with image"""
        svc = ComposeServiceConfig(
            name="redis",
            image="redis:7-alpine",
            ports=["6379:6379"]
        )

        assert svc.image == "redis:7-alpine"
        assert len(svc.ports) == 1
        assert svc.ports[0] == "6379:6379"

    def test_compose_service_with_build(self):
        """Test ComposeServiceConfig with build configuration"""
        svc = ComposeServiceConfig(
            name="app",
            build={
                "context": ".",
                "dockerfile": "Dockerfile",
                "args": {"VERSION": "1.0"}
            },
            ports=["8080:8080"]
        )

        assert svc.build is not None
        assert svc.build["context"] == "."
        assert svc.build["dockerfile"] == "Dockerfile"
        assert "VERSION" in svc.build["args"]

    def test_compose_service_with_environment(self):
        """Test ComposeServiceConfig with environment variables"""
        svc = ComposeServiceConfig(
            name="api",
            environment={
                "DATABASE_URL": "postgres://localhost/db",
                "LOG_LEVEL": "info"
            },
            env_file=[".env", ".env.local"]
        )

        assert len(svc.environment) == 2
        assert svc.environment["DATABASE_URL"] == "postgres://localhost/db"
        assert len(svc.env_file) == 2

    def test_compose_service_with_volumes(self):
        """Test ComposeServiceConfig with volumes"""
        svc = ComposeServiceConfig(
            name="db",
            volumes=[
                "db-data:/var/lib/postgresql/data",
                "./init.sql:/docker-entrypoint-initdb.d/init.sql:ro"
            ]
        )

        assert len(svc.volumes) == 2
        assert "db-data:/var/lib/postgresql/data" in svc.volumes

    def test_compose_service_with_dependencies(self):
        """Test ComposeServiceConfig with service dependencies"""
        svc = ComposeServiceConfig(
            name="web",
            depends_on=["db", "redis", "rabbitmq"]
        )

        assert len(svc.depends_on) == 3
        assert "db" in svc.depends_on
        assert "redis" in svc.depends_on

    def test_compose_service_with_networks(self):
        """Test ComposeServiceConfig with networks"""
        svc = ComposeServiceConfig(
            name="app",
            networks=["frontend", "backend"]
        )

        assert len(svc.networks) == 2
        assert "frontend" in svc.networks

    def test_compose_service_with_healthcheck(self):
        """Test ComposeServiceConfig with healthcheck"""
        svc = ComposeServiceConfig(
            name="api",
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3
            }
        )

        assert svc.healthcheck is not None
        assert svc.healthcheck["interval"] == "30s"

    def test_compose_service_restart_policies(self):
        """Test ComposeServiceConfig restart policies"""
        svc1 = ComposeServiceConfig(name="always", restart="always")
        svc2 = ComposeServiceConfig(name="never", restart="no")
        svc3 = ComposeServiceConfig(name="on-failure", restart="on-failure")

        assert svc1.restart == "always"
        assert svc2.restart == "no"
        assert svc3.restart == "on-failure"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestNetworkConfig:
    """Test NetworkConfig model"""

    def test_network_config_minimal(self):
        """Test NetworkConfig with minimal required fields"""
        net = NetworkConfig(name="backend")

        assert net.name == "backend"
        assert net.driver == "bridge"
        assert net.external is False
        assert net.ipam is None

    def test_network_config_custom_driver(self):
        """Test NetworkConfig with custom driver"""
        net = NetworkConfig(name="overlay-net", driver="overlay")

        assert net.driver == "overlay"

    def test_network_config_external(self):
        """Test NetworkConfig as external"""
        net = NetworkConfig(name="existing-net", external=True)

        assert net.external is True

    def test_network_config_with_ipam(self):
        """Test NetworkConfig with IPAM configuration"""
        net = NetworkConfig(
            name="custom-net",
            ipam={
                "driver": "default",
                "config": [{"subnet": "172.28.0.0/16"}]
            }
        )

        assert net.ipam is not None
        assert net.ipam["driver"] == "default"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestVolumeConfig:
    """Test VolumeConfig model"""

    def test_volume_config_minimal(self):
        """Test VolumeConfig with minimal required fields"""
        vol = VolumeConfig(name="data")

        assert vol.name == "data"
        assert vol.driver == "local"
        assert vol.external is False
        assert vol.driver_opts == {}

    def test_volume_config_external(self):
        """Test VolumeConfig as external"""
        vol = VolumeConfig(name="shared-data", external=True)

        assert vol.external is True

    def test_volume_config_with_driver_opts(self):
        """Test VolumeConfig with driver options"""
        vol = VolumeConfig(
            name="nfs-data",
            driver="local",
            driver_opts={
                "type": "nfs",
                "o": "addr=192.168.1.1,rw",
                "device": ":/path/to/dir"
            }
        )

        assert len(vol.driver_opts) == 3
        assert vol.driver_opts["type"] == "nfs"


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestComposeConfig:
    """Test ComposeConfig model"""

    def test_compose_config_minimal(self):
        """Test ComposeConfig with minimal required fields"""
        svc = ComposeServiceConfig(name="web")
        config = ComposeConfig(services=[svc])

        assert len(config.services) == 1
        assert config.version == "3.8"
        assert config.networks == []
        assert config.volumes == []
        assert config.configs == {}
        assert config.secrets == {}

    def test_compose_config_full(self):
        """Test ComposeConfig with all components"""
        services = [
            ComposeServiceConfig(name="web", image="nginx"),
            ComposeServiceConfig(name="api", build={"context": "./api"})
        ]
        networks = [
            NetworkConfig(name="frontend"),
            NetworkConfig(name="backend")
        ]
        volumes = [
            VolumeConfig(name="db-data"),
            VolumeConfig(name="cache-data")
        ]

        config = ComposeConfig(
            version="3.9",
            services=services,
            networks=networks,
            volumes=volumes,
            secrets={"db_password": {"file": "./secrets/db_pass.txt"}}
        )

        assert config.version == "3.9"
        assert len(config.services) == 2
        assert len(config.networks) == 2
        assert len(config.volumes) == 2
        assert "db_password" in config.secrets

    def test_compose_config_validation_missing_services(self):
        """Test ComposeConfig fails without services"""
        with pytest.raises(ValidationError):
            ComposeConfig()


@pytest.mark.L0
@pytest.mark.volundr
@pytest.mark.unit
@pytest.mark.fast
class TestGeneratedDockerConfig:
    """Test GeneratedDockerConfig model"""

    def test_generated_docker_config_minimal(self):
        """Test GeneratedDockerConfig with minimal required fields"""
        config = GeneratedDockerConfig(
            id="docker-123",
            config_hash="abc123",
            best_practice_score=85.5
        )

        assert config.id == "docker-123"
        assert config.config_hash == "abc123"
        assert config.dockerfile_content is None
        assert config.compose_content is None
        assert config.validation_results == []
        assert config.best_practice_score == 85.5
        assert isinstance(config.created_at, datetime)
        assert config.file_path is None

    def test_generated_docker_config_with_dockerfile(self):
        """Test GeneratedDockerConfig with Dockerfile content"""
        config = GeneratedDockerConfig(
            id="docker-456",
            config_hash="def456",
            dockerfile_content="FROM python:3.12-slim\nWORKDIR /app\n",
            best_practice_score=95.0
        )

        assert config.dockerfile_content is not None
        assert "FROM python:3.12-slim" in config.dockerfile_content

    def test_generated_docker_config_with_compose(self):
        """Test GeneratedDockerConfig with compose content"""
        config = GeneratedDockerConfig(
            id="docker-789",
            config_hash="ghi789",
            compose_content="version: '3.8'\nservices:\n  web:\n    image: nginx\n",
            best_practice_score=90.0
        )

        assert config.compose_content is not None
        assert "services:" in config.compose_content

    def test_generated_docker_config_with_validation_results(self):
        """Test GeneratedDockerConfig with validation issues"""
        config = GeneratedDockerConfig(
            id="docker-000",
            config_hash="xyz000",
            validation_results=[
                "Missing healthcheck",
                "Running as root user",
                "Using latest tag"
            ],
            best_practice_score=60.0
        )

        assert len(config.validation_results) == 3
        assert "Missing healthcheck" in config.validation_results

    def test_generated_docker_config_has_issues_property(self):
        """Test GeneratedDockerConfig has_issues property"""
        config1 = GeneratedDockerConfig(
            id="clean",
            config_hash="clean123",
            validation_results=[],
            best_practice_score=100.0
        )
        assert config1.has_issues is False

        config2 = GeneratedDockerConfig(
            id="issues",
            config_hash="issues123",
            validation_results=["Problem 1", "Problem 2"],
            best_practice_score=75.0
        )
        assert config2.has_issues is True

    def test_generated_docker_config_score_validation(self):
        """Test GeneratedDockerConfig score must be 0-100"""
        with pytest.raises(ValidationError):
            GeneratedDockerConfig(
                id="invalid",
                config_hash="invalid",
                best_practice_score=150.0
            )

        with pytest.raises(ValidationError):
            GeneratedDockerConfig(
                id="invalid",
                config_hash="invalid",
                best_practice_score=-10.0
            )

    def test_generated_docker_config_created_at_default(self):
        """Test GeneratedDockerConfig created_at defaults to current time"""
        before = datetime.now()
        config = GeneratedDockerConfig(
            id="time-test",
            config_hash="time123",
            best_practice_score=88.0
        )
        after = datetime.now()

        assert before <= config.created_at <= after
