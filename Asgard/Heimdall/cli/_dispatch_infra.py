"""
Heimdall CLI - Infrastructure analysis command dispatcher.

Handles routing for: dependencies, architecture, coverage, syntax,
requirements, licenses, logic.
"""

import sys

from Asgard.Heimdall.cli.handlers import (
    run_deps_analysis,
    run_deps_export,
    run_arch_analysis,
    run_coverage_analysis,
    run_syntax_analysis,
    run_requirements_analysis,
    run_licenses_analysis,
    run_logic_analysis,
)

_INFRA_COMMANDS = {
    "dependencies", "architecture", "coverage", "syntax",
    "requirements", "licenses", "logic",
}


def handles_infra(command: str) -> bool:
    """Return True if this module handles the given command."""
    return command in _INFRA_COMMANDS


def dispatch_infra(args, verbose: bool) -> None:
    """Dispatch infrastructure analysis commands."""

    if args.command == "dependencies":
        if not hasattr(args, 'deps_command') or args.deps_command is None:
            print("Error: Please specify a dependencies subcommand. Available subcommands:")
            print("  analyze    Run full dependency analysis")
            print("  cycles     Detect circular import dependencies")
            print("  graph      Build and display the dependency graph")
            print("  modularity Score project modularity based on coupling between packages")
            print("  export     Export the dependency graph to mermaid, graphviz/dot, or json")
            print("\nUse 'heimdall dependencies <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        if args.deps_command == "export":
            sys.exit(run_deps_export(args, verbose))
        else:
            deps_types = {"analyze": "all", "cycles": "cycles", "graph": "all", "modularity": "modularity"}
            if args.deps_command in deps_types:
                sys.exit(run_deps_analysis(args, verbose, deps_types[args.deps_command]))
            else:
                print(f"Unknown dependencies command: {args.deps_command}")
                sys.exit(1)

    elif args.command == "architecture":
        if not hasattr(args, 'arch_command') or args.arch_command is None:
            print("Error: Please specify an architecture subcommand. Available subcommands:")
            print("  analyze   Run full architecture analysis")
            print("  solid     Validate SOLID principle adherence")
            print("  layers    Check architectural layer boundary compliance")
            print("  patterns  Detect design patterns and flag antipatterns")
            print("\nUse 'heimdall architecture <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        arch_types = {"analyze": "all", "solid": "solid", "layers": "layers", "patterns": "patterns", "hexagonal": "hexagonal"}
        if args.arch_command in arch_types:
            sys.exit(run_arch_analysis(args, verbose, arch_types[args.arch_command]))
        else:
            print(f"Unknown architecture command: {args.arch_command}")
            sys.exit(1)

    elif args.command == "coverage":
        if not hasattr(args, 'cov_command') or args.cov_command is None:
            print("Error: Please specify a coverage subcommand. Available subcommands:")
            print("  analyze      Run full coverage analysis")
            print("  gaps         Identify methods and classes with no test coverage")
            print("  suggestions  Generate suggested test cases for uncovered methods")
            print("\nUse 'heimdall coverage <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        cov_types = {"analyze": "all", "gaps": "gaps", "suggestions": "suggestions"}
        if args.cov_command in cov_types:
            sys.exit(run_coverage_analysis(args, verbose, cov_types[args.cov_command]))
        else:
            print(f"Unknown coverage command: {args.cov_command}")
            sys.exit(1)

    elif args.command == "syntax":
        if not hasattr(args, 'syntax_command') or args.syntax_command is None:
            print("Error: Please specify a syntax subcommand. Available subcommands:")
            print("  check   Run syntax and linting checks")
            print("  fix     Auto-fix syntax violations where safe to do so")
            print("\nUse 'heimdall syntax <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        if args.syntax_command == "check":
            sys.exit(run_syntax_analysis(args, verbose, fix_mode=False))
        elif args.syntax_command == "fix":
            sys.exit(run_syntax_analysis(args, verbose, fix_mode=True))
        else:
            print(f"Unknown syntax command: {args.syntax_command}")
            sys.exit(1)

    elif args.command == "requirements":
        if not hasattr(args, 'req_command') or args.req_command is None:
            print("Error: Please specify a requirements subcommand. Available subcommands:")
            print("  check   Report missing, unused, and mismatched requirements")
            print("  sync    Update requirements.txt to match actual imports")
            print("\nUse 'heimdall requirements <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        if args.req_command == "check":
            sys.exit(run_requirements_analysis(args, verbose, sync_mode=False))
        elif args.req_command == "sync":
            sys.exit(run_requirements_analysis(args, verbose, sync_mode=True))
        else:
            print(f"Unknown requirements command: {args.req_command}")
            sys.exit(1)

    elif args.command == "licenses":
        if not hasattr(args, 'lic_command') or args.lic_command is None:
            print("Error: Please specify a licenses subcommand. Available subcommands:")
            print("  check   Verify dependency licenses against allowed/denied lists")
            print("\nUse 'heimdall licenses <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        if args.lic_command == "check":
            sys.exit(run_licenses_analysis(args, verbose))
        else:
            print(f"Unknown licenses command: {args.lic_command}")
            sys.exit(1)

    elif args.command == "logic":
        if not hasattr(args, 'logic_command') or args.logic_command is None:
            print("Error: Please specify a logic subcommand. Available subcommands:")
            print("  duplication   Detect structurally duplicated logic blocks")
            print("  patterns      Detect inefficient patterns and logic antipatterns")
            print("  complexity    Calculate complexity for logic-heavy functions")
            print("  audit         Run all logic checks")
            print("\nUse 'heimdall logic <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        logic_types = {"duplication": "duplication", "patterns": "patterns", "complexity": "complexity", "audit": "audit"}
        if args.logic_command in logic_types:
            sys.exit(run_logic_analysis(args, verbose, analysis_type=logic_types[args.logic_command]))
        else:
            print(f"Unknown logic command: {args.logic_command}")
            sys.exit(1)

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)
