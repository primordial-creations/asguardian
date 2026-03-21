from Asgard.Freya.cli._parser_flags import add_performance_flags


def add_images_parser(subparsers) -> None:
    """Add images command group."""
    images_parser = subparsers.add_parser(
        "images",
        help="Image optimization scanning commands"
    )
    images_subparsers = images_parser.add_subparsers(
        dest="images_command",
        help="Images commands"
    )

    audit_parser = images_subparsers.add_parser(
        "audit",
        help="Run full image optimization audit"
    )
    audit_parser.add_argument("url", type=str, help="URL to scan")
    audit_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text",
        help="Output format (default: text)"
    )
    audit_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    audit_parser.add_argument(
        "--include-all", action="store_true",
        help="Include all images in report, not just those with issues"
    )
    add_performance_flags(audit_parser)

    alt_text_parser = images_subparsers.add_parser(
        "alt-text",
        help="Check image alt text only"
    )
    alt_text_parser.add_argument("url", type=str, help="URL to scan")
    alt_text_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text",
        help="Output format (default: text)"
    )
    alt_text_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    performance_parser = images_subparsers.add_parser(
        "performance",
        help="Check image performance issues only"
    )
    performance_parser.add_argument("url", type=str, help="URL to scan")
    performance_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text",
        help="Output format (default: text)"
    )
    performance_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    performance_parser.add_argument(
        "--oversized-threshold", type=float, default=1.5,
        help="Ratio threshold for oversized detection (default: 1.5)"
    )


def add_test_parser(subparsers) -> None:
    """Add unified test command."""
    test_parser = subparsers.add_parser(
        "test",
        help="Run all tests (accessibility, visual, responsive)"
    )
    test_parser.add_argument("url", type=str, help="URL to test")
    test_parser.add_argument(
        "--level", "-l", choices=["A", "AA", "AAA"], default="AA",
        help="WCAG conformance level"
    )
    test_parser.add_argument(
        "--format", "-f", choices=["text", "json", "html", "junit"],
        default="text", help="Output format"
    )
    test_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    test_parser.add_argument(
        "--severity", "-s",
        choices=["critical", "serious", "moderate", "minor"],
        default="minor", help="Minimum severity to report"
    )
    test_parser.add_argument(
        "--skip-accessibility", action="store_true",
        help="Skip accessibility tests"
    )
    test_parser.add_argument(
        "--skip-visual", action="store_true",
        help="Skip visual tests"
    )
    test_parser.add_argument(
        "--skip-responsive", action="store_true",
        help="Skip responsive tests"
    )
    add_performance_flags(test_parser)


def add_crawl_parser(subparsers) -> None:
    """Add site crawl command."""
    crawl_parser = subparsers.add_parser(
        "crawl",
        help="Crawl and test entire site"
    )
    crawl_parser.add_argument("url", type=str, help="Starting URL to crawl")
    crawl_parser.add_argument(
        "--depth", "-d", type=int, default=3,
        help="Maximum crawl depth (default: 3)"
    )
    crawl_parser.add_argument(
        "--max-pages", "-m", type=int, default=100,
        help="Maximum pages to crawl (default: 100)"
    )
    crawl_parser.add_argument(
        "--output", "-o", type=str, default="./freya_crawl_output",
        help="Output directory for reports"
    )
    crawl_parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Delay between requests in seconds (default: 0.5)"
    )
    crawl_parser.add_argument(
        "--no-screenshots", action="store_true",
        help="Skip capturing screenshots"
    )
    crawl_parser.add_argument(
        "--include", type=str, action="append", default=[],
        help="URL patterns to include (regex, can be repeated)"
    )
    crawl_parser.add_argument(
        "--exclude", type=str, action="append", default=[],
        help="URL patterns to exclude (regex, can be repeated)"
    )
    crawl_parser.add_argument(
        "--login-url", type=str,
        help="URL of login page for authentication"
    )
    crawl_parser.add_argument(
        "--username", type=str,
        help="Username for authentication"
    )
    crawl_parser.add_argument(
        "--password", type=str,
        help="Password for authentication"
    )
    crawl_parser.add_argument(
        "--username-selector", type=str, default='input[name="username"]',
        help="CSS selector for username field"
    )
    crawl_parser.add_argument(
        "--password-selector", type=str, default='input[name="password"]',
        help="CSS selector for password field"
    )
    crawl_parser.add_argument(
        "--submit-selector", type=str, default='button[type="submit"]',
        help="CSS selector for submit button"
    )
    crawl_parser.add_argument(
        "--headless", action="store_true", default=True,
        help="Run browser in headless mode (default: true)"
    )
    crawl_parser.add_argument(
        "--no-headless", action="store_true",
        help="Show browser window during crawl"
    )
    crawl_parser.add_argument(
        "--routes", type=str, action="append", default=[],
        help="Additional routes to test (for SPAs), e.g., --routes /notes --routes /calendar"
    )
    crawl_parser.add_argument(
        "--discover-items", action="store_true", default=True,
        help="Auto-discover clickable items like notes, boards, etc. (default: true)"
    )
    crawl_parser.add_argument(
        "--no-discover-items", action="store_true",
        help="Disable auto-discovery of clickable items"
    )
    add_performance_flags(crawl_parser)


def add_baseline_parser(subparsers) -> None:
    """Add baseline management commands."""
    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Baseline management commands"
    )
    baseline_subparsers = baseline_parser.add_subparsers(
        dest="baseline_command",
        help="Baseline commands"
    )

    update_parser = baseline_subparsers.add_parser(
        "update",
        help="Create or update a baseline"
    )
    update_parser.add_argument("url", type=str, help="URL to capture")
    update_parser.add_argument("--name", "-n", type=str, required=True, help="Baseline name")
    update_parser.add_argument("--device", "-d", type=str, help="Device to emulate")
    update_parser.add_argument("--width", "-w", type=int, default=1920, help="Viewport width")
    update_parser.add_argument("--height", "-H", type=int, default=1080, help="Viewport height")

    compare_parser = baseline_subparsers.add_parser(
        "compare",
        help="Compare current page to baseline"
    )
    compare_parser.add_argument("url", type=str, help="URL to compare")
    compare_parser.add_argument("--name", "-n", type=str, required=True, help="Baseline name")
    compare_parser.add_argument("--device", "-d", type=str, help="Device to emulate")
    compare_parser.add_argument("--threshold", "-t", type=float, default=0.1, help="Difference threshold")

    list_parser = baseline_subparsers.add_parser(
        "list",
        help="List all baselines"
    )
    list_parser.add_argument("--url", type=str, help="Filter by URL")

    delete_parser = baseline_subparsers.add_parser(
        "delete",
        help="Delete a baseline"
    )
    delete_parser.add_argument("--name", "-n", type=str, required=True, help="Baseline name")
    delete_parser.add_argument("url", type=str, help="URL of baseline")
    delete_parser.add_argument("--device", "-d", type=str, help="Device of baseline")


def add_config_parser(subparsers) -> None:
    """Add configuration commands."""
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration commands"
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_command",
        help="Config commands"
    )

    config_subparsers.add_parser("show", help="Show current configuration")
    config_subparsers.add_parser("init", help="Initialize configuration file")
