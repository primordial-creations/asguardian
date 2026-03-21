"""
Heimdall CLI - Quality core subparser registration.

Registers analyze, file-length, complexity, duplication, smells, debt,
maintainability, env-fallback, lazy-imports, forbidden-imports, datetime,
typing, and type-check subcommands onto a quality_subparsers object.
"""

import argparse

from Asgard.Heimdall.cli.common import (
    add_common_args,
    add_complexity_args,
    add_duplication_args,
    add_smell_args,
    add_debt_args,
    add_maintainability_args,
    add_env_fallback_args,
    add_lazy_imports_args,
    add_forbidden_imports_args,
    add_datetime_args,
    add_typing_args,
    add_type_check_args,
)


def register_quality_core_subcommands(quality_subparsers) -> None:
    """Register core quality subcommands onto quality_subparsers."""
    quality_analyze = quality_subparsers.add_parser(
        "analyze",
        help="Run all quality checks and report violations across all quality dimensions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality analyze ./src\n"
            "  heimdall quality analyze ./src --format html\n"
            "  heimdall quality analyze ./src --parallel --incremental\n"
            "  heimdall quality analyze ./src --exclude '*/tests/*' '*/migrations/*'\n"
            "  heimdall quality analyze ./src --baseline .asgard-baseline.json\n"
        ),
    )
    add_common_args(quality_analyze)

    quality_file_length = quality_subparsers.add_parser(
        "file-length",
        help="Report files that exceed the configured line length threshold",
    )
    add_common_args(quality_file_length)

    quality_complexity = quality_subparsers.add_parser(
        "complexity",
        help="Report functions exceeding cyclomatic or cognitive complexity thresholds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality complexity ./src\n"
            "  heimdall quality complexity ./src --cyclomatic-threshold 8 --cognitive-threshold 12\n"
            "  heimdall quality complexity ./src --format json\n"
        ),
    )
    add_complexity_args(quality_complexity)

    quality_duplication = quality_subparsers.add_parser(
        "duplication",
        help="Detect copy-pasted code blocks that exceed the minimum line/token thresholds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality duplication ./src\n"
            "  heimdall quality duplication ./src --min-lines 10 --min-tokens 80\n"
            "  heimdall quality duplication ./src --format markdown\n"
        ),
    )
    add_duplication_args(quality_duplication)

    quality_smells = quality_subparsers.add_parser(
        "smells",
        help="Detect code smells such as long methods, large classes, and feature envy",
    )
    add_smell_args(quality_smells)

    quality_debt = quality_subparsers.add_parser(
        "debt",
        help="Estimate and categorize technical debt by horizon (immediate, short, medium, long)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality debt ./src\n"
            "  heimdall quality debt ./src --horizon immediate\n"
            "  heimdall quality debt ./src --severity high --format markdown\n"
        ),
    )
    add_debt_args(quality_debt)

    quality_maintainability = quality_subparsers.add_parser(
        "maintainability",
        help="Score files by maintainability index and flag those rated poor or critical",
    )
    add_maintainability_args(quality_maintainability)

    quality_env_fallback = quality_subparsers.add_parser(
        "env-fallback",
        help="Detect default/fallback values in environment variable access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality env-fallback ./src\n"
            "  heimdall quality env-fallback ./src --severity high\n"
            "  heimdall quality env-fallback ./src --include-tests --format json\n"
        ),
    )
    add_env_fallback_args(quality_env_fallback)

    quality_lazy_imports = quality_subparsers.add_parser(
        "lazy-imports",
        help="Detect imports not at module level (inside functions, methods, etc.)"
    )
    add_lazy_imports_args(quality_lazy_imports)

    quality_forbidden_imports = quality_subparsers.add_parser(
        "forbidden-imports",
        help="Detect imports of forbidden libraries that should use wrappers"
    )
    add_forbidden_imports_args(quality_forbidden_imports)

    quality_datetime = quality_subparsers.add_parser(
        "datetime",
        help="Detect deprecated and unsafe datetime usage patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality datetime ./src\n"
            "  heimdall quality datetime ./src --no-check-utcnow --no-check-today\n"
            "  heimdall quality datetime ./src --include-tests --format json\n"
        ),
    )
    add_datetime_args(quality_datetime)

    quality_typing = quality_subparsers.add_parser(
        "typing",
        help="Analyze type annotation coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality typing ./src\n"
            "  heimdall quality typing ./src --threshold 90.0\n"
            "  heimdall quality typing ./src --include-private --include-dunder\n"
        ),
    )
    add_typing_args(quality_typing)

    quality_type_check = quality_subparsers.add_parser(
        "type-check",
        help="Run static type checking using Pyright (Pylance engine) across the entire codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality type-check ./src\n"
            "  heimdall quality type-check ./src --mode strict\n"
            "  heimdall quality type-check ./src --errors-only\n"
            "  heimdall quality type-check ./src --category missing_import\n"
            "  heimdall quality type-check ./src --venv-path .venv --format json\n"
            "\n"
            "Type checking modes (Pylance equivalent):\n"
            "  off         No type checking\n"
            "  basic       Basic checks (Pylance default)\n"
            "  standard    Standard checks (more thorough)\n"
            "  strict      All checks enabled (strictest)\n"
            "  all         All checks + all optional rules\n"
        ),
    )
    add_type_check_args(quality_type_check)
