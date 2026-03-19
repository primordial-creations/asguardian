"""
Heimdall CLI Main Entry Point

This module provides the main CLI entry point and parser creation.
Command handlers are delegated to submodules for better organization.
"""

import argparse
import io
import sys

from Asgard.Heimdall.cli.common import (
    add_common_args,
    add_complexity_args,
    add_duplication_args,
    add_smell_args,
    add_debt_args,
    add_maintainability_args,
    add_env_fallback_args,
    add_lazy_imports_args,
    add_forbidden_imports_args,
    add_datetime_args,
    add_typing_args,
    add_type_check_args,
    add_thread_safety_args,
    add_race_conditions_args,
    add_daemon_threads_args,
    add_future_leaks_args,
    add_blocking_async_args,
    add_resource_cleanup_args,
    add_error_handling_args,
    add_config_secrets_args,
    add_security_args,
    add_performance_args,
    add_oop_args,
    add_deps_args,
    add_deps_export_args,
    add_arch_args,
    add_coverage_args,
    add_syntax_args,
    add_requirements_args,
    add_licenses_args,
    add_logic_args,
    add_baseline_args,
    add_documentation_args,
    add_naming_args,
    add_hotspots_args,
    add_compliance_args,
    add_ratings_args,
    add_gate_args,
    add_profiles_args,
    add_profile_assign_args,
    add_profile_show_args,
    add_profile_create_args,
    add_history_args,
    add_new_code_args,
    add_taint_args,
    add_bugs_args,
    add_js_args,
    add_ts_args,
    add_shell_args,
    add_issues_args,
    add_sbom_args,
    add_codefix_args,
    add_mcp_server_args,
    add_dashboard_args,
)

# Import handlers from the original CLI (will be refactored into separate modules)
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
    run_config_secrets_analysis,
    run_security_analysis,
    run_performance_analysis,
    run_oop_analysis,
    run_deps_analysis,
    run_deps_export,
    run_arch_analysis,
    run_coverage_analysis,
    run_syntax_analysis,
    run_requirements_analysis,
    run_licenses_analysis,
    run_logic_analysis,
    run_baseline_command,
    run_init_linter,
    run_documentation_analysis,
    run_naming_analysis,
    run_hotspots_analysis,
    run_compliance_analysis,
    run_ratings_analysis,
    run_gate_evaluation,
    run_profiles_command,
    run_history_command,
    run_new_code_detect,
    run_taint_analysis,
    run_bugs_analysis,
    run_js_analysis,
    run_ts_analysis,
    run_shell_analysis,
    run_issues_command,
    run_sbom_generation,
    run_codefix_suggestions,
    run_mcp_server,
    run_dashboard,
    run_full_scan,
    _TeeStream,
    open_output_in_browser,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="heimdall",
        description="Heimdall - Static code analysis and quality enforcement tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality analyze ./src\n"
            "  heimdall audit ./src --format html\n"
            "  heimdall security scan ./src --severity high\n"
            "  heimdall dependencies export ./src --export-format mermaid\n"
            "  heimdall baseline list ./src --type env-fallback\n"
            "\n"
            "Named after the Norse watchman god who guards Bifrost and sees all."
        ),
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all scanned files, including those with no issues",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Heimdall 1.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Top-level command group")

    # Quality command group
    _setup_quality_commands(subparsers)

    # Audit command (alias for quality analyze)
    audit_parser = subparsers.add_parser(
        "audit",
        help="Run all quality checks against a path (shorthand for 'quality analyze')",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall audit ./src\n"
            "  heimdall audit ./src --format html\n"
            "  heimdall audit ./src --parallel --incremental\n"
        ),
    )
    add_common_args(audit_parser)

    # Security command group
    _setup_security_commands(subparsers)

    # Performance command group
    _setup_performance_commands(subparsers)

    # OOP command group
    _setup_oop_commands(subparsers)

    # Dependencies command group
    _setup_deps_commands(subparsers)

    # Architecture command group
    _setup_arch_commands(subparsers)

    # Coverage command group
    _setup_coverage_commands(subparsers)

    # Syntax command group
    _setup_syntax_commands(subparsers)

    # Requirements command group
    _setup_requirements_commands(subparsers)

    # Licenses command group
    _setup_licenses_commands(subparsers)

    # Logic command group
    _setup_logic_commands(subparsers)

    # Baseline command group
    _setup_baseline_commands(subparsers)

    # Init-linter command
    _setup_init_linter_command(subparsers)

    # Ratings command (top-level)
    _setup_ratings_command(subparsers)

    # Gate command (top-level)
    _setup_gate_command(subparsers)

    # Profiles command group
    _setup_profiles_commands(subparsers)

    # History command group
    _setup_history_commands(subparsers)

    # New-code command group
    _setup_new_code_commands(subparsers)

    # Issues command (top-level)
    _setup_issues_command(subparsers)

    # SBOM command (top-level)
    _setup_sbom_command(subparsers)

    # Codefix command (top-level)
    _setup_codefix_command(subparsers)

    # MCP server command (top-level)
    _setup_mcp_server_command(subparsers)

    # Dashboard command (top-level)
    _setup_dashboard_command(subparsers)

    # Scan command (runs ALL analyses)
    scan_parser = subparsers.add_parser(
        "scan",
        help="Run ALL analysis categories (quality, security, performance, OOP, architecture, type-check, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall scan ./src\n"
            "  heimdall scan ./src --format markdown\n"
            "  heimdall scan ./src --include-tests\n"
            "  heimdall scan ./src --type-check-mode strict\n"
            "\n"
            "This runs all Heimdall analyses in sequence:\n"
            "  1. File length analysis\n"
            "  2. Complexity analysis\n"
            "  3. Lazy import detection\n"
            "  4. Environment variable fallback detection\n"
            "  5. Static type checking (Pyright/Pylance)\n"
            "  6. Security vulnerability scan\n"
            "  7. Performance pattern analysis\n"
            "  8. OOP metrics (coupling/cohesion)\n"
            "  9. Architecture analysis (SOLID/layers)\n"
            "  10. Dependency analysis (circular imports)\n"
        ),
    )
    scan_parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    scan_parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    scan_parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=300,
        help="File length threshold (default: 300)",
    )
    scan_parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in analysis",
    )
    scan_parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude",
    )
    scan_parser.add_argument(
        "--type-check-mode",
        choices=["off", "basic", "standard", "strict", "all"],
        default="basic",
        help="Pyright type checking mode (default: basic)",
    )

    return parser


