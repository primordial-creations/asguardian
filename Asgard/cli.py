"""
Asgard CLI - Unified command-line interface for development tools.

Usage:
    asguardian <module> [command] [options]
    asguardian init [--format yaml|toml|json]
    asguardian init-backend <folder_name>
    asguardian setup-hooks [--pre-push] [--vscode] [--path <dir>]
    asguardian heimdall analyze <path>
    asguardian freya crawl <url>
    asguardian forseti validate <spec>
    asguardian verdandi metrics <path>
    asguardian volundr generate <type>
"""

import argparse
import sys
from typing import Optional, cast

from Asgard.Forseti.cli import main as forseti_main
from Asgard.Freya.cli import main as freya_main
from Asgard.Heimdall.cli import main as heimdall_main
from Asgard.Verdandi.cli import main as verdandi_main
from Asgard.Volundr.cli import main as volundr_main
from Asgard._cli_handlers import (
    COMPREHENSIVE_HELP,
    handle_init,
    handle_init_backend,
    handle_install_browsers,
    handle_setup_hooks,
)


def main(args: Optional[list] = None) -> int:
    """Main entry point for the Asgard CLI."""
    parser = argparse.ArgumentParser(
        prog="asguardian",
        description="Asgard - Universal Development Tools Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Subcommands:
  init              Initialize Asgard configuration file
  init-backend      Scaffold a standard backend project structure
  setup-hooks       Install pre-commit git hooks (add --vscode for editor config)
  install-browsers  Install Playwright browsers for Freya
  heimdall          Code quality control and static analysis
  freya             Visual and UI testing
  forseti           API and schema specification
  verdandi          Runtime performance metrics
  volundr           Infrastructure generation

Examples:
  asguardian init --format yaml
  asguardian init-backend my_service
  asguardian setup-hooks --pre-push --vscode  # Hooks + VS Code config
  asguardian install-browsers              # Required once for Freya
  asguardian heimdall analyze ./src
  asguardian freya crawl http://localhost:3000
  asguardian forseti validate openapi.yaml
  asguardian verdandi report ./metrics
  asguardian volundr generate kubernetes --name myapp
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    parser.add_argument(
        "--help-all",
        action="store_true",
        help="Show comprehensive help for all modules and commands",
    )

    subparsers = parser.add_subparsers(
        dest="module",
        title="modules",
        description="Available Asgard modules",
    )

    # Init subcommand
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize Asgard configuration file",
        description="Generate a default Asgard configuration file",
    )
    init_parser.add_argument(
        "--format",
        choices=["yaml", "toml", "json"],
        default="yaml",
        help="Configuration file format (default: yaml)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration file",
    )

    # Init-backend subcommand
    init_backend_parser = subparsers.add_parser(
        "init-backend",
        help="Scaffold a standard backend project structure",
        description=(
            "Create a new backend project directory with a standard layout: "
            "apis, models, services, prompts, tests, utilities, and supporting files."
        ),
    )
    init_backend_parser.add_argument(
        "folder_name",
        help="Name of the folder to create (or populate if it already exists)",
    )

    # Setup-hooks subcommand
    hooks_parser = subparsers.add_parser(
        "setup-hooks",
        help="Install pre-commit git hooks and (optionally) configure VS Code",
        description=(
            "Install pre-commit as a git commit hook so that linting, formatting, "
            "and type checks run automatically before code reaches a reviewer. "
            "Use --pre-push to also run checks on git push, and --vscode to write "
            ".vscode/settings.json and .vscode/extensions.json with matching editor config."
        ),
    )
    hooks_parser.add_argument(
        "--pre-push",
        action="store_true",
        dest="pre_push",
        help="Also install a pre-push hook (runs checks before git push)",
    )
    hooks_parser.add_argument(
        "--vscode",
        action="store_true",
        help="Write .vscode/settings.json and extensions.json for matching editor config",
    )
    hooks_parser.add_argument(
        "--path",
        default=".",
        metavar="DIR",
        help="Project root directory (default: current directory)",
    )

    # Install-browsers subcommand
    browsers_parser = subparsers.add_parser(
        "install-browsers",
        help="Install Playwright browsers for Freya",
        description="Download and install browser binaries required for Freya's visual testing",
    )
    browsers_parser.add_argument(
        "browsers",
        nargs="*",
        default=["chromium"],
        help="Browsers to install (default: chromium). Options: chromium, firefox, webkit",
    )

    # Heimdall subcommand
    heimdall_parser = subparsers.add_parser(
        "heimdall",
        help="Code quality control and static analysis",
        description="Heimdall - The watchman who guards code quality",
    )
    heimdall_parser.add_argument(
        "heimdall_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to heimdall",
    )

    # Freya subcommand
    freya_parser = subparsers.add_parser(
        "freya",
        help="Visual and UI testing",
        description="Freya - The goddess of beauty who ensures UI quality",
    )
    freya_parser.add_argument(
        "freya_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to freya",
    )

    # Forseti subcommand
    forseti_parser = subparsers.add_parser(
        "forseti",
        help="API and schema specification",
        description="Forseti - The god of justice who validates contracts",
    )
    forseti_parser.add_argument(
        "forseti_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to forseti",
    )

    # Verdandi subcommand
    verdandi_parser = subparsers.add_parser(
        "verdandi",
        help="Runtime performance metrics",
        description="Verdandi - The Norn who measures the present",
    )
    verdandi_parser.add_argument(
        "verdandi_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to verdandi",
    )

    # Volundr subcommand
    volundr_parser = subparsers.add_parser(
        "volundr",
        help="Infrastructure generation",
        description="Volundr - The master smith who forges infrastructure",
    )
    volundr_parser.add_argument(
        "volundr_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to volundr",
    )

    parsed_args = parser.parse_args(args)

    # Handle --help-all before anything else
    if getattr(parsed_args, "help_all", False):
        print(COMPREHENSIVE_HELP)
        return 0

    if parsed_args.module is None:
        parser.print_help()
        return 0

    # Handle init command directly
    if parsed_args.module == "init":
        return handle_init(parsed_args)

    # Handle init-backend command
    if parsed_args.module == "init-backend":
        return handle_init_backend(parsed_args)

    # Handle setup-hooks command
    if parsed_args.module == "setup-hooks":
        return handle_setup_hooks(parsed_args)

    # Handle install-browsers command
    if parsed_args.module == "install-browsers":
        return handle_install_browsers(parsed_args)

    # Dispatch to the appropriate module CLI
    if parsed_args.module == "heimdall":
        return cast(int, heimdall_main(parsed_args.heimdall_args))

    elif parsed_args.module == "freya":
        return cast(int, freya_main(parsed_args.freya_args))

    elif parsed_args.module == "forseti":
        return cast(int, forseti_main(parsed_args.forseti_args))

    elif parsed_args.module == "verdandi":
        return cast(int, verdandi_main(parsed_args.verdandi_args))

    elif parsed_args.module == "volundr":
        return cast(int, volundr_main(parsed_args.volundr_args))

    return 0


if __name__ == "__main__":
    sys.exit(main())
