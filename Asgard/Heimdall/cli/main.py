"""
Heimdall CLI Main Entry Point

This module provides the main CLI entry point and parser creation.
Command handlers are delegated to submodules for better organization.
"""

import argparse
import io
import sys

from Asgard.Heimdall.cli.common import add_common_args
from Asgard.Heimdall.cli.handlers import (
    _TeeStream,
    _save_html_report,
    _open_in_browser,
)
from Asgard.Heimdall.cli._dispatcher import dispatch
from Asgard.Heimdall.cli.subparsers._quality import setup_quality_commands
from Asgard.Heimdall.cli.subparsers._security import setup_security_commands
from Asgard.Heimdall.cli.subparsers._analysis import (
    setup_performance_commands,
    setup_oop_commands,
    setup_deps_commands,
    setup_arch_commands,
    setup_coverage_commands,
    setup_syntax_commands,
    setup_requirements_commands,
    setup_licenses_commands,
    setup_logic_commands,
)
from Asgard.Heimdall.cli.subparsers._management import (
    setup_baseline_commands,
    setup_init_linter_command,
    setup_ratings_command,
    setup_gate_command,
    setup_profiles_commands,
    setup_history_commands,
    setup_new_code_commands,
    setup_issues_command,
    setup_sbom_command,
    setup_codefix_command,
    setup_mcp_server_command,
    setup_dashboard_command,
)


COMMAND_DEFAULT_SUBCOMMANDS = {
    "security": "scan",
    "performance": "scan",
    "oop": "analyze",
    "logic": "audit",
    "syntax": "check",
}

COMMAND_KNOWN_SUBCOMMANDS = {
    "security": {
        "scan", "secrets", "dependencies", "vulnerabilities", "crypto", "access",
        "auth", "headers", "tls", "container", "infra", "config-secrets",
        "hotspots", "compliance", "taint",
    },
    "performance": {"scan", "memory", "cpu", "database", "cache"},
    "oop": {"analyze", "coupling", "cohesion", "inheritance"},
    "logic": {"duplication", "patterns", "complexity", "audit"},
    "syntax": {"check", "fix"},
}


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="heimdall",
        description="Heimdall - Static code analysis and quality enforcement tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality analyze ./src\n"
            "  heimdall audit ./src --format html\n"
            "  heimdall security scan ./src --severity high\n"
            "  heimdall dependencies export ./src --export-format mermaid\n"
            "  heimdall baseline list ./src --type env-fallback\n"
            "\n"
            "Named after the Norse watchman god who guards Bifrost and sees all."
        ),
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all scanned files, including those with no issues",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Heimdall 1.1.0",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        default=False,
        help="Open the HTML report in the default browser after scanning (default: off)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Top-level command group")

    setup_quality_commands(subparsers)

    # Audit command (alias for quality analyze)
    audit_parser = subparsers.add_parser(
        "audit",
        help="Run all quality checks against a path (shorthand for 'quality analyze')",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall audit ./src\n"
            "  heimdall audit ./src --format html\n"
            "  heimdall audit ./src --parallel --incremental\n"
        ),
    )
    add_common_args(audit_parser)

    setup_security_commands(subparsers)
    setup_performance_commands(subparsers)
    setup_oop_commands(subparsers)
    setup_deps_commands(subparsers)
    setup_arch_commands(subparsers)
    setup_coverage_commands(subparsers)
    setup_syntax_commands(subparsers)
    setup_requirements_commands(subparsers)
    setup_licenses_commands(subparsers)
    setup_logic_commands(subparsers)
    setup_baseline_commands(subparsers)
    setup_init_linter_command(subparsers)
    setup_ratings_command(subparsers)
    setup_gate_command(subparsers)
    setup_profiles_commands(subparsers)
    setup_history_commands(subparsers)
    setup_new_code_commands(subparsers)
    setup_issues_command(subparsers)
    setup_sbom_command(subparsers)
    setup_codefix_command(subparsers)
    setup_mcp_server_command(subparsers)
    setup_dashboard_command(subparsers)

    # Scan command (runs ALL analyses)
    scan_parser = subparsers.add_parser(
        "scan",
        help="Run ALL analysis categories (quality, security, performance, OOP, architecture, type-check, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall scan ./src\n"
            "  heimdall scan ./src --format markdown\n"
            "  heimdall scan ./src --include-tests\n"
            "  heimdall scan ./src --type-check-mode strict\n"
            "\n"
            "This runs all Heimdall analyses in sequence:\n"
            "  1. File length analysis\n"
            "  2. Complexity analysis\n"
            "  3. Lazy import detection\n"
            "  4. Environment variable fallback detection\n"
            "  5. Static type checking (Pyright/Pylance)\n"
            "  6. Security vulnerability scan\n"
            "  7. Performance pattern analysis\n"
            "  8. OOP metrics (coupling/cohesion)\n"
            "  9. Architecture analysis (SOLID/layers)\n"
            "  10. Dependency analysis (circular imports)\n"
        ),
    )
    scan_parser.add_argument("path", type=str, nargs="?", default=".", help="Root path to scan (default: current directory)")
    scan_parser.add_argument("--format", "-f", choices=["text", "json", "markdown"], default="text", help="Output format (default: text)")
    scan_parser.add_argument("--threshold", "-t", type=int, default=300, help="File length threshold (default: 300)")
    scan_parser.add_argument("--include-tests", action="store_true", help="Include test files in analysis")
    scan_parser.add_argument("--exclude", "-x", type=str, nargs="+", default=[], help="Glob patterns for paths to exclude")
    scan_parser.add_argument("--type-check-mode", choices=["off", "basic", "standard", "strict", "all"], default="basic", help="Pyright type checking mode (default: basic)")
    scan_parser.add_argument("--open-browser", action="store_true", default=False, help="Open the HTML report in the default browser after scanning (default: off)")

    return parser


