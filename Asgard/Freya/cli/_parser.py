import argparse

from Asgard.Freya.cli._parser_flags import add_performance_flags
from Asgard.Freya.cli._parser_subcommands_a import (
    add_accessibility_parser,
    add_visual_parser,
    add_responsive_parser,
)
from Asgard.Freya.cli._parser_subcommands_b import (
    add_performance_parser,
    add_seo_parser,
    add_security_parser,
    add_console_parser,
    add_links_parser,
    add_images_parser,
    add_test_parser,
    add_crawl_parser,
    add_baseline_parser,
    add_config_parser,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="freya",
        description="Freya - Visual and UI Testing",
        epilog="Named after the Norse goddess of beauty and love.",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Freya 2.0.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    add_accessibility_parser(subparsers)
    add_visual_parser(subparsers)
    add_responsive_parser(subparsers)
    add_performance_parser(subparsers)
    add_seo_parser(subparsers)
    add_security_parser(subparsers)
    add_console_parser(subparsers)
    add_links_parser(subparsers)
    add_images_parser(subparsers)
    add_test_parser(subparsers)
    add_crawl_parser(subparsers)
    add_baseline_parser(subparsers)
    add_config_parser(subparsers)

    return parser
