import argparse

from Asgard.Freya.Integration.models.integration_models import (
    TestCategory,
    TestSeverity,
    CrawlConfig,
    BrowserConfig,
)
from Asgard.Freya.Integration.services import (
    UnifiedTester,
    HTMLReporter,
    BaselineManager,
)
from Asgard.Freya.Integration.services.site_crawler import SiteCrawler
from Asgard.Freya.cli._formatters_visual_responsive import format_unified_text


async def run_unified_test(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run unified test."""
    categories = []
    if not args.skip_accessibility:
        categories.append(TestCategory.ACCESSIBILITY)
    if not args.skip_visual:
        categories.append(TestCategory.VISUAL)
    if not args.skip_responsive:
        categories.append(TestCategory.RESPONSIVE)

    if not categories:
        categories = [TestCategory.ALL]

    severity_map = {
        "critical": TestSeverity.CRITICAL,
        "serious": TestSeverity.SERIOUS,
        "moderate": TestSeverity.MODERATE,
        "minor": TestSeverity.MINOR,
    }
    min_severity = severity_map.get(args.severity, TestSeverity.MINOR)

    tester = UnifiedTester()

    print(f"\nRunning unified tests on: {args.url}")
    print("-" * 60)

    result = await tester.test(
        args.url,
        categories=categories,
        min_severity=min_severity
    )

    if args.format == "json":
        output = result.model_dump_json(indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Report saved to: {args.output}")
        else:
            print(output)
    elif args.format == "html":
        reporter = HTMLReporter()
        output_path = args.output or "./freya_report.html"
        reporter.generate(result, output_path)
        print(f"HTML report saved to: {output_path}")
    elif args.format == "junit":
        reporter = HTMLReporter()
        output_path = args.output or "./freya_report.xml"
        reporter.generate_junit(result, output_path)
        print(f"JUnit report saved to: {output_path}")
    else:
        output = format_unified_text(result)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Report saved to: {args.output}")
        else:
            print(output)

    return 1 if result.failed > 0 else 0


async def run_baseline_update(args: argparse.Namespace, verbose: bool = False) -> int:
    """Update baseline."""
    manager = BaselineManager()

    print(f"\nUpdating baseline: {args.name}")
    print(f"URL: {args.url}")
    print("-" * 60)

    result = await manager.create_baseline(
        args.url,
        args.name,
        viewport_width=args.width,
        viewport_height=args.height,
        device=getattr(args, "device", None)
    )

    print(f"Baseline created: {result.screenshot_path}")
    print(f"Hash: {result.hash}")

    return 0


async def run_baseline_compare(args: argparse.Namespace, verbose: bool = False) -> int:
    """Compare to baseline."""
    manager = BaselineManager()

    print(f"\nComparing to baseline: {args.name}")
    print(f"URL: {args.url}")
    print("-" * 60)

    result = await manager.compare_to_baseline(
        args.url,
        args.name,
        device=getattr(args, "device", None),
        threshold=args.threshold
    )

    if not result["success"]:
        print(f"Error: {result['error']}")
        return 1

    print(f"Passed: {'Yes' if result['passed'] else 'No'}")
    print(f"Difference: {result['difference_percentage']:.2f}%")
    if result["diff_image_path"]:
        print(f"Diff image: {result['diff_image_path']}")

    return 0 if result["passed"] else 1


def run_baseline_list(args: argparse.Namespace, verbose: bool = False) -> int:
    """List baselines."""
    manager = BaselineManager()

    url_filter = getattr(args, "url", None)
    baselines = manager.list_baselines(url=url_filter)

    print("\nBaselines:")
    print("-" * 60)

    if not baselines:
        print("  No baselines found.")
    else:
        for baseline in baselines:
            print(f"  {baseline.name}")
            print(f"    URL: {baseline.url}")
            print(f"    Created: {baseline.created_at}")
            print(f"    Device: {baseline.device or 'desktop'}")
            print("")

    return 0


def run_baseline_delete(args: argparse.Namespace, verbose: bool = False) -> int:
    """Delete baseline."""
    manager = BaselineManager()

    success = manager.delete_baseline(
        args.url,
        args.name,
        device=getattr(args, "device", None)
    )

    if success:
        print(f"Baseline '{args.name}' deleted.")
        return 0
    else:
        print(f"Baseline '{args.name}' not found.")
        return 1


async def run_crawl(args: argparse.Namespace, verbose: bool = False) -> int:
    """Run site crawl and test."""
    print(f"\nCrawling and testing: {args.url}")
    print(f"Max depth: {args.depth}, Max pages: {args.max_pages}")
    print("-" * 60)

    auth_config = None
    if args.username and args.password:
        auth_config = {
            "login_url": args.login_url or args.url,
            "username": args.username,
            "password": args.password,
            "username_selector": args.username_selector,
            "password_selector": args.password_selector,
            "submit_selector": args.submit_selector,
        }

    exclude_patterns = [
        r".*\.(jpg|jpeg|png|gif|svg|ico|css|js|woff|woff2|ttf|eot)$",
        r".*#.*",
        r".*/api/.*",
        r".*logout.*",
    ]
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    config = CrawlConfig(
        start_url=args.url,
        max_depth=args.depth,
        max_pages=args.max_pages,
        additional_routes=args.routes or [],
        discover_items=not getattr(args, 'no_discover_items', False),
        include_patterns=args.include or [],
        exclude_patterns=exclude_patterns,
        delay_between_requests=args.delay,
        capture_screenshots=not args.no_screenshots,
        auth_config=auth_config,
        output_directory=args.output,
        browser_config=BrowserConfig(
            headless=not args.no_headless
        ),
    )

    crawler = SiteCrawler(config)

    def progress_callback(message: str, current: int = 0, total: int = 0):
        if total > 0:
            print(f"  [{current}/{total}] {message}")
        else:
            print(f"  {message}")

    crawler.set_progress_callback(progress_callback)

    report = await crawler.crawl_and_test()

    print("")
    print("=" * 70)
    print("  FREYA SITE CRAWL REPORT")
    print("=" * 70)
    print("")
    print(f"  Start URL:        {report.start_url}")
    print(f"  Duration:         {report.total_duration_ms / 1000:.1f}s")
    print("")
    print(f"  Pages Discovered: {report.pages_discovered}")
    print(f"  Pages Tested:     {report.pages_tested}")
    print(f"  Pages Skipped:    {report.pages_skipped}")
    print(f"  Pages Errored:    {report.pages_errored}")
    print("")
    print("-" * 70)
    print("  SCORES (Average)")
    print("-" * 70)
    print(f"  Overall:        {report.average_overall_score:.0f}/100")
    print(f"  Accessibility:  {report.average_accessibility_score:.0f}/100")
    print(f"  Visual:         {report.average_visual_score:.0f}/100")
    print(f"  Responsive:     {report.average_responsive_score:.0f}/100")
    print("")
    print("-" * 70)
    print("  ISSUES")
    print("-" * 70)
    print(f"  Critical: {report.total_critical}")
    print(f"  Serious:  {report.total_serious}")
    print(f"  Moderate: {report.total_moderate}")
    print(f"  Minor:    {report.total_minor}")
    print("")

    if report.worst_pages:
        print("-" * 70)
        print("  WORST PAGES")
        print("-" * 70)
        for url in report.worst_pages[:5]:
            result = next((r for r in report.page_results if r.url == url), None)
            if result:
                print(f"  {result.overall_score:.0f}/100 - {url}")
        print("")

    if report.common_issues:
        print("-" * 70)
        print("  COMMON ISSUES")
        print("-" * 70)
        for issue in report.common_issues[:5]:
            print(f"  [{issue['count']}x] {issue['issue']}: {issue['message']}")
        print("")

    print("=" * 70)
    print(f"\nReports saved to: {args.output}")
    print(f"  - JSON: {args.output}/crawl_report.json")
    print(f"  - HTML: {args.output}/crawl_report.html")

    has_critical = report.total_critical > 0
    return 1 if has_critical else 0
