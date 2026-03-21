"""
Heimdall CLI - Analysis command dispatcher.

Handles routing for: quality, audit, security, performance, oop.
Delegates infrastructure commands (deps, arch, coverage, syntax,
requirements, licenses, logic) to _dispatch_infra.
"""

import sys

from Asgard.Heimdall.cli.handlers import (
    run_quality_analysis,
    run_complexity_analysis,
    run_duplication_analysis,
    run_smell_analysis,
    run_debt_analysis,
    run_maintainability_analysis,
    run_env_fallback_analysis,
    run_lazy_imports_analysis,
    run_forbidden_imports_analysis,
    run_datetime_analysis,
    run_typing_analysis,
    run_type_check_analysis,
    run_thread_safety_analysis,
    run_race_conditions_analysis,
    run_daemon_threads_analysis,
    run_future_leaks_analysis,
    run_blocking_async_analysis,
    run_resource_cleanup_analysis,
    run_error_handling_analysis,
    run_documentation_analysis,
    run_naming_analysis,
    run_bugs_analysis,
    run_js_analysis,
    run_ts_analysis,
    run_shell_analysis,
    run_config_secrets_analysis,
    run_hotspots_analysis,
    run_compliance_analysis,
    run_taint_analysis,
    run_security_analysis,
    run_performance_analysis,
    run_oop_analysis,
)
from Asgard.Heimdall.cli._dispatch_infra import dispatch_infra, handles_infra

_PRIMARY_COMMANDS = {"quality", "audit", "security", "performance", "oop"}
_ANALYSIS_COMMANDS = _PRIMARY_COMMANDS | {
    "dependencies", "architecture", "coverage", "syntax",
    "requirements", "licenses", "logic",
}


def handles(command: str) -> bool:
    """Return True if this module handles the given command."""
    return command in _ANALYSIS_COMMANDS


