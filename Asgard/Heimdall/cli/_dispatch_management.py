"""
Heimdall CLI - Management command dispatcher.

Handles routing for: baseline, init-linter, ratings, gate, profiles,
history, new-code, issues, sbom, codefix, mcp-server, dashboard, scan.
"""

import sys

from Asgard.Heimdall.cli.handlers import (
    run_baseline_command,
    run_init_linter,
    run_ratings_analysis,
    run_gate_evaluation,
    run_profiles_command,
    run_history_command,
    run_new_code_detect,
    run_issues_command,
    run_sbom_generation,
    run_codefix_suggestions,
    run_mcp_server,
    run_dashboard,
    run_full_scan,
)


def dispatch_management(args, verbose: bool) -> None:
    """Dispatch management and utility commands."""

    if args.command == "baseline":
        if not hasattr(args, 'baseline_command') or args.baseline_command is None:
            print("Error: Please specify a baseline subcommand. Available subcommands:")
            print("  show     Display a summary report of all baselined violations")
            print("  list     List baseline entries, optionally filtered by type or file")
            print("  clean    Remove expired baseline entries")
            print("  remove   Remove a single baseline entry by ID (requires --id)")
            print("\nUse 'heimdall baseline <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        if args.baseline_command in ("show", "list", "clean", "remove"):
            sys.exit(run_baseline_command(args, verbose))
        else:
            print(f"Unknown baseline command: {args.baseline_command}")
            sys.exit(1)

    elif args.command == "init-linter":
        sys.exit(run_init_linter(args, verbose))

    elif args.command == "ratings":
        sys.exit(run_ratings_analysis(args, verbose))

    elif args.command == "gate":
        sys.exit(run_gate_evaluation(args, verbose))

    elif args.command == "profiles":
        if not hasattr(args, "profiles_command") or args.profiles_command is None:
            print("Error: Please specify a profiles subcommand. Available subcommands:")
            print("  list     List all available quality profiles")
            print("  show     Show details for a specific profile")
            print("  assign   Assign a profile to a project")
            print("  create   Create a new custom profile")
            print("\nUse 'heimdall profiles <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)
        sys.exit(run_profiles_command(args, verbose))

    elif args.command == "history":
        if not hasattr(args, "history_command") or args.history_command is None:
            print("Error: Please specify a history subcommand. Available subcommands:")
            print("  show    Show recorded analysis snapshots")
            print("  trends  Show metric trend directions")
            print("\nUse 'heimdall history <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)
        sys.exit(run_history_command(args, verbose))

    elif args.command == "new-code":
        if not hasattr(args, "new_code_command") or args.new_code_command is None:
            print("Error: Please specify a new-code subcommand. Available subcommands:")
            print("  detect  Show which files are considered new or modified code")
            print("\nUse 'heimdall new-code <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)
        sys.exit(run_new_code_detect(args, verbose))

    elif args.command == "issues":
        sys.exit(run_issues_command(args, verbose))

    elif args.command == "sbom":
        sys.exit(run_sbom_generation(args, verbose))

    elif args.command == "codefix":
        sys.exit(run_codefix_suggestions(args, verbose))

    elif args.command == "mcp-server":
        sys.exit(run_mcp_server(args, verbose))

    elif args.command == "dashboard":
        sys.exit(run_dashboard(args, verbose))

    elif args.command == "scan":
        sys.exit(run_full_scan(args, verbose))

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)
