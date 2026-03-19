"""
Volundr CLI

Command-line interface for infrastructure generation.

Usage:
    python -m Volundr --help
    python -m Volundr kubernetes generate --name myapp --image nginx:latest
    python -m Volundr terraform generate --name vpc-module --provider aws --category networking
    python -m Volundr docker dockerfile --name myapp --base python:3.12-slim
    python -m Volundr cicd generate --name build-deploy --platform github_actions
    python -m Volundr helm init myapp
    python -m Volundr kustomize init myapp
    python -m Volundr argocd app https://github.com/org/repo
    python -m Volundr flux source https://github.com/org/repo
    python -m Volundr compose generate myapp
    python -m Volundr validate kubernetes ./manifests
    python -m Volundr scaffold microservice myapp
"""

import argparse
import json
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from Asgard.common.output_formatter import OutputFormat, UnifiedFormatter
from Asgard.common.progress import ProgressReporter

from Asgard.Volundr.Kubernetes import (
    ManifestConfig,
    ManifestGenerator,
    WorkloadType,
    SecurityProfile,
    EnvironmentType,
    PortConfig,
)
from Asgard.Volundr.Terraform import (
    ModuleConfig,
    ModuleBuilder,
    CloudProvider,
    ResourceCategory,
    ModuleComplexity,
    VariableConfig,
    OutputConfig,
)
from Asgard.Volundr.Docker import (
    DockerfileConfig,
    DockerfileGenerator,
    ComposeConfig,
    ComposeGenerator,
    ComposeServiceConfig,
    BuildStage,
)
from Asgard.Volundr.CICD import (
    PipelineConfig,
    PipelineGenerator,
    CICDPlatform,
    PipelineStage,
    TriggerConfig,
    TriggerType,
    StepConfig,
)
from Asgard.Volundr.Helm import (
    HelmChart,
    HelmValues,
    HelmConfig,
    ChartGenerator,
    ValuesGenerator,
)
from Asgard.Volundr.Kustomize import (
    KustomizeBase,
    KustomizeOverlay,
    KustomizeConfig,
    BaseGenerator,
    OverlayGenerator,
)
from Asgard.Volundr.GitOps import (
    ArgoApplication,
    ArgoSource,
    ArgoDestination,
    ArgoCDGenerator,
    FluxGenerator,
    FluxGitRepository,
    FluxKustomization,
)
from Asgard.Volundr.Compose import (
    ComposeProject,
    ComposeService,
    ComposeProjectGenerator,
    ComposeValidator,
    HealthCheckConfig,
)
from Asgard.Volundr.Validation import (
    KubernetesValidator,
    TerraformValidator,
    DockerfileValidator,
    ValidationContext,
)
from Asgard.Volundr.Scaffold import (
    ServiceConfig,
    ProjectConfig,
    MicroserviceScaffold,
    MonorepoScaffold,
    Language,
    Framework,
    ProjectType,
)


