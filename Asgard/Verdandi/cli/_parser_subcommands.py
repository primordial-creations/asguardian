import argparse

from Asgard.Verdandi.cli._parser_flags import add_performance_flags


def _add_apm_parser(subparsers) -> None:
    """Add APM commands."""
    apm_parser = subparsers.add_parser(
        "apm",
        help="Application Performance Monitoring"
    )
    apm_subparsers = apm_parser.add_subparsers(
        dest="apm_command",
        help="APM commands"
    )

    analyze_parser = apm_subparsers.add_parser(
        "analyze",
        help="Analyze APM traces"
    )
    analyze_parser.add_argument(
        "traces",
        type=str,
        help="Path to traces JSON file"
    )
    analyze_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=1000,
        help="Slow trace threshold in ms (default: 1000)"
    )

    service_map_parser = apm_subparsers.add_parser(
        "service-map",
        help="Generate service dependency map"
    )
    service_map_parser.add_argument(
        "traces",
        type=str,
        help="Path to traces JSON file"
    )

    add_performance_flags(apm_parser)


def _add_slo_parser(subparsers) -> None:
    """Add SLO commands."""
    slo_parser = subparsers.add_parser(
        "slo",
        help="Service Level Objective management"
    )
    slo_subparsers = slo_parser.add_subparsers(
        dest="slo_command",
        help="SLO commands"
    )

    calc_parser = slo_subparsers.add_parser(
        "calculate",
        help="Calculate SLO compliance"
    )
    calc_parser.add_argument(
        "metrics",
        type=str,
        help="Path to metrics JSON file or comma-separated good,total values"
    )
    calc_parser.add_argument(
        "--target",
        "-t",
        type=float,
        default=99.9,
        help="SLO target percentage (default: 99.9)"
    )
    calc_parser.add_argument(
        "--window",
        "-w",
        type=int,
        default=30,
        help="SLO window in days (default: 30)"
    )

    budget_parser = slo_subparsers.add_parser(
        "error-budget",
        help="Calculate error budget"
    )
    budget_parser.add_argument(
        "metrics",
        type=str,
        help="Path to metrics JSON file"
    )
    budget_parser.add_argument(
        "--target",
        "-t",
        type=float,
        default=99.9,
        help="SLO target percentage (default: 99.9)"
    )

    burn_parser = slo_subparsers.add_parser(
        "burn-rate",
        help="Analyze burn rate"
    )
    burn_parser.add_argument(
        "metrics",
        type=str,
        help="Path to metrics JSON file"
    )
    burn_parser.add_argument(
        "--target",
        "-t",
        type=float,
        default=99.9,
        help="SLO target percentage (default: 99.9)"
    )
    burn_parser.add_argument(
        "--window",
        type=float,
        default=1.0,
        help="Analysis window in hours (default: 1.0)"
    )

    add_performance_flags(slo_parser)


def _add_anomaly_parser(subparsers) -> None:
    """Add anomaly detection commands."""
    anomaly_parser = subparsers.add_parser(
        "anomaly",
        help="Anomaly detection"
    )
    anomaly_subparsers = anomaly_parser.add_subparsers(
        dest="anomaly_command",
        help="Anomaly commands"
    )

    detect_parser = anomaly_subparsers.add_parser(
        "detect",
        help="Detect anomalies in metrics"
    )
    detect_parser.add_argument(
        "data",
        type=str,
        help="Comma-separated values or path to JSON file"
    )
    detect_parser.add_argument(
        "--method",
        "-m",
        choices=["zscore", "iqr", "combined"],
        default="combined",
        help="Detection method (default: combined)"
    )
    detect_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=3.0,
        help="Z-score threshold (default: 3.0)"
    )

    regression_parser = anomaly_subparsers.add_parser(
        "regression",
        help="Check for performance regressions"
    )
    regression_parser.add_argument(
        "before",
        type=str,
        help="Comma-separated before values or path to JSON file"
    )
    regression_parser.add_argument(
        "after",
        type=str,
        help="Comma-separated after values or path to JSON file"
    )
    regression_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=10.0,
        help="Regression threshold percentage (default: 10.0)"
    )

    add_performance_flags(anomaly_parser)


def _add_tracing_parser(subparsers) -> None:
    """Add distributed tracing commands."""
    tracing_parser = subparsers.add_parser(
        "tracing",
        help="Distributed tracing analysis"
    )
    tracing_subparsers = tracing_parser.add_subparsers(
        dest="tracing_command",
        help="Tracing commands"
    )

    parse_parser = tracing_subparsers.add_parser(
        "parse",
        help="Parse trace data"
    )
    parse_parser.add_argument(
        "file",
        type=str,
        help="Path to trace JSON file"
    )
    parse_parser.add_argument(
        "--format",
        choices=["otlp", "jaeger", "zipkin", "auto"],
        default="auto",
        help="Trace format (default: auto)"
    )

    critical_parser = tracing_subparsers.add_parser(
        "critical-path",
        help="Analyze critical path in traces"
    )
    critical_parser.add_argument(
        "file",
        type=str,
        help="Path to trace JSON file"
    )

    add_performance_flags(tracing_parser)


def _add_trend_parser(subparsers) -> None:
    """Add trend analysis commands."""
    trend_parser = subparsers.add_parser(
        "trend",
        help="Performance trend analysis"
    )
    trend_subparsers = trend_parser.add_subparsers(
        dest="trend_command",
        help="Trend commands"
    )

    analyze_parser = trend_subparsers.add_parser(
        "analyze",
        help="Analyze performance trends"
    )
    analyze_parser.add_argument(
        "data",
        type=str,
        help="Comma-separated values or path to JSON file"
    )
    analyze_parser.add_argument(
        "--name",
        "-n",
        type=str,
        default="metric",
        help="Metric name (default: metric)"
    )

    forecast_parser = trend_subparsers.add_parser(
        "forecast",
        help="Forecast future performance"
    )
    forecast_parser.add_argument(
        "data",
        type=str,
        help="Comma-separated values or path to JSON file"
    )
    forecast_parser.add_argument(
        "--periods",
        "-p",
        type=int,
        default=7,
        help="Number of periods to forecast (default: 7)"
    )
    forecast_parser.add_argument(
        "--method",
        "-m",
        choices=["linear", "exponential", "moving_average"],
        default="linear",
        help="Forecasting method (default: linear)"
    )

    add_performance_flags(trend_parser)


