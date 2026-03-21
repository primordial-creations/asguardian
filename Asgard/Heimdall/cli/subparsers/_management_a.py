"""
Heimdall CLI - Management subparser setup (part A).

Covers: baseline, init-linter, ratings, gate, profiles.
"""

import argparse

from Asgard.Heimdall.cli.common import (
    add_baseline_args,
    add_ratings_args,
    add_gate_args,
    add_profiles_args,
    add_profile_assign_args,
    add_profile_show_args,
    add_profile_create_args,
)


def setup_baseline_commands(subparsers) -> None:
    """Set up baseline command group."""
    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Manage the baseline of known/accepted violations (show, list, clean, remove)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall baseline show ./src\n"
            "  heimdall baseline list ./src --type env-fallback\n"
            "  heimdall baseline list ./src --file services/auth.py\n"
            "  heimdall baseline remove ./src --id abc-1234\n"
            "  heimdall baseline clean ./src\n"
        ),
    )
    baseline_subparsers = baseline_parser.add_subparsers(
        dest="baseline_command",
        help="Baseline subcommand to run",
    )

    baseline_show = baseline_subparsers.add_parser(
        "show",
        help="Display a summary report of all baselined violations and their status",
    )
    add_baseline_args(baseline_show)

    baseline_list = baseline_subparsers.add_parser(
        "list",
        help="List baseline entries, optionally filtered by violation type or file path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall baseline list ./src\n"
            "  heimdall baseline list ./src --type env-fallback\n"
            "  heimdall baseline list ./src --file services/auth.py\n"
            "  heimdall baseline list ./src --format json\n"
        ),
    )
    add_baseline_args(baseline_list)

    baseline_clean = baseline_subparsers.add_parser(
        "clean",
        help="Remove baseline entries that have expired based on their configured TTL",
    )
    add_baseline_args(baseline_clean)

    baseline_remove = baseline_subparsers.add_parser(
        "remove",
        help="Remove a single baseline entry by its violation ID (requires --id)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall baseline remove ./src --id abc-1234\n"
            "  heimdall baseline remove ./src --id abc-1234 --baseline-file .asgard-baseline.json\n"
        ),
    )
    add_baseline_args(baseline_remove)


def setup_init_linter_command(subparsers) -> None:
    """Set up the init-linter command."""
    init_linter_parser = subparsers.add_parser(
        "init-linter",
        help="Generate linting configuration files for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Generate linting configuration files based on GAIA coding standards.\n"
            "Auto-detects the project type (Python, TypeScript, or both) and creates\n"
            "the appropriate config files (ruff, mypy, eslint, prettier, pre-commit, etc.)."
        ),
        epilog=(
            "Examples:\n"
            "  heimdall init-linter .                         # Auto-detect and init in current dir\n"
            "  heimdall init-linter ./my-project               # Init in a specific directory\n"
            "  heimdall init-linter . --type python             # Force Python configs only\n"
            "  heimdall init-linter . --type typescript         # Force TypeScript configs only\n"
            "  heimdall init-linter . --type both               # Generate configs for both\n"
            "  heimdall init-linter . --name my-package         # Set the project/package name\n"
            "  heimdall init-linter . --force                   # Overwrite existing config files\n"
        ),
    )
    init_linter_parser.add_argument(
        "path",
        help="Project directory to initialize linting configs in",
    )
    init_linter_parser.add_argument(
        "--type",
        choices=["python", "typescript", "both"],
        default=None,
        dest="project_type",
        help="Force project type instead of auto-detecting (default: auto-detect)",
    )
    init_linter_parser.add_argument(
        "--name",
        default=None,
        dest="project_name",
        help="Project/package name for config templates (default: directory name)",
    )
    init_linter_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration files",
    )


def setup_ratings_command(subparsers) -> None:
    """Set up the ratings top-level command."""
    ratings_parser = subparsers.add_parser(
        "ratings",
        help="Calculate A-E quality ratings for maintainability, reliability, and security",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall ratings ./src\n"
            "  heimdall ratings ./src --format json\n"
            "  heimdall ratings ./src --format markdown\n"
        ),
    )
    add_ratings_args(ratings_parser)


def setup_gate_command(subparsers) -> None:
    """Set up the gate top-level command."""
    gate_parser = subparsers.add_parser(
        "gate",
        help="Evaluate the quality gate (Asgard Way) against analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall gate ./src\n"
            "  heimdall gate ./src --gate asgard-way\n"
            "  heimdall gate ./src --format json\n"
        ),
    )
    add_gate_args(gate_parser)


def setup_profiles_commands(subparsers) -> None:
    """Set up the profiles command group."""
    profiles_parser = subparsers.add_parser(
        "profiles",
        help="Manage quality profiles (rule sets assigned to projects)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles list\n"
            "  heimdall profiles show 'Asgard Way - Python'\n"
            "  heimdall profiles assign ./src 'Asgard Way - Strict'\n"
            "  heimdall profiles create MyProfile --parent 'Asgard Way - Python'\n"
            "  heimdall profiles create MyProfile --from-file my_profile.json\n"
        ),
    )
    profiles_subparsers = profiles_parser.add_subparsers(
        dest="profiles_command",
        help="Profiles subcommand to run",
    )

    profiles_list = profiles_subparsers.add_parser(
        "list",
        help="List all available quality profiles (built-in and user-defined)",
    )
    add_profiles_args(profiles_list)

    profiles_show = profiles_subparsers.add_parser(
        "show",
        help="Show all rules in a profile with inheritance fully resolved",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles show 'Asgard Way - Python'\n"
            "  heimdall profiles show 'Asgard Way - Strict' --format json\n"
        ),
    )
    add_profile_show_args(profiles_show)

    profiles_assign = profiles_subparsers.add_parser(
        "assign",
        help="Assign a quality profile to a project path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles assign ./src 'Asgard Way - Python'\n"
            "  heimdall profiles assign /abs/path/to/project 'Asgard Way - Strict'\n"
        ),
    )
    add_profile_assign_args(profiles_assign)

    profiles_create = profiles_subparsers.add_parser(
        "create",
        help="Create a new custom quality profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles create MyProfile --parent 'Asgard Way - Python'\n"
            "  heimdall profiles create MyProfile --from-file my_profile.json\n"
            "  heimdall profiles create MyProfile --language python --description 'My team profile'\n"
        ),
    )
    add_profile_create_args(profiles_create)
