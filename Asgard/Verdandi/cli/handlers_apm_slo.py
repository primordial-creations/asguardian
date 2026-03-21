import argparse
import json
from datetime import datetime

from Asgard.Verdandi.APM import SpanAnalyzer, TraceAggregator, ServiceMapBuilder
from Asgard.Verdandi.APM.models.apm_models import Span, SpanKind, SpanStatus
from Asgard.Verdandi.SLO import ErrorBudgetCalculator, SLITracker, BurnRateAnalyzer
from Asgard.Verdandi.SLO.models.slo_models import SLODefinition, SLOType, SLIMetric
from Asgard.Verdandi.Tracing import TraceParser, CriticalPathAnalyzer
from Asgard.Verdandi.cli.handlers_analysis import load_json_or_parse


def run_apm_analyze(args: argparse.Namespace, output_format: str) -> int:
    """Run APM trace analysis."""
    with open(args.traces, "r") as f:
        traces_data = json.load(f)

    parser = TraceParser()
    if isinstance(traces_data, dict) and "resourceSpans" in traces_data:
        traces = parser.parse_otlp(traces_data)
    elif isinstance(traces_data, dict) and "data" in traces_data:
        traces = parser.parse_jaeger(traces_data)
    else:
        traces = [parser.build_trace(traces_data)]

    aggregator = TraceAggregator(slow_trace_threshold_ms=args.threshold)
    report = aggregator.aggregate(traces)

    if output_format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - APM ANALYSIS")
        print("=" * 60)
        print("")
        print(f"  Traces Analyzed: {report.trace_count}")
        print(f"  Total Spans:     {report.span_count}")
        print(f"  Error Rate:      {report.overall_error_rate * 100:.2f}%")
        print(f"  Avg Latency:     {report.overall_avg_latency_ms:.0f}ms")
        print(f"  P99 Latency:     {report.overall_p99_latency_ms:.0f}ms")
        print(f"  Health Score:    {report.health_score:.0f}/100")
        print("")

        if report.service_metrics:
            print("-" * 60)
            print("  SERVICE METRICS")
            print("-" * 60)
            for svc in report.service_metrics:
                print(f"  {svc.service_name}:")
                print(f"    Requests:    {svc.request_count}")
                print(f"    Avg Latency: {svc.avg_duration_ms:.0f}ms")
                print(f"    Error Rate:  {svc.error_rate * 100:.2f}%")
            print("")

        if report.recommendations:
            print("-" * 60)
            print("  RECOMMENDATIONS")
            print("-" * 60)
            for rec in report.recommendations:
                print(f"  - {rec}")
            print("")

        print("=" * 60)

    return 0 if report.health_score >= 80 else 1


def run_apm_service_map(args: argparse.Namespace, output_format: str) -> int:
    """Generate service dependency map."""
    with open(args.traces, "r") as f:
        traces_data = json.load(f)

    parser = TraceParser()
    if isinstance(traces_data, dict) and "resourceSpans" in traces_data:
        traces = parser.parse_otlp(traces_data)
    elif isinstance(traces_data, dict) and "data" in traces_data:
        traces = parser.parse_jaeger(traces_data)
    else:
        traces = [parser.build_trace(traces_data)]

    builder = ServiceMapBuilder()
    service_map = builder.build(traces)

    if output_format == "json":
        print(service_map.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - SERVICE DEPENDENCY MAP")
        print("=" * 60)
        print("")
        print(f"  Services:     {service_map.service_count}")
        print(f"  Dependencies: {service_map.edge_count}")
        print("")
        print(f"  Root Services:   {', '.join(service_map.root_services) or 'None'}")
        print(f"  Leaf Services:   {', '.join(service_map.leaf_services) or 'None'}")
        print("")

        if service_map.dependencies:
            print("-" * 60)
            print("  DEPENDENCIES")
            print("-" * 60)
            for dep in service_map.dependencies:
                print(f"  {dep.source_service} -> {dep.target_service}")
                print(f"    Calls: {dep.call_count}, Avg Latency: {dep.avg_latency_ms:.0f}ms")
            print("")

        print("=" * 60)

    return 0


def run_slo_calculate(args: argparse.Namespace, output_format: str) -> int:
    """Calculate SLO compliance."""
    data = load_json_or_parse(args.metrics)

    slo = SLODefinition(
        name="CLI SLO",
        slo_type=SLOType.AVAILABILITY,
        target=args.target,
        window_days=args.window,
        service_name="cli_service",
    )

    if isinstance(data, list) and len(data) == 2:
        metrics = [
            SLIMetric(
                timestamp=datetime.now(),
                service_name="cli_service",
                slo_type=SLOType.AVAILABILITY,
                good_events=int(data[0]),
                total_events=int(data[1]),
            )
        ]
    else:
        metrics = [
            SLIMetric(
                timestamp=datetime.now(),
                service_name="cli_service",
                slo_type=SLOType.AVAILABILITY,
                good_events=int(m.get("good", 0)),
                total_events=int(m.get("total", 0)),
            )
            for m in data
        ]

    calculator = ErrorBudgetCalculator()
    budget = calculator.calculate(slo, metrics)

    if output_format == "json":
        print(budget.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - SLO COMPLIANCE")
        print("=" * 60)
        print("")
        print(f"  SLO Target:      {budget.slo_target}%")
        print(f"  Current SLI:     {budget.current_sli:.3f}%")
        print(f"  Status:          {budget.status.value.upper()}")
        print("")
        print(f"  Total Events:    {budget.total_events}")
        print(f"  Good Events:     {budget.good_events}")
        print(f"  Bad Events:      {budget.bad_events}")
        print("")
        print(f"  Budget Consumed: {budget.budget_consumed_percent:.1f}%")
        print(f"  Remaining:       {budget.remaining_budget:.0f} failures allowed")
        print("")
        print("=" * 60)

    return 0 if budget.status.value == "compliant" else 1
