"""
CLI handlers for Bragi's Calibration surface, exposed via the Heimdall CLI:

- calibrate run              derive a local per-language profile from
                              sampled metric distributions (Bragi
                              Calibration/services/local_calibrator.py)
- calibrate validate-rules   score empirical rule validity from bugfix-vs-
                              clean file observations (rule_validator.py)

Both are thin wrappers: JSON input file in, JSON or human-readable text out.
"""

import argparse
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


def run_calibrate(args: argparse.Namespace, verbose: bool = False) -> int:
    """`heimdall calibrate run <input.json>`.

    Input: {"language": "python", "metric_samples": {metric: [values...]},
            "anchor_profile": {...LanguageProfile fields...},
            "min_sample_size": 30?}
    """
    from Asgard.Bragi.Calibration.models.calibration_models import LanguageProfile
    from Asgard.Bragi.Calibration.services.local_calibrator import (
        MIN_SAMPLE_SIZE,
        calibrate,
    )

    data = _load_json(args.input_file)
    if data is None:
        return 1
    if not isinstance(data, dict):
        print("Error: Expected a JSON object.")
        return 1

    language = data.get("language")
    metric_samples = data.get("metric_samples")
    anchor_profile_data = data.get("anchor_profile")
    if not language or not isinstance(metric_samples, dict) or not anchor_profile_data:
        print(
            "Error: Expected 'language', 'metric_samples' "
            "({metric: [values...]}), and 'anchor_profile' fields."
        )
        return 1

    try:
        anchor_profile = LanguageProfile.model_validate(anchor_profile_data)
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid anchor_profile: {e}")
        return 1

    min_sample_size = int(data.get("min_sample_size", MIN_SAMPLE_SIZE))
    profile, run = calibrate(
        language, metric_samples, anchor_profile, min_sample_size=min_sample_size
    )

    output_format = getattr(args, "format", "text")
    if output_format == "json":
        print(json.dumps({
            "profile": _dump(profile) if profile else None,
            "run": _dump(run),
        }, indent=2, default=str))
    else:
        lines = ["", "LOCAL CALIBRATION RUN", "=" * 60,
                 f"  Language:    {run.language}",
                 f"  Sample size: {run.sample_size}",
                 f"  Refused:     {run.refused}"]
        if run.refused:
            lines.append(f"  Reason:      {run.refusal_reason}")
        if run.clamped_metrics:
            lines.append(f"  Clamped metrics: {', '.join(run.clamped_metrics)}")
        print("\n".join(lines))

        if profile is not None and getattr(args, "write", False):
            from Asgard.Bragi.Calibration.services.local_calibrator import (
                write_local_profile,
            )
            path = write_local_profile(profile)
            print(f"  Wrote local profile to: {path}")

    return 1 if run.refused else 0


def run_validate_rules(args: argparse.Namespace, verbose: bool = False) -> int:
    """`heimdall validate-rules <input.json>`.

    Input: {"rule_id": "...", "observations": [{"file_path", "loc",
            "violation_count", "touched_by_bugfix"}, ...],
            "burn_in_threshold": 15?}
    """
    from Asgard.Bragi.Calibration.services.rule_validator import (
        BURN_IN_THRESHOLD,
        FileObservation,
        compute_rule_validity,
    )

    data = _load_json(args.input_file)
    if data is None:
        return 1
    if not isinstance(data, dict) or "rule_id" not in data:
        print("Error: Expected a JSON object with 'rule_id' and 'observations'.")
        return 1

    raw_observations = data.get("observations", [])
    if not isinstance(raw_observations, list):
        print("Error: 'observations' must be an array.")
        return 1

    try:
        observations = [
            FileObservation(
                file_path=o["file_path"],
                loc=int(o["loc"]),
                violation_count=int(o["violation_count"]),
                touched_by_bugfix=bool(o["touched_by_bugfix"]),
            )
            for o in raw_observations
        ]
    except (KeyError, TypeError, ValueError) as e:
        print(f"Error: Invalid observation entry: {e}")
        return 1

    report = compute_rule_validity(
        data["rule_id"],
        observations,
        burn_in_threshold=int(data.get("burn_in_threshold", BURN_IN_THRESHOLD)),
    )

    output_format = getattr(args, "format", "text")
    if output_format == "json":
        print(json.dumps(_dump(report), indent=2, default=str))
    else:
        verdict = getattr(report.verdict, "value", report.verdict)
        lines = ["", "RULE VALIDITY REPORT", "=" * 60,
                 f"  Rule:    {report.rule_id}",
                 f"  Verdict: {verdict}",
                 f"  n:       {report.n}"]
        if report.lift is not None:
            lines.append(f"  Lift:    {report.lift:.3f}")
        if report.note:
            lines.append(f"  Note:    {report.note}")
        print("\n".join(lines))

    verdict = str(getattr(report.verdict, "value", report.verdict))
    return 1 if verdict == "neutral" else 0
