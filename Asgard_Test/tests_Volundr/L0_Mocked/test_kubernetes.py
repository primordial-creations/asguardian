"""
Volundr Kubernetes Module Tests

Unit tests for Kubernetes manifest generation.
"""

import pytest
import yaml

from Asgard.Volundr.Kubernetes import (
    ManifestConfig,
    ManifestGenerator,
    GeneratedManifest,
    WorkloadType,
    SecurityProfile,
    EnvironmentType,
)
from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    ResourceRequirements,
    SecurityContext,
    ProbeConfig,
    PortConfig,
)


class TestManifestConfig:
    """Tests for ManifestConfig model validation."""

    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = ManifestConfig(name="myapp", image="nginx:latest")
        assert config.name == "myapp"
        assert config.image == "nginx:latest"
        assert config.workload_type == WorkloadType.DEPLOYMENT
        assert config.replicas == 1

    def test_full_config(self):
        """Test creating config with all fields."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            workload_type=WorkloadType.STATEFULSET,
            replicas=3,
            namespace="production",
            labels={"app": "myapp", "tier": "frontend"},
            security_profile=SecurityProfile.STRICT,
            environment=EnvironmentType.PRODUCTION,
        )
        assert config.workload_type == WorkloadType.STATEFULSET
        assert config.replicas == 3
        assert config.namespace == "production"
        assert config.security_profile == SecurityProfile.STRICT

    def test_resource_requirements(self):
        """Test ResourceRequirements model."""
        resources = ResourceRequirements(
            cpu_request="100m",
            cpu_limit="500m",
            memory_request="128Mi",
            memory_limit="512Mi",
        )
        assert resources.cpu_request == "100m"
        assert resources.memory_limit == "512Mi"

    def test_probe_config(self):
        """Test ProbeConfig model."""
        probe = ProbeConfig(
            http_path="/health",
            http_port=8080,
            initial_delay_seconds=10,
            period_seconds=30,
        )
        assert probe.http_path == "/health"
        assert probe.http_port == 8080
        assert probe.initial_delay_seconds == 10

    def test_port_config(self):
        """Test PortConfig model."""
        port = PortConfig(
            container_port=8080,
            service_port=80,
            protocol="TCP",
            name="http",
        )
        assert port.container_port == 8080
        assert port.service_port == 80

    def test_security_context(self):
        """Test SecurityContext model."""
        context = SecurityContext(
            run_as_non_root=True,
            run_as_user=1000,
            read_only_root_filesystem=True,
        )
        assert context.run_as_non_root is True
        assert context.run_as_user == 1000


class TestWorkloadType:
    """Tests for WorkloadType enum."""

    def test_all_workload_types(self):
        """Test all workload types exist."""
        assert WorkloadType.DEPLOYMENT.value == "Deployment"
        assert WorkloadType.STATEFULSET.value == "StatefulSet"
        assert WorkloadType.DAEMONSET.value == "DaemonSet"
        assert WorkloadType.JOB.value == "Job"
        assert WorkloadType.CRONJOB.value == "CronJob"


class TestSecurityProfile:
    """Tests for SecurityProfile enum."""

    def test_all_security_profiles(self):
        """Test all security profiles exist."""
        assert SecurityProfile.BASIC.value == "basic"
        assert SecurityProfile.ENHANCED.value == "enhanced"
        assert SecurityProfile.STRICT.value == "strict"
        assert SecurityProfile.ZERO_TRUST.value == "zero-trust"


class TestManifestGenerator:
    """Tests for ManifestGenerator service."""

    @pytest.fixture
    def generator(self):
        """Create a ManifestGenerator instance."""
        return ManifestGenerator()

    @pytest.fixture
    def basic_config(self):
        """Create a basic manifest config."""
        return ManifestConfig(name="testapp", image="nginx:latest")

    def test_generate_returns_manifest(self, generator, basic_config):
        """Test that generate returns a GeneratedManifest."""
        result = generator.generate(basic_config)
        assert isinstance(result, GeneratedManifest)
        assert result.yaml_content is not None
        assert len(result.yaml_content) > 0

    def test_generate_valid_yaml(self, generator, basic_config):
        """Test that generated content is valid YAML."""
        result = generator.generate(basic_config)
        # Should not raise an exception
        parsed = list(yaml.safe_load_all(result.yaml_content))
        assert len(parsed) > 0

    def test_generate_deployment(self, generator):
        """Test generating a Deployment."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            workload_type=WorkloadType.DEPLOYMENT,
            replicas=3,
        )
        result = generator.generate(config)
        assert "Deployment" in result.yaml_content
        assert "replicas: 3" in result.yaml_content

    def test_generate_statefulset(self, generator):
        """Test generating a StatefulSet."""
        config = ManifestConfig(
            name="myapp",
            image="postgres:15",
            workload_type=WorkloadType.STATEFULSET,
        )
        result = generator.generate(config)
        assert "StatefulSet" in result.yaml_content

    def test_generate_daemonset(self, generator):
        """Test generating a DaemonSet."""
        config = ManifestConfig(
            name="myapp",
            image="fluentd:latest",
            workload_type=WorkloadType.DAEMONSET,
        )
        result = generator.generate(config)
        assert "DaemonSet" in result.yaml_content

    def test_generate_job(self, generator):
        """Test generating a Job."""
        config = ManifestConfig(
            name="myjob",
            image="busybox:latest",
            workload_type=WorkloadType.JOB,
        )
        result = generator.generate(config)
        assert "Job" in result.yaml_content

    def test_generate_cronjob(self, generator):
        """Test generating a CronJob."""
        config = ManifestConfig(
            name="mycron",
            image="busybox:latest",
            workload_type=WorkloadType.CRONJOB,
            cron_schedule="0 * * * *",
        )
        result = generator.generate(config)
        assert "CronJob" in result.yaml_content

    def test_generate_includes_service(self, generator):
        """Test generating manifest includes Service when ports defined."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            ports=[PortConfig(container_port=80, service_port=80)],
        )
        result = generator.generate(config)
        assert "Service" in result.yaml_content
        assert "service" in result.manifests

    def test_generate_includes_configmap(self, generator):
        """Test generating manifest includes ConfigMap when specified."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            config_maps=["myapp-config"],
        )
        result = generator.generate(config)
        assert "ConfigMap" in result.yaml_content

    def test_generate_includes_network_policy(self, generator):
        """Test generating manifest includes NetworkPolicy for enhanced security."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            security_profile=SecurityProfile.STRICT,
        )
        result = generator.generate(config)
        assert "NetworkPolicy" in result.yaml_content
        assert "networkpolicy" in result.manifests

    def test_generate_includes_pdb(self, generator):
        """Test generating manifest includes PodDisruptionBudget for production."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            replicas=3,
            environment=EnvironmentType.PRODUCTION,
        )
        result = generator.generate(config)
        assert "PodDisruptionBudget" in result.yaml_content
        assert "poddisruptionbudget" in result.manifests

    def test_generate_with_probes(self, generator):
        """Test generating manifest includes liveness and readiness probes."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            liveness_probe=ProbeConfig(http_path="/health", http_port=8080),
            readiness_probe=ProbeConfig(http_path="/ready", http_port=8080),
        )
        result = generator.generate(config)
        assert "livenessProbe" in result.yaml_content
        assert "readinessProbe" in result.yaml_content

    def test_generate_with_resources(self, generator):
        """Test generating manifest with resource limits."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            resources=ResourceRequirements(
                cpu_request="100m",
                cpu_limit="500m",
                memory_request="128Mi",
                memory_limit="512Mi",
            ),
        )
        result = generator.generate(config)
        assert "resources:" in result.yaml_content
        assert "limits:" in result.yaml_content
        assert "requests:" in result.yaml_content

    def test_generate_with_security_context(self, generator):
        """Test generating manifest with security context."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            security_context=SecurityContext(
                run_as_non_root=True,
                run_as_user=1000,
            ),
        )
        result = generator.generate(config)
        assert "securityContext:" in result.yaml_content
        assert "runAsNonRoot: true" in result.yaml_content

    def test_best_practice_score(self, generator):
        """Test that best practice score is calculated."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            resources=ResourceRequirements(
                cpu_request="100m",
                cpu_limit="500m",
                memory_request="128Mi",
                memory_limit="512Mi",
            ),
            liveness_probe=ProbeConfig(http_path="/health", http_port=8080),
            readiness_probe=ProbeConfig(http_path="/ready", http_port=8080),
            security_context=SecurityContext(run_as_non_root=True),
            security_profile=SecurityProfile.STRICT,
            environment=EnvironmentType.PRODUCTION,
            replicas=3,
        )
        result = generator.generate(config)
        assert result.best_practice_score > 0
        assert result.best_practice_score <= 100

    def test_validation_results(self, generator, basic_config):
        """Test that validation results are included."""
        result = generator.generate(basic_config)
        assert isinstance(result.validation_results, list)

    def test_save_to_file(self, generator, basic_config, temp_output_dir):
        """Test saving manifest to file."""
        result = generator.generate(basic_config)
        file_path = generator.save_to_file(result, output_dir=str(temp_output_dir))
        assert file_path is not None
        assert "testapp" in file_path

    def test_namespace_in_manifest(self, generator):
        """Test that namespace is included in manifest."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            namespace="production",
        )
        result = generator.generate(config)
        assert "namespace: production" in result.yaml_content

    def test_labels_in_manifest(self, generator):
        """Test that custom labels are included."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            labels={"tier": "frontend"},
        )
        result = generator.generate(config)
        assert "tier: frontend" in result.yaml_content

    def test_environment_variables(self, generator):
        """Test that environment variables are included."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            env_vars={"LOG_LEVEL": "debug", "API_URL": "http://api"},
        )
        result = generator.generate(config)
        assert "LOG_LEVEL" in result.yaml_content
        assert "API_URL" in result.yaml_content

    def test_manifest_id_generated(self, generator, basic_config):
        """Test that manifest ID is generated."""
        result = generator.generate(basic_config)
        assert result.id is not None
        assert "testapp" in result.id

    def test_config_hash_generated(self, generator, basic_config):
        """Test that config hash is generated."""
        result = generator.generate(basic_config)
        assert result.config_hash is not None
        assert len(result.config_hash) > 0

    def test_manifests_dict_populated(self, generator, basic_config):
        """Test that manifests dict is populated."""
        result = generator.generate(basic_config)
        assert isinstance(result.manifests, dict)
        assert len(result.manifests) > 0

    def test_service_account_in_manifest(self, generator):
        """Test that service account is included when specified."""
        config = ManifestConfig(
            name="myapp",
            image="nginx:latest",
            service_account="myapp-sa",
        )
        result = generator.generate(config)
        assert "serviceAccountName: myapp-sa" in result.yaml_content
