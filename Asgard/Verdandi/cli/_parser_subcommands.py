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

    policy_parser = slo_subparsers.add_parser(
        "burn-rate-policy",
        help=(
            "Evaluate the three-tier multi-window burn-rate alert policy "
            "(page_fast / page_slow / ticket)"
        ),
    )
    policy_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {slo: {name, type, target}, metrics: "
            "[{timestamp, good_events, total_events}, ...]}"
        ),
    )
    policy_parser.add_argument(
        "--target",
        "-t",
        type=float,
        default=None,
        help="Override the SLO target percentage from the file",
    )
    policy_parser.add_argument(
        "--at",
        type=str,
        default=None,
        help="Evaluate as of this ISO timestamp (default: now)",
    )

    portfolio_parser = slo_subparsers.add_parser(
        "portfolio",
        help=(
            "Cross-journey/service portfolio health score (CXI/SRI) from "
            "journey success rates and/or per-service burn rates"
        ),
    )
    portfolio_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {journey_success_rates: {}, business_weights: {}?, "
            "service_burn_rates: {}, centrality: {}?}"
        ),
    )

    budget_policy_parser = slo_subparsers.add_parser(
        "budget-policy",
        help="Evaluate the error-budget policy tier (normal/caution/freeze)",
    )
    budget_policy_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {budget: {...ErrorBudget...}, incidents: [...]?, "
            "slo: {...SLODefinition...}?}"
        ),
    )

    dynamic_budget_parser = slo_subparsers.add_parser(
        "dynamic-budget",
        help="Evaluate a complexity-aware dynamic latency budget",
    )
    dynamic_budget_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {base_ms, cost_per_unit_ms, cost_function: "
            "'linear'|'nlogn', durations_ms: [...], complexity_units: [...]}"
        ),
    )

    add_performance_flags(slo_parser)


def _add_db_parser(subparsers) -> None:
    """Add database performance commands."""
    db_parser = subparsers.add_parser(
        "db",
        help="Database performance analysis",
    )
    db_subparsers = db_parser.add_subparsers(
        dest="db_command",
        help="Database commands",
    )

    signature_parser = db_subparsers.add_parser(
        "pool-signature",
        help=(
            "Classify a bimodal latency distribution: pool exhaustion vs "
            "cache-aside pattern"
        ),
    )
    signature_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: array of latencies in ms, or {latencies_ms: [...], "
            "acquisition_waits_ms: [...]}"
        ),
    )

    budget_parser = db_subparsers.add_parser(
        "budget",
        help="Evaluate query-duration budgets against a complexity-scaled config",
    )
    budget_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {config: {...QueryBudgetConfig...}, "
            "durations_ms: [...], units: [...]}"
        ),
    )

    queries_parser = db_subparsers.add_parser(
        "queries",
        help="Analyze query metrics, optionally grouped per query class",
    )
    queries_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: array of {...QueryMetricsInput...}, or "
            "{queries: [...], baseline: {fingerprint: [durations_ms]}?}"
        ),
    )
    queries_parser.add_argument(
        "--per-class",
        action="store_true",
        help="Group and analyze metrics per query fingerprint/class",
    )
    queries_parser.add_argument(
        "--slow-threshold",
        type=float,
        default=100.0,
        help="Slow-query threshold in ms (default: 100.0)",
    )


def _add_system_parser(subparsers) -> None:
    """Add system-level performance commands (PSI, cgroup throttle, USE/RED)."""
    system_parser = subparsers.add_parser(
        "system",
        help="System-level performance analysis (PSI, cgroups, USE/RED)",
    )
    system_subparsers = system_parser.add_subparsers(
        dest="system_command",
        help="System commands",
    )

    psi_parser = system_subparsers.add_parser(
        "psi",
        help="Analyze pressure stall information (PSI) severity/trajectory",
    )
    psi_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {snapshot: {...PsiSnapshot...}, previous: {...}?} "
            "or {snapshots: {cpu: {...}, memory: {...}, io: {...}}}"
        ),
    )

    throttle_parser = system_subparsers.add_parser(
        "throttle",
        help="Analyze cgroup CPU-throttle stats for limit-induced latency",
    )
    throttle_parser.add_argument(
        "metrics_file",
        help="JSON file: {...CgroupCpuStats fields...}",
    )

    correlate_parser = system_subparsers.add_parser(
        "correlate",
        help="Correlate USE-method saturation against RED-method latency",
    )
    correlate_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {saturation: [...], p99_duration_ms: [...], "
            "max_lag: 5, rate: [...]?, errors: [...]?}"
        ),
    )

    add_performance_flags(system_parser)


def _add_network_parser(subparsers) -> None:
    """Add network performance commands (phases, USE method, signatures)."""
    network_parser = subparsers.add_parser(
        "network",
        help="Network performance analysis (phases, USE method, signatures)",
    )
    network_subparsers = network_parser.add_subparsers(
        dest="network_command",
        help="Network commands",
    )

    phases_parser = network_subparsers.add_parser(
        "phases",
        help="Analyze connection-phase breakdown (DNS/TCP/TLS/request/response)",
    )
    phases_parser.add_argument(
        "metrics_file",
        help="JSON file: array of {...ConnectionPhases fields...} samples",
    )

    use_parser = network_subparsers.add_parser(
        "use",
        help="USE-method analysis of NIC/TCP-stack/DNS-resolver saturation",
    )
    use_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {snapshot: {...UseCounterSnapshot...}, "
            "retransmit_series: [...]?, utilization_series: [...]?}"
        ),
    )

    signature_parser = network_subparsers.add_parser(
        "signature",
        help=(
            "Classify network signature (route change / congestion / DNS "
            "hijack / clock skew) from RTT and related series"
        ),
    )
    signature_parser.add_argument(
        "metrics_file",
        help=(
            "JSON file: {rtt_series: [...], hop_count_series: [...]?, "
            "resolved_asn_series: [...]?, tls_failure_series: [...]?, "
            "one_way_latencies_ms: [...]?, sample_interval_seconds: 60}"
        ),
    )

    add_performance_flags(network_parser)


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
        help=(
            "Regression threshold percentage: minimum relative "
            "Hodges-Lehmann shift for the practical-significance gate "
            "(default: 10.0)"
        )
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


