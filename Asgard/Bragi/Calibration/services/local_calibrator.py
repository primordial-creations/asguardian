"""
Local Percentile Calibrator (Plan 05 Phase B).

DEEPTHINK_02's "ultimate evolution": compute this project's own empirical
CDF per metric and derive P90/P95 anchors, guardrailed so a uniformly bad
codebase cannot normalize its own rot.

Pure computation - callers supply the raw per-function/per-file metric
samples (typically from Quality's metric extraction, PRODUCTION context
only via `Bragi.common.context_classifier`, generated excluded). This
module has no scanning/I-O responsibility of its own beyond writing the
resulting profile YAML.
"""

import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import yaml

from Asgard.Bragi.Calibration.models.calibration_models import (
    CalibrationRun,
    LanguageProfile,
    ThresholdSpec,
)
from Asgard.Bragi.Calibration.services.profile_service import LOCAL_PROFILE_RELATIVE_PATH

# Guardrails (Plan 05 Sec.3.2).
MIN_SAMPLE_SIZE = 200
CLAMP_FRACTION = 0.5  # local thresholds clamp to +-50% of the language profile value


def percentile(samples: Sequence[float], pct: float) -> float:
    """
    Nearest-rank percentile (pct in [0, 100]) over a sorted copy of `samples`.

    Deterministic: no interpolation-order ambiguity, stable across runs for
    the same input multiset.
    """
    if not samples:
        return 0.0
    ordered = sorted(samples)
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    rank = math.ceil((pct / 100.0) * len(ordered))
    rank = max(1, min(rank, len(ordered)))
    return ordered[rank - 1]


def _clamp(local_value: float, anchor_value: float, fraction: float = CLAMP_FRACTION) -> float:
    """Clamp `local_value` to within +-fraction of `anchor_value`."""
    if anchor_value <= 0:
        return local_value
    lo = anchor_value * (1.0 - fraction)
    hi = anchor_value * (1.0 + fraction)
    return min(max(local_value, lo), hi)


def calibrate(
    language: str,
    metric_samples: Dict[str, List[float]],
    anchor_profile: LanguageProfile,
    min_sample_size: int = MIN_SAMPLE_SIZE,
) -> "tuple[Optional[LanguageProfile], CalibrationRun]":
    """
    Compute a local profile from raw metric samples.

    Refuses (returns `(None, run_with_refused=True)`) when every metric's
    sample count is below `min_sample_size` - a partial sample for one
    metric among several measured ones is fine; total starvation is not.

    Each derived P95 anchor is clamped to +-50% of the corresponding
    language-profile threshold's `fail` value (or scalar value) so a
    uniformly bad codebase cannot normalize its own rot into "clean".
    """
    total_samples = sum(len(v) for v in metric_samples.values())
    if total_samples < min_sample_size:
        run = CalibrationRun(
            sample_size=total_samples, language=language, refused=True,
            refusal_reason=(
                f"insufficient sample: {total_samples} data point(s) collected, "
                f"minimum {min_sample_size} required"
            ),
        )
        return None, run

    thresholds: Dict[str, ThresholdSpec] = {}
    scalars: Dict[str, float] = {}
    clamped_metrics: List[str] = []

    for metric_id, samples in metric_samples.items():
        if not samples:
            continue
        p95 = percentile(samples, 95)
        p90 = percentile(samples, 90)

        anchor_fail = None
        if metric_id in anchor_profile.thresholds:
            anchor_fail = anchor_profile.thresholds[metric_id].fail
        elif metric_id in anchor_profile.scalar_thresholds:
            anchor_fail = anchor_profile.scalar_thresholds[metric_id]

        clamped_p95 = p95
        if anchor_fail is not None:
            clamped_p95 = _clamp(p95, anchor_fail)
            if clamped_p95 != p95:
                clamped_metrics.append(metric_id)

        if metric_id in anchor_profile.thresholds:
            thresholds[metric_id] = ThresholdSpec(warn=p90, fail=clamped_p95)
        else:
            scalars[metric_id] = clamped_p95

    n = total_samples
    profile = LanguageProfile(
        language=language,
        provenance=f"local P95, {datetime.now().date().isoformat()}, n={n}",
        thresholds=thresholds,
        scalar_thresholds=scalars,
    )
    run = CalibrationRun(
        sample_size=n, language=language, refused=False, clamped_metrics=clamped_metrics,
    )
    return profile, run


def write_local_profile(profile: LanguageProfile, project_path: Optional[Path] = None) -> Path:
    """Persist a calibrated profile to `.asgard_cache/bragi_local_profile.yaml`."""
    project_path = Path(project_path or Path.cwd())
    out_path = project_path / LOCAL_PROFILE_RELATIVE_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = profile.model_dump(mode="json", exclude_none=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=True, default_flow_style=False)
    return out_path
