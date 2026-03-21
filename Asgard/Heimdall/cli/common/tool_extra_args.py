import argparse


def add_issue_update_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues update subcommand."""
    parser.add_argument(
        "issue_id",
        type=str,
        help="UUID of the issue to update",
    )
    parser.add_argument(
        "--status",
        type=str,
        required=True,
        choices=["open", "confirmed", "resolved", "closed", "false_positive", "wont_fix"],
        help="New status to set",
    )
    parser.add_argument(
        "--reason",
        type=str,
        default=None,
        help="Reason for the status change (required when marking false_positive)",
    )


def add_issue_assign_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues assign subcommand."""
    parser.add_argument(
        "issue_id",
        type=str,
        help="UUID of the issue to assign",
    )
    parser.add_argument(
        "assignee",
        type=str,
        help="Username or email to assign the issue to",
    )


def add_issue_show_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues show subcommand."""
    parser.add_argument(
        "issue_id",
        type=str,
        help="UUID of the issue to display",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_issue_summary_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the issues summary subcommand."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Project root path (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_sbom_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the SBOM generation command."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Project directory to scan for dependencies (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["spdx", "cyclonedx"],
        default="cyclonedx",
        help="SBOM output format (default: cyclonedx)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Write SBOM JSON to this file (default: print to stdout)",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        default="",
        help="Override project name in the SBOM document",
    )
    parser.add_argument(
        "--project-version",
        type=str,
        default="",
        help="Project version to embed in the SBOM document",
    )


def add_codefix_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the codefix suggestion command."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Project path to generate fix suggestions for (default: current directory)",
    )
    parser.add_argument(
        "--rule",
        type=str,
        default=None,
        dest="rule_id",
        help="Limit suggestions to a specific rule ID (e.g. quality.lazy_imports)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def add_mcp_server_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the MCP server command."""
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host address to bind to (default: localhost)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        dest="project_path",
        help="Default project path for analysis tools (default: current directory)",
    )


def add_dashboard_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the dashboard command."""
    parser.add_argument(
        "--path",
        default=".",
        help="Project path to display in dashboard",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to serve dashboard on (default: 8080)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Do not automatically open browser on launch",
    )
