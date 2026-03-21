"""
Freya Site Crawler page test runner.

Single-page test execution extracted from site_crawler.py.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import BrowserContext

from Asgard.Freya.Integration.models.integration_models import (
    CrawledPage,
    PageTestResult,
    TestCategory,
)
from Asgard.Freya.Integration.services._crawler_checks import (
    run_accessibility_checks,
    run_responsive_checks,
    run_visual_checks,
)
from Asgard.Freya.Integration.services._crawler_report import url_to_filename


async def test_page(
    context: BrowserContext,
    page_info: CrawledPage,
    output_dir: Path,
    capture_screenshots: bool,
    test_categories: List[TestCategory],
) -> PageTestResult:
    """Run tests on a single page."""
    start_time = time.time()
    issues = []
    screenshot_path: Optional[str] = None

    try:
        page = await context.new_page()
        await page.goto(page_info.url, wait_until="networkidle", timeout=30000)
        title = await page.title()

        if capture_screenshots:
            screenshot_filename = url_to_filename(page_info.url) + ".png"
            screenshot_path = str(output_dir / "screenshots" / screenshot_filename)
            await page.screenshot(path=screenshot_path, full_page=True)

        accessibility_score = 100.0
        visual_score = 100.0
        responsive_score = 100.0

        if TestCategory.ALL in test_categories or \
           TestCategory.ACCESSIBILITY in test_categories:
            a11y_issues = await run_accessibility_checks(page)
            issues.extend(a11y_issues)
            if a11y_issues:
                accessibility_score = max(0, 100 - len(a11y_issues) * 10)

        if TestCategory.ALL in test_categories or \
           TestCategory.VISUAL in test_categories:
            visual_issues = await run_visual_checks(page)
            issues.extend(visual_issues)
            if visual_issues:
                visual_score = max(0, 100 - len(visual_issues) * 5)

        if TestCategory.ALL in test_categories or \
           TestCategory.RESPONSIVE in test_categories:
            responsive_issues = await run_responsive_checks(page)
            issues.extend(responsive_issues)
            if responsive_issues:
                responsive_score = max(0, 100 - len(responsive_issues) * 5)

        await page.close()

        overall_score = (accessibility_score + visual_score + responsive_score) / 3

        critical = sum(1 for i in issues if i.get("severity") == "critical")
        serious = sum(1 for i in issues if i.get("severity") == "serious")
        moderate = sum(1 for i in issues if i.get("severity") == "moderate")
        minor = sum(1 for i in issues if i.get("severity") == "minor")

        duration_ms = int((time.time() - start_time) * 1000)

        return PageTestResult(
            url=page_info.url,
            title=title,
            tested_at=datetime.now().isoformat(),
            duration_ms=duration_ms,
            screenshot_path=screenshot_path,
            accessibility_score=accessibility_score,
            visual_score=visual_score,
            responsive_score=responsive_score,
            overall_score=overall_score,
            critical_issues=critical,
            serious_issues=serious,
            moderate_issues=moderate,
            minor_issues=minor,
            issues=issues,
            passed=critical == 0 and serious == 0,
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return PageTestResult(
            url=page_info.url,
            title=page_info.title,
            tested_at=datetime.now().isoformat(),
            duration_ms=duration_ms,
            passed=False,
            error=str(e),
        )
