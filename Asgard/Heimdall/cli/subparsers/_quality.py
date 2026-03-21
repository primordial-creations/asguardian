"""
Heimdall CLI - Quality subparser setup.
"""

import argparse

from Asgard.Heimdall.cli.subparsers._quality_core import register_quality_core_subcommands
from Asgard.Heimdall.cli.subparsers._quality_checks import register_quality_check_subcommands


def setup_quality_commands(subparsers) -> None:
    """Set up quality command group."""
    quality_parser = subparsers.add_parser(
        "quality",
        help="Code quality checks (complexity, smells, debt, typing, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality analyze ./src\n"
            "  heimdall quality analyze ./src --format json\n"
            "  heimdall quality complexity ./src --cyclomatic-threshold 8\n"
            "  heimdall quality env-fallback ./src --severity high\n"
            "  heimdall quality thread-safety ./src --include-tests\n"
        ),
    )
    quality_subparsers = quality_parser.add_subparsers(dest="quality_command", help="Quality subcommand to run")
    register_quality_core_subcommands(quality_subparsers)
    register_quality_check_subcommands(quality_subparsers)
