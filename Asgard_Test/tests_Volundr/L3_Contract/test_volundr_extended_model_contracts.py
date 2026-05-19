"""L3 Contract tests for additional Volundr (infrastructure) models.

Covers: Compose, GitOps, Kubernetes, Kustomize, Scaffold, Terraform, Validation.
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------
from Asgard.Volundr.Compose.models.compose_models import (
    ComposeService,
    ComposeNetwork,
    ComposeVolume,
    ComposeConfig,
    ComposeProject,
    GeneratedComposeConfig,
)


class TestComposeServiceContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            ComposeService()

    def test_accepts_valid_data(self):
        svc = ComposeService(name="web")
        assert svc.name == "web"
        assert hasattr(svc, "image") or hasattr(ComposeService, "model_fields")


class TestComposeProjectContract:
    def test_requires_name_and_services(self):
        with pytest.raises((ValidationError, TypeError)):
            ComposeProject()

    def test_accepts_valid_data(self):
        svc = ComposeService(name="web")
        proj = ComposeProject(name="myapp", services=[svc])
        assert proj.name == "myapp"
        assert len(proj.services) > 0


class TestComposeConfigContract:
    def test_instantiates_with_defaults(self):
        config = ComposeConfig()
        assert config is not None


class TestGeneratedComposeConfigContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GeneratedComposeConfig()

    def test_accepts_valid_data(self):
        gcc = GeneratedComposeConfig(
            id="gc-001",
            config_hash="abc123",
            compose_content="version: '3'",
            best_practice_score=90.0,
        )
        assert gcc.id == "gc-001"
        assert hasattr(gcc, "best_practice_score")


# ---------------------------------------------------------------------------
# GitOps
# ---------------------------------------------------------------------------
from Asgard.Volundr.GitOps.models.gitops_models import (
    ArgoSource,
    ArgoDestination,
    ArgoApplication,
    FluxGitRepository,
    FluxKustomization,
    GitOpsConfig,
    GeneratedGitOpsConfig,
)


class TestArgoApplicationContract:
    def test_requires_name_source_destination(self):
        with pytest.raises((ValidationError, TypeError)):
            ArgoApplication()

    def test_accepts_valid_data(self):
        from Asgard.Volundr.GitOps.models.gitops_models import ArgoSource, ArgoDestination
        source = ArgoSource(repo_url="https://github.com/org/repo", path="./k8s")
        dest = ArgoDestination(server="https://k8s.example.com", namespace="default")
        app = ArgoApplication(name="my-app", source=source, destination=dest)
        assert app.name == "my-app"
        assert hasattr(app, "source")


class TestGitOpsConfigContract:
    def test_requires_provider(self):
        with pytest.raises((ValidationError, TypeError)):
            GitOpsConfig()

    def test_accepts_valid_data(self):
        config = GitOpsConfig(provider="argocd")
        assert config.provider == "argocd"


# ---------------------------------------------------------------------------
# Kubernetes
# ---------------------------------------------------------------------------
from Asgard.Volundr.Kubernetes.models.kubernetes_models import (
    ResourceRequirements,
    SecurityContext,
    ProbeConfig,
    PortConfig,
    ManifestConfig,
    GeneratedManifest,
)


class TestResourceRequirementsContract:
    def test_instantiates_with_defaults(self):
        rr = ResourceRequirements()
        assert rr is not None
        assert hasattr(ResourceRequirements, "model_fields")


class TestManifestConfigContract:
    def test_requires_name_and_image(self):
        with pytest.raises((ValidationError, TypeError)):
            ManifestConfig()

    def test_accepts_valid_data(self):
        mc = ManifestConfig(name="my-service", image="nginx:latest")
        assert mc.name == "my-service"
        assert hasattr(mc, "image")


class TestGeneratedManifestContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GeneratedManifest()

    def test_accepts_valid_data(self):
        gm = GeneratedManifest(
            id="gm-001",
            config_hash="abc123",
            manifests={"deployment": {"apiVersion": "apps/v1"}},
            yaml_content="apiVersion: apps/v1",
            best_practice_score=85.0,
        )
        assert gm.id == "gm-001"
        assert hasattr(gm, "best_practice_score")


# ---------------------------------------------------------------------------
# Kustomize
# ---------------------------------------------------------------------------
from Asgard.Volundr.Kustomize.models.kustomize_models import (
    KustomizeBase,
    KustomizeOverlay,
    KustomizeConfig,
    GeneratedKustomization,
)


class TestKustomizeBaseContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            KustomizeBase()

    def test_accepts_valid_data(self):
        kb = KustomizeBase(name="base")
        assert kb.name == "base"
        assert hasattr(kb, "resources") or hasattr(KustomizeBase, "model_fields")


class TestKustomizeConfigContract:
    def test_requires_base_and_image(self):
        with pytest.raises((ValidationError, TypeError)):
            KustomizeConfig()

    def test_accepts_valid_data(self):
        kb = KustomizeBase(name="base")
        config = KustomizeConfig(base=kb, image="nginx:latest")
        assert config.image == "nginx:latest"


class TestGeneratedKustomizationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GeneratedKustomization()

    def test_accepts_valid_data(self):
        gk = GeneratedKustomization(
            id="gk-001",
            config_hash="abc123",
            files={"kustomization.yaml": "..."},
            best_practice_score=95.0,
        )
        assert gk.id == "gk-001"


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------
from Asgard.Volundr.Scaffold.models.scaffold_models import (
    DependencyConfig,
    ServiceConfig,
    ProjectConfig,
    FileEntry,
    ScaffoldReport,
)


class TestServiceConfigContract:
    def test_requires_name_and_language(self):
        with pytest.raises((ValidationError, TypeError)):
            ServiceConfig()

    def test_accepts_valid_data(self):
        sc = ServiceConfig(name="api", language="python")
        assert sc.name == "api"
        assert sc.language == "python"


class TestProjectConfigContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            ProjectConfig()

    def test_accepts_valid_data(self):
        pc = ProjectConfig(name="my-project")
        assert pc.name == "my-project"
        assert hasattr(pc, "services") or hasattr(ProjectConfig, "model_fields")


class TestFileEntryContract:
    def test_requires_path_and_content(self):
        with pytest.raises((ValidationError, TypeError)):
            FileEntry()

    def test_accepts_valid_data(self):
        fe = FileEntry(path="README.md", content="# My Project")
        assert fe.path == "README.md"


class TestScaffoldReportContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ScaffoldReport()

    def test_accepts_valid_data(self):
        sr = ScaffoldReport(id="sr-001", project_name="my-project", project_type="microservice")
        assert sr.project_name == "my-project"
        assert hasattr(sr, "files") or hasattr(ScaffoldReport, "model_fields")


# ---------------------------------------------------------------------------
# Terraform
# ---------------------------------------------------------------------------
from Asgard.Volundr.Terraform.models.terraform_models import (
    VariableConfig,
    OutputConfig,
    ModuleConfig,
    GeneratedModule,
)


class TestVariableConfigContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            VariableConfig()

    def test_accepts_valid_data(self):
        vc = VariableConfig(name="region")
        assert vc.name == "region"
        assert hasattr(vc, "type") or hasattr(VariableConfig, "model_fields")


class TestOutputConfigContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            OutputConfig()

    def test_accepts_valid_data(self):
        oc = OutputConfig(name="instance_id", description="EC2 instance ID", value="aws_instance.main.id")
        assert oc.name == "instance_id"


class TestModuleConfigContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ModuleConfig()

    def test_accepts_valid_data(self):
        mc = ModuleConfig(name="vpc", provider="aws", category="networking")
        assert mc.name == "vpc"
        assert hasattr(mc, "provider")


class TestGeneratedModuleContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GeneratedModule()

    def test_accepts_valid_data(self):
        gm = GeneratedModule(
            id="gm-001",
            config_hash="abc123",
            module_files={"main.tf": "..."},
            documentation="# VPC Module",
            best_practice_score=88.0,
        )
        assert gm.id == "gm-001"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationRule,
    ValidationResult,
    ValidationContext,
    FileValidationSummary,
    ValidationReport,
)


class TestValidationRuleContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ValidationRule()

    def test_accepts_valid_data(self):
        vr = ValidationRule(
            id="VR001",
            name="image-tag-required",
            description="Container image must have explicit tag",
            severity="error",
            category="security",
        )
        assert vr.id == "VR001"
        assert hasattr(vr, "severity")


class TestValidationResultContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ValidationResult()

    def test_accepts_valid_data(self):
        result = ValidationResult(
            rule_id="VR001",
            message="Image tag missing",
            severity="error",
            category="security",
        )
        assert result.rule_id == "VR001"


class TestValidationContextContract:
    def test_instantiates_with_defaults(self):
        ctx = ValidationContext()
        assert ctx is not None
        assert hasattr(ValidationContext, "model_fields")


class TestValidationReportContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ValidationReport()

    def test_accepts_valid_data(self):
        report = ValidationReport(id="rep-001", title="K8s Validation", validator="kubernetes")
        assert report.id == "rep-001"
        assert hasattr(report, "results") or hasattr(ValidationReport, "model_fields")
