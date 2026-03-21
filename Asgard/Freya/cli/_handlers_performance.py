import argparse

from Asgard.Freya.Performance.services.page_load_analyzer import PageLoadAnalyzer
from Asgard.Freya.Performance.services.resource_timing_analyzer import ResourceTimingAnalyzer
from Asgard.Freya.cli._formatters_performance import (
    format_performance_text,
    format_load_time_text,
    format_resources_text,
)


async def run_performance_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run performance audit."""
    analyzer = PageLoadAnalyzer()

    print(f"\nRunning performance audit on: {args.url}")
    print("-" * 60)

    result = await analyzer.get_performance_report(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_performance_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0


async def run_performance_load_time(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run page load time analysis."""
    analyzer = PageLoadAnalyzer()

    print(f"\nMeasuring page load time: {args.url}")
    print("-" * 60)

    result = await analyzer.analyze(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_load_time_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 0


async def run_performance_resources(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run resource timing analysis."""
    analyzer = ResourceTimingAnalyzer()

    print(f"\nAnalyzing resources: {args.url}")
    print("-" * 60)

    result = await analyzer.analyze(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_resources_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if len(result.large_resources) > 0 or len(result.slow_resources) > 0 else 0