def _setup_quality_commands(subparsers) -> None:
    """Set up quality command group."""
    quality_parser = subparsers.add_parser(
        "quality",
        help="Code quality checks (complexity, smells, debt, typing, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality analyze ./src\n"
            "  heimdall quality analyze ./src --format json\n"
            "  heimdall quality complexity ./src --cyclomatic-threshold 8\n"
            "  heimdall quality env-fallback ./src --severity high\n"
            "  heimdall quality thread-safety ./src --include-tests\n"
        ),
    )
    quality_subparsers = quality_parser.add_subparsers(dest="quality_command", help="Quality subcommand to run")

    # Quality analyze (all quality checks)
    quality_analyze = quality_subparsers.add_parser(
        "analyze",
        help="Run all quality checks and report violations across all quality dimensions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality analyze ./src\n"
            "  heimdall quality analyze ./src --format html\n"
            "  heimdall quality analyze ./src --parallel --incremental\n"
            "  heimdall quality analyze ./src --exclude '*/tests/*' '*/migrations/*'\n"
            "  heimdall quality analyze ./src --baseline .asgard-baseline.json\n"
        ),
    )
    add_common_args(quality_analyze)

    # Quality file-length
    quality_file_length = quality_subparsers.add_parser(
        "file-length",
        help="Report files that exceed the configured line length threshold",
    )
    add_common_args(quality_file_length)

    # Quality complexity
    quality_complexity = quality_subparsers.add_parser(
        "complexity",
        help="Report functions exceeding cyclomatic or cognitive complexity thresholds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality complexity ./src\n"
            "  heimdall quality complexity ./src --cyclomatic-threshold 8 --cognitive-threshold 12\n"
            "  heimdall quality complexity ./src --format json\n"
        ),
    )
    add_complexity_args(quality_complexity)

    # Quality duplication
    quality_duplication = quality_subparsers.add_parser(
        "duplication",
        help="Detect copy-pasted code blocks that exceed the minimum line/token thresholds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality duplication ./src\n"
            "  heimdall quality duplication ./src --min-lines 10 --min-tokens 80\n"
            "  heimdall quality duplication ./src --format markdown\n"
        ),
    )
    add_duplication_args(quality_duplication)

    # Quality smells
    quality_smells = quality_subparsers.add_parser(
        "smells",
        help="Detect code smells such as long methods, large classes, and feature envy",
    )
    add_smell_args(quality_smells)

    # Quality debt
    quality_debt = quality_subparsers.add_parser(
        "debt",
        help="Estimate and categorize technical debt by horizon (immediate, short, medium, long)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality debt ./src\n"
            "  heimdall quality debt ./src --horizon immediate\n"
            "  heimdall quality debt ./src --severity high --format markdown\n"
        ),
    )
    add_debt_args(quality_debt)

    # Quality maintainability
    quality_maintainability = quality_subparsers.add_parser(
        "maintainability",
        help="Score files by maintainability index and flag those rated poor or critical",
    )
    add_maintainability_args(quality_maintainability)

    # Quality env-fallback
    quality_env_fallback = quality_subparsers.add_parser(
        "env-fallback",
        help="Detect default/fallback values in environment variable access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality env-fallback ./src\n"
            "  heimdall quality env-fallback ./src --severity high\n"
            "  heimdall quality env-fallback ./src --include-tests --format json\n"
        ),
    )
    add_env_fallback_args(quality_env_fallback)

    # Quality lazy-imports
    quality_lazy_imports = quality_subparsers.add_parser(
        "lazy-imports",
        help="Detect imports not at module level (inside functions, methods, etc.)"
    )
    add_lazy_imports_args(quality_lazy_imports)

    # Quality forbidden-imports
    quality_forbidden_imports = quality_subparsers.add_parser(
        "forbidden-imports",
        help="Detect imports of forbidden libraries that should use wrappers"
    )
    add_forbidden_imports_args(quality_forbidden_imports)

    # Quality datetime
    quality_datetime = quality_subparsers.add_parser(
        "datetime",
        help="Detect deprecated and unsafe datetime usage patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality datetime ./src\n"
            "  heimdall quality datetime ./src --no-check-utcnow --no-check-today\n"
            "  heimdall quality datetime ./src --include-tests --format json\n"
        ),
    )
    add_datetime_args(quality_datetime)

    # Quality typing
    quality_typing = quality_subparsers.add_parser(
        "typing",
        help="Analyze type annotation coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality typing ./src\n"
            "  heimdall quality typing ./src --threshold 90.0\n"
            "  heimdall quality typing ./src --include-private --include-dunder\n"
        ),
    )
    add_typing_args(quality_typing)

    # Quality type-check (Pyright/Pylance static type checking)
    quality_type_check = quality_subparsers.add_parser(
        "type-check",
        help="Run static type checking using Pyright (Pylance engine) across the entire codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality type-check ./src\n"
            "  heimdall quality type-check ./src --mode strict\n"
            "  heimdall quality type-check ./src --errors-only\n"
            "  heimdall quality type-check ./src --category missing_import\n"
            "  heimdall quality type-check ./src --venv-path .venv --format json\n"
            "\n"
            "Type checking modes (Pylance equivalent):\n"
            "  off         No type checking\n"
            "  basic       Basic checks (Pylance default)\n"
            "  standard    Standard checks (more thorough)\n"
            "  strict      All checks enabled (strictest)\n"
            "  all         All checks + all optional rules\n"
            "\n"
            "Diagnostic categories:\n"
            "  type_mismatch       Type compatibility errors\n"
            "  missing_import      Unresolved imports\n"
            "  undefined_variable  Undefined names\n"
            "  argument_error      Wrong argument types/counts\n"
            "  return_type         Return type mismatches\n"
            "  attribute_error     Invalid attribute access\n"
            "  assignment_error    Incompatible assignments\n"
            "  operator_error      Invalid operator usage\n"
            "  override_error      Incorrect method overrides\n"
            "  generic_error       Generic type violations\n"
            "  protocol_error      Protocol conformance issues\n"
            "  typed_dict_error    TypedDict violations\n"
            "  overload_error      Overload resolution issues\n"
            "  unreachable_code    Unreachable code (type-based)\n"
            "  deprecated          Deprecated API usage\n"
        ),
    )
    add_type_check_args(quality_type_check)

    # Quality thread-safety
    quality_thread_safety = quality_subparsers.add_parser(
        "thread-safety",
        help="Detect thread safety issues (uninitialized attrs, shared mutable collections)"
    )
    add_thread_safety_args(quality_thread_safety)

    # Quality race-conditions
    quality_race_conditions = quality_subparsers.add_parser(
        "race-conditions",
        help="Detect race condition patterns (start-before-store, assign-after-start, check-then-act)"
    )
    add_race_conditions_args(quality_race_conditions)

    # Quality daemon-threads
    quality_daemon_threads = quality_subparsers.add_parser(
        "daemon-threads",
        help="Detect daemon thread lifecycle issues (no join, local var only, event patterns)"
    )
    add_daemon_threads_args(quality_daemon_threads)

    # Quality future-leaks
    quality_future_leaks = quality_subparsers.add_parser(
        "future-leaks",
        help="Detect futures, tasks, and threads that are created but never resolved"
    )
    add_future_leaks_args(quality_future_leaks)

    # Quality blocking-async
    quality_blocking_async = quality_subparsers.add_parser(
        "blocking-async",
        help="Detect blocking calls (time.sleep, requests, open, subprocess) inside async functions"
    )
    add_blocking_async_args(quality_blocking_async)

    # Quality resource-cleanup
    quality_resource_cleanup = quality_subparsers.add_parser(
        "resource-cleanup",
        help="Detect resource cleanup issues (unclosed files, connections, and context manager violations)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality resource-cleanup ./src\n"
            "  heimdall quality resource-cleanup ./src --severity high\n"
            "  heimdall quality resource-cleanup ./src --include-tests --format json\n"
        ),
    )
    add_resource_cleanup_args(quality_resource_cleanup)

    # Quality error-handling
    quality_error_handling = quality_subparsers.add_parser(
        "error-handling",
        help="Detect error handling coverage issues (bare excepts, swallowed exceptions, missing handlers)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality error-handling ./src\n"
            "  heimdall quality error-handling ./src --severity high --format json\n"
            "  heimdall quality error-handling ./src --include-tests\n"
        ),
    )
    add_error_handling_args(quality_error_handling)

    # Quality documentation
    quality_documentation = quality_subparsers.add_parser(
        "documentation",
        help="Scan comment density and public API documentation coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality documentation ./src\n"
            "  heimdall quality documentation ./src --min-comment-density 15.0\n"
            "  heimdall quality documentation ./src --min-api-coverage 80.0 --format json\n"
        ),
    )
    add_documentation_args(quality_documentation)

    # Quality naming
    quality_naming = quality_subparsers.add_parser(
        "naming",
        help="Enforce PEP 8 naming conventions for functions, classes, variables, and constants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality naming ./src\n"
            "  heimdall quality naming ./src --no-variables --format json\n"
            "  heimdall quality naming ./src --allow MySpecialName --format markdown\n"
        ),
    )
    add_naming_args(quality_naming)

    # Quality bugs
    quality_bugs = quality_subparsers.add_parser(
        "bugs",
        help="Detect null dereferences, unreachable code, and other bugs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality bugs ./src\n"
            "  heimdall quality bugs ./src --null-only\n"
            "  heimdall quality bugs ./src --unreachable-only --format json\n"
        ),
    )
    add_bugs_args(quality_bugs)

    # Quality javascript
    quality_javascript = quality_subparsers.add_parser(
        "javascript",
        help="Analyze JavaScript files for quality issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality javascript ./src\n"
            "  heimdall quality javascript ./src --severity high\n"
            "  heimdall quality javascript ./src --format json\n"
        ),
    )
    add_js_args(quality_javascript)

    # Quality typescript
    quality_typescript = quality_subparsers.add_parser(
        "typescript",
        help="Analyze TypeScript files for quality issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality typescript ./src\n"
            "  heimdall quality typescript ./src --severity high\n"
            "  heimdall quality typescript ./src --format json\n"
        ),
    )
    add_ts_args(quality_typescript)

    # Quality shell
    quality_shell = quality_subparsers.add_parser(
        "shell",
        help="Analyze shell/bash scripts for quality and security issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall quality shell ./src\n"
            "  heimdall quality shell ./scripts --severity high\n"
            "  heimdall quality shell ./src --format json\n"
        ),
    )
    add_shell_args(quality_shell)


