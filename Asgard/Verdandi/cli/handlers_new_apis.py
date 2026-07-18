"""
CLI handlers for the Wave-1/2 Verdandi APIs:

- web cwv-assess          distribution-based Core Web Vitals (p75) assessment
- slo burn-rate-policy    three-tier multi-window burn-rate alert policy
- cache warmup            post-deploy hit-rate trajectory classification
- db pool-signature       pool-exhaustion bimodal signature detection

All are thin wrappers over the existing services: JSON metrics file in,
JSON or human-readable text out.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def _load_json(path: str) -> Optional[Any]:
    file_path = Path(path)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: Could not parse JSON from {file_path}: {e}")
        return None


def _dump(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def run_cwv_assess(args, output_format: str = "text") -> int:
    """`verdandi web cwv-assess <metrics.json>`.

    Input: {"lcp": [ms...], "inp": [ms...], "cls": [...], "ttfb": [...]}
    — raw RUM sample arrays per metric.
    """
    from Asgard.Verdandi.Web.services.vitals_calculator import (
        CoreWebVitalsCalculator,
    )

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict) or not data:
        print("Error: Expected a JSON object of {metric: [samples...]}.")
        return 1

    calculator = CoreWebVitalsCalculator()
    try:
        assessment = calculator.assess_page(data)
    except (ValueError, TypeError) as e:
        print(f"Error: {e}")
        return 1

    if output_format == "json":
        print(json.dumps(_dump(assessment), indent=2, default=str))
    else:
        lines = ["", "CORE WEB VITALS ASSESSMENT (p75, distribution-based)",
                 "=" * 60]
        for name in ("lcp", "inp", "cls"):
            r = getattr(assessment, name)
            if r is None:
                lines.append(f"  {name.upper():5} : not provided")
                continue
            rating = getattr(r.rating, "value", r.rating)
            p75 = f"{r.p75:g}" if r.p75 is not None else "n/a"
            lines.append(
                f"  {name.upper():5} : {rating}  (p75={p75}, "
                f"n={r.sample_count})"
            )
        passing = assessment.core_passing
        verdict = ("PASS" if passing else
                   "FAIL" if passing is False else "UNDETERMINED")
        lines.append(f"  Core Web Vitals: {verdict}")
        for name, r in sorted(assessment.diagnostics.items()):
            rating = getattr(r.rating, "value", r.rating)
            lines.append(f"  {name.upper():5} : {rating} (diagnostic)")
        for rec in assessment.recommendations:
            lines.append(f"  - {rec}")
        print("\n".join(lines))

    return 0 if assessment.core_passing else 1


def run_burn_rate_policy(args, output_format: str = "text") -> int:
    """`verdandi slo burn-rate-policy <metrics.json>`.

    Input: {"slo": {"name", "type", "target"},
            "metrics": [{"timestamp", "good_events", "total_events"}, ...]}
    """
    from Asgard.Verdandi.SLO.models.slo_models import (
        SLIMetric,
        SLODefinition,
        SLOType,
    )
    from Asgard.Verdandi.SLO.services.burn_rate_analyzer import (
        BurnRateAnalyzer,
    )

    data = _load_json(args.metrics_file)
    if data is None:
        return 1

    try:
        slo_spec = data.get("slo", {}) if isinstance(data, dict) else {}
        slo = SLODefinition(
            name=slo_spec.get("name", "cli-slo"),
            service_name=slo_spec.get(
                "service_name", slo_spec.get("name", "cli-slo")
            ),
            slo_type=SLOType(slo_spec.get("type", "availability")),
            target=float(
                args.target if args.target is not None
                else slo_spec.get("target", 99.9)
            ),
        )
        metrics = [
            SLIMetric(
                timestamp=datetime.fromisoformat(m["timestamp"]),
                service_name=m.get("service_name", slo.name),
                slo_type=slo.slo_type,
                good_events=int(m.get("good_events", 0)),
                total_events=int(m.get("total_events", 0)),
            )
            for m in (data.get("metrics", []) if isinstance(data, dict) else data)
        ]
    except (KeyError, TypeError, ValueError) as e:
        print(f"Error: Invalid burn-rate input: {e}")
        return 1

    now = None
    if getattr(args, "at", None):
        try:
            now = datetime.fromisoformat(args.at)
        except ValueError:
            print(f"Error: Invalid --at timestamp: {args.at}")
            return 1

    alerts = BurnRateAnalyzer().evaluate_alert_policy(
        slo, metrics, current_time=now
    )

    if output_format == "json":
        print(json.dumps([_dump(a) for a in alerts], indent=2, default=str))
    else:
        lines = ["", f"BURN-RATE ALERT POLICY  (target {slo.target}%)",
                 "=" * 60]
        for a in alerts:
            state = ("FIRED" if a.fired else
                     "insufficient traffic" if a.insufficient_traffic
                     else "quiet")
            lines.append(
                f"  {a.tier:10} [{state}]  long {a.long_window_hours:g}h="
                f"{a.long_burn_rate:.2f}x  short "
                f"{a.short_window_hours * 60:.0f}m={a.short_burn_rate:.2f}x  "
                f"threshold {a.threshold:g}x"
            )
            for rec in a.recommendations:
                lines.append(f"    - {rec}")
        print("\n".join(lines))

    return 1 if any(a.fired for a in alerts) else 0


def run_cache_warmup(args, output_format: str = "text") -> int:
    """`verdandi cache warmup <buckets.json>`.

    Input: [{"hits": int, "misses": int}, ...] in time order, or
    {"buckets": [...], "db_load": [...]} to add the DB-load correlate.
    """
    from Asgard.Verdandi.Cache.services.warmup_analyzer import WarmupAnalyzer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1

    if isinstance(data, dict):
        buckets = data.get("buckets", [])
        db_load = data.get("db_load")
    else:
        buckets, db_load = data, None
    if not isinstance(buckets, list) or not buckets:
        print("Error: Expected a JSON array of {hits, misses} buckets.")
        return 1

    result = WarmupAnalyzer().analyze(buckets, db_load_series=db_load)

    if output_format == "json":
        print(json.dumps(_dump(result), indent=2, default=str))
    else:
        state = getattr(result.state, "value", result.state)
        lines = ["", "CACHE WARM-UP TRAJECTORY", "=" * 60,
                 f"  State:    {state}",
                 f"  Severity: {result.severity}",
                 f"  Alert suppressed: {result.suppress_alert}"]
        for note in result.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))

    return 1 if result.severity == "critical" else 0


def run_cache_stampede(args, output_format: str = "text") -> int:
    """`verdandi cache stampede <access_log.json>`.

    Input: JSON array of {key, t, hit, recompute_ms?, ttl_s?} access-log
    records.
    """
    from Asgard.Verdandi.Cache.services.stampede_analyzer import StampedeAnalyzer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    records = data.get("access_log", data) if isinstance(data, dict) else data
    if not isinstance(records, list) or not records:
        print("Error: Expected a non-empty JSON array of access-log records.")
        return 1

    analyzer = StampedeAnalyzer()
    kwargs = {}
    beta = getattr(args, "beta", None)
    if beta is not None:
        kwargs["beta"] = beta

    try:
        report = analyzer.analyze(records, **kwargs)
    except (TypeError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    if output_format == "json":
        print(json.dumps(_dump(report), indent=2, default=str))
    else:
        lines = ["", "CACHE STAMPEDE ANALYSIS", "=" * 60,
                 f"  Status: {report.status}",
                 f"  Keys analyzed: {report.total_keys_analyzed}",
                 f"  Flagged keys:  {len(report.flagged_keys)}"]
        for rec in report.recommendations:
            lines.append(f"  ! {rec}")
        for note in report.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))

    return 1 if report.status == "critical" else 0


def run_pool_signature(args, output_format: str = "text") -> int:
    """`verdandi db pool-signature <latencies.json>`.

    Input: [latency_ms, ...] or
    {"latencies_ms": [...], "acquisition_waits_ms": [...]}.
    """
    from Asgard.Verdandi.Database.services.pool_signature_detector import (
        PoolSignatureDetector,
    )

    data = _load_json(args.metrics_file)
    if data is None:
        return 1

    if isinstance(data, dict):
        latencies = data.get("latencies_ms", [])
        waits = data.get("acquisition_waits_ms")
    else:
        latencies, waits = data, None
    if not isinstance(latencies, list) or not latencies:
        print("Error: Expected a JSON array of latencies in ms.")
        return 1

    signature = PoolSignatureDetector().detect(
        latencies, acquisition_wait_samples=waits
    )

    if output_format == "json":
        print(json.dumps(_dump(signature), indent=2, default=str))
    else:
        classification = getattr(
            signature.classification, "value", signature.classification
        )
        lines = ["", "DB POOL-EXHAUSTION SIGNATURE", "=" * 60,
                 f"  Classification: {classification}",
                 f"  Confidence:     {signature.confidence}"]
        if signature.mean_queue_wait_ms is not None:
            lines.append(
                f"  Mean queue wait: {signature.mean_queue_wait_ms:.1f} ms"
            )
        for w in signature.warnings:
            lines.append(f"  ! {w}")
        for rec in signature.recommendations:
            lines.append(f"  - {rec}")
        print("\n".join(lines))

    classification = str(getattr(
        signature.classification, "value", signature.classification
    ))
    return 1 if classification == "pool_exhaustion" else 0


def run_db_budget(args, output_format: str = "text") -> int:
    """`verdandi db budget <input.json>`.

    Input: {"config": {...QueryBudgetConfig fields...},
            "durations_ms": [...], "units": [...]}
    """
    from Asgard.Verdandi.Database.models.database_models import QueryBudgetConfig
    from Asgard.Verdandi.Database.services.query_budget import QueryBudgetAnalyzer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object.")
        return 1

    durations = data.get("durations_ms")
    units = data.get("units")
    if not isinstance(durations, list) or not isinstance(units, list):
        print("Error: 'durations_ms' and 'units' arrays are required.")
        return 1

    try:
        config = QueryBudgetConfig.model_validate(data.get("config", {}))
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid budget config: {e}")
        return 1

    result = QueryBudgetAnalyzer().evaluate(config, durations, units)

    if output_format == "json":
        print(json.dumps(_dump(result), indent=2, default=str))
    else:
        lines = ["", "DATABASE QUERY BUDGET EVALUATION", "=" * 60,
                 f"  Passed: {result.good}/{result.total}"]
        if result.sli_passed_fraction is not None:
            lines.append(f"  SLI passed fraction: {result.sli_passed_fraction:.4f}")
        lines.append(f"  Violations: {len(result.violations)}")
        for note in result.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))

    return 1 if result.violations else 0


def run_db_queries_per_class(args, output_format: str = "text") -> int:
    """`verdandi db queries <input.json> --per-class`.

    Input: {"queries": [...QueryMetricsInput...], "baseline": {fingerprint:
            [durations_ms...]}?} or a bare JSON array of queries.
    """
    from Asgard.Verdandi.Database.models.database_models import QueryMetricsInput
    from Asgard.Verdandi.Database.services.query_metrics import (
        QueryMetricsCalculator,
    )

    data = _load_json(args.metrics_file)
    if data is None:
        return 1

    if isinstance(data, dict):
        raw_queries = data.get("queries", [])
        baseline = data.get("baseline")
    else:
        raw_queries, baseline = data, None
    if not isinstance(raw_queries, list) or not raw_queries:
        print("Error: Expected a non-empty array of queries.")
        return 1

    try:
        queries = [QueryMetricsInput.model_validate(q) for q in raw_queries]
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid query input: {e}")
        return 1

    threshold = getattr(args, "slow_threshold", None) or 100.0
    calculator = QueryMetricsCalculator(slow_query_threshold_ms=threshold)
    classes = calculator.analyze_by_fingerprint(queries, baseline=baseline)

    if output_format == "json":
        print(json.dumps([_dump(c) for c in classes], indent=2, default=str))
    else:
        lines = ["", "DATABASE QUERY METRICS BY CLASS (fingerprint)", "=" * 60]
        for c in classes:
            lines.append(
                f"  {c.fingerprint[:60]:<60} n={c.count:<5} "
                f"p50={c.p50_ms:.1f}ms p95={c.p95_ms:.1f}ms "
                f"shift={c.shift_detected}"
            )
            for note in c.shift_notes:
                lines.append(f"      ! {note}")
        print("\n".join(lines))

    return 1 if any(c.shift_detected for c in classes) else 0
