import argparse


def add_profiles_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the profiles command group."""
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_profile_assign_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'profiles assign' subcommand."""
    parser.add_argument(
        "project_path",
        type=str,
        help="Absolute or relative path to the project root",
    )
    parser.add_argument(
        "profile_name",
        type=str,
        help="Name of the quality profile to assign",
    )


def add_profile_show_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'profiles show' subcommand."""
    parser.add_argument(
        "name",
        type=str,
        help="Name of the quality profile to display",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_profile_create_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the 'profiles create' subcommand."""
    parser.add_argument(
        "name",
        type=str,
        help="Name for the new quality profile",
    )
    parser.add_argument(
        "--parent",
        type=str,
        default=None,
        help="Name of the parent profile to inherit from",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="python",
        help="Target language for this profile (default: python)",
    )
    parser.add_argument(
        "--from-file",
        type=str,
        default=None,
        dest="from_file",
        help="Create the profile from a JSON file instead of prompting interactively",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Human-readable description of the profile",
    )


def add_history_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the history subcommands."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path of the project to show history for (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of snapshots to display (default: 10)",
    )


def add_new_code_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the new-code detect subcommand."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path of the project to analyse (default: current directory)",
    )
    parser.add_argument(
        "--since-date",
        type=str,
        default=None,
        help="Detect code changed since this date (YYYY-MM-DD format)",
    )
    parser.add_argument(
        "--since-branch",
        type=str,
        default=None,
        help="Detect code added since diverging from this branch",
    )
    parser.add_argument(
        "--since-version",
        type=str,
        default=None,
        help="Detect code changed since this tagged version",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