def main(args=None):
    """Main entry point for the Heimdall CLI.

    Args:
        args: Optional list of arguments. If None, uses sys.argv.
    """
    if args is None:
        argv = sys.argv[1:]
    else:
        argv = list(args)

    # Insert default subcommand when a command group is given a path directly
    # e.g. "heimdall security ./src" -> "heimdall security scan ./src"
    if len(argv) >= 2:
        cmd = argv[0]
        if cmd in COMMAND_DEFAULT_SUBCOMMANDS:
            next_arg = argv[1]
            known = COMMAND_KNOWN_SUBCOMMANDS[cmd]
            if next_arg not in known and next_arg not in ("-h", "--help"):
                argv.insert(1, COMMAND_DEFAULT_SUBCOMMANDS[cmd])

    parser = create_parser()
    args = parser.parse_args(argv)
    verbose = args.verbose if hasattr(args, "verbose") else False

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Commands that stream output continuously and never produce a report
    _NO_REPORT = {"mcp-server", "dashboard", "install-browsers"}
    _open_browser = getattr(args, "open_browser", False)
    _capture_output = args.command not in _NO_REPORT and args.command != "scan"

    _buf: io.StringIO = io.StringIO()
    _tee = _TeeStream(sys.stdout, _buf)
    if _capture_output:
        sys.stdout = _tee

    try:
        dispatch(args, verbose)
    finally:
        if _capture_output:
            sys.stdout = sys.__stdout__
            _captured = _buf.getvalue()
            if _captured.strip():
                sub = (
                    getattr(args, "quality_command", None)
                    or getattr(args, "security_command", None)
                    or getattr(args, "performance_command", None)
                    or getattr(args, "deps_command", None)
                    or getattr(args, "arch_command", None)
                    or getattr(args, "oop_command", None)
                    or getattr(args, "logic_command", None)
                    or getattr(args, "syntax_command", None)
                    or getattr(args, "req_command", None)
                    or getattr(args, "lic_command", None)
                )
                _cmd_label = args.command
                if sub:
                    _cmd_label = f"{args.command} {sub}"
                _title = f"Heimdall - {_cmd_label}"
                report_path = _save_html_report(_captured, _title)
                print(f"Report saved: {report_path}", file=sys.__stdout__)
                if _open_browser:
                    _open_in_browser(report_path)


if __name__ == "__main__":
    main()
