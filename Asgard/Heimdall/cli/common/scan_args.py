import argparse


def add_coverage_args(parser: argparse.ArgumentParser) -> None:
    """Add coverage analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--test-path",
        type=str,
        default=None,
        help="Path to the test directory to match against source methods (default: auto-detect)",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private methods (prefixed with _) in coverage analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--max-suggestions",
        type=int,
        default=10,
        help="Maximum number of test case suggestions to generate per run (default: 10)",
    )


def add_syntax_args(parser: argparse.ArgumentParser) -> None:
    """Add syntax checking arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--linters",
        nargs="+",
        choices=["ruff", "flake8", "pylint", "mypy"],
        default=["ruff"],
        help="Linters to run; multiple values allowed (default: ruff)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["error", "warning", "info", "style"],
        default="warning",
        help="Minimum severity level to report; lower levels are suppressed (default: warning)",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".py"],
        help="File extensions to include in the scan (default: .py)",
    )
    parser.add_argument(
        "--include-style",
        action="store_true",
        help="Include style-level issues in output (e.g. formatting, naming conventions)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_requirements_args(parser: argparse.ArgumentParser) -> None:
    """Add requirements checking arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--requirements-files",
        nargs="+",
        default=["requirements.txt"],
        help="One or more requirements files to validate (default: requirements.txt)",
    )
    parser.add_argument(
        "--no-check-unused",
        action="store_true",
        help="Do not report packages that are listed in requirements but never imported",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_licenses_args(parser: argparse.ArgumentParser) -> None:
    """Add license checking arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--allowed",
        nargs="+",
        default=None,
        help="License identifiers that are permitted (e.g. MIT Apache-2.0 BSD-3-Clause)",
    )
    parser.add_argument(
        "--denied",
        nargs="+",
        default=None,
        help="License identifiers that are forbidden; any match is reported as a violation",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_logic_args(parser: argparse.ArgumentParser) -> None:
    """Add logic analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_baseline_args(parser: argparse.ArgumentParser) -> None:
    """Add baseline management arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path of the project (default: current directory)",
    )
    parser.add_argument(
        "--baseline-file",
        "-b",
        type=str,
        default=".asgard-baseline.json",
        help="Path to the baseline JSON file (default: .asgard-baseline.json)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--type",
        "-t",
        type=str,
        default=None,
        help="Filter baseline entries by violation type (e.g. env-fallback, lazy-imports)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Filter baseline entries to those whose file path contains this pattern",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=None,
        help="Unique violation ID to target; required when using the 'remove' subcommand",
    )
