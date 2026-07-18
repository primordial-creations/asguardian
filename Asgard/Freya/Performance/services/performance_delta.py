"""
Freya Performance Delta Snapshot

The delta is the lab's ground truth (DEEPTHINK_03): absolute lab
numbers are weak evidence, but a shift between two runs in the same
controlled environment isolates the code as the changing variable.

Stores a simple JSON snapshot (performance_baseline.json) beside the
output and computes per-metric deltas against it.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

#: Metrics captured in the snapshot (all lab data).
SNAPSHOT_METRICS = (
    "lcp_ms", "fcp_ms", "cls", "tbt_ms", "ttfb_ms", "page_load_ms",
    "js_bytes", "image_bytes", "font_bytes", "render_blocking_count",
)


def snapshot_from_report(report: Any) -> Dict[str, float]:
    """Extract a metric snapshot dict from a PerformanceReport."""
    snapshot: Dict[str, float] = {}
    metrics = getattr(report, "page_load_metrics", None)
    if metrics is not None:
        pairs = {
            "lcp_ms": metrics.largest_contentful_paint,
            "fcp_ms": metrics.first_contentful_paint,
            "cls": metrics.cumulative_layout_shift,
            "tbt_ms": metrics.total_blocking_time,
            "ttfb_ms": metrics.time_to_first_byte,
            "page_load_ms": metrics.page_load,
        }
        for key, value in pairs.items():
            if value is not None:
                snapshot[key] = float(value)
    resources = getattr(report, "resource_timing_report", None)
    if resources is not None:
        snapshot["js_bytes"] = float(resources.script_size)
        snapshot["image_bytes"] = float(resources.image_size)
        snapshot["font_bytes"] = float(resources.font_size)
        snapshot["render_blocking_count"] = float(resources.render_blocking_count)
    return snapshot


def compute_deltas(
    current: Dict[str, float],
    previous: Dict[str, float],
) -> Dict[str, float]:
    """Per-metric delta (current - previous) for metrics present in both."""
    return {
        key: current[key] - previous[key]
        for key in current
        if key in previous
    }


def load_snapshot(path: str) -> Optional[Dict[str, float]]:
    """Load a stored snapshot; None when absent or unreadable."""
    snapshot_file = Path(path)
    if not snapshot_file.exists():
        return None
    try:
        data = json.loads(snapshot_file.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    metrics = data.get("metrics") if isinstance(data, dict) else None
    if not isinstance(metrics, dict):
        return None
    return {str(k): float(v) for k, v in metrics.items()
            if isinstance(v, (int, float))}


def save_snapshot(path: str, snapshot: Dict[str, float], url: str = "") -> None:
    """Persist a snapshot as performance_baseline.json."""
    snapshot_file = Path(path)
    snapshot_file.parent.mkdir(parents=True, exist_ok=True)
    snapshot_file.write_text(json.dumps(
        {
            "note": "Lab Data — synthetic baseline for delta comparison",
            "url": url,
            "metrics": snapshot,
        },
        indent=2,
    ))


def apply_delta_snapshot(report: Any, path: str) -> Dict[str, float]:
    """
    Compute deltas for a report against the stored snapshot (if any),
    then update the snapshot with the current run. Returns the deltas.
    """
    current = snapshot_from_report(report)
    previous = load_snapshot(path)
    deltas = compute_deltas(current, previous) if previous else {}
    save_snapshot(path, current, url=getattr(report, "url", "") or "")
    return deltas