def _setup_security_commands(subparsers) -> None:
    """Set up security command group."""
    security_parser = subparsers.add_parser(
        "security",
        help="Security vulnerability analysis (secrets, injections, crypto, auth, config, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security scan ./src\n"
            "  heimdall security secrets ./src --severity high\n"
            "  heimdall security config-secrets ./src --entropy-threshold 4.0\n"
            "  heimdall security vulnerabilities ./src --format json\n"
        ),
    )
    security_subparsers = security_parser.add_subparsers(dest="security_command", help="Security subcommand to run")

    for cmd, desc in [
        ("scan", "Run all security checks across all categories"),
        ("secrets", "Detect hardcoded secrets, tokens, and credentials in source code"),
        ("dependencies", "Scan third-party dependencies for known CVEs and vulnerabilities"),
        ("vulnerabilities", "Detect injection vulnerabilities (SQL, command, path traversal, etc.)"),
        ("crypto", "Validate cryptographic implementations for weak algorithms or misuse"),
        ("access", "Analyze access control patterns for missing or incorrectly applied checks"),
        ("auth", "Analyze authentication flows for common weaknesses"),
        ("headers", "Check HTTP response header configuration for security best practices"),
        ("tls", "Analyze TLS/SSL configuration for weak protocols or cipher suites"),
        ("container", "Audit container configuration for security misconfigurations"),
        ("infra", "Analyze infrastructure-as-code for security misconfigurations"),
    ]:
        sub = security_subparsers.add_parser(cmd, help=desc)
        add_security_args(sub)

    # Security config-secrets
    security_config_secrets = security_subparsers.add_parser(
        "config-secrets",
        help="Detect secrets, API keys, and sensitive values in config files using pattern matching and entropy analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security config-secrets ./src\n"
            "  heimdall security config-secrets ./src --severity high\n"
            "  heimdall security config-secrets ./src --entropy-threshold 4.0 --entropy-min-length 16\n"
            "  heimdall security config-secrets ./src --format json\n"
        ),
    )
    add_config_secrets_args(security_config_secrets)

    # Security hotspots
    security_hotspots = security_subparsers.add_parser(
        "hotspots",
        help="Detect security-sensitive code patterns requiring manual review (OWASP hotspot categories)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security hotspots ./src\n"
            "  heimdall security hotspots ./src --priority high\n"
            "  heimdall security hotspots ./src --format json\n"
        ),
    )
    add_hotspots_args(security_hotspots)

    # Security compliance
    security_compliance = security_subparsers.add_parser(
        "compliance",
        help="Generate OWASP Top 10 and CWE Top 25 compliance reports from security analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security compliance ./src\n"
            "  heimdall security compliance ./src --no-cwe\n"
            "  heimdall security compliance ./src --format markdown\n"
        ),
    )
    add_compliance_args(security_compliance)

    # Security taint
    security_taint = security_subparsers.add_parser(
        "taint",
        help="Perform taint analysis to track untrusted data to dangerous sinks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall security taint ./src\n"
            "  heimdall security taint ./src --severity high\n"
            "  heimdall security taint ./src --format json\n"
        ),
    )
    add_taint_args(security_taint)


