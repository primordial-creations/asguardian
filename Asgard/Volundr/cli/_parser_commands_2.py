import argparse

from Asgard.Volundr.Scaffold import Language, Framework
from Asgard.Volundr.cli._parser_flags import add_performance_flags


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
