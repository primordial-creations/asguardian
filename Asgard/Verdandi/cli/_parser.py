import argparse

from Asgard.Verdandi.cli._parser_flags import (
    add_performance_flags,
    _add_web_parser,
    _add_analyze_parser,
    _add_cache_parser,
    _add_report_parser,
)
from Asgard.Verdandi.cli._parser_subcommands import (
    _add_apm_parser,
    _add_slo_parser,
    _add_anomaly_parser,
    _add_tracing_parser,
    _add_trend_parser,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="verdandi",
        description="Verdandi - Runtime Performance Metrics",
        epilog="Named after the Norse Norn who measures the present moment.",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Verdandi 2.0.0",
    )

    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "github", "html"],
        default="text",
        help="Output format (default: text)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    _add_web_parser(subparsers)
    _add_analyze_parser(subparsers)
    _add_cache_parser(subparsers)
    _add_apm_parser(subparsers)
    _add_slo_parser(subparsers)
    _add_anomaly_parser(subparsers)
    _add_tracing_parser(subparsers)
    _add_trend_parser(subparsers)
    _add_report_parser(subparsers)

    return parser