def _setup_performance_commands(subparsers) -> None:
    """Set up performance command group."""
    performance_parser = subparsers.add_parser(
        "performance",
        help="Performance analysis (memory, CPU, database access, caching patterns)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall performance scan ./src\n"
            "  heimdall performance database ./src --severity high\n"
            "  heimdall performance memory ./src --format json\n"
        ),
    )
    performance_subparsers = performance_parser.add_subparsers(dest="performance_command", help="Performance subcommand to run")

    for cmd, desc in [
        ("scan", "Run all performance checks across all categories"),
        ("memory", "Detect memory usage patterns likely to cause leaks or excessive allocation"),
        ("cpu", "Flag computationally expensive patterns and high-complexity hot paths"),
        ("database", "Detect inefficient database access patterns such as N+1 queries"),
        ("cache", "Identify missed caching opportunities and cache invalidation issues"),
    ]:
        sub = performance_subparsers.add_parser(cmd, help=desc)
        add_performance_args(sub)


def _setup_oop_commands(subparsers) -> None:
    """Set up OOP command group."""
    oop_parser = subparsers.add_parser(
        "oop",
        help="Object-oriented design metrics (coupling, cohesion, inheritance depth)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall oop analyze ./src\n"
            "  heimdall oop coupling ./src --cbo-threshold 10\n"
            "  heimdall oop cohesion ./src --format json\n"
        ),
    )
    oop_subparsers = oop_parser.add_subparsers(dest="oop_command", help="OOP subcommand to run")

    for cmd, desc in [
        ("analyze", "Run all OOP metrics checks and report classes with poor scores"),
        ("coupling", "Report classes with excessive coupling between objects (CBO metric)"),
        ("cohesion", "Report classes with poor method cohesion (LCOM metric)"),
        ("inheritance", "Report classes with deep inheritance trees or high subclass count (DIT/NOC)"),
    ]:
        sub = oop_subparsers.add_parser(cmd, help=desc)
        add_oop_args(sub)


