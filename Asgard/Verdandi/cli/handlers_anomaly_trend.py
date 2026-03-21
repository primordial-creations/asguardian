import argparse
import json

from Asgard.Verdandi.Anomaly import StatisticalDetector, BaselineComparator, RegressionDetector
from Asgard.Verdandi.Trend import TrendAnalyzer, ForecastCalculator
from Asgard.Verdandi.Trend.models.trend_models import TrendData
from Asgard.Verdandi.cli.handlers_analysis import load_json_or_parse


def run_anomaly_detect(args: argparse.Namespace, output_format: str) -> int:
    """Detect anomalies in data."""
    data = load_json_or_parse(args.data)

    detector = StatisticalDetector(z_threshold=args.threshold)
    anomalies = detector.detect(data, metric_name="cli_metric", method=args.method)

    if output_format == "json":
        print(json.dumps([a.model_dump() for a in anomalies], indent=2, default=str))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - ANOMALY DETECTION")
        print("=" * 60)
        print("")
        print(f"  Data Points:     {len(data)}")
        print(f"  Method:          {args.method}")
        print(f"  Z-Threshold:     {args.threshold}")
        print(f"  Anomalies Found: {len(anomalies)}")
        print("")

        if anomalies:
            print("-" * 60)
            print("  DETECTED ANOMALIES")
            print("-" * 60)
            for a in anomalies[:10]:
                print(f"  [{a.severity.value.upper()}] {a.anomaly_type.value}: {a.actual_value:.2f}")
                print(f"    Expected: {a.expected_value:.2f}, Deviation: {a.deviation_percent:+.1f}%")
            if len(anomalies) > 10:
                print(f"  ... and {len(anomalies) - 10} more")
            print("")

        print("=" * 60)

    return 0 if len(anomalies) == 0 else 1


def run_regression_check(args: argparse.Namespace, output_format: str) -> int:
    """Check for performance regressions."""
    before = load_json_or_parse(args.before)
    after = load_json_or_parse(args.after)

    detector = RegressionDetector(regression_threshold_percent=args.threshold)
    result = detector.detect(before, after, metric_name="cli_metric")

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - REGRESSION CHECK")
        print("=" * 60)
        print("")
        print(f"  Before Mean:     {result.before_mean:.2f}")
        print(f"  After Mean:      {result.after_mean:.2f}")
        print(f"  Mean Change:     {result.mean_change_percent:+.1f}%")
        print("")
        print(f"  Before P99:      {result.before_p99:.2f}")
        print(f"  After P99:       {result.after_p99:.2f}")
        print(f"  P99 Change:      {result.p99_change_percent:+.1f}%")
        print("")
        print(f"  Regression:      {'YES' if result.is_regression else 'NO'}")
        print(f"  Severity:        {result.regression_severity.value.upper()}")
        print(f"  Confidence:      {result.confidence * 100:.0f}%")
        print("")

        if result.recommendations:
            print("-" * 60)
            print("  RECOMMENDATIONS")
            print("-" * 60)
            for rec in result.recommendations:
                print(f"  - {rec}")
            print("")

        print("=" * 60)

    return 0 if not result.is_regression else 1


def run_trend_analyze(args: argparse.Namespace, output_format: str) -> int:
    """Analyze performance trends."""
    values = load_json_or_parse(args.data)

    analyzer = TrendAnalyzer()
    result = analyzer.analyze_values(values, metric_name=args.name)

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - TREND ANALYSIS")
        print("=" * 60)
        print("")
        print(f"  Metric:          {result.metric_name}")
        print(f"  Data Points:     {result.data_point_count}")
        print(f"  Direction:       {result.direction.value.upper()}")
        print(f"  R-squared:       {result.r_squared:.3f}")
        print(f"  Confidence:      {result.confidence * 100:.0f}%")
        print("")
        print(f"  Start Value:     {result.start_value:.2f}")
        print(f"  End Value:       {result.end_value:.2f}")
        print(f"  Change:          {result.change_percent:+.1f}%")
        print(f"  Slope/Day:       {result.slope_per_day:+.4f}")
        print("")
        print(f"  Mean:            {result.mean:.2f}")
        print(f"  Std Dev:         {result.std_dev:.2f}")
        print(f"  Volatility:      {result.volatility:.3f}")
        print("")
        print(f"  Significant:     {'YES' if result.is_significant else 'NO'}")
        print("")
        print("=" * 60)

    return 0


def run_forecast(args: argparse.Namespace, output_format: str) -> int:
    """Forecast future performance."""
    values = load_json_or_parse(args.data)

    forecaster = ForecastCalculator()
    result = forecaster.forecast_values(
        values,
        periods=args.periods,
        metric_name="cli_metric",
        method=args.method,
    )

    if output_format == "json":
        print(result.model_dump_json(indent=2))
    else:
        print("")
        print("=" * 60)
        print("  VERDANDI - PERFORMANCE FORECAST")
        print("=" * 60)
        print("")
        print(f"  Method:              {result.method}")
        print(f"  Training Points:     {result.training_data_points}")
        print(f"  Forecast Periods:    {args.periods}")
        print(f"  Trend Direction:     {result.trend_direction.value.upper()}")
        print(f"  Model Fit:           {result.model_fit_score:.3f}")
        print("")
        print(f"  Expected at End:     {result.expected_value_at_end:.2f}")
        print(f"  Expected Change:     {result.expected_change_percent:+.1f}%")
        print("")

        if result.forecast_points:
            print("-" * 60)
            print("  FORECAST")
            print("-" * 60)
            for point in result.forecast_points:
                print(f"  {point.timestamp.strftime('%Y-%m-%d')}: "
                      f"{point.predicted_value:.2f} "
                      f"[{point.lower_bound:.2f}, {point.upper_bound:.2f}]")
            print("")

        if result.warnings:
            print("-" * 60)
            print("  WARNINGS")
            print("-" * 60)
            for warning in result.warnings:
                print(f"  - {warning}")
            print("")

        print("=" * 60)

    return 0