def add_performance_flags(parser: argparse.ArgumentParser) -> None:
    """Add performance-related flags to a parser (parallel, incremental, cache)."""
    parser.add_argument(
        "--parallel",
        "-P",
        action="store_true",
        help="Enable parallel processing for faster analysis",
    )
    parser.add_argument(
        "--workers",
        "-W",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count - 1)",
    )
    parser.add_argument(
        "--incremental",
        "-I",
        action="store_true",
        help="Enable incremental scanning (skip unchanged files)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching even if incremental mode is enabled",
    )
    parser.add_argument(
        "--baseline",
        "-B",
        type=str,
        default=None,
        help="Path to baseline file for filtering known issues",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="volundr",
        description="Volundr - Infrastructure Generation",
        epilog="Named after the legendary Norse master smith.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Volundr 2.0.0",
    )

    # Common flags
    parser.add_argument(
        "--format",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing files",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _add_kubernetes_commands(subparsers)
    _add_terraform_commands(subparsers)
    _add_docker_commands(subparsers)
    _add_cicd_commands(subparsers)
    _add_helm_commands(subparsers)
    _add_kustomize_commands(subparsers)
    _add_argocd_commands(subparsers)
    _add_flux_commands(subparsers)
    _add_compose_commands(subparsers)
    _add_validate_commands(subparsers)
    _add_scaffold_commands(subparsers)

    return parser


def _add_kubernetes_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add Kubernetes subcommands."""
    k8s_parser = subparsers.add_parser("kubernetes", aliases=["k8s"], help="Kubernetes manifest generation")
    k8s_subparsers = k8s_parser.add_subparsers(dest="k8s_command", help="Kubernetes commands")

    generate = k8s_subparsers.add_parser("generate", help="Generate Kubernetes manifests")
    generate.add_argument("--name", required=True, help="Application name")
    generate.add_argument("--image", required=True, help="Container image")
    generate.add_argument("--namespace", default="default", help="Kubernetes namespace")
    generate.add_argument(
        "--type",
        choices=[t.value for t in WorkloadType],
        default="Deployment",
        help="Workload type",
    )
    generate.add_argument("--replicas", type=int, default=1, help="Number of replicas")
    generate.add_argument(
        "--environment",
        choices=[e.value for e in EnvironmentType],
        default="development",
        help="Environment type",
    )
    generate.add_argument(
        "--security-profile",
        choices=[s.value for s in SecurityProfile],
        default="basic",
        help="Security profile",
    )
    generate.add_argument("--port", type=int, default=8080, help="Container port")
    generate.add_argument("--output-dir", default="manifests", help="Output directory")
    generate.add_argument("--format", choices=["yaml", "json"], default="yaml", help="Output format")

    add_performance_flags(k8s_parser)


def _add_terraform_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add Terraform subcommands."""
    tf_parser = subparsers.add_parser("terraform", aliases=["tf"], help="Terraform module generation")
    tf_subparsers = tf_parser.add_subparsers(dest="tf_command", help="Terraform commands")

    generate = tf_subparsers.add_parser("generate", help="Generate Terraform module")
    generate.add_argument("--name", required=True, help="Module name")
    generate.add_argument(
        "--provider",
        choices=[p.value for p in CloudProvider],
        required=True,
        help="Cloud provider",
    )
    generate.add_argument(
        "--category",
        choices=[c.value for c in ResourceCategory],
        required=True,
        help="Resource category",
    )
    generate.add_argument(
        "--complexity",
        choices=[c.value for c in ModuleComplexity],
        default="simple",
        help="Module complexity",
    )
    generate.add_argument("--description", default="", help="Module description")
    generate.add_argument("--output-dir", default="modules", help="Output directory")

    add_performance_flags(tf_parser)


def _add_docker_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add Docker subcommands."""
    docker_parser = subparsers.add_parser("docker", help="Docker configuration generation")
    docker_subparsers = docker_parser.add_subparsers(dest="docker_command", help="Docker commands")

    dockerfile = docker_subparsers.add_parser("dockerfile", help="Generate Dockerfile")
    dockerfile.add_argument("--name", required=True, help="Application name")
    dockerfile.add_argument("--base", required=True, help="Base image")
    dockerfile.add_argument("--workdir", default="/app", help="Working directory")
    dockerfile.add_argument("--port", type=int, default=8080, help="Exposed port")
    dockerfile.add_argument("--user", default="appuser", help="Non-root user")
    dockerfile.add_argument("--output-dir", default=".", help="Output directory")
    dockerfile.add_argument("--multi-stage", action="store_true", help="Use multi-stage build")

    compose = docker_subparsers.add_parser("compose", help="Generate docker-compose.yml")
    compose.add_argument("--name", required=True, help="Project name")
    compose.add_argument("--services", nargs="+", required=True, help="Service names")
    compose.add_argument("--output-dir", default=".", help="Output directory")

    add_performance_flags(docker_parser)


def _add_cicd_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add CI/CD subcommands."""
    cicd_parser = subparsers.add_parser("cicd", help="CI/CD pipeline generation")
    cicd_subparsers = cicd_parser.add_subparsers(dest="cicd_command", help="CI/CD commands")

    generate = cicd_subparsers.add_parser("generate", help="Generate CI/CD pipeline")
    generate.add_argument("--name", required=True, help="Pipeline name")
    generate.add_argument(
        "--platform",
        choices=[p.value for p in CICDPlatform],
        default="github_actions",
        help="CI/CD platform",
    )
    generate.add_argument("--branch", default="main", help="Main branch name")
    generate.add_argument("--docker-image", help="Docker image to build/push")
    generate.add_argument("--output-dir", default=".", help="Output directory")

    add_performance_flags(cicd_parser)


def _add_helm_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add Helm subcommands."""
    helm_parser = subparsers.add_parser("helm", help="Helm chart generation")
    helm_subparsers = helm_parser.add_subparsers(dest="helm_command", help="Helm commands")

    init = helm_subparsers.add_parser("init", help="Initialize a new Helm chart")
    init.add_argument("name", help="Chart name")
    init.add_argument("--image", required=True, help="Container image repository")
    init.add_argument("--version", default="0.1.0", help="Chart version")
    init.add_argument("--app-version", default="1.0.0", help="Application version")
    init.add_argument("--description", default="", help="Chart description")
    init.add_argument("--output-dir", default="charts", help="Output directory")

    values = helm_subparsers.add_parser("values", help="Generate values.yaml for environment")
    values.add_argument("chart", help="Chart name")
    values.add_argument("--image", required=True, help="Container image repository")
    values.add_argument("--environment", default="development", help="Target environment")
    values.add_argument("--output-dir", default=".", help="Output directory")

    add_performance_flags(helm_parser)


def _add_kustomize_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add Kustomize subcommands."""
    kustomize_parser = subparsers.add_parser("kustomize", help="Kustomize configuration generation")
    kustomize_subparsers = kustomize_parser.add_subparsers(dest="kustomize_command", help="Kustomize commands")

    init = kustomize_subparsers.add_parser("init", help="Initialize Kustomize base")
    init.add_argument("name", help="Application name")
    init.add_argument("--image", required=True, help="Container image")
    init.add_argument("--namespace", default="default", help="Namespace")
    init.add_argument("--port", type=int, default=8080, help="Container port")
    init.add_argument("--output-dir", default="kustomize", help="Output directory")

    overlay = kustomize_subparsers.add_parser("overlay", help="Generate environment overlay")
    overlay.add_argument("base", help="Base path or name")
    overlay.add_argument("--env", required=True, help="Environment name")
    overlay.add_argument("--namespace", help="Override namespace")
    overlay.add_argument("--replicas", type=int, help="Replica count")
    overlay.add_argument("--output-dir", default="kustomize", help="Output directory")

    add_performance_flags(kustomize_parser)


def _add_argocd_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add ArgoCD subcommands."""
    argocd_parser = subparsers.add_parser("argocd", help="ArgoCD configuration generation")
    argocd_subparsers = argocd_parser.add_subparsers(dest="argocd_command", help="ArgoCD commands")

    app = argocd_subparsers.add_parser("app", help="Generate ArgoCD Application manifest")
    app.add_argument("repo", help="Git repository URL")
    app.add_argument("--name", required=True, help="Application name")
    app.add_argument("--path", default=".", help="Path within repository")
    app.add_argument("--namespace", required=True, help="Target namespace")
    app.add_argument("--revision", default="HEAD", help="Target revision")
    app.add_argument("--project", default="default", help="ArgoCD project")
    app.add_argument("--auto-sync", action="store_true", help="Enable automated sync")
    app.add_argument("--output-dir", default="argocd", help="Output directory")

    add_performance_flags(argocd_parser)


def _add_flux_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add Flux subcommands."""
    flux_parser = subparsers.add_parser("flux", help="Flux configuration generation")
    flux_subparsers = flux_parser.add_subparsers(dest="flux_command", help="Flux commands")

    source = flux_subparsers.add_parser("source", help="Generate Flux GitRepository")
    source.add_argument("repo", help="Git repository URL")
    source.add_argument("--name", required=True, help="GitRepository name")
    source.add_argument("--branch", default="main", help="Git branch")
    source.add_argument("--interval", default="1m", help="Sync interval")
    source.add_argument("--output-dir", default="flux", help="Output directory")

    kustomization = flux_subparsers.add_parser("kustomization", help="Generate Flux Kustomization")
    kustomization.add_argument("source", help="Source reference name")
    kustomization.add_argument("--name", required=True, help="Kustomization name")
    kustomization.add_argument("--path", default="./", help="Path in repository")
    kustomization.add_argument("--namespace", help="Target namespace")
    kustomization.add_argument("--interval", default="10m", help="Sync interval")
    kustomization.add_argument("--output-dir", default="flux", help="Output directory")

    add_performance_flags(flux_parser)


def _add_compose_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add Compose subcommands."""
    compose_parser = subparsers.add_parser("compose", help="Docker Compose generation")
    compose_subparsers = compose_parser.add_subparsers(dest="compose_command", help="Compose commands")

    generate = compose_subparsers.add_parser("generate", help="Generate docker-compose.yaml")
    generate.add_argument("name", help="Project name")
    generate.add_argument("--service", action="append", dest="services", help="Service definition (name:image:port)")
    generate.add_argument("--environment", default="development", help="Target environment")
    generate.add_argument("--output-dir", default=".", help="Output directory")

    validate = compose_subparsers.add_parser("validate", help="Validate docker-compose.yaml")
    validate.add_argument("file", help="Compose file to validate")

    add_performance_flags(compose_parser)


def _add_validate_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add validation subcommands."""
    validate_parser = subparsers.add_parser("validate", help="Validate infrastructure configurations")
    validate_subparsers = validate_parser.add_subparsers(dest="validate_command", help="Validate commands")

    k8s = validate_subparsers.add_parser("kubernetes", aliases=["k8s"], help="Validate Kubernetes manifests")
    k8s.add_argument("path", help="File or directory to validate")
    k8s.add_argument("--strict", action="store_true", help="Enable strict mode")

    tf = validate_subparsers.add_parser("terraform", aliases=["tf"], help="Validate Terraform configurations")
    tf.add_argument("path", help="File or directory to validate")

    dockerfile = validate_subparsers.add_parser("dockerfile", help="Validate Dockerfile")
    dockerfile.add_argument("path", help="Dockerfile or directory to validate")

    add_performance_flags(validate_parser)


def _add_scaffold_commands(subparsers: argparse._SubParsersAction) -> None:
    """Add scaffold subcommands."""
    scaffold_parser = subparsers.add_parser("scaffold", help="Project scaffolding")
    scaffold_subparsers = scaffold_parser.add_subparsers(dest="scaffold_command", help="Scaffold commands")

    microservice = scaffold_subparsers.add_parser("microservice", help="Scaffold a microservice")
    microservice.add_argument("name", help="Service name")
    microservice.add_argument(
        "--language",
        choices=[l.value for l in Language],
        default="python",
        help="Programming language",
    )
    microservice.add_argument(
        "--framework",
        choices=[f.value for f in Framework],
        default="fastapi",
        help="Framework to use",
    )
    microservice.add_argument("--port", type=int, default=8080, help="Service port")
    microservice.add_argument("--description", default="", help="Service description")
    microservice.add_argument("--output-dir", default=".", help="Output directory")

    monorepo = scaffold_subparsers.add_parser("monorepo", help="Scaffold a monorepo")
    monorepo.add_argument("name", help="Project name")
    monorepo.add_argument("--services", nargs="+", help="Service names to include")
    monorepo.add_argument(
        "--language",
        choices=[l.value for l in Language],
        default="python",
        help="Primary language",
    )
    monorepo.add_argument("--description", default="", help="Project description")
    monorepo.add_argument("--output-dir", default=".", help="Output directory")

    add_performance_flags(scaffold_parser)


# Command handlers
def run_kubernetes_generate(args: argparse.Namespace) -> int:
    """Execute Kubernetes manifest generation."""
    config = ManifestConfig(
        name=args.name,
        namespace=args.namespace,
        workload_type=WorkloadType(args.type),
        image=args.image,
        replicas=args.replicas,
        environment=EnvironmentType(args.environment),
        security_profile=SecurityProfile(args.security_profile),
        ports=[PortConfig(container_port=args.port)],
    )

    generator = ManifestGenerator(output_dir=args.output_dir)
    manifest = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(manifest, args.output_dir)
        print(f"\nManifest generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate manifest:")
        print(manifest.yaml_content[:500] + "..." if len(manifest.yaml_content) > 500 else manifest.yaml_content)

    print(f"Best Practice Score: {manifest.best_practice_score:.1f}/100")

    if manifest.validation_results:
        print("\nValidation Issues:")
        for issue in manifest.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_terraform_generate(args: argparse.Namespace) -> int:
    """Execute Terraform module generation."""
    variables = []
    outputs = []
    resources = []
    data_sources = []

    if args.provider == "aws":
        if args.category == "compute":
            variables.extend([
                VariableConfig(name="instance_type", type="string", description="EC2 instance type", default="t3.micro"),
                VariableConfig(name="instance_name", type="string", description="Name for the EC2 instance"),
            ])
            resources.append("aws_instance")
            data_sources.extend(["aws_ami", "aws_vpc", "aws_subnets"])
            outputs.extend([
                OutputConfig(name="instance_id", description="The ID of the EC2 instance", value="aws_instance.main.id"),
                OutputConfig(name="instance_arn", description="The ARN of the EC2 instance", value="aws_instance.main.arn"),
            ])
        elif args.category == "storage":
            variables.append(VariableConfig(name="bucket_name", type="string", description="Name of the S3 bucket"))
            resources.append("aws_s3_bucket")
            outputs.extend([
                OutputConfig(name="bucket_id", description="The ID of the S3 bucket", value="aws_s3_bucket.main.id"),
                OutputConfig(name="bucket_arn", description="The ARN of the S3 bucket", value="aws_s3_bucket.main.arn"),
            ])

    config = ModuleConfig(
        name=args.name,
        provider=CloudProvider(args.provider),
        category=ResourceCategory(args.category),
        complexity=ModuleComplexity(args.complexity),
        description=args.description or f"Terraform module for {args.category} resources on {args.provider}",
        variables=variables,
        outputs=outputs,
        resources=resources,
        data_sources=data_sources,
        tags={"ManagedBy": "Terraform", "Module": args.name},
    )

    builder = ModuleBuilder(output_dir=args.output_dir)
    module = builder.generate(config)

    if not args.dry_run:
        module_dir = builder.save_to_directory(module, args.output_dir)
        print(f"\nModule generated successfully!")
        print(f"Directory: {module_dir}")
    else:
        print("\n[DRY RUN] Would generate module with files:")
        for filename in module.module_files.keys():
            print(f"  - {filename}")

    print(f"Files: {module.file_count}")
    print(f"Best Practice Score: {module.best_practice_score:.1f}/100")

    if module.validation_results:
        print("\nValidation Issues:")
        for issue in module.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_docker_dockerfile(args: argparse.Namespace) -> int:
    """Execute Dockerfile generation."""
    stages = []

    if args.multi_stage:
        stages.append(BuildStage(
            name="builder",
            base_image=args.base,
            workdir=args.workdir,
            copy_commands=[{"src": "requirements.txt", "dst": "."}],
            run_commands=["pip install --no-cache-dir -r requirements.txt"],
        ))
        stages.append(BuildStage(
            name="runtime",
            base_image=args.base.replace(":latest", "-slim") if ":latest" in args.base else args.base,
            workdir=args.workdir,
            user=args.user,
            copy_from="builder",
            copy_src="/usr/local/lib/python",
            copy_dst="/usr/local/lib/python",
            copy_commands=[{"src": ".", "dst": ".", "chown": f"{args.user}:{args.user}"}],
            expose_ports=[args.port],
            cmd=["python", "main.py"],
        ))
    else:
        stages.append(BuildStage(
            name="",
            base_image=args.base,
            workdir=args.workdir,
            user=args.user,
            copy_commands=[{"src": ".", "dst": "."}],
            run_commands=[
                "adduser --disabled-password --gecos '' " + args.user,
                "chown -R " + args.user + ":" + args.user + " " + args.workdir,
            ],
            expose_ports=[args.port],
            cmd=["python", "main.py"],
        ))

    config = DockerfileConfig(
        name=args.name,
        stages=stages,
        labels={
            "org.opencontainers.image.title": args.name,
            "org.opencontainers.image.source": "https://github.com/your-org/your-repo",
        },
        healthcheck={
            "test": ["CMD", "curl", "-f", f"http://localhost:{args.port}/health"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 3,
        },
    )

    generator = DockerfileGenerator(output_dir=args.output_dir)
    docker_config = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(docker_config, args.output_dir)
        print(f"\nDockerfile generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate Dockerfile")

    print(f"Best Practice Score: {docker_config.best_practice_score:.1f}/100")

    if docker_config.validation_results:
        print("\nValidation Issues:")
        for issue in docker_config.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_docker_compose(args: argparse.Namespace) -> int:
    """Execute docker-compose.yml generation."""
    services = []
    for svc_name in args.services:
        services.append(ComposeServiceConfig(
            name=svc_name,
            build={"context": f"./{svc_name}", "dockerfile": "Dockerfile"},
            ports=[f"8080:8080"],
            restart="unless-stopped",
            healthcheck={
                "test": ["CMD", "curl", "-f", "http://localhost:8080/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
        ))

    config = ComposeConfig(services=services)

    generator = ComposeGenerator(output_dir=args.output_dir)
    compose_config = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(compose_config, args.output_dir)
        print(f"\ndocker-compose.yml generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate docker-compose.yml")

    print(f"Best Practice Score: {compose_config.best_practice_score:.1f}/100")

    if compose_config.validation_results:
        print("\nValidation Issues:")
        for issue in compose_config.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_cicd_generate(args: argparse.Namespace) -> int:
    """Execute CI/CD pipeline generation."""
    triggers = [
        TriggerConfig(type=TriggerType.PUSH, branches=[args.branch]),
        TriggerConfig(type=TriggerType.PULL_REQUEST, branches=[args.branch]),
    ]

    stages = [
        PipelineStage(
            name="build",
            runs_on="ubuntu-latest",
            steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(name="Setup Python", uses="actions/setup-python@v5", with_params={"python-version": "3.12"}),
                StepConfig(name="Install dependencies", run="pip install -r requirements.txt"),
                StepConfig(name="Run tests", run="pytest"),
            ],
        ),
    ]

    if args.docker_image:
        stages.append(PipelineStage(
            name="docker",
            runs_on="ubuntu-latest",
            needs=["build"],
            steps=[
                StepConfig(name="Checkout", uses="actions/checkout@v4"),
                StepConfig(
                    name="Build and push",
                    uses="docker/build-push-action@v5",
                    with_params={
                        "push": True,
                        "tags": args.docker_image,
                    },
                ),
            ],
        ))

    config = PipelineConfig(
        name=args.name,
        platform=CICDPlatform(args.platform),
        triggers=triggers,
        stages=stages,
        concurrency={"group": "${{ github.workflow }}-${{ github.ref }}", "cancel-in-progress": True},
    )

    generator = PipelineGenerator(output_dir=args.output_dir)
    pipeline = generator.generate(config)

    if not args.dry_run:
        file_path = generator.save_to_file(pipeline, args.output_dir)
        print(f"\nPipeline generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate pipeline")

    print(f"Platform: {pipeline.platform.value}")
    print(f"Best Practice Score: {pipeline.best_practice_score:.1f}/100")

    if pipeline.validation_results:
        print("\nValidation Issues:")
        for issue in pipeline.validation_results:
            print(f"  - {issue}")
    else:
        print("\nNo validation issues found!")

    return 0


def run_helm_init(args: argparse.Namespace) -> int:
    """Initialize a new Helm chart."""
    chart = HelmChart(
        name=args.name,
        version=args.version,
        app_version=args.app_version,
        description=args.description or f"A Helm chart for {args.name}",
    )

    values = HelmValues(
        image_repository=args.image,
        image_tag=args.app_version,
    )

    config = HelmConfig(chart=chart, values=values)
    generator = ChartGenerator(output_dir=args.output_dir)
    result = generator.generate(config)

    if not args.dry_run:
        chart_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nHelm chart initialized successfully!")
        print(f"Directory: {chart_dir}")
    else:
        print("\n[DRY RUN] Would generate Helm chart with files:")
        for filename in result.chart_files.keys():
            print(f"  - {filename}")

    print(f"Files: {result.file_count}")
    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_helm_values(args: argparse.Namespace) -> int:
    """Generate values.yaml for an environment."""
    generator = ValuesGenerator(output_dir=args.output_dir)
    values_yaml = generator.generate_yaml(
        image_repository=args.image,
        environment=args.environment,
    )

    if not args.dry_run:
        output_file = Path(args.output_dir) / f"values-{args.environment}.yaml"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(values_yaml)
        print(f"\nValues file generated successfully!")
        print(f"File: {output_file}")
    else:
        print("\n[DRY RUN] Would generate values.yaml:")
        print(values_yaml[:500] + "..." if len(values_yaml) > 500 else values_yaml)

    return 0


def run_kustomize_init(args: argparse.Namespace) -> int:
    """Initialize Kustomize base."""
    base = KustomizeBase(name=args.name, namespace=args.namespace)
    config = KustomizeConfig(
        base=base,
        image=args.image,
        container_port=args.port,
    )

    generator = BaseGenerator(output_dir=args.output_dir)
    result = generator.generate(config)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nKustomize base initialized successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate Kustomize base with files:")
        for filename in result.files.keys():
            print(f"  - {filename}")

    print(f"Files: {result.file_count}")
    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_kustomize_overlay(args: argparse.Namespace) -> int:
    """Generate Kustomize overlay."""
    overlay = KustomizeOverlay(
        name=args.env,
        bases=[args.base],
        namespace=args.namespace,
    )

    generator = OverlayGenerator(output_dir=args.output_dir)
    result = generator.generate(overlay, base_path=args.base)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nKustomize overlay generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate overlay with files:")
        for filename in result.files.keys():
            print(f"  - {filename}")

    print(f"Files: {result.file_count}")
    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_argocd_app(args: argparse.Namespace) -> int:
    """Generate ArgoCD Application manifest."""
    generator = ArgoCDGenerator(output_dir=args.output_dir)
    result = generator.generate_from_repo(
        name=args.name,
        repo_url=args.repo,
        path=args.path,
        target_namespace=args.namespace,
        target_revision=args.revision,
        project=args.project,
        automated=args.auto_sync,
    )

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nArgoCD Application generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate ArgoCD Application:")
        for filename, content in result.files.items():
            print(f"\n--- {filename} ---")
            print(content[:500] + "..." if len(content) > 500 else content)

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_flux_source(args: argparse.Namespace) -> int:
    """Generate Flux GitRepository."""
    git_repo = FluxGitRepository(
        name=args.name,
        url=args.repo,
        branch=args.branch,
        interval=args.interval,
    )

    generator = FluxGenerator(output_dir=args.output_dir)
    result = generator.generate_git_repository(git_repo)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nFlux GitRepository generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate Flux GitRepository")

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_flux_kustomization(args: argparse.Namespace) -> int:
    """Generate Flux Kustomization."""
    ks = FluxKustomization(
        name=args.name,
        source_ref_name=args.source,
        path=args.path,
        target_namespace=args.namespace,
        interval=args.interval,
    )

    generator = FluxGenerator(output_dir=args.output_dir)
    result = generator.generate_kustomization(ks)

    if not args.dry_run:
        output_dir = generator.save_to_directory(result, args.output_dir)
        print(f"\nFlux Kustomization generated successfully!")
        print(f"Directory: {output_dir}")
    else:
        print("\n[DRY RUN] Would generate Flux Kustomization")

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_compose_generate(args: argparse.Namespace) -> int:
    """Generate docker-compose.yaml."""
    services = []
    if args.services:
        for svc_def in args.services:
            parts = svc_def.split(":")
            name = parts[0]
            image = parts[1] if len(parts) > 1 else f"{name}:latest"
            port = int(parts[2]) if len(parts) > 2 else 8080

            services.append(ComposeService(
                name=name,
                image=image,
                ports=[f"{port}:{port}"],
                healthcheck=HealthCheckConfig(
                    test=["CMD", "curl", "-f", f"http://localhost:{port}/health"],
                ),
            ))
    else:
        services.append(ComposeService(
            name=args.name,
            build={"context": ".", "dockerfile": "Dockerfile"},
            ports=["8080:8080"],
        ))

    project = ComposeProject(name=args.name, services=services)
    generator = ComposeProjectGenerator(output_dir=args.output_dir)
    result = generator.generate_with_override(project, args.environment)

    if not args.dry_run:
        file_path = generator.save_to_file(result, args.output_dir)
        print(f"\ndocker-compose.yaml generated successfully!")
        print(f"File: {file_path}")
    else:
        print("\n[DRY RUN] Would generate docker-compose.yaml")

    print(f"Best Practice Score: {result.best_practice_score:.1f}/100")

    return 0


def run_compose_validate(args: argparse.Namespace) -> int:
    """Validate docker-compose.yaml."""
    validator = ComposeValidator()
    report = validator.validate_file(args.file)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    return 0 if not report.error_count else 1


def run_validate_kubernetes(args: argparse.Namespace) -> int:
    """Validate Kubernetes manifests."""
    context = ValidationContext(strict_mode=args.strict) if hasattr(args, 'strict') else None
    validator = KubernetesValidator(context=context)

    path = Path(args.path)
    if path.is_file():
        report = validator.validate_file(args.path)
    else:
        report = validator.validate_directory(args.path)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    print(f"\nValidation Score: {report.score:.1f}/100")
    print(f"Files validated: {report.total_files}")

    return 0 if report.passed else 1


def run_validate_terraform(args: argparse.Namespace) -> int:
    """Validate Terraform configurations."""
    validator = TerraformValidator()

    path = Path(args.path)
    if path.is_file():
        report = validator.validate_file(args.path)
    else:
        report = validator.validate_directory(args.path)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    print(f"\nValidation Score: {report.score:.1f}/100")

    return 0 if report.passed else 1


def run_validate_dockerfile(args: argparse.Namespace) -> int:
    """Validate Dockerfile."""
    validator = DockerfileValidator()

    path = Path(args.path)
    if path.is_file():
        report = validator.validate_file(args.path)
    else:
        report = validator.validate_directory(args.path)

    formatter = UnifiedFormatter(OutputFormat.TEXT)
    print(formatter.format_report(report))

    print(f"\nValidation Score: {report.score:.1f}/100")

    return 0 if report.passed else 1


def run_scaffold_microservice(args: argparse.Namespace) -> int:
    """Scaffold a microservice."""
    config = ServiceConfig(
        name=args.name,
        description=args.description or f"A {args.language} microservice",
        language=Language(args.language),
        framework=Framework(args.framework),
        port=args.port,
    )

    scaffold = MicroserviceScaffold(output_dir=args.output_dir)
    report = scaffold.generate(config)

    if not args.dry_run:
        output_path = scaffold.save_to_directory(report, args.output_dir)
        print(f"\nMicroservice scaffolded successfully!")
        print(f"Directory: {output_path}")
    else:
        print("\n[DRY RUN] Would create files:")
        for f in report.files[:10]:
            print(f"  - {f.path}")
        if len(report.files) > 10:
            print(f"  ... and {len(report.files) - 10} more files")

    print(f"\nTotal files: {report.file_count}")
    print(f"Total directories: {report.total_directories}")

    if report.next_steps:
        print("\nNext steps:")
        for step in report.next_steps:
            if step:
                print(f"  {step}")

    return 0


def run_scaffold_monorepo(args: argparse.Namespace) -> int:
    """Scaffold a monorepo."""
    services = []
    if args.services:
        for svc_name in args.services:
            services.append(ServiceConfig(
                name=svc_name,
                language=Language(args.language),
                framework=Framework.FASTAPI if args.language == "python" else Framework.EXPRESS,
            ))

    config = ProjectConfig(
        name=args.name,
        description=args.description or f"A {args.language} monorepo",
        services=services,
        monorepo=True,
    )

    scaffold = MonorepoScaffold(output_dir=args.output_dir)
    report = scaffold.generate(config)

    if not args.dry_run:
        output_path = scaffold.save_to_directory(report, args.output_dir)
        print(f"\nMonorepo scaffolded successfully!")
        print(f"Directory: {output_path}")
    else:
        print("\n[DRY RUN] Would create structure with:")
        print(f"  - {len(report.directories)} directories")
        print(f"  - {len(report.files)} files")

    print(f"\nTotal files: {report.file_count}")
    print(f"Total directories: {report.total_directories}")

    if report.next_steps:
        print("\nNext steps:")
        for step in report.next_steps:
            if step:
                print(f"  {step}")

    return 0


def main(args=None) -> int:
    """Main entry point.

    Args:
        args: Optional list of arguments. If None, uses sys.argv.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Handle global flags
    if hasattr(parsed_args, 'output') and parsed_args.output:
        if hasattr(parsed_args, 'output_dir'):
            parsed_args.output_dir = parsed_args.output

    if hasattr(parsed_args, 'dry_run'):
        pass  # dry_run is handled in individual commands

    if parsed_args.command is None:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate handler
    if parsed_args.command in ("kubernetes", "k8s"):
        if not hasattr(parsed_args, "k8s_command") or parsed_args.k8s_command is None:
            print("Error: Please specify a kubernetes command (e.g., 'generate')")
            sys.exit(1)
        if parsed_args.k8s_command == "generate":
            sys.exit(run_kubernetes_generate(parsed_args))

    elif parsed_args.command in ("terraform", "tf"):
        if not hasattr(parsed_args, "tf_command") or parsed_args.tf_command is None:
            print("Error: Please specify a terraform command (e.g., 'generate')")
            sys.exit(1)
        if parsed_args.tf_command == "generate":
            sys.exit(run_terraform_generate(parsed_args))

    elif parsed_args.command == "docker":
        if not hasattr(parsed_args, "docker_command") or parsed_args.docker_command is None:
            print("Error: Please specify a docker command (e.g., 'dockerfile', 'compose')")
            sys.exit(1)
        if parsed_args.docker_command == "dockerfile":
            sys.exit(run_docker_dockerfile(parsed_args))
        elif parsed_args.docker_command == "compose":
            sys.exit(run_docker_compose(parsed_args))

    elif parsed_args.command == "cicd":
        if not hasattr(parsed_args, "cicd_command") or parsed_args.cicd_command is None:
            print("Error: Please specify a cicd command (e.g., 'generate')")
            sys.exit(1)
        if parsed_args.cicd_command == "generate":
            sys.exit(run_cicd_generate(parsed_args))

    elif parsed_args.command == "helm":
        if not hasattr(parsed_args, "helm_command") or parsed_args.helm_command is None:
            print("Error: Please specify a helm command (e.g., 'init', 'values')")
            sys.exit(1)
        if parsed_args.helm_command == "init":
            sys.exit(run_helm_init(parsed_args))
        elif parsed_args.helm_command == "values":
            sys.exit(run_helm_values(parsed_args))

    elif parsed_args.command == "kustomize":
        if not hasattr(parsed_args, "kustomize_command") or parsed_args.kustomize_command is None:
            print("Error: Please specify a kustomize command (e.g., 'init', 'overlay')")
            sys.exit(1)
        if parsed_args.kustomize_command == "init":
            sys.exit(run_kustomize_init(parsed_args))
        elif parsed_args.kustomize_command == "overlay":
            sys.exit(run_kustomize_overlay(parsed_args))

    elif parsed_args.command == "argocd":
        if not hasattr(parsed_args, "argocd_command") or parsed_args.argocd_command is None:
            print("Error: Please specify an argocd command (e.g., 'app')")
            sys.exit(1)
        if parsed_args.argocd_command == "app":
            sys.exit(run_argocd_app(parsed_args))

    elif parsed_args.command == "flux":
        if not hasattr(parsed_args, "flux_command") or parsed_args.flux_command is None:
            print("Error: Please specify a flux command (e.g., 'source', 'kustomization')")
            sys.exit(1)
        if parsed_args.flux_command == "source":
            sys.exit(run_flux_source(parsed_args))
        elif parsed_args.flux_command == "kustomization":
            sys.exit(run_flux_kustomization(parsed_args))

    elif parsed_args.command == "compose":
        if not hasattr(parsed_args, "compose_command") or parsed_args.compose_command is None:
            print("Error: Please specify a compose command (e.g., 'generate', 'validate')")
            sys.exit(1)
        if parsed_args.compose_command == "generate":
            sys.exit(run_compose_generate(parsed_args))
        elif parsed_args.compose_command == "validate":
            sys.exit(run_compose_validate(parsed_args))

    elif parsed_args.command == "validate":
        if not hasattr(parsed_args, "validate_command") or parsed_args.validate_command is None:
            print("Error: Please specify a validate command (e.g., 'kubernetes', 'terraform', 'dockerfile')")
            sys.exit(1)
        if parsed_args.validate_command in ("kubernetes", "k8s"):
            sys.exit(run_validate_kubernetes(parsed_args))
        elif parsed_args.validate_command in ("terraform", "tf"):
            sys.exit(run_validate_terraform(parsed_args))
        elif parsed_args.validate_command == "dockerfile":
            sys.exit(run_validate_dockerfile(parsed_args))

    elif parsed_args.command == "scaffold":
        if not hasattr(parsed_args, "scaffold_command") or parsed_args.scaffold_command is None:
            print("Error: Please specify a scaffold command (e.g., 'microservice', 'monorepo')")
            sys.exit(1)
        if parsed_args.scaffold_command == "microservice":
            sys.exit(run_scaffold_microservice(parsed_args))
        elif parsed_args.scaffold_command == "monorepo":
            sys.exit(run_scaffold_monorepo(parsed_args))

    else:
        print(f"Unknown command: {parsed_args.command}")
        sys.exit(1)

    return 0


if __name__ == "__main__":
    main()