def _setup_deps_commands(subparsers) -> None:
    """Set up dependencies command group."""
    deps_parser = subparsers.add_parser(
        "dependencies",
        help="Dependency graph analysis (cycles, modularity, graph export in mermaid/graphviz/json)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall dependencies analyze ./src\n"
            "  heimdall dependencies cycles ./src --format json\n"
            "  heimdall dependencies export ./src --export-format mermaid --output deps.mmd\n"
            "  heimdall dependencies export ./src --export-format graphviz --direction TB\n"
        ),
    )
    deps_subparsers = deps_parser.add_subparsers(dest="deps_command", help="Dependencies subcommand to run")

    for cmd, desc in [
        ("analyze", "Run full dependency analysis including cycles, graph, and modularity"),
        ("cycles", "Detect circular import dependencies between modules"),
        ("graph", "Build and display the module dependency graph"),
        ("modularity", "Score the project's modularity based on coupling between packages"),
    ]:
        sub = deps_subparsers.add_parser(cmd, help=desc)
        add_deps_args(sub)

    # Export subcommand with its own args (mermaid, graphviz/dot, json)
    export_parser = deps_subparsers.add_parser(
        "export",
        help="Export the dependency graph to a file in mermaid, graphviz/dot, or json format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall dependencies export ./src\n"
            "  heimdall dependencies export ./src --export-format mermaid --output deps.mmd\n"
            "  heimdall dependencies export ./src --export-format graphviz --output deps.dot\n"
            "  heimdall dependencies export ./src --export-format json --output deps.json\n"
            "  heimdall dependencies export ./src --export-format mermaid --direction TB\n"
        ),
    )
    add_deps_export_args(export_parser)


def _setup_arch_commands(subparsers) -> None:
    """Set up architecture command group."""
    arch_parser = subparsers.add_parser(
        "architecture",
        help="Architecture analysis (SOLID principles, layer compliance, design pattern detection)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall architecture analyze ./src\n"
            "  heimdall architecture solid ./src --format markdown\n"
            "  heimdall architecture layers ./src --no-patterns\n"
        ),
    )
    arch_subparsers = arch_parser.add_subparsers(dest="arch_command", help="Architecture subcommand to run")

    for cmd, desc in [
        ("analyze", "Run full architecture analysis including SOLID, layers, and patterns"),
        ("solid", "Validate adherence to SOLID principles and report violations"),
        ("layers", "Check that modules respect defined architectural layer boundaries"),
        ("patterns", "Detect implemented design patterns and flag antipatterns"),
        ("hexagonal", "Analyze hexagonal (ports and adapters) architecture compliance"),
    ]:
        sub = arch_subparsers.add_parser(cmd, help=desc)
        add_arch_args(sub)


def _setup_coverage_commands(subparsers) -> None:
    """Set up coverage command group."""
    cov_parser = subparsers.add_parser(
        "coverage",
        help="Test coverage analysis (gap detection, untested method suggestions)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall coverage analyze ./src\n"
            "  heimdall coverage gaps ./src --test-path ./tests\n"
            "  heimdall coverage suggestions ./src --max-suggestions 20\n"
        ),
    )
    cov_subparsers = cov_parser.add_subparsers(dest="cov_command", help="Coverage subcommand to run")

    for cmd, desc in [
        ("analyze", "Run full coverage analysis including gaps and suggestions"),
        ("gaps", "Identify methods and classes with no corresponding test coverage"),
        ("suggestions", "Generate suggested test cases for uncovered methods"),
    ]:
        sub = cov_subparsers.add_parser(cmd, help=desc)
        add_coverage_args(sub)


def _setup_syntax_commands(subparsers) -> None:
    """Set up syntax command group."""
    syntax_parser = subparsers.add_parser(
        "syntax",
        help="Syntax and linting checks using ruff, flake8, pylint, or mypy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall syntax check ./src\n"
            "  heimdall syntax check ./src --linters ruff mypy --severity error\n"
            "  heimdall syntax fix ./src\n"
        ),
    )
    syntax_subparsers = syntax_parser.add_subparsers(dest="syntax_command", help="Syntax subcommand to run")

    for cmd, desc in [
        ("check", "Run syntax and linting checks and report all violations"),
        ("fix", "Auto-fix syntax violations where safe to do so"),
    ]:
        sub = syntax_subparsers.add_parser(cmd, help=desc)
        add_syntax_args(sub)


def _setup_requirements_commands(subparsers) -> None:
    """Set up requirements command group."""
    req_parser = subparsers.add_parser(
        "requirements",
        help="Validate requirements.txt against actual imports (missing, unused, version drift)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall requirements check ./src\n"
            "  heimdall requirements check ./src --requirements-files requirements.txt requirements-dev.txt\n"
            "  heimdall requirements sync ./src\n"
        ),
    )
    req_subparsers = req_parser.add_subparsers(dest="req_command", help="Requirements subcommand to run")

    for cmd, desc in [
        ("check", "Report missing, unused, and potentially mismatched requirements"),
        ("sync", "Update requirements.txt to match packages actually imported in the codebase"),
    ]:
        sub = req_subparsers.add_parser(cmd, help=desc)
        add_requirements_args(sub)


def _setup_licenses_commands(subparsers) -> None:
    """Set up licenses command group."""
    lic_parser = subparsers.add_parser(
        "licenses",
        help="License compliance checking for third-party dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall licenses check ./src\n"
            "  heimdall licenses check ./src --allowed MIT Apache-2.0 BSD-3-Clause\n"
            "  heimdall licenses check ./src --denied GPL-3.0 AGPL-3.0\n"
        ),
    )
    lic_subparsers = lic_parser.add_subparsers(dest="lic_command", help="Licenses subcommand to run")

    lic_check = lic_subparsers.add_parser(
        "check",
        help="Verify that all dependency licenses are in the allowed list and none are in the denied list",
    )
    add_licenses_args(lic_check)


