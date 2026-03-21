import argparse
import json
from pathlib import Path
from typing import Any, List

from Asgard.Verdandi.Analysis import (
    ApdexCalculator,
    ApdexConfig,
    PercentileCalculator,
    SLAChecker,
    SLAConfig,
)
from Asgard.Verdandi.Web import CoreWebVitalsCalculator
from Asgard.Verdandi.Cache import CacheMetricsCalculator


def parse_data_list(data_str: str) -> List[float]:
    """Parse comma-separated data string to list of floats."""
    return [float(x.strip()) for x in data_str.split(",")]


def load_json_or_parse(data_str: str) -> Any:
    """Load from JSON file or parse as comma-separated values."""
    path = Path(data_str)
    if path.exists() and path.suffix == ".json":
        with open(path, "r") as f:
            return json.load(f)
    return parse_data_list(data_str)


def run_web_vitals(args: argparse.Namespace, output_format: str) -> int:
    """Run Core Web Vitals calculation."""
    calc = CoreWebVitalsCalculator()
    result = calc.calculate(
        lcp_ms=args.lcp,
        fid_ms=args.fid,
        cls=args.cls,
        inp_ms=args.inp,
        ttfb_ms=args.ttfb,
        fcp_ms=args.fcp,
    )

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - CORE WEB VITALS")
        print("=" * 60)
        print("")
        if result.lcp_ms is not None:
            print(f"  LCP:  {result.lcp_ms:.0f}ms ({result.lcp_rating.value})")
        if result.fid_ms is not None:
            print(f"  FID:  {result.fid_ms:.0f}ms ({result.fid_rating.value})")
        if result.cls is not None:
            print(f"  CLS:  {result.cls:.3f} ({result.cls_rating.value})")
        if result.inp_ms is not None:
            print(f"  INP:  {result.inp_ms:.0f}ms ({result.inp_rating.value})")
        if result.ttfb_ms is not None:
            print(f"  TTFB: {result.ttfb_ms:.0f}ms ({result.ttfb_rating.value})")
        if result.fcp_ms is not None:
            print(f"  FCP:  {result.fcp_ms:.0f}ms ({result.fcp_rating.value})")
        print("")
        print(f"  Overall: {result.overall_rating.value.upper()}")
        print(f"  Score:   {result.score:.0f}/100")
        print("")

        if result.recommendations:
            print("-" * 60)
            print("  RECOMMENDATIONS")
            print("-" * 60)
            for rec in result.recommendations:
                print(f"  - {rec}")
            print("")

        print("=" * 60)

    return 0 if result.overall_rating.value == "good" else 1


def run_percentiles(args: argparse.Namespace, output_format: str) -> int:
    """Run percentile calculation."""
    data = parse_data_list(args.data)
    calc = PercentileCalculator()
    result = calc.calculate(data)

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - PERCENTILE ANALYSIS")
        print("=" * 60)
        print("")
        print(f"  Samples: {result.sample_count}")
        print(f"  Min:     {result.min_value:.2f}")
        print(f"  Max:     {result.max_value:.2f}")
        print(f"  Mean:    {result.mean:.2f}")
        print(f"  Std Dev: {result.std_dev:.2f}")
        print("")
        print("  PERCENTILES")
        print(f"  P50:     {result.p50:.2f}")
        print(f"  P75:     {result.p75:.2f}")
        print(f"  P90:     {result.p90:.2f}")
        print(f"  P95:     {result.p95:.2f}")
        print(f"  P99:     {result.p99:.2f}")
        print(f"  P99.9:   {result.p999:.2f}")
        print("")
        print("=" * 60)

    return 0


def run_apdex(args: argparse.Namespace, output_format: str) -> int:
    """Run Apdex calculation."""
    data = parse_data_list(args.data)
    calc = ApdexCalculator(threshold_ms=args.threshold)
    result = calc.calculate(data)

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - APDEX SCORE")
        print("=" * 60)
        print("")
        print(f"  Threshold T: {result.threshold_ms}ms")
        print(f"  Frustration: {result.threshold_ms * 4}ms")
        print("")
        print(f"  Score:      {result.score:.4f}")
        print(f"  Rating:     {result.rating}")
        print("")
        print("  BREAKDOWN")
        print(f"  Satisfied:  {result.satisfied_count} ({result.satisfied_count/result.total_count*100:.1f}%)")
        print(f"  Tolerating: {result.tolerating_count} ({result.tolerating_count/result.total_count*100:.1f}%)")
        print(f"  Frustrated: {result.frustrated_count} ({result.frustrated_count/result.total_count*100:.1f}%)")
        print("")
        print("=" * 60)

    return 0 if result.score >= 0.85 else 1


def run_sla_check(args: argparse.Namespace, output_format: str) -> int:
    """Run SLA compliance check."""
    data = parse_data_list(args.data)
    config = SLAConfig(
        target_percentile=args.percentile,
        threshold_ms=args.threshold,
    )
    checker = SLAChecker(config)
    result = checker.check(data)

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - SLA COMPLIANCE CHECK")
        print("=" * 60)
        print("")
        print(f"  Target:     P{result.percentile_target} <= {result.threshold_ms}ms")
        print(f"  Actual:     P{result.percentile_target} = {result.percentile_value}ms")
        print(f"  Margin:     {result.margin_percent:+.1f}%")
        print("")
        status_display = result.status.value.upper()
        print(f"  Status:     {status_display}")
        print("")

        if result.violations:
            print("-" * 60)
            print("  VIOLATIONS")
            print("-" * 60)
            for violation in result.violations:
                print(f"  - {violation}")
            print("")

        print("=" * 60)

    return 0 if result.status.value == "compliant" else 1


def run_cache_metrics(args: argparse.Namespace, output_format: str) -> int:
    """Run cache metrics calculation."""
    calc = CacheMetricsCalculator()
    result = calc.analyze(
        hits=args.hits,
        misses=args.misses,
        avg_hit_latency_ms=getattr(args, "hit_latency", None),
        avg_miss_latency_ms=getattr(args, "miss_latency", None),
    )

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - CACHE METRICS")
        print("=" * 60)
        print("")
        print(f"  Total:    {result.total_requests}")
        print(f"  Hits:     {result.hits}")
        print(f"  Misses:   {result.misses}")
        print("")
        print(f"  Hit Rate: {result.hit_rate_percent:.2f}%")
        print(f"  Status:   {result.status.upper()}")
        print("")

        if result.latency_savings_ms:
            print(f"  Latency Saved: {result.latency_savings_ms:.0f}ms total")
            print("")

        if result.recommendations:
            print("-" * 60)
            print("  RECOMMENDATIONS")
            print("-" * 60)
            for rec in result.recommendations:
                print(f"  - {rec}")
            print("")

        print("=" * 60)

    return 0
