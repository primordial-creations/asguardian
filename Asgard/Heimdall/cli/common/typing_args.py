import argparse


def add_typing_args(parser: argparse.ArgumentParser) -> None:
    """Add typing coverage scanner arguments to a parser."""
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
        "--threshold",
        "-t",
        type=float,
        default=80.0,
        help="Minimum typing coverage percentage (default: 80.0)",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private methods (_method) in analysis",
    )
    parser.add_argument(
        "--include-dunder",
        action="store_true",
        help="Include dunder methods (__method__) in analysis",
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


def add_type_check_args(parser: argparse.ArgumentParser) -> None:
    """Add static type checking (Pyright/Pylance) arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to type-check (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["off", "basic", "standard", "strict", "all"],
        default="basic",
        help="Type checking strictness (default: basic). "
             "mypy: normal/strict map to basic/strict. "
             "pyright: off/basic/standard/strict/all.",
    )
    parser.add_argument(
        "--python-version",
        type=str,
        default="",
        help="Python version to target (e.g. 3.12). Auto-detected if not set.",
    )
    parser.add_argument(
        "--python-platform",
        type=str,
        default="",
        help="Python platform to target (e.g. Linux). Auto-detected if not set.",
    )
    parser.add_argument(
        "--venv-path",
        type=str,
        default="",
        help="Path to virtual environment for import resolution.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in analysis",
    )
    parser.add_argument(
        "--include-warnings",
        action="store_true",
        default=True,
        help="Include warnings in output (default: True)",
    )
    parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Show only errors (suppress warnings and info)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["error", "warning", "information"],
        default=None,
        help="Filter output to only this severity level",
    )
    parser.add_argument(
        "--category",
        "-c",
        choices=[
            "type_mismatch", "missing_import", "undefined_variable",
            "argument_error", "return_type", "attribute_error",
            "assignment_error", "operator_error", "override_error",
            "generic_error", "protocol_error", "typed_dict_error",
            "overload_error", "unreachable_code", "deprecated", "general",
        ],
        default=None,
        help="Filter output to only this diagnostic category",
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
        "--npx-path",
        type=str,
        default="npx",
        help="Path to npx binary (default: npx, only used with --engine=pyright)",
    )
    parser.add_argument(
        "--engine",
        choices=["mypy", "pyright"],
        default="mypy",
        help="Type checking engine: mypy (default, pure Python) or pyright (Pylance engine, requires Node.js/npx)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Subprocess timeout in seconds (default: 300)",
    )


