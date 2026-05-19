"""
Volundr L8 Performance Benchmarks

Benchmarks for Volundr infrastructure configuration generation services
including Dockerfile generation, Kubernetes manifest generation,
Docker Compose generation, CI/CD pipeline generation, GitOps, Helm,
Kustomize, Scaffold, Terraform, and Validation services.
"""

import pytest

from Asgard.Volundr.Docker.services.dockerfile_generator import DockerfileGenerator
from Asgard.Volundr.Docker.models.docker_models import DockerfileConfig, BuildStage
from Asgard.Volundr.Kubernetes.services.manifest_generator import ManifestGenerator
from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    ManifestConfig,
    WorkloadType,
    SecurityProfile,
    EnvironmentType,
    PortConfig,
)
from Asgard.Volundr.Docker.services.compose_generator import ComposeGenerator
from Asgard.Volundr.Docker.models.docker_models import (
    ComposeServiceConfig,
    ComposeConfig,
    NetworkConfig,
)


# --- Shared input data ----------------------------------------------------------

SIMPLE_DOCKERFILE_CONFIG = DockerfileConfig(
    name="my-api",
    stages=[
        BuildStage(
            name="final",
            base_image="python:3.12-slim",
            workdir="/app",
            run_commands=["pip install --no-cache-dir -r requirements.txt"],
            copy_commands=[
                {"src": "requirements.txt", "dst": "."},
                {"src": ".", "dst": "."},
            ],
            cmd=["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
            expose_ports=[8000],
        )
    ],
)

MULTISTAGE_DOCKERFILE_CONFIG = DockerfileConfig(
    name="my-service",
    stages=[
        BuildStage(
            name="builder",
            base_image="python:3.12",
            workdir="/build",
            run_commands=[
                "pip install --no-cache-dir build",
                "python -m build",
            ],
            copy_commands=[{"src": ".", "dst": "."}],
        ),
        BuildStage(
            name="final",
            base_image="python:3.12-slim",
            workdir="/app",
            copy_from="builder",
            copy_src="/build/dist",
            copy_dst="/app/dist",
            run_commands=["pip install --no-cache-dir /app/dist/*.whl"],
            env_vars={"ENV": "production", "PORT": "8000"},
            expose_ports=[8000],
            cmd=["python", "-m", "myservice"],
        ),
    ],
    labels={"maintainer": "team@example.com", "version": "1.0.0"},
)

KUBERNETES_CONFIG = ManifestConfig(
    name="api-gateway",
    namespace="production",
    workload_type=WorkloadType.DEPLOYMENT,
    image="registry.example.com/api-gateway:v1.2.3",
    replicas=3,
    environment=EnvironmentType.PRODUCTION,
    security_profile=SecurityProfile.ENHANCED,
    env_vars={"LOG_LEVEL": "info", "DB_HOST": "postgres-svc", "CACHE_HOST": "redis-svc"},
    ports=[PortConfig(name="http", container_port=8080, service_port=80)],
    config_maps=["app-config"],
    secrets=["db-credentials"],
)


class TestVolundrPerformance:
    """L8 performance benchmarks for Volundr infrastructure generation services."""

    def test_dockerfile_generation_simple(self, benchmark):
        """Benchmark single-stage Dockerfile generation from in-memory config."""
        generator = DockerfileGenerator()

        result = benchmark(generator.generate, SIMPLE_DOCKERFILE_CONFIG)

        assert result is not None
        assert result.dockerfile_content
        assert "FROM python:3.12-slim" in result.dockerfile_content

    def test_dockerfile_generation_multistage(self, benchmark):
        """Benchmark multi-stage Dockerfile generation with copy-from directives."""
        generator = DockerfileGenerator()

        result = benchmark(generator.generate, MULTISTAGE_DOCKERFILE_CONFIG)

        assert result is not None
        assert result.dockerfile_content
        assert "AS builder" in result.dockerfile_content
        assert "AS final" in result.dockerfile_content

    def test_kubernetes_manifest_generation(self, benchmark):
        """Benchmark full K8s manifest generation (Deployment + Service + NetworkPolicy)."""
        generator = ManifestGenerator()

        result = benchmark(generator.generate, KUBERNETES_CONFIG)

        assert result is not None
        assert result.yaml_content
        assert result.id
        # Production with enhanced security should produce multiple resources
        assert len(result.manifests) >= 2

    def test_compose_generation(self, benchmark):
        """Benchmark Docker Compose config generation with multiple services."""
        generator = ComposeGenerator()
        config = ComposeConfig(
            services=[
                ComposeServiceConfig(
                    name="api",
                    image="my-api:latest",
                    ports=["8000:8000"],
                    environment={"DATABASE_URL": "postgres://db:5432/app"},
                    depends_on=["db", "redis"],
                    networks=["backend"],
                ),
                ComposeServiceConfig(
                    name="db",
                    image="postgres:15-alpine",
                    environment={"POSTGRES_DB": "app", "POSTGRES_PASSWORD": "secret"},
                    volumes=["pg_data:/var/lib/postgresql/data"],
                    networks=["backend"],
                ),
                ComposeServiceConfig(
                    name="redis",
                    image="redis:7-alpine",
                    networks=["backend"],
                ),
            ],
            networks=[NetworkConfig(name="backend")],
        )

        result = benchmark(generator.generate, config)

        assert result is not None
        assert result.compose_content
        assert "api" in result.compose_content


# --- CI/CD benchmarks ---------------------------------------------------------

class TestCICDPerformance:
    """Benchmarks for CI/CD services."""

    def test_pipeline_generator_generate(self, benchmark):
        """Benchmark PipelineGenerator.generate for a GitHub Actions pipeline."""
        from Asgard.Volundr.CICD.services.pipeline_generator import PipelineGenerator
        from Asgard.Volundr.CICD.models.cicd_models import (
            PipelineConfig,
            PipelineStage,
            StepConfig,
            TriggerConfig,
            TriggerType,
            CICDPlatform,
            DeploymentStrategy,
        )

        config = PipelineConfig(
            name="my-service-pipeline",
            platform=CICDPlatform.GITHUB_ACTIONS,
            triggers=[
                TriggerConfig(type=TriggerType.PUSH, branches=["main"]),
                TriggerConfig(type=TriggerType.PULL_REQUEST, branches=["main"]),
            ],
            stages=[
                PipelineStage(
                    name="test",
                    steps=[
                        StepConfig(name="Checkout", uses="actions/checkout@v4"),
                        StepConfig(name="Setup Python", uses="actions/setup-python@v5"),
                        StepConfig(name="Run tests", run="pytest"),
                    ],
                ),
                PipelineStage(
                    name="build",
                    needs=["test"],
                    steps=[
                        StepConfig(name="Build Docker image", run="docker build -t my-service ."),
                    ],
                ),
            ],
            deployment_strategy=DeploymentStrategy.ROLLING,
            docker_registry="registry.example.com",
        )
        generator = PipelineGenerator()

        result = benchmark(generator.generate, config)

        assert result is not None
        assert result.pipeline_content


# --- GitOps benchmarks --------------------------------------------------------

class TestGitOpsPerformance:
    """Benchmarks for GitOps services."""

    def test_argocd_generator_generate(self, benchmark):
        """Benchmark ArgocdGenerator.generate for an ArgoCD Application."""
        from Asgard.Volundr.GitOps.services.argocd_generator import ArgoCDGenerator as ArgocdGenerator
        from Asgard.Volundr.GitOps.models.gitops_models import (
            ArgoApplication,
            ArgoSource,
            ArgoDestination,
            SyncPolicy,
        )

        app = ArgoApplication(
            name="my-service",
            project="default",
            source=ArgoSource(
                repo_url="https://github.com/example/my-service",
                target_revision="HEAD",
                path="k8s/overlays/production",
            ),
            destination=ArgoDestination(namespace="production"),
            sync_policy=SyncPolicy(automated=True, prune=True, self_heal=True),
        )
        generator = ArgocdGenerator()

        result = benchmark(generator.generate, app)

        assert result is not None
        assert result.files

    def test_flux_generator_generate_git_repository(self, benchmark):
        """Benchmark FluxGenerator.generate_git_repository."""
        from Asgard.Volundr.GitOps.services.flux_generator import FluxGenerator
        from Asgard.Volundr.GitOps.models.gitops_models import FluxGitRepository

        git_repo = FluxGitRepository(
            name="my-service",
            namespace="flux-system",
            url="https://github.com/example/my-service",
            branch="main",
            interval="1m",
        )
        generator = FluxGenerator()

        result = benchmark(generator.generate_git_repository, git_repo)

        assert result is not None
        assert result.files


# --- Helm benchmarks ----------------------------------------------------------

class TestHelmPerformance:
    """Benchmarks for Helm services."""

    def test_chart_generator_generate(self, benchmark):
        """Benchmark ChartGenerator.generate for a production Helm chart."""
        from Asgard.Volundr.Helm.services.chart_generator import ChartGenerator
        from Asgard.Volundr.Helm.models.helm_models import (
            HelmConfig,
            HelmChart,
            HelmValues,
        )

        config = HelmConfig(
            chart=HelmChart(
                name="my-service",
                version="1.0.0",
                app_version="2.3.4",
                description="My microservice Helm chart",
            ),
            values=HelmValues(
                image_repository="registry.example.com/my-service",
                image_tag="2.3.4",
                replica_count=3,
            ),
            generate_tests=True,
            generate_notes=True,
            generate_helpers=True,
            include_hpa=True,
            include_service_account=True,
        )
        generator = ChartGenerator()

        result = benchmark(generator.generate, config)

        assert result is not None
        assert result.chart_files
        assert "Chart.yaml" in result.chart_files

    def test_values_generator_generate(self, benchmark):
        """Benchmark ValuesGenerator.generate for production environment."""
        from Asgard.Volundr.Helm.services.values_generator import ValuesGenerator

        generator = ValuesGenerator()

        result = benchmark(
            generator.generate,
            image_repository="registry.example.com/my-service",
            environment="production",
            image_tag="2.3.4",
            service_port=8080,
            ingress_enabled=True,
            ingress_host="my-service.example.com",
        )

        assert result is not None
        assert isinstance(result, dict)


# --- Kustomize benchmarks -----------------------------------------------------

class TestKustomizePerformance:
    """Benchmarks for Kustomize services."""

    def test_base_generator_generate(self, benchmark):
        """Benchmark BaseGenerator.generate for a standard base configuration."""
        from Asgard.Volundr.Kustomize.services.base_generator import BaseGenerator
        from Asgard.Volundr.Kustomize.models.kustomize_models import (
            KustomizeConfig,
            KustomizeBase,
        )

        config = KustomizeConfig(
            base=KustomizeBase(
                name="my-service",
                namespace="default",
                common_labels={"app": "my-service", "team": "platform"},
            ),
            image="registry.example.com/my-service:latest",
            container_port=8080,
            replicas=2,
            generate_deployment=True,
            generate_service=True,
        )
        generator = BaseGenerator()

        result = benchmark(generator.generate, config)

        assert result is not None
        assert result.files

    def test_overlay_generator_generate(self, benchmark):
        """Benchmark OverlayGenerator.generate for a production overlay."""
        from Asgard.Volundr.Kustomize.services.overlay_generator import OverlayGenerator
        from Asgard.Volundr.Kustomize.models.kustomize_models import (
            KustomizeOverlay,
            ImageTransformer,
            ReplicaTransformer,
        )

        overlay = KustomizeOverlay(
            name="production",
            bases=["../../base"],
            namespace="production",
            images=[
                ImageTransformer(
                    name="registry.example.com/my-service",
                    new_tag="1.2.3",
                )
            ],
            replicas=[ReplicaTransformer(name="my-service", count=5)],
            common_labels={"environment": "production"},
        )
        generator = OverlayGenerator()

        result = benchmark(generator.generate, overlay, app_name="my-service")

        assert result is not None
        assert result.files

    def test_patch_generator_generate_replica_patch(self, benchmark):
        """Benchmark PatchGenerator.generate_replica_patch."""
        from Asgard.Volundr.Kustomize.services.patch_generator import PatchGenerator

        generator = PatchGenerator()

        result = benchmark(
            generator.generate_replica_patch,
            resource_name="my-service",
            replicas=5,
            kind="Deployment",
        )

        assert result is not None
        assert isinstance(result, str)
        assert "replicas" in result


# --- Scaffold benchmarks -------------------------------------------------------

class TestScaffoldPerformance:
    """Benchmarks for Scaffold services."""

    def test_microservice_scaffold_generate(self, benchmark):
        """Benchmark MicroserviceScaffold.generate for a Python FastAPI service."""
        from Asgard.Volundr.Scaffold.services.microservice_scaffold import MicroserviceScaffold
        from Asgard.Volundr.Scaffold.models.scaffold_models import (
            ServiceConfig,
            Language,
            Framework,
            ProjectType,
        )

        config = ServiceConfig(
            name="my-api",
            description="My FastAPI microservice",
            project_type=ProjectType.MICROSERVICE,
            language=Language.PYTHON,
            framework=Framework.FASTAPI,
            port=8080,
            include_tests=True,
            include_docker=True,
            include_cicd=True,
            include_healthcheck=True,
        )
        scaffold = MicroserviceScaffold()

        result = benchmark(scaffold.generate, config)

        assert result is not None
        assert result.files


# --- Terraform benchmarks -----------------------------------------------------

class TestTerraformPerformance:
    """Benchmarks for Terraform services."""

    def test_module_builder_generate(self, benchmark):
        """Benchmark ModuleBuilder.generate for an AWS networking module."""
        from Asgard.Volundr.Terraform.services.module_builder import ModuleBuilder
        from Asgard.Volundr.Terraform.models.terraform_models import (
            ModuleConfig,
            CloudProvider,
            ResourceCategory,
            ModuleComplexity,
            VariableConfig,
            OutputConfig,
        )

        config = ModuleConfig(
            name="vpc",
            provider=CloudProvider.AWS,
            category=ResourceCategory.NETWORKING,
            complexity=ModuleComplexity.MODERATE,
            description="AWS VPC module with public and private subnets",
            version="1.0.0",
            variables=[
                VariableConfig(
                    name="vpc_cidr",
                    type="string",
                    description="VPC CIDR block",
                    default="10.0.0.0/16",
                ),
                VariableConfig(
                    name="availability_zones",
                    type="list(string)",
                    description="List of availability zones",
                ),
            ],
            outputs=[
                OutputConfig(
                    name="vpc_id",
                    description="The VPC ID",
                    value="aws_vpc.main.id",
                ),
            ],
            resources=["aws_vpc", "aws_subnet", "aws_internet_gateway"],
            tags={"managed-by": "terraform", "team": "platform"},
        )
        builder = ModuleBuilder()

        result = benchmark(builder.generate, config)

        assert result is not None
        assert result.module_files
        assert "main.tf" in result.module_files


# --- Validation benchmarks ----------------------------------------------------

class TestValidationPerformance:
    """Benchmarks for Validation services."""

    def test_dockerfile_validator_validate_content(self, benchmark):
        """Benchmark DockerfileValidator.validate_content on a real Dockerfile."""
        from Asgard.Volundr.Validation.services.dockerfile_validator import DockerfileValidator

        dockerfile_content = """\
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS final
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .
USER 1000
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8080/health || exit 1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
"""
        validator = DockerfileValidator()

        result = benchmark(validator.validate_content, dockerfile_content, "Dockerfile")

        assert result is not None

    def test_kubernetes_validator_validate_content(self, benchmark):
        """Benchmark KubernetesValidator.validate_content on a Deployment manifest."""
        from Asgard.Volundr.Validation.services.kubernetes_validator import KubernetesValidator

        manifest_content = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
  namespace: production
  labels:
    app: my-service
    version: "1.0.0"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-service
  template:
    metadata:
      labels:
        app: my-service
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: my-service
          image: registry.example.com/my-service:1.0.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
"""
        validator = KubernetesValidator()

        result = benchmark(validator.validate_content, manifest_content, "deployment.yaml")

        assert result is not None

    def test_terraform_validator_validate_content(self, benchmark):
        """Benchmark TerraformValidator._validate_content on a simple HCL module."""
        from Asgard.Volundr.Validation.services.terraform_validator import TerraformValidator

        tf_content = """\
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr

  tags = {
    Name        = "main-vpc"
    Environment = var.environment
  }
}

output "vpc_id" {
  description = "The VPC ID"
  value       = aws_vpc.main.id
}
"""
        validator = TerraformValidator()

        result = benchmark(validator._validate_content, tf_content, "main.tf")

        assert result is not None
        assert isinstance(result, list)
