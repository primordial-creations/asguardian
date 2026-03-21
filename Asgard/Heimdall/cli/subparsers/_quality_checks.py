"""
Heimdall CLI - Quality checks subparser registration.

Registers thread-safety, race-conditions, daemon-threads, future-leaks,
blocking-async, resource-cleanup, error-handling, documentation, naming,
bugs, javascript, typescript, and shell subcommands onto a quality_subparsers
object.
"""

import argparse

from Asgard.Heimdall.cli.common import (
    add_thread_safety_args,
    add_race_conditions_args,
    add_daemon_threads_args,
    add_future_leaks_args,
    add_blocking_async_args,
    add_resource_cleanup_args,
    add_error_handling_args,
    add_documentation_args,
    add_naming_args,
    add_bugs_args,
    add_js_args,
    add_ts_args,
    add_shell_args,
)


def register_quality_check_subcommands(quality_subparsers) -> None:
    """Register safety/checks quality subcommands onto quality_subparsers."""
    quality_thread_safety = quality_subparsers.add_parser(
        "thread-safety",
        help="Detect thread safety issues (uninitialized attrs, shared mutable collections)"
    )
    add_thread_safety_args(quality_thread_safety)

    quality_race_conditions = quality_subparsers.add_parser(
        "race-conditions",
        help="Detect race condition patterns (start-before-store, assign-after-start, check-then-act)"
    )
    add_race_conditions_args(quality_race_conditions)

    quality_daemon_threads = quality_subparsers.add_parser(
        "daemon-threads",
        help="Detect daemon thread lifecycle issues (no join, local var only, event patterns)"
    )
    add_daemon_threads_args(quality_daemon_threads)

    quality_future_leaks = quality_subparsers.add_parser(
        "future-leaks",
        help="Detect futures, tasks, and threads that are created but never resolved"
    )
    add_future_leaks_args(quality_future_leaks)

    quality_blocking_async = quality_subparsers.add_parser(
        "blocking-async",
        help="Detect blocking calls (time.sleep, requests, open, subprocess) inside async functions"
    )
    add_blocking_async_args(quality_blocking_async)

    quality_resource_cleanup = quality_subparsers.add_parser(
        "resource-cleanup",
        help="Detect resource cleanup issues (unclosed files, connections, and context manager violations)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality resource-cleanup ./src\n"
            "  heimdall quality resource-cleanup ./src --severity high\n"
            "  heimdall quality resource-cleanup ./src --include-tests --format json\n"
        ),
    )
    add_resource_cleanup_args(quality_resource_cleanup)

    quality_error_handling = quality_subparsers.add_parser(
        "error-handling",
        help="Detect error handling coverage issues (bare excepts, swallowed exceptions, missing handlers)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality error-handling ./src\n"
            "  heimdall quality error-handling ./src --severity high --format json\n"
            "  heimdall quality error-handling ./src --include-tests\n"
        ),
    )
    add_error_handling_args(quality_error_handling)

    quality_documentation = quality_subparsers.add_parser(
        "documentation",
        help="Scan comment density and public API documentation coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality documentation ./src\n"
            "  heimdall quality documentation ./src --min-comment-density 15.0\n"
            "  heimdall quality documentation ./src --min-api-coverage 80.0 --format json\n"
        ),
    )
    add_documentation_args(quality_documentation)

    quality_naming = quality_subparsers.add_parser(
        "naming",
        help="Enforce PEP 8 naming conventions for functions, classes, variables, and constants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality naming ./src\n"
            "  heimdall quality naming ./src --no-variables --format json\n"
            "  heimdall quality naming ./src --allow MySpecialName --format markdown\n"
        ),
    )
    add_naming_args(quality_naming)

    quality_bugs = quality_subparsers.add_parser(
        "bugs",
        help="Detect null dereferences, unreachable code, and other bugs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality bugs ./src\n"
            "  heimdall quality bugs ./src --null-only\n"
            "  heimdall quality bugs ./src --unreachable-only --format json\n"
        ),
    )
    add_bugs_args(quality_bugs)

    quality_javascript = quality_subparsers.add_parser(
        "javascript",
        help="Analyze JavaScript files for quality issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality javascript ./src\n"
            "  heimdall quality javascript ./src --severity high\n"
            "  heimdall quality javascript ./src --format json\n"
        ),
    )
    add_js_args(quality_javascript)

    quality_typescript = quality_subparsers.add_parser(
        "typescript",
        help="Analyze TypeScript files for quality issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality typescript ./src\n"
            "  heimdall quality typescript ./src --severity high\n"
            "  heimdall quality typescript ./src --format json\n"
        ),
    )
    add_ts_args(quality_typescript)

    quality_shell = quality_subparsers.add_parser(
        "shell",
        help="Analyze shell/bash scripts for quality and security issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality shell ./src\n"
            "  heimdall quality shell ./scripts --severity high\n"
            "  heimdall quality shell ./src --format json\n"
        ),
    )
    add_shell_args(quality_shell)
