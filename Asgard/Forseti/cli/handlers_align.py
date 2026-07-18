"""
Align Handler - `forseti align check` / `forseti align discover` (plan 07).
"""

import argparse
import json
import sys
from pathlib import Path

from Asgard.Forseti.Alignment.services._discover_helpers import discover, write_config
from Asgard.Forseti.Alignment.services.alignment_loader_service import check_config, load_config
from Asgard.Forseti.cli._handler_runner import EXIT_GATE_FAILURE, EXIT_INPUT_ERROR, EXIT_OK


def _render_text(findings, report) -> str:
    lines = ["=" * 60, "Cross-Format Alignment Report", "=" * 60]
    for entity in report.entities_checked:
        lines.append(f"\nEntity: {entity}")
        entity_findings = [f for f in findings if f.message.startswith(f"{entity}.")]
        if not entity_findings:
            lines.append("  (no findings)")
        for finding in entity_findings:
            lines.append(f"  [{finding.rule_id}] {finding.severity.value.upper()}: {finding.message}")
    lines.append("-" * 60)
    lines.append(
        f"CRITICAL: {report.critical_count}  WARNING: {report.warning_count}  INFO: {report.info_count}"
    )
    lines.append(f"Build: {'PASS' if report.build_passes else 'FAIL'}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _handle_align(args: argparse.Namespace) -> int:
    """Handle `forseti align` commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti align --help' for options.")
        return EXIT_GATE_FAILURE

    if args.command == "check":
        config_path = Path(args.config)
        if not config_path.is_file():
            print(f"Error: alignment config not found: {config_path}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        config = load_config(str(config_path))
        try:
            findings, report = check_config(
                config, base_dir=str(config_path.parent), entity_filter=args.entity or ""
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_INPUT_ERROR

        if getattr(args, "format", "text") == "json":
            payload = {
                "findings": [f.model_dump(mode="json") for f in findings],
                "report": report.model_dump(mode="json"),
            }
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(_render_text(findings, report))
        return EXIT_OK if report.build_passes else EXIT_GATE_FAILURE

    if args.command == "discover":
        config = discover(list(args.paths))
        write_config(config, args.output)
        print(f"Drafted {len(config.entities)} candidate entities -> {args.output}")
        print("Review and edit before using with 'align check' - heuristics never enforce.")
        return EXIT_OK

    return 1
