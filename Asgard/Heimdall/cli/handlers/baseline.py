import argparse
import json
from pathlib import Path

from Asgard.Baseline.baseline_manager import BaselineManager


def run_baseline_command(args: argparse.Namespace, verbose: bool = False) -> int:
    project_path = Path(args.path).resolve()
    baseline_file = getattr(args, "baseline_file", ".asgard-baseline.json")
    output_format = getattr(args, "format", "text")
    baseline_subcommand = getattr(args, "baseline_command", None)

    if baseline_subcommand is None:
        print("Error: Please specify a baseline command: show, list, clean, remove")
        return 1

    try:
        manager = BaselineManager(project_path=project_path, baseline_file=baseline_file)

        if baseline_subcommand == "show":
            report = manager.generate_report(output_format)
            print(report)
            return 0

        elif baseline_subcommand == "list":
            violation_type = getattr(args, "type", None)
            file_pattern = getattr(args, "file", None)
            entries = manager.list_entries(
                violation_type=violation_type,
                file_path=file_pattern,
            )
            if output_format == "json":
                print(json.dumps(
                    [
                        {
                            "violation_id": e.violation_id,
                            "file_path": e.file_path,
                            "line_number": e.line_number,
                            "violation_type": e.violation_type,
                            "message": e.message,
                            "reason": e.reason,
                            "expired": e.is_expired,
                        }
                        for e in entries
                    ],
                    indent=2,
                ))
            else:
                if not entries:
                    print("No baseline entries found.")
                else:
                    print(f"\nBaseline Entries ({len(entries)}):")
                    print("-" * 60)
                    for entry in entries:
                        status = "[EXPIRED]" if entry.is_expired else ""
                        print(
                            f"  {entry.file_path}:{entry.line_number}"
                            f" [{entry.violation_type}] {status}"
                        )
                        if entry.reason:
                            print(f"    Reason: {entry.reason}")
                        print(f"    ID: {entry.violation_id}")
            return 0

        elif baseline_subcommand == "clean":
            removed = manager.clean_expired()
            print(f"Removed {removed} expired baseline entries.")
            return 0

        elif baseline_subcommand == "remove":
            violation_id = getattr(args, "id", None)
            if not violation_id:
                print("Error: --id is required for the remove subcommand.")
                return 1
            removed = manager.remove_entry(violation_id)
            if removed:
                print(f"Removed baseline entry: {violation_id}")
                return 0
            else:
                print(f"No baseline entry found with ID: {violation_id}")
                return 1

        else:
            print(f"Unknown baseline command: {baseline_subcommand}")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1
