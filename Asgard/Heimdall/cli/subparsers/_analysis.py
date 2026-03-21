"""
Heimdall CLI - Analysis subparser setup.

Covers: performance, oop, dependencies, architecture, coverage,
        syntax, requirements, licenses, logic.
"""

import argparse

from Asgard.Heimdall.cli.common import (
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
)


def setup_performance_commands(subparsers) -> None:
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


def setup_oop_commands(subparsers) -> None:
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


def setup_deps_commands(subparsers) -> None:
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


def setup_arch_commands(subparsers) -> None:
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


def setup_coverage_commands(subparsers) -> None:
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


def setup_syntax_commands(subparsers) -> None:
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


def setup_requirements_commands(subparsers) -> None:
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


def setup_licenses_commands(subparsers) -> None:
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


def setup_logic_commands(subparsers) -> None:
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
