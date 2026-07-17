"""
Compat Handler - `forseti compat check` on the unified compatibility engine.
"""

import argparse
import json
import sys
from pathlib import Path

from Asgard.Forseti.cli._handler_runner import (
    EXIT_GATE_FAILURE,
    EXIT_INPUT_ERROR,
    EXIT_OK,
)
from Asgard.Forseti.Compatibility import (
    CompatEngineService,
    CompatMode,
    CompatReport,
    CompatStatus,
    JsonFileTelemetrySource,
)

_MODE_MAP = {
    "backward": CompatMode.BACKWARD,
    "forward": CompatMode.FORWARD,
    "full": CompatMode.FULL,
    "backward-transitive": CompatMode.BACKWARD_TRANSITIVE,
    "forward-transitive": CompatMode.FORWARD_TRANSITIVE,
    "full-transitive": CompatMode.FULL_TRANSITIVE,
}


def render_compat_text(report: CompatReport) -> str:
    """Human-readable compat report with the Blast Radius Receipt."""
    lines = [
        "=" * 60,
        "Unified Compatibility Report",
        "=" * 60,
        f"Format: {report.format.value}",
        f"Mode: {report.mode.value}",
        f"Old: {report.source or 'N/A'}",
        f"New: {report.target or 'N/A'}",
        f"Status: {report.status.value.upper()}",
        f"Score: {report.score}/100 (confidence: {report.confidence})",
        f"Structural breaks: {report.structural_breaks}  "
        f"Semantic hazards: {report.semantic_hazards}",
        "-" * 60,
    ]
    if report.changes:
        lines.append("Changes:")
        for change in report.changes:
            tier = (f"structural={change.impact.structural.value}/"
                    f"semantic={change.impact.semantic.value}")
            lines.append(f"  [{change.rule_id}] ({change.direction.value}, {tier})")
            lines.append(f"    {change.location}: {change.message}")
            if change.mitigation:
                lines.append(f"    Mitigation: {change.mitigation}")
    if report.score_receipt:
        lines.append("")
        lines.append("Blast Radius Receipt:")
        for line in report.score_receipt:
            lines.append(f"  {line}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _handle_compat(args: argparse.Namespace) -> int:
    """Handle `forseti compat` commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti compat --help' for options.")
        return EXIT_GATE_FAILURE

    if args.command == "check":
        specs = list(args.specs)
        if len(specs) < 2:
            print("Error: compat check needs at least two specs (old new)",
                  file=sys.stderr)
            return EXIT_INPUT_ERROR
        for spec in specs:
            if not Path(spec).is_file():
                print(f"Error: file not found: {spec}", file=sys.stderr)
                return EXIT_INPUT_ERROR

        telemetry = None
        usage_report = getattr(args, "usage_report", None)
        if usage_report:
            try:
                telemetry = JsonFileTelemetrySource(usage_report)
            except Exception as exc:
                print(f"Error: cannot read usage report: {exc}", file=sys.stderr)
                return EXIT_INPUT_ERROR

        mode = _MODE_MAP[getattr(args, "mode", "backward")]
        engine = CompatEngineService(telemetry=telemetry)
        try:
            if len(specs) > 2 or mode.is_transitive:
                report = engine.check_history(
                    specs, format_hint=args.format_hint, mode=mode,
                )
            else:
                report = engine.check(
                    specs[0], specs[1], format_hint=args.format_hint, mode=mode,
                )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_INPUT_ERROR

        output_format = getattr(args, "format", "text")
        if output_format == "json":
            print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
        else:
            print(render_compat_text(report))

        if report.changes and report.changes[0].rule_id == "COMPAT-PARSE-ERROR":
            return EXIT_INPUT_ERROR
        min_score = getattr(args, "min_score", None)
        if min_score is not None and report.score < min_score:
            return EXIT_GATE_FAILURE
        if report.status == CompatStatus.FAILED:
            return EXIT_GATE_FAILURE
        return EXIT_OK

    return EXIT_GATE_FAILURE


def engine_score_extras(old_path: str, new_path: str, format_hint: str,
                        mode: str = "backward") -> dict:
    """
    Best-effort unified-engine score fields for legacy check-compat JSON
    output ('plus new score field', plan 01 step 3). Returns {} on failure
    so legacy behavior is never disturbed.
    """
    try:
        engine = CompatEngineService()
        report = engine.check(
            old_path, new_path,
            format_hint=format_hint,
            mode=_MODE_MAP.get(mode, CompatMode.BACKWARD),
        )
        return {
            "score": report.score,
            "compat_status": report.status.value,
            "score_receipt": report.score_receipt,
        }
    except Exception:
        return {}
