import argparse
import json

from Asgard.Freya.SEO.services.meta_tag_analyzer import MetaTagAnalyzer
from Asgard.Freya.SEO.services.structured_data_validator import StructuredDataValidator
from Asgard.Freya.SEO.services.robots_analyzer import RobotsAnalyzer
from Asgard.Freya.Security.services.security_header_scanner import SecurityHeaderScanner
from Asgard.Freya.Console.services.console_capture import ConsoleCapture
from Asgard.Freya.Console.models.console_models import ConsoleConfig
from Asgard.Freya.Links.services.link_validator import LinkValidator
from Asgard.Freya.Links.models.link_models import LinkConfig
from Asgard.Freya.cli._formatters_seo import (
    format_seo_text,
    format_meta_text,
    format_structured_data_text,
    format_robots_text,
)
from Asgard.Freya.cli._formatters_security_console_links import (
    format_security_text,
    format_csp_text,
    format_console_text,
    format_links_text,
)


async def run_seo_audit(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run SEO audit."""
    meta_analyzer = MetaTagAnalyzer()

    print(f"\nRunning SEO audit on: {args.url}")
    print("-" * 60)

    meta_result = await meta_analyzer.analyze(args.url)

    if args.format == "json":
        output = meta_result.model_dump_json(indent=2)
    else:
        output = format_seo_text(meta_result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if meta_result.has_issues else 0


async def run_seo_meta(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run meta tag analysis."""
    analyzer = MetaTagAnalyzer()

    print(f"\nAnalyzing meta tags: {args.url}")
    print("-" * 60)

    result = await analyzer.analyze(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_meta_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_issues else 0


async def run_seo_structured_data(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run structured data validation."""
    validator = StructuredDataValidator()

    print(f"\nValidating structured data: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_structured_data_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_errors else 0


async def run_seo_robots(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run robots.txt analysis."""
    analyzer = RobotsAnalyzer()

    print(f"\nAnalyzing robots.txt: {args.url}")
    print("-" * 60)

    robots_result = await analyzer.analyze_robots(args.url)
    sitemap_result = await analyzer.analyze_sitemap(args.url)

    if args.format == "json":
        output = json.dumps({
            "robots": robots_result.model_dump(),
            "sitemap": sitemap_result.model_dump(),
        }, indent=2, default=str)
    else:
        output = format_robots_text(robots_result, sitemap_result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await analyzer.close()

    return 1 if robots_result.has_issues or sitemap_result.has_issues else 0


async def run_security_headers(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run security headers analysis."""
    scanner = SecurityHeaderScanner()

    print(f"\nScanning security headers: {args.url}")
    print("-" * 60)

    result = await scanner.scan(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_security_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.has_issues else 0


async def run_security_csp(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run CSP analysis."""
    scanner = SecurityHeaderScanner()

    print(f"\nAnalyzing CSP: {args.url}")
    print("-" * 60)

    result = await scanner.scan(args.url)

    if result.csp_report:
        if args.format == "json":
            output = result.csp_report.model_dump_json(indent=2)
        else:
            output = format_csp_text(result.csp_report)
    else:
        output = "No Content-Security-Policy header found."

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await scanner.close()

    return 1 if result.csp_report and result.csp_report.has_issues else 0


async def run_console_errors(args: argparse.Namespace, verbose: bool = False) -> int:
    """Capture console errors."""
    config = ConsoleConfig(
        capture_warnings=getattr(args, "include_warnings", False),
        wait_time_ms=args.wait,
    )
    capture = ConsoleCapture(config)

    print(f"\nCapturing console errors: {args.url}")
    print("-" * 60)

    result = await capture.capture(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_console_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 1 if result.has_errors else 0


async def run_links_validate(args: argparse.Namespace, verbose: bool = False) -> int:
    """Validate links on a page."""
    config = LinkConfig(
        check_external=getattr(args, "external", True),
        max_links=args.max_links,
        timeout_ms=args.timeout,
    )
    validator = LinkValidator(config)

    print(f"\nValidating links: {args.url}")
    print("-" * 60)

    result = await validator.validate(args.url)

    if args.format == "json":
        output = result.model_dump_json(indent=2)
    else:
        output = format_links_text(result)

    if hasattr(args, "output") and args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    await validator.close()

    return 1 if result.has_broken_links else 0
