"""
CLI handlers for the `system` command group:

- system psi         PSI (pressure stall information) severity analysis
- system throttle     cgroup CPU-throttle analysis
- system correlate    USE/RED cross-signal correlation (saturation vs. latency)

All are thin wrappers over Asgard.Verdandi.System.services.*: JSON metrics
file in, JSON or human-readable text out.
"""

import json
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


def run_system_psi(args, output_format: str = "text") -> int:
    """`verdandi system psi <snapshot.json>`.

    Input: {"snapshot": {...PsiSnapshot fields...}, "previous": {...}?}
    or {"snapshots": {"cpu": {...}, "memory": {...}, "io": {...}}} for a
    cross-resource diagnosis.
    """
    from Asgard.Verdandi.System.models.system_models import PsiSnapshot
    from Asgard.Verdandi.System.services.psi_analyzer import PsiAnalyzer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object.")
        return 1

    analyzer = PsiAnalyzer()
    try:
        if "snapshots" in data:
            snapshots = {
                k: PsiSnapshot.model_validate(v)
                for k, v in data["snapshots"].items()
            }
            report = analyzer.analyze_cross_resource(snapshots)
        else:
            snapshot = PsiSnapshot.model_validate(data.get("snapshot", data))
            previous = data.get("previous")
            report = analyzer.analyze(
                snapshot,
                previous=PsiSnapshot.model_validate(previous) if previous else None,
            )
    except (KeyError, TypeError, ValueError) as e:
        print(f"Error: Invalid PSI input: {e}")
        return 1

    if output_format == "json":
        print(json.dumps(_dump(report), indent=2, default=str))
    else:
        lines = ["", "PSI (PRESSURE STALL INFORMATION) ANALYSIS", "=" * 60,
                 f"  Severity:   {report.severity}"]
        if report.trajectory:
            lines.append(f"  Trajectory: {report.trajectory}")
        lines.append(f"  Micro-burst detected: {report.micro_burst_detected}")
        if report.cross_resource_diagnosis:
            lines.append(f"  Cross-resource: {report.cross_resource_diagnosis}")
        for note in report.notes:
            lines.append(f"  - {note}")
        for rec in report.recommendations:
            lines.append(f"  ! {rec}")
        print("\n".join(lines))

    return 1 if report.severity in ("warning", "critical") else 0


def run_system_throttle(args, output_format: str = "text") -> int:
    """`verdandi system throttle <cgroup_stats.json>`.

    Input: {...CgroupCpuStats fields...} (cpu_quota_us, nr_periods,
    nr_throttled, throttled_time_ns, ...).
    """
    from Asgard.Verdandi.System.models.system_models import CgroupCpuStats
    from Asgard.Verdandi.System.services.cgroup_analyzer import CgroupAnalyzer

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object of cgroup CPU stats.")
        return 1

    try:
        stats = CgroupCpuStats.model_validate(data)
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid cgroup stats input: {e}")
        return 1

    report = CgroupAnalyzer().analyze(stats)

    if output_format == "json":
        print(json.dumps(_dump(report), indent=2, default=str))
    else:
        lines = ["", "CGROUP CPU THROTTLE ANALYSIS", "=" * 60,
                 f"  Verdict: {report.verdict}",
                 f"  Limit-induced latency: {report.limit_induced_latency}"]
        if report.throttle_ratio is not None:
            lines.append(f"  Throttle ratio: {report.throttle_ratio:.4f}")
        if report.avg_stall_ms is not None:
            lines.append(f"  Avg stall: {report.avg_stall_ms:.2f} ms")
        for note in report.notes:
            lines.append(f"  - {note}")
        for rec in report.recommendations:
            lines.append(f"  ! {rec}")
        print("\n".join(lines))

    return 1 if report.limit_induced_latency else 0


def run_system_correlate(args, output_format: str = "text") -> int:
    """`verdandi system correlate <series.json>`.

    Input: {"saturation": [...], "p99_duration_ms": [...],
            "max_lag": 5, "rate": [...]?, "errors": [...]?}
    """
    from Asgard.Verdandi.System.services.use_red_correlator import UseRedCorrelator

    data = _load_json(args.metrics_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object with 'saturation' and "
              "'p99_duration_ms' arrays.")
        return 1

    saturation = data.get("saturation")
    p99 = data.get("p99_duration_ms")
    if not isinstance(saturation, list) or not isinstance(p99, list):
        print("Error: 'saturation' and 'p99_duration_ms' arrays are required.")
        return 1

    try:
        result = UseRedCorrelator().correlate(
            saturation,
            p99,
            max_lag=int(data.get("max_lag", 5)),
            rate=data.get("rate"),
            errors=data.get("errors"),
        )
    except (TypeError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    if output_format == "json":
        print(json.dumps(_dump(result), indent=2, default=str))
    else:
        lines = ["", "USE/RED CROSS-SIGNAL CORRELATION", "=" * 60,
                 f"  Verdict: {result.verdict}",
                 f"  Ordering confirmed: {result.ordering_confirmed}"]
        if result.best_lag is not None:
            lines.append(f"  Best lag: {result.best_lag}")
        if result.best_correlation is not None:
            lines.append(f"  Best correlation: {result.best_correlation:.4f}")
        for note in result.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))

    return 0 if result.ordering_confirmed else 1
