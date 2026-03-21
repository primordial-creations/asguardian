import argparse

from Asgard.Freya.cli._parser_flags import add_performance_flags


def add_accessibility_parser(subparsers) -> None:
    """Add accessibility command group."""
    accessibility_parser = subparsers.add_parser(
        "accessibility",
        help="Accessibility testing commands"
    )
    accessibility_subparsers = accessibility_parser.add_subparsers(
        dest="accessibility_command",
        help="Accessibility commands"
    )

    audit_parser = accessibility_subparsers.add_parser(
        "audit",
        help="Run full accessibility audit"
    )
    _add_accessibility_common_args(audit_parser)

    contrast_parser = accessibility_subparsers.add_parser(
        "contrast",
        help="Check color contrast"
    )
    _add_accessibility_common_args(contrast_parser)

    keyboard_parser = accessibility_subparsers.add_parser(
        "keyboard",
        help="Test keyboard navigation"
    )
    _add_accessibility_common_args(keyboard_parser)

    aria_parser = accessibility_subparsers.add_parser(
        "aria",
        help="Validate ARIA implementation"
    )
    _add_accessibility_common_args(aria_parser)

    screen_reader_parser = accessibility_subparsers.add_parser(
        "screen-reader",
        help="Test screen reader compatibility"
    )
    _add_accessibility_common_args(screen_reader_parser)


def _add_accessibility_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common accessibility arguments."""
    parser.add_argument(
        "url",
        type=str,
        help="URL to test",
    )
    parser.add_argument(
        "--level",
        "-l",
        choices=["A", "AA", "AAA"],
        default="AA",
        help="WCAG conformance level (default: AA)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "markdown", "html"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path",
    )
    parser.add_argument(
        "--severity",
        "-s",
        choices=["critical", "serious", "moderate", "minor", "info"],
        default="minor",
        help="Minimum severity to report (default: minor)",
    )


def add_visual_parser(subparsers) -> None:
    """Add visual command group."""
    visual_parser = subparsers.add_parser(
        "visual",
        help="Visual testing commands"
    )
    visual_subparsers = visual_parser.add_subparsers(
        dest="visual_command",
        help="Visual commands"
    )

    capture_parser = visual_subparsers.add_parser(
        "capture",
        help="Capture screenshot"
    )
    capture_parser.add_argument("url", type=str, help="URL to capture")
    capture_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    capture_parser.add_argument(
        "--full-page", action="store_true", help="Capture full page"
    )
    capture_parser.add_argument(
        "--device", "-d", type=str, help="Device to emulate"
    )
    capture_parser.add_argument(
        "--width", "-w", type=int, default=1920, help="Viewport width"
    )
    capture_parser.add_argument(
        "--height", "-H", type=int, default=1080, help="Viewport height"
    )

    compare_parser = visual_subparsers.add_parser(
        "compare",
        help="Compare two images"
    )
    compare_parser.add_argument("baseline", type=str, help="Baseline image path")
    compare_parser.add_argument("current", type=str, help="Current image path")
    compare_parser.add_argument(
        "--threshold", "-t", type=float, default=0.95,
        help="Similarity threshold (default: 0.95)"
    )
    compare_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format"
    )

    layout_parser = visual_subparsers.add_parser(
        "layout",
        help="Validate layout"
    )
    layout_parser.add_argument("url", type=str, help="URL to test")
    layout_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    layout_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    style_parser = visual_subparsers.add_parser(
        "style",
        help="Check style consistency"
    )
    style_parser.add_argument("url", type=str, help="URL to test")
    style_parser.add_argument(
        "--theme", type=str, help="Theme file to validate against"
    )
    style_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    style_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def add_responsive_parser(subparsers) -> None:
    """Add responsive command group."""
    responsive_parser = subparsers.add_parser(
        "responsive",
        help="Responsive testing commands"
    )
    responsive_subparsers = responsive_parser.add_subparsers(
        dest="responsive_command",
        help="Responsive commands"
    )

    breakpoints_parser = responsive_subparsers.add_parser(
        "breakpoints",
        help="Test breakpoints"
    )
    breakpoints_parser.add_argument("url", type=str, help="URL to test")
    breakpoints_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    breakpoints_parser.add_argument(
        "--screenshots", action="store_true", help="Capture screenshots"
    )
    breakpoints_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    touch_parser = responsive_subparsers.add_parser(
        "touch",
        help="Validate touch targets"
    )
    touch_parser.add_argument("url", type=str, help="URL to test")
    touch_parser.add_argument(
        "--min-size", type=int, default=44,
        help="Minimum touch target size in pixels (default: 44)"
    )
    touch_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    touch_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    viewport_parser = responsive_subparsers.add_parser(
        "viewport",
        help="Test viewport behavior"
    )
    viewport_parser.add_argument("url", type=str, help="URL to test")
    viewport_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    viewport_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    mobile_parser = responsive_subparsers.add_parser(
        "mobile",
        help="Test mobile compatibility"
    )
    mobile_parser.add_argument("url", type=str, help="URL to test")
    mobile_parser.add_argument(
        "--devices", "-d", type=str, nargs="+",
        help="Devices to test (e.g., iphone-14 pixel-7)"
    )
    mobile_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    mobile_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
