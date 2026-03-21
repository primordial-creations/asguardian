import argparse


def add_performance_flags(parser: argparse.ArgumentParser) -> None:
    """Add performance-related flags to a parser (parallel, incremental, cache)."""
    parser.add_argument(
        "--parallel",
        "-P",
        action="store_true",
        help="Enable parallel processing for faster analysis",
    )
    parser.add_argument(
        "--workers",
        "-W",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count - 1)",
    )
    parser.add_argument(
        "--incremental",
        "-I",
        action="store_true",
        help="Enable incremental scanning (skip unchanged files)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching even if incremental mode is enabled",
    )
    parser.add_argument(
        "--baseline",
        "-B",
        type=str,
        default=None,
        help="Path to baseline file for filtering known issues",
    )


def _add_web_parser(subparsers) -> None:
    """Add web performance commands."""
    web_parser = subparsers.add_parser(
        "web",
        help="Web performance metrics"
    )
    web_subparsers = web_parser.add_subparsers(
        dest="web_command",
        help="Web commands"
    )

    vitals_parser = web_subparsers.add_parser(
        "vitals",
        help="Calculate Core Web Vitals ratings"
    )
    vitals_parser.add_argument(
        "--lcp",
        type=float,
        help="Largest Contentful Paint in milliseconds"
    )
    vitals_parser.add_argument(
        "--fid",
        type=float,
        help="First Input Delay in milliseconds"
    )
    vitals_parser.add_argument(
        "--cls",
        type=float,
        help="Cumulative Layout Shift"
    )
    vitals_parser.add_argument(
        "--inp",
        type=float,
        help="Interaction to Next Paint in milliseconds"
    )
    vitals_parser.add_argument(
        "--ttfb",
        type=float,
        help="Time to First Byte in milliseconds"
    )
    vitals_parser.add_argument(
        "--fcp",
        type=float,
        help="First Contentful Paint in milliseconds"
    )

    add_performance_flags(web_parser)


def _add_analyze_parser(subparsers) -> None:
    """Add analysis commands."""
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Statistical analysis commands"
    )
    analyze_subparsers = analyze_parser.add_subparsers(
        dest="analyze_command",
        help="Analysis commands"
    )

    percentiles_parser = analyze_subparsers.add_parser(
        "percentiles",
        help="Calculate percentiles for a dataset"
    )
    percentiles_parser.add_argument(
        "--data",
        "-d",
        type=str,
        required=True,
        help="Comma-separated list of values"
    )

    apdex_parser = analyze_subparsers.add_parser(
        "apdex",
        help="Calculate Apdex score"
    )
    apdex_parser.add_argument(
        "--data",
        "-d",
        type=str,
        required=True,
        help="Comma-separated list of response times in ms"
    )
    apdex_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=500,
        help="Apdex threshold T in milliseconds (default: 500)"
    )

    sla_parser = analyze_subparsers.add_parser(
        "sla",
        help="Check SLA compliance"
    )
    sla_parser.add_argument(
        "--data",
        "-d",
        type=str,
        required=True,
        help="Comma-separated list of response times in ms"
    )
    sla_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        required=True,
        help="SLA threshold in milliseconds"
    )
    sla_parser.add_argument(
        "--percentile",
        "-p",
        type=float,
        default=95,
        help="Target percentile (default: 95)"
    )

    add_performance_flags(analyze_parser)


def _add_cache_parser(subparsers) -> None:
    """Add cache performance commands."""
    cache_parser = subparsers.add_parser(
        "cache",
        help="Cache performance metrics"
    )
    cache_subparsers = cache_parser.add_subparsers(
        dest="cache_command",
        help="Cache commands"
    )

    metrics_parser = cache_subparsers.add_parser(
        "metrics",
        help="Calculate cache hit rate and metrics"
    )
    metrics_parser.add_argument(
        "--hits",
        type=int,
        required=True,
        help="Number of cache hits"
    )
    metrics_parser.add_argument(
        "--misses",
        type=int,
        required=True,
        help="Number of cache misses"
    )
    metrics_parser.add_argument(
        "--hit-latency",
        type=float,
        help="Average hit latency in ms"
    )
    metrics_parser.add_argument(
        "--miss-latency",
        type=float,
        help="Average miss latency in ms"
    )

    add_performance_flags(cache_parser)


def _add_report_parser(subparsers) -> None:
    """Add report generation commands."""
    report_parser = subparsers.add_parser(
        "report",
        help="Generate comprehensive reports"
    )
    report_subparsers = report_parser.add_subparsers(
        dest="report_command",
        help="Report commands"
    )

    generate_parser = report_subparsers.add_parser(
        "generate",
        help="Generate comprehensive performance report"
    )
    generate_parser.add_argument(
        "metrics",
        type=str,
        help="Path to metrics JSON file"
    )
    generate_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path"
    )

    add_performance_flags(report_parser)