def _setup_logic_commands(subparsers) -> None:
    """Set up logic command group."""
    logic_parser = subparsers.add_parser(
        "logic",
        help="Logic and structural pattern analysis (duplication, complexity, inefficient patterns)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall logic audit ./src\n"
            "  heimdall logic duplication ./src --severity high\n"
            "  heimdall logic complexity ./src --format markdown\n"
        ),
    )
    logic_subparsers = logic_parser.add_subparsers(dest="logic_command", help="Logic subcommand to run")

    for cmd, desc in [
        ("duplication", "Detect structurally duplicated logic blocks across the codebase"),
        ("patterns", "Detect inefficient patterns, antipatterns, and logic code smells"),
        ("complexity", "Calculate cyclomatic and cognitive complexity for logic-heavy functions"),
        ("audit", "Run all logic checks and produce a combined report"),
    ]:
        sub = logic_subparsers.add_parser(cmd, help=desc)
        add_logic_args(sub)


def _setup_baseline_commands(subparsers) -> None:
    """Set up baseline command group."""
    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Manage the baseline of known/accepted violations (show, list, clean, remove)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall baseline show ./src\n"
            "  heimdall baseline list ./src --type env-fallback\n"
            "  heimdall baseline list ./src --file services/auth.py\n"
            "  heimdall baseline remove ./src --id abc-1234\n"
            "  heimdall baseline clean ./src\n"
        ),
    )
    baseline_subparsers = baseline_parser.add_subparsers(
        dest="baseline_command",
        help="Baseline subcommand to run",
    )

    baseline_show = baseline_subparsers.add_parser(
        "show",
        help="Display a summary report of all baselined violations and their status",
    )
    add_baseline_args(baseline_show)

    baseline_list = baseline_subparsers.add_parser(
        "list",
        help="List baseline entries, optionally filtered by violation type or file path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall baseline list ./src\n"
            "  heimdall baseline list ./src --type env-fallback\n"
            "  heimdall baseline list ./src --file services/auth.py\n"
            "  heimdall baseline list ./src --format json\n"
        ),
    )
    add_baseline_args(baseline_list)

    baseline_clean = baseline_subparsers.add_parser(
        "clean",
        help="Remove baseline entries that have expired based on their configured TTL",
    )
    add_baseline_args(baseline_clean)

    baseline_remove = baseline_subparsers.add_parser(
        "remove",
        help="Remove a single baseline entry by its violation ID (requires --id)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall baseline remove ./src --id abc-1234\n"
            "  heimdall baseline remove ./src --id abc-1234 --baseline-file .asgard-baseline.json\n"
        ),
    )
    add_baseline_args(baseline_remove)


def _setup_init_linter_command(subparsers) -> None:
    """Set up the init-linter command."""
    init_linter_parser = subparsers.add_parser(
        "init-linter",
        help="Generate linting configuration files for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Generate linting configuration files based on GAIA coding standards.\n"
            "Auto-detects the project type (Python, TypeScript, or both) and creates\n"
            "the appropriate config files (ruff, mypy, eslint, prettier, pre-commit, etc.)."
        ),
        epilog=(
            "Examples:\n"
            "  heimdall init-linter .                         # Auto-detect and init in current dir\n"
            "  heimdall init-linter ./my-project               # Init in a specific directory\n"
            "  heimdall init-linter . --type python             # Force Python configs only\n"
            "  heimdall init-linter . --type typescript         # Force TypeScript configs only\n"
            "  heimdall init-linter . --type both               # Generate configs for both\n"
            "  heimdall init-linter . --name my-package         # Set the project/package name\n"
            "  heimdall init-linter . --force                   # Overwrite existing config files\n"
        ),
    )
    init_linter_parser.add_argument(
        "path",
        help="Project directory to initialize linting configs in",
    )
    init_linter_parser.add_argument(
        "--type",
        choices=["python", "typescript", "both"],
        default=None,
        dest="project_type",
        help="Force project type instead of auto-detecting (default: auto-detect)",
    )
    init_linter_parser.add_argument(
        "--name",
        default=None,
        dest="project_name",
        help="Project/package name for config templates (default: directory name)",
    )
    init_linter_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration files",
    )


def _setup_ratings_command(subparsers) -> None:
    """Set up the ratings top-level command."""
    ratings_parser = subparsers.add_parser(
        "ratings",
        help="Calculate A-E quality ratings for maintainability, reliability, and security",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall ratings ./src\n"
            "  heimdall ratings ./src --format json\n"
            "  heimdall ratings ./src --format markdown\n"
        ),
    )
    add_ratings_args(ratings_parser)


def _setup_gate_command(subparsers) -> None:
    """Set up the gate top-level command."""
    gate_parser = subparsers.add_parser(
        "gate",
        help="Evaluate the quality gate (Asgard Way) against analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall gate ./src\n"
            "  heimdall gate ./src --gate asgard-way\n"
            "  heimdall gate ./src --format json\n"
        ),
    )
    add_gate_args(gate_parser)


