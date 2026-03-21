import argparse

from Asgard.Volundr.Kubernetes import WorkloadType, SecurityProfile, EnvironmentType
from Asgard.Volundr.Terraform import CloudProvider, ResourceCategory, ModuleComplexity
from Asgard.Volundr.CICD import CICDPlatform
from Asgard.Volundr.cli._parser_flags import add_performance_flags


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
