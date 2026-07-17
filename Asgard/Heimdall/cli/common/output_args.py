import argparse


def add_documentation_args(parser: argparse.ArgumentParser) -> None:
    """Add documentation scanner arguments to a parser."""
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
        "--min-comment-density",
        type=float,
        default=10.0,
        help="Minimum acceptable comment density percentage (default: 10.0)",
    )
    parser.add_argument(
        "--min-api-coverage",
        type=float,
        default=70.0,
        help="Minimum acceptable public API documentation coverage percentage (default: 70.0)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_naming_args(parser: argparse.ArgumentParser) -> None:
    """Add naming convention scanner arguments to a parser."""
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
        "--no-functions",
        action="store_true",
        help="Skip checking function and method names",
    )
    parser.add_argument(
        "--no-classes",
        action="store_true",
        help="Skip checking class names",
    )
    parser.add_argument(
        "--no-variables",
        action="store_true",
        help="Skip checking module-level variable names",
    )
    parser.add_argument(
        "--no-constants",
        action="store_true",
        help="Skip checking module-level constant names",
    )
    parser.add_argument(
        "--allow",
        type=str,
        nargs="+",
        default=[],
        dest="allow_list",
        help="Names to exclude from convention checking (exact matches)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files (test_*.py, *_test.py) in analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_ratings_args(parser: argparse.ArgumentParser) -> None:
    """Add A-E ratings calculator arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to rate (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
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
        "--history",
        action="store_true",
        help="Save the ratings result to the local history store (~/.asgard/history.db)",
    )


def add_gate_args(parser: argparse.ArgumentParser) -> None:
    """Add quality gate evaluation arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to evaluate (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--gate",
        type=str,
        default="asgard-way",
        help="Quality gate to use (default: asgard-way)",
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
        "--history",
        action="store_true",
        help="Save the gate result to the local history store (~/.asgard/history.db)",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        default=False,
        help=(
            "Also evaluate the differential ('clean as you code') gate: only "
            "NEW HIGH/CRITICAL findings vs the base ref's fingerprint baseline "
            "block; changed lines come from the git diff engine."
        ),
    )
    parser.add_argument(
        "--base",
        type=str,
        default="main",
        help="Base git ref for the differential gate baseline/diff (default: main)",
    )
    parser.add_argument(
        "--tier",
        choices=["pr", "main"],
        default=None,
        help=(
            "Gate tier: 'pr' runs the differential gate in git-diff mode "
            "(implies --diff); 'main' evaluates fingerprints against the "
            "baseline without a diff."
        ),
    )