def _setup_profiles_commands(subparsers) -> None:
    """Set up the profiles command group."""
    profiles_parser = subparsers.add_parser(
        "profiles",
        help="Manage quality profiles (rule sets assigned to projects)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles list\n"
            "  heimdall profiles show 'Asgard Way - Python'\n"
            "  heimdall profiles assign ./src 'Asgard Way - Strict'\n"
            "  heimdall profiles create MyProfile --parent 'Asgard Way - Python'\n"
            "  heimdall profiles create MyProfile --from-file my_profile.json\n"
        ),
    )
    profiles_subparsers = profiles_parser.add_subparsers(
        dest="profiles_command",
        help="Profiles subcommand to run",
    )

    profiles_list = profiles_subparsers.add_parser(
        "list",
        help="List all available quality profiles (built-in and user-defined)",
    )
    add_profiles_args(profiles_list)

    profiles_show = profiles_subparsers.add_parser(
        "show",
        help="Show all rules in a profile with inheritance fully resolved",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles show 'Asgard Way - Python'\n"
            "  heimdall profiles show 'Asgard Way - Strict' --format json\n"
        ),
    )
    add_profile_show_args(profiles_show)

    profiles_assign = profiles_subparsers.add_parser(
        "assign",
        help="Assign a quality profile to a project path",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles assign ./src 'Asgard Way - Python'\n"
            "  heimdall profiles assign /abs/path/to/project 'Asgard Way - Strict'\n"
        ),
    )
    add_profile_assign_args(profiles_assign)

    profiles_create = profiles_subparsers.add_parser(
        "create",
        help="Create a new custom quality profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall profiles create MyProfile --parent 'Asgard Way - Python'\n"
            "  heimdall profiles create MyProfile --from-file my_profile.json\n"
            "  heimdall profiles create MyProfile --language python --description 'My team profile'\n"
        ),
    )
    add_profile_create_args(profiles_create)


def _setup_history_commands(subparsers) -> None:
    """Set up the history command group."""
    history_parser = subparsers.add_parser(
        "history",
        help="View analysis history and metric trends for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall history show ./src\n"
            "  heimdall history show ./src --limit 20\n"
            "  heimdall history trends ./src\n"
            "  heimdall history trends ./src --format json\n"
        ),
    )
    history_subparsers = history_parser.add_subparsers(
        dest="history_command",
        help="History subcommand to run",
    )

    history_show = history_subparsers.add_parser(
        "show",
        help="Show recorded analysis snapshots for a project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall history show ./src\n"
            "  heimdall history show ./src --limit 20 --format json\n"
        ),
    )
    add_history_args(history_show)

    history_trends = history_subparsers.add_parser(
        "trends",
        help="Show metric trend directions computed from recorded analysis history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall history trends ./src\n"
            "  heimdall history trends ./src --format json\n"
        ),
    )
    add_history_args(history_trends)


def _setup_new_code_commands(subparsers) -> None:
    """Set up the new-code command group."""
    new_code_parser = subparsers.add_parser(
        "new-code",
        help="Detect which files count as new code relative to a configured reference point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall new-code detect ./src\n"
            "  heimdall new-code detect ./src --since-branch main\n"
            "  heimdall new-code detect ./src --since-date 2026-01-01\n"
            "  heimdall new-code detect ./src --since-version v1.2.0\n"
        ),
    )
    new_code_subparsers = new_code_parser.add_subparsers(
        dest="new_code_command",
        help="New-code subcommand to run",
    )

    new_code_detect = new_code_subparsers.add_parser(
        "detect",
        help="Show which files are considered new or modified relative to the reference point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall new-code detect ./src\n"
            "  heimdall new-code detect ./src --since-branch main\n"
            "  heimdall new-code detect ./src --since-date 2026-01-01\n"
            "  heimdall new-code detect ./src --since-version v1.2.0\n"
        ),
    )
    add_new_code_args(new_code_detect)


def _setup_issues_command(subparsers) -> None:
    """Set up the issues top-level command."""
    issues_parser = subparsers.add_parser(
        "issues",
        help="Manage tracked issues lifecycle (list, show, update, assign, summary)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall issues list ./src\n"
            "  heimdall issues show ./src --id abc-1234\n"
            "  heimdall issues update ./src --id abc-1234 --status resolved\n"
            "  heimdall issues assign ./src --id abc-1234 --assignee alice\n"
            "  heimdall issues summary ./src\n"
        ),
    )
    add_issues_args(issues_parser)


def _setup_sbom_command(subparsers) -> None:
    """Set up the sbom top-level command."""
    sbom_parser = subparsers.add_parser(
        "sbom",
        help="Generate Software Bill of Materials (SBOM) in SPDX or CycloneDX format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall sbom ./src\n"
            "  heimdall sbom ./src --format spdx\n"
            "  heimdall sbom ./src --format cyclonedx --output sbom.json\n"
        ),
    )
    add_sbom_args(sbom_parser)


def _setup_codefix_command(subparsers) -> None:
    """Set up the codefix top-level command."""
    codefix_parser = subparsers.add_parser(
        "codefix",
        help="Get fix suggestions for detected code issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall codefix ./src\n"
            "  heimdall codefix ./src --rule ENV001\n"
            "  heimdall codefix ./src --format json\n"
        ),
    )
    add_codefix_args(codefix_parser)


def _setup_mcp_server_command(subparsers) -> None:
    """Set up the mcp-server top-level command."""
    mcp_server_parser = subparsers.add_parser(
        "mcp-server",
        help="Start the Asgard MCP server for AI agent integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall mcp-server\n"
            "  heimdall mcp-server --port 8080\n"
            "  heimdall mcp-server --path /api/mcp\n"
        ),
    )
    add_mcp_server_args(mcp_server_parser)


def _setup_dashboard_command(subparsers) -> None:
    """Set up the dashboard top-level command."""
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch web dashboard for browsing analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  heimdall dashboard --path ./my-project\n"
            "  heimdall dashboard --path ./my-project --port 9090\n"
            "  heimdall dashboard --path ./my-project --no-open-browser\n"
        ),
    )
    add_dashboard_args(dashboard_parser)