def dispatch_analysis(args, verbose: bool) -> None:
    """Dispatch analysis-category commands."""

    if handles_infra(args.command):
        dispatch_infra(args, verbose)
        return

    if args.command == "quality":
        if not hasattr(args, 'quality_command') or args.quality_command is None:
            print("Error: Please specify a quality subcommand. Available subcommands:")
            print("  analyze         Run all quality checks")
            print("  file-length     Report files exceeding line length threshold")
            print("  complexity      Report functions exceeding complexity thresholds")
            print("  duplication     Detect copy-pasted code blocks")
            print("  smells          Detect code smells (long methods, large classes, etc.)")
            print("  debt            Estimate and categorize technical debt")
            print("  maintainability Score files by maintainability index")
            print("  env-fallback    Detect default/fallback values in environment variable access")
            print("  lazy-imports    Detect imports not at module level")
            print("  forbidden-imports  Detect use of libraries that should use wrappers")
            print("  datetime        Detect unsafe datetime usage (utcnow, naive now, today)")
            print("  typing          Report functions and methods missing type annotations")
            print("  type-check      Run Pyright/Pylance static type checking across the codebase")
            print("  thread-safety   Detect uninitialized attrs and shared mutable collections")
            print("  race-conditions Detect race condition patterns (start-before-store, etc.)")
            print("  daemon-threads  Detect daemon thread lifecycle issues (no join, local-only, etc.)")
            print("  future-leaks    Detect futures, tasks, and threads never awaited or joined")
            print("  blocking-async  Detect blocking calls inside async functions")
            print("  resource-cleanup  Detect unclosed files, connections, and context manager issues")
            print("  error-handling  Detect bare excepts, swallowed exceptions, and missing handlers")
            print("  documentation   Scan comment density and public API documentation coverage")
            print("  naming          Enforce PEP 8 naming conventions")
            print("  bugs            Detect null dereferences, unreachable code, and other bugs")
            print("  javascript      Analyze JavaScript files for quality issues")
            print("  typescript      Analyze TypeScript files for quality issues")
            print("  shell           Analyze shell/bash scripts for quality and security issues")
            print("\nUse 'heimdall quality <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        handlers = {
            "analyze": lambda: run_quality_analysis(args, verbose),
            "file-length": lambda: run_quality_analysis(args, verbose),
            "complexity": lambda: run_complexity_analysis(args, verbose),
            "duplication": lambda: run_duplication_analysis(args, verbose),
            "smells": lambda: run_smell_analysis(args, verbose),
            "debt": lambda: run_debt_analysis(args, verbose),
            "maintainability": lambda: run_maintainability_analysis(args, verbose),
            "env-fallback": lambda: run_env_fallback_analysis(args, verbose),
            "lazy-imports": lambda: run_lazy_imports_analysis(args, verbose),
            "forbidden-imports": lambda: run_forbidden_imports_analysis(args, verbose),
            "datetime": lambda: run_datetime_analysis(args, verbose),
            "typing": lambda: run_typing_analysis(args, verbose),
            "type-check": lambda: run_type_check_analysis(args, verbose),
            "thread-safety": lambda: run_thread_safety_analysis(args, verbose),
            "race-conditions": lambda: run_race_conditions_analysis(args, verbose),
            "daemon-threads": lambda: run_daemon_threads_analysis(args, verbose),
            "future-leaks": lambda: run_future_leaks_analysis(args, verbose),
            "blocking-async": lambda: run_blocking_async_analysis(args, verbose),
            "resource-cleanup": lambda: run_resource_cleanup_analysis(args, verbose),
            "error-handling": lambda: run_error_handling_analysis(args, verbose),
            "documentation": lambda: run_documentation_analysis(args, verbose),
            "naming": lambda: run_naming_analysis(args, verbose),
            "bugs": lambda: run_bugs_analysis(args, verbose),
            "javascript": lambda: run_js_analysis(args, verbose),
            "typescript": lambda: run_ts_analysis(args, verbose),
            "shell": lambda: run_shell_analysis(args, verbose),
        }

        if args.quality_command in handlers:
            sys.exit(handlers[args.quality_command]())
        else:
            print(f"Unknown quality command: {args.quality_command}")
            sys.exit(1)

    elif args.command == "audit":
        sys.exit(run_quality_analysis(args, verbose))

    elif args.command == "security":
        if not hasattr(args, 'security_command') or args.security_command is None:
            print("Error: Please specify a security subcommand. Available subcommands:")
            print("  scan            Run all security checks")
            print("  secrets         Detect hardcoded secrets, tokens, and credentials")
            print("  dependencies    Scan for vulnerable third-party dependencies")
            print("  vulnerabilities Detect injection vulnerabilities")
            print("  crypto          Validate cryptographic implementations")
            print("  access          Analyze access control patterns")
            print("  auth            Analyze authentication flows")
            print("  headers         Check HTTP security header configuration")
            print("  tls             Analyze TLS/SSL configuration")
            print("  container       Audit container security configuration")
            print("  infra           Analyze infrastructure-as-code for misconfigurations")
            print("  config-secrets  Detect secrets in config files using pattern and entropy analysis")
            print("  hotspots        Detect security-sensitive code patterns requiring manual review")
            print("  compliance      Generate OWASP Top 10 and CWE Top 25 compliance reports")
            print("  taint           Perform taint analysis to track untrusted data to dangerous sinks")
            print("\nUse 'heimdall security <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        security_types = {
            "scan": "all", "secrets": "secrets", "dependencies": "dependencies",
            "vulnerabilities": "vulnerabilities", "crypto": "crypto", "access": "access",
            "auth": "auth", "headers": "headers", "tls": "tls", "container": "container",
            "infra": "infra"
        }

        if args.security_command == "config-secrets":
            sys.exit(run_config_secrets_analysis(args, verbose))
        elif args.security_command == "hotspots":
            sys.exit(run_hotspots_analysis(args, verbose))
        elif args.security_command == "compliance":
            sys.exit(run_compliance_analysis(args, verbose))
        elif args.security_command == "taint":
            sys.exit(run_taint_analysis(args, verbose))
        elif args.security_command in security_types:
            sys.exit(run_security_analysis(args, verbose, security_types[args.security_command]))
        else:
            print(f"Unknown security command: {args.security_command}")
            sys.exit(1)

    elif args.command == "performance":
        if not hasattr(args, 'performance_command') or args.performance_command is None:
            print("Error: Please specify a performance subcommand. Available subcommands:")
            print("  scan      Run all performance checks")
            print("  memory    Detect memory leak patterns and excessive allocation")
            print("  cpu       Flag high-complexity CPU hot paths")
            print("  database  Detect inefficient database access patterns")
            print("  cache     Identify missed caching opportunities")
            print("\nUse 'heimdall performance <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        perf_types = {"scan": "all", "memory": "memory", "cpu": "cpu", "database": "database", "cache": "cache"}
        if args.performance_command in perf_types:
            sys.exit(run_performance_analysis(args, verbose, perf_types[args.performance_command]))
        else:
            print(f"Unknown performance command: {args.performance_command}")
            sys.exit(1)

    elif args.command == "oop":
        if not hasattr(args, 'oop_command') or args.oop_command is None:
            print("Error: Please specify an OOP subcommand. Available subcommands:")
            print("  analyze     Run all OOP metrics checks")
            print("  coupling    Report classes with excessive coupling (CBO)")
            print("  cohesion    Report classes with poor method cohesion (LCOM)")
            print("  inheritance Report classes with deep inheritance or high subclass count (DIT/NOC)")
            print("\nUse 'heimdall oop <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)

        if args.oop_command in ("analyze", "coupling", "cohesion", "inheritance"):
            sys.exit(run_oop_analysis(args, verbose))
        else:
            print(f"Unknown OOP command: {args.oop_command}")
            sys.exit(1)

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)
