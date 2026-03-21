"""
Heimdall CLI - Management subparser setup (part B).

Covers: history, new-code, issues, sbom, codefix, mcp-server, dashboard.
"""

import argparse

from Asgard.Heimdall.cli.common import (
    add_history_args,
    add_new_code_args,
    add_issues_args,
    add_sbom_args,
    add_codefix_args,
    add_mcp_server_args,
    add_dashboard_args,
)


def setup_history_commands(subparsers) -> None:
    """Set up the history command group."""
    history_parser = subparsers.add_parser(
        "history",
        help="View analysis history and metric trends for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall history show ./src\n"
            "  heimdall history show ./src --limit 20\n"
            "  heimdall history trends ./src\n"
            "  heimdall history trends ./src --format json\n"
        ),
    )
    history_subparsers = history_parser.add_subparsers(
        dest="history_command",
        help="History subcommand to run",
    )

    history_show = history_subparsers.add_parser(
        "show",
        help="Show recorded analysis snapshots for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall history show ./src\n"
            "  heimdall history show ./src --limit 20 --format json\n"
        ),
    )
    add_history_args(history_show)

    history_trends = history_subparsers.add_parser(
        "trends",
        help="Show metric trend directions computed from recorded analysis history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall history trends ./src\n"
            "  heimdall history trends ./src --format json\n"
        ),
    )
    add_history_args(history_trends)


def setup_new_code_commands(subparsers) -> None:
    """Set up the new-code command group."""
    new_code_parser = subparsers.add_parser(
        "new-code",
        help="Detect which files count as new code relative to a configured reference point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall new-code detect ./src\n"
            "  heimdall new-code detect ./src --since-branch main\n"
            "  heimdall new-code detect ./src --since-date 2026-01-01\n"
            "  heimdall new-code detect ./src --since-version v1.2.0\n"
        ),
    )
    new_code_subparsers = new_code_parser.add_subparsers(
        dest="new_code_command",
        help="New-code subcommand to run",
    )

    new_code_detect = new_code_subparsers.add_parser(
        "detect",
        help="Show which files are considered new or modified relative to the reference point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall new-code detect ./src\n"
            "  heimdall new-code detect ./src --since-branch main\n"
            "  heimdall new-code detect ./src --since-date 2026-01-01\n"
            "  heimdall new-code detect ./src --since-version v1.2.0\n"
        ),
    )
    add_new_code_args(new_code_detect)


def setup_issues_command(subparsers) -> None:
    """Set up the issues top-level command."""
    issues_parser = subparsers.add_parser(
        "issues",
        help="Manage tracked issues lifecycle (list, show, update, assign, summary)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall issues list ./src\n"
            "  heimdall issues show ./src --id abc-1234\n"
            "  heimdall issues update ./src --id abc-1234 --status resolved\n"
            "  heimdall issues assign ./src --id abc-1234 --assignee alice\n"
            "  heimdall issues summary ./src\n"
        ),
    )
    add_issues_args(issues_parser)


def setup_sbom_command(subparsers) -> None:
    """Set up the sbom top-level command."""
    sbom_parser = subparsers.add_parser(
        "sbom",
        help="Generate Software Bill of Materials (SBOM) in SPDX or CycloneDX format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall sbom ./src\n"
            "  heimdall sbom ./src --format spdx\n"
            "  heimdall sbom ./src --format cyclonedx --output sbom.json\n"
        ),
    )
    add_sbom_args(sbom_parser)


def setup_codefix_command(subparsers) -> None:
    """Set up the codefix top-level command."""
    codefix_parser = subparsers.add_parser(
        "codefix",
        help="Get fix suggestions for detected code issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall codefix ./src\n"
            "  heimdall codefix ./src --rule ENV001\n"
            "  heimdall codefix ./src --format json\n"
        ),
    )
    add_codefix_args(codefix_parser)


def setup_mcp_server_command(subparsers) -> None:
    """Set up the mcp-server top-level command."""
    mcp_server_parser = subparsers.add_parser(
        "mcp-server",
        help="Start the Asgard MCP server for AI agent integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall mcp-server\n"
            "  heimdall mcp-server --port 8080\n"
            "  heimdall mcp-server --path /api/mcp\n"
        ),
    )
    add_mcp_server_args(mcp_server_parser)


def setup_dashboard_command(subparsers) -> None:
    """Set up the dashboard top-level command."""
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch web dashboard for browsing analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall dashboard --path ./my-project\n"
            "  heimdall dashboard --path ./my-project --port 9090\n"
            "  heimdall dashboard --path ./my-project --no-open-browser\n"
        ),
    )
    add_dashboard_args(dashboard_parser)