COMMAND_DEFAULT_SUBCOMMANDS = {
    "security": "scan",
    "performance": "scan",
    "oop": "analyze",
    "logic": "audit",
    "syntax": "check",
}

COMMAND_KNOWN_SUBCOMMANDS = {
    "security": {
        "scan", "secrets", "dependencies", "vulnerabilities", "crypto", "access",
        "auth", "headers", "tls", "container", "infra", "config-secrets",
        "hotspots", "compliance", "taint",
    },
    "performance": {"scan", "memory", "cpu", "database", "cache"},
    "oop": {"analyze", "coupling", "cohesion", "inheritance"},
    "logic": {"duplication", "patterns", "complexity", "audit"},
    "syntax": {"check", "fix"},
}


def main(args=None):
    """Main entry point for the Heimdall CLI.

    Args:
        args: Optional list of arguments. If None, uses sys.argv.
    """
    if args is None:
        argv = sys.argv[1:]
    else:
        argv = list(args)

    # Insert default subcommand when a command group is given a path directly
    # e.g. "heimdall security ./src" -> "heimdall security scan ./src"
    if len(argv) >= 2:
        cmd = argv[0]
        if cmd in COMMAND_DEFAULT_SUBCOMMANDS:
            next_arg = argv[1]
            known = COMMAND_KNOWN_SUBCOMMANDS[cmd]
            if next_arg not in known and next_arg not in ("-h", "--help"):
                argv.insert(1, COMMAND_DEFAULT_SUBCOMMANDS[cmd])

    parser = create_parser()
    args = parser.parse_args(argv)
    verbose = args.verbose if hasattr(args, "verbose") else False

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Commands that should NOT open a browser (long-running servers / no report output)
    _NO_BROWSER = {"mcp-server", "dashboard", "install-browsers", "scan"}
    _should_open_browser = args.command not in _NO_BROWSER

    _buf: io.StringIO = io.StringIO()
    _tee = _TeeStream(sys.stdout, _buf)
    if _should_open_browser:
        sys.stdout = _tee

    try:
        _dispatch(args, verbose)
    finally:
        if _should_open_browser:
            sys.stdout = sys.__stdout__
            _captured = _buf.getvalue()
            if _captured.strip():
                # Build a descriptive title including subcommand if available
                sub = (
                    getattr(args, "quality_command", None)
                    or getattr(args, "security_command", None)
                    or getattr(args, "performance_command", None)
                    or getattr(args, "deps_command", None)
                    or getattr(args, "arch_command", None)
                    or getattr(args, "oop_command", None)
                    or getattr(args, "logic_command", None)
                    or getattr(args, "syntax_command", None)
                    or getattr(args, "req_command", None)
                    or getattr(args, "lic_command", None)
                )
                _cmd_label = args.command
                if sub:
                    _cmd_label = f"{args.command} {sub}"
                _title = f"Heimdall - {_cmd_label}"
                open_output_in_browser(_captured, _title)


def _dispatch(args, verbose: bool) -> None:
    """Inner dispatch — separated so the browser-open finally block always runs."""

    # Handle quality subcommands
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

    # Handle audit command (alias for quality analyze)
    elif args.command == "audit":
        sys.exit(run_quality_analysis(args, verbose))

    # Handle security subcommands
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

    # Handle performance subcommands
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

    # Handle OOP subcommands
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

    # Handle dependencies subcommands
    elif args.command == "dependencies":
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

    # Handle architecture subcommands
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

    # Handle coverage subcommands
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

    # Handle syntax subcommands
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

    # Handle requirements subcommands
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

    # Handle licenses subcommands
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

    # Handle logic subcommands
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

    # Handle baseline subcommands
    elif args.command == "baseline":
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

    # Handle init-linter command
    elif args.command == "init-linter":
        sys.exit(run_init_linter(args, verbose))

    # Handle ratings command
    elif args.command == "ratings":
        sys.exit(run_ratings_analysis(args, verbose))

    # Handle gate command
    elif args.command == "gate":
        sys.exit(run_gate_evaluation(args, verbose))

    # Handle profiles command group
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

    # Handle history command group
    elif args.command == "history":
        if not hasattr(args, "history_command") or args.history_command is None:
            print("Error: Please specify a history subcommand. Available subcommands:")
            print("  show    Show recorded analysis snapshots")
            print("  trends  Show metric trend directions")
            print("\nUse 'heimdall history <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)
        sys.exit(run_history_command(args, verbose))

    # Handle new-code command group
    elif args.command == "new-code":
        if not hasattr(args, "new_code_command") or args.new_code_command is None:
            print("Error: Please specify a new-code subcommand. Available subcommands:")
            print("  detect  Show which files are considered new or modified code")
            print("\nUse 'heimdall new-code <subcommand> -h' for help on a specific subcommand.")
            sys.exit(1)
        sys.exit(run_new_code_detect(args, verbose))

    # Handle issues command
    elif args.command == "issues":
        sys.exit(run_issues_command(args, verbose))

    # Handle sbom command
    elif args.command == "sbom":
        sys.exit(run_sbom_generation(args, verbose))

    # Handle codefix command
    elif args.command == "codefix":
        sys.exit(run_codefix_suggestions(args, verbose))

    # Handle mcp-server command
    elif args.command == "mcp-server":
        sys.exit(run_mcp_server(args, verbose))

    # Handle dashboard command
    elif args.command == "dashboard":
        sys.exit(run_dashboard(args, verbose))

    # Handle scan command (runs ALL analyses)
    elif args.command == "scan":
        sys.exit(run_full_scan(args, verbose))

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
