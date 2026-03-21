import argparse

from Asgard.Volundr.cli._parser_flags import add_performance_flags
from Asgard.Volundr.cli._parser_commands_1 import (
    _add_kubernetes_commands,
    _add_terraform_commands,
    _add_docker_commands,
    _add_cicd_commands,
)
from Asgard.Volundr.cli._parser_commands_2 import (
    _add_helm_commands,
    _add_kustomize_commands,
    _add_argocd_commands,
    _add_flux_commands,
    _add_compose_commands,
    _add_validate_commands,
    _add_scaffold_commands,
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
