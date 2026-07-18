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
from Asgard.Freya.Scoring.models.scoring_models import (
    GateConfig,
    QualityGrade,
    UniversalSeverity,
)
from Asgard.Freya.Scoring.services.epistemics import TREND_INDICATOR_NOTE
from Asgard.Freya.Scoring.services.quality_gate import QualityGate
from Asgard.Freya.cli._formatters_visual_responsive import format_unified_text


def _build_gate_config(args: argparse.Namespace) -> GateConfig:
    """Build a GateConfig from CLI flags (config-file support comes later)."""
    fail_on_raw = getattr(args, "fail_on", None)
    if not isinstance(fail_on_raw, str):
        fail_on_raw = "blocker,critical"
    fail_on = []
    for token in str(fail_on_raw).split(","):
        token = token.strip().lower()
        if not token:
            continue
        try:
            fail_on.append(UniversalSeverity(token))
        except ValueError:
            continue
    min_grade_raw = getattr(args, "min_grade", None)
    min_grade = None
    if isinstance(min_grade_raw, str) and min_grade_raw.upper() in QualityGrade.__members__:
        min_grade = QualityGrade(min_grade_raw.upper())
    return GateConfig(fail_on=fail_on, min_grade=min_grade)


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
        threshold=args.threshold,
        allow_env_mismatch=getattr(args, "allow_env_mismatch", False),
    )

    if not result["success"]:
        print(f"Error: {result['error']}")
        return 1

    output_format = getattr(args, "format", "text")
    if output_format == "json":
        import json as _json
        print(_json.dumps(result, indent=2, default=str))
        if result.get("status") == "environment_mismatch":
            return 2
        return 0 if result.get("passed") else 1

    if output_format == "html":
        from Asgard.Freya.Integration.services.html_reporter import HTMLReporter
        output_path = getattr(args, "output", None) or "freya_baseline_comparison.html"
        report_path = HTMLReporter().generate_baseline_comparison(result, output_path)
        print(f"Report saved to: {report_path}")
        if result.get("status") == "environment_mismatch":
            return 2
        return 0 if result.get("passed") else 1

    baseline_fp = (result.get("baseline") or {}).get("fingerprint")
    current_fp = result.get("current_fingerprint")
    if baseline_fp or current_fp:
        print("Environment (baseline vs current):")
        for field in ("os_name", "browser_name", "browser_version",
                      "viewport", "device_scale_factor", "font_stack_hash"):
            base_value = (baseline_fp or {}).get(field, "unverified")
            curr_value = (current_fp or {}).get(field, "unverified")
            print(f"  {field}: {base_value} vs {curr_value}")

    if result.get("status") == "environment_mismatch":
        print("INCONCLUSIVE: environment mismatch — comparison refused.")
        print(f"Mismatched fields: {', '.join(result.get('mismatched_fields', []))}")
        print(result.get("rationale", ""))
        # Inconclusive is distinct from regression-found (exit 2, not 1)
        return 2

    if result.get("environment_warning"):
        print(f"WARNING: {result['environment_warning']}")

    if result.get("framing"):
        print(result["framing"])

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

    config_kwargs = dict(
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
    if isinstance(getattr(args, "concurrency", None), int):
        config_kwargs["concurrency"] = args.concurrency
    if isinstance(getattr(args, "concurrency_discovery", None), int):
        config_kwargs["concurrency_discovery"] = args.concurrency_discovery
    if isinstance(getattr(args, "min_request_interval_ms", None), int):
        config_kwargs["min_request_interval_ms"] = args.min_request_interval_ms

    config = CrawlConfig(**config_kwargs)

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
    site_grade = getattr(report, "site_grade", None)
    if isinstance(site_grade, str):
        cap_reason = getattr(report, "site_cap_reason", None)
        cap_suffix = f" (capped by: {cap_reason})" if isinstance(cap_reason, str) else ""
        print("-" * 70)
        print(f"  SITE GRADE: {site_grade}{cap_suffix}")
        print(f"  {TREND_INDICATOR_NOTE}")
        print("-" * 70)
        print("")
    print("-" * 70)
    print("  SCORES (Average - trend indicator only)")
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

    # Inconclusive: crawl produced no usable results (e.g. every page errored).
    # Exit code 2, distinct from a real gate FAIL, so pipelines can treat
    # environment/network flake differently from a genuine regression.
    pages_tested = getattr(report, "pages_tested", 0)
    pages_errored = getattr(report, "pages_errored", 0)
    if pages_tested == 0 and pages_errored > 0:
        print("Quality gate: INCONCLUSIVE (no pages tested successfully)")
        return 2

    if not getattr(args, "gate", True):
        print("Quality gate: SKIPPED (--no-gate / report-only mode)")
        return 0

    gate = QualityGate(_build_gate_config(args))
    grade = None
    if isinstance(site_grade, str) and site_grade in QualityGrade.__members__:
        grade = QualityGrade(site_grade)
    gate_result = gate.evaluate_counts(
        {
            "blocker": getattr(report, "total_blockers", 0),
            "critical": getattr(report, "total_critical", 0),
            "major": getattr(report, "total_serious", 0),
            "minor": getattr(report, "total_moderate", 0),
        },
        grade=grade,
    )
    if gate_result.passed:
        print("Quality gate: PASSED")
        return 0
    print("Quality gate: FAILED")
    for reason in gate_result.reasons:
        print(f"  - {reason}")
    return 1
