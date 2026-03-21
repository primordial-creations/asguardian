from Asgard.Freya.cli._parser_flags import add_performance_flags


def add_performance_parser(subparsers) -> None:
    """Add performance command group."""
    performance_parser = subparsers.add_parser(
        "performance",
        help="Performance testing commands"
    )
    performance_subparsers = performance_parser.add_subparsers(
        dest="performance_command",
        help="Performance commands"
    )

    audit_parser = performance_subparsers.add_parser(
        "audit",
        help="Run full performance audit"
    )
    audit_parser.add_argument("url", type=str, help="URL to test")
    audit_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    audit_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    loadtime_parser = performance_subparsers.add_parser(
        "load-time",
        help="Measure page load timing"
    )
    loadtime_parser.add_argument("url", type=str, help="URL to test")
    loadtime_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    loadtime_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    resources_parser = performance_subparsers.add_parser(
        "resources",
        help="Analyze resource loading"
    )
    resources_parser.add_argument("url", type=str, help="URL to test")
    resources_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    resources_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def add_seo_parser(subparsers) -> None:
    """Add SEO command group."""
    seo_parser = subparsers.add_parser(
        "seo",
        help="SEO analysis commands"
    )
    seo_subparsers = seo_parser.add_subparsers(
        dest="seo_command",
        help="SEO commands"
    )

    audit_parser = seo_subparsers.add_parser(
        "audit",
        help="Run full SEO audit"
    )
    audit_parser.add_argument("url", type=str, help="URL to test")
    audit_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    audit_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    meta_parser = seo_subparsers.add_parser(
        "meta",
        help="Analyze meta tags"
    )
    meta_parser.add_argument("url", type=str, help="URL to test")
    meta_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    meta_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    structured_parser = seo_subparsers.add_parser(
        "structured-data",
        help="Validate structured data"
    )
    structured_parser.add_argument("url", type=str, help="URL to test")
    structured_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    structured_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    robots_parser = seo_subparsers.add_parser(
        "robots",
        help="Analyze robots.txt and sitemap"
    )
    robots_parser.add_argument("url", type=str, help="Site URL")
    robots_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    robots_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def add_security_parser(subparsers) -> None:
    """Add security command group."""
    security_parser = subparsers.add_parser(
        "security",
        help="Security header analysis commands"
    )
    security_subparsers = security_parser.add_subparsers(
        dest="security_command",
        help="Security commands"
    )

    headers_parser = security_subparsers.add_parser(
        "headers",
        help="Analyze security headers"
    )
    headers_parser.add_argument("url", type=str, help="URL to test")
    headers_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    headers_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )

    csp_parser = security_subparsers.add_parser(
        "csp",
        help="Deep CSP analysis"
    )
    csp_parser.add_argument("url", type=str, help="URL to test")
    csp_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text"
    )
    csp_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )


def add_console_parser(subparsers) -> None:
    """Add console command group."""
    console_parser = subparsers.add_parser(
        "console",
        help="JavaScript console capture commands"
    )
    console_subparsers = console_parser.add_subparsers(
        dest="console_command",
        help="Console commands"
    )

    errors_parser = console_subparsers.add_parser(
        "errors",
        help="Capture JavaScript errors"
    )
    errors_parser.add_argument("url", type=str, help="URL to test")
    errors_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    errors_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    errors_parser.add_argument(
        "--wait", "-w", type=int, default=3000,
        help="Wait time in ms for messages (default: 3000)"
    )
    errors_parser.add_argument(
        "--include-warnings", action="store_true",
        help="Also capture warnings"
    )


def add_links_parser(subparsers) -> None:
    """Add links command group."""
    links_parser = subparsers.add_parser(
        "links",
        help="Link validation commands"
    )
    links_subparsers = links_parser.add_subparsers(
        dest="links_command",
        help="Links commands"
    )

    validate_parser = links_subparsers.add_parser(
        "validate",
        help="Validate links on a page"
    )
    validate_parser.add_argument("url", type=str, help="URL to test")
    validate_parser.add_argument(
        "--format", "-f", choices=["text", "json", "github"], default="text"
    )
    validate_parser.add_argument(
        "--output", "-o", type=str, help="Output file path"
    )
    validate_parser.add_argument(
        "--external", "-e", action="store_true",
        help="Also check external links"
    )
    validate_parser.add_argument(
        "--max-links", "-m", type=int, default=500,
        help="Maximum links to check (default: 500)"
    )
    validate_parser.add_argument(
        "--timeout", "-t", type=int, default=10000,
        help="Timeout per link in ms (default: 10000)"
    )
    add_performance_flags(validate_parser)
