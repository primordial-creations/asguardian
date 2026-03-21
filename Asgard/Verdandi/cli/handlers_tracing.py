import argparse
import json
import sys

from Asgard.Verdandi.Tracing import TraceParser, CriticalPathAnalyzer


def run_tracing_parse(args: argparse.Namespace, output_format: str) -> None:
    """Parse trace data and display results."""
    with open(args.file, "r") as f:
        traces_data = json.load(f)
    parser = TraceParser()
    traces = parser.parse_otlp(traces_data) if "resourceSpans" in traces_data else parser.parse_jaeger(traces_data)
    if output_format == "json":
        print(json.dumps([t.model_dump() for t in traces], indent=2, default=str))
    else:
        print(f"Parsed {len(traces)} traces")
        for t in traces:
            print(f"  Trace {t.trace_id[:8]}...: {t.span_count} spans, {t.total_duration_ms:.0f}ms")
    sys.exit(0)


def run_tracing_critical_path(args: argparse.Namespace, output_format: str) -> None:
    """Analyze critical path in traces."""
    with open(args.file, "r") as f:
        traces_data = json.load(f)
    parser = TraceParser()
    traces = parser.parse_otlp(traces_data) if "resourceSpans" in traces_data else parser.parse_jaeger(traces_data)
    analyzer = CriticalPathAnalyzer()
    for trace in traces:
        result = analyzer.analyze(trace)
        if output_format == "json":
            print(result.model_dump_json(indent=2))
        else:
            print(f"Critical path for trace {trace.trace_id[:8]}...")
            print(f"  Duration: {result.total_duration_ms:.0f}ms")
            print(f"  Bottleneck: {result.bottleneck_service}/{result.bottleneck_operation}")
            for segment in result.segments:
                print(f"    {segment.span.operation_name}: {segment.contribution_ms:.0f}ms ({segment.contribution_percent:.1f}%)")
    sys.exit(0)
