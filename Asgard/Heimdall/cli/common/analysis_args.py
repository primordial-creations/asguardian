import argparse


def add_performance_args(parser: argparse.ArgumentParser) -> None:
    """Add performance analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["info", "low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to report (default: low)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_oop_args(parser: argparse.ArgumentParser) -> None:
    """Add OOP analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--cbo-threshold",
        type=int,
        default=14,
        help="CBO threshold for high coupling (default: 14)",
    )
    parser.add_argument(
        "--lcom-threshold",
        type=float,
        default=0.8,
        help="LCOM threshold for poor cohesion (default: 0.8)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_deps_args(parser: argparse.ArgumentParser) -> None:
    """Add dependency analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown", "mermaid", "graphviz"],
        default="text",
        help="Output format: text, json, markdown, mermaid (.mmd), graphviz (.dot) (default: text)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum depth for dependency graph (default: 10)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )
    parser.add_argument(
        "--direction",
        "-d",
        choices=["LR", "TB", "RL", "BT"],
        default="LR",
        help="Graph direction for mermaid/graphviz output (default: LR)",
    )


def add_deps_export_args(parser: argparse.ArgumentParser) -> None:
    """Add dependency export arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--export-format",
        "-e",
        choices=["dot", "graphviz", "json", "mermaid"],
        default="mermaid",
        help="Export format for the dependency graph: mermaid (.mmd), graphviz/dot (.dot), json (default: mermaid)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: print to stdout)",
    )
    parser.add_argument(
        "--direction",
        "-d",
        choices=["LR", "TB", "RL", "BT"],
        default="LR",
        help="Graph direction for Mermaid/DOT output (default: LR)",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


def add_arch_args(parser: argparse.ArgumentParser) -> None:
    """Add architecture analysis arguments to a parser."""
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Root path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-solid",
        action="store_true",
        help="Skip SOLID principle validation",
    )
    parser.add_argument(
        "--no-layers",
        action="store_true",
        help="Skip layer analysis",
    )
    parser.add_argument(
        "--no-patterns",
        action="store_true",
        help="Skip design pattern detection",
    )
    parser.add_argument(
        "--hexagonal",
        action="store_true",
        help="Include hexagonal (ports and adapters) architecture analysis",
    )
    parser.add_argument(
        "--exclude",
        "-x",
        type=str,
        nargs="+",
        default=[],
        help="Glob patterns for paths to exclude from scanning",
    )


