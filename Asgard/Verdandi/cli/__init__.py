import sys

from Asgard.Verdandi.cli._parser import create_parser
from Asgard.Verdandi.cli.handlers_analysis import (
    run_web_vitals,
    run_percentiles,
    run_apdex,
    run_sla_check,
    run_cache_metrics,
)
from Asgard.Verdandi.cli.handlers_apm_slo import (
    run_apm_analyze,
    run_apm_service_map,
    run_slo_calculate,
)
from Asgard.Verdandi.cli.handlers_anomaly_trend import (
    run_anomaly_detect,
    run_regression_check,
    run_trend_analyze,
    run_forecast,
)
from Asgard.Verdandi.cli.handlers_tracing import (
    run_tracing_parse,
    run_tracing_critical_path,
)


def main(args=None) -> int:
    """Main entry point.

    Args:
        args: Optional list of arguments. If None, uses sys.argv.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    args = parser.parse_args(args)

    output_format = getattr(args, "format", "text")

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "web":
        if not hasattr(args, "web_command") or args.web_command is None:
            print("Error: Please specify a web command (e.g., 'vitals')")
            sys.exit(1)

        if args.web_command == "vitals":
            exit_code = run_web_vitals(args, output_format)
        else:
            print(f"Unknown web command: {args.web_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "analyze":
        if not hasattr(args, "analyze_command") or args.analyze_command is None:
            print("Error: Please specify an analysis command")
            sys.exit(1)

        if args.analyze_command == "percentiles":
            exit_code = run_percentiles(args, output_format)
        elif args.analyze_command == "apdex":
            exit_code = run_apdex(args, output_format)
        elif args.analyze_command == "sla":
            exit_code = run_sla_check(args, output_format)
        else:
            print(f"Unknown analyze command: {args.analyze_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "cache":
        if not hasattr(args, "cache_command") or args.cache_command is None:
            print("Error: Please specify a cache command")
            sys.exit(1)

        if args.cache_command == "metrics":
            exit_code = run_cache_metrics(args, output_format)
        else:
            print(f"Unknown cache command: {args.cache_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "apm":
        if not hasattr(args, "apm_command") or args.apm_command is None:
            print("Error: Please specify an APM command (e.g., 'analyze', 'service-map')")
            sys.exit(1)

        if args.apm_command == "analyze":
            exit_code = run_apm_analyze(args, output_format)
        elif args.apm_command == "service-map":
            exit_code = run_apm_service_map(args, output_format)
        else:
            print(f"Unknown APM command: {args.apm_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "slo":
        if not hasattr(args, "slo_command") or args.slo_command is None:
            print("Error: Please specify an SLO command (e.g., 'calculate', 'error-budget')")
            sys.exit(1)

        if args.slo_command == "calculate":
            exit_code = run_slo_calculate(args, output_format)
        elif args.slo_command == "error-budget":
            exit_code = run_slo_calculate(args, output_format)
        elif args.slo_command == "burn-rate":
            exit_code = run_slo_calculate(args, output_format)
        else:
            print(f"Unknown SLO command: {args.slo_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "anomaly":
        if not hasattr(args, "anomaly_command") or args.anomaly_command is None:
            print("Error: Please specify an anomaly command (e.g., 'detect', 'regression')")
            sys.exit(1)

        if args.anomaly_command == "detect":
            exit_code = run_anomaly_detect(args, output_format)
        elif args.anomaly_command == "regression":
            exit_code = run_regression_check(args, output_format)
        else:
            print(f"Unknown anomaly command: {args.anomaly_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "tracing":
        if not hasattr(args, "tracing_command") or args.tracing_command is None:
            print("Error: Please specify a tracing command (e.g., 'parse', 'critical-path')")
            sys.exit(1)

        if args.tracing_command == "parse":
            run_tracing_parse(args, output_format)
        elif args.tracing_command == "critical-path":
            run_tracing_critical_path(args, output_format)
        else:
            print(f"Unknown tracing command: {args.tracing_command}")
            sys.exit(1)

    elif args.command == "trend":
        if not hasattr(args, "trend_command") or args.trend_command is None:
            print("Error: Please specify a trend command (e.g., 'analyze', 'forecast')")
            sys.exit(1)

        if args.trend_command == "analyze":
            exit_code = run_trend_analyze(args, output_format)
        elif args.trend_command == "forecast":
            exit_code = run_forecast(args, output_format)
        else:
            print(f"Unknown trend command: {args.trend_command}")
            sys.exit(1)

        sys.exit(exit_code)

    elif args.command == "report":
        if not hasattr(args, "report_command") or args.report_command is None:
            print("Error: Please specify a report command (e.g., 'generate')")
            sys.exit(1)

        print("Report generation not yet implemented")
        sys.exit(1)

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
