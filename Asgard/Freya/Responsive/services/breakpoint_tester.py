"""
Freya Breakpoint Tester

Tests responsive layouts across different viewport sizes.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    BreakpointIssue,
    BreakpointIssueType,
    BreakpointReport,
    BreakpointTestResult,
    COMMON_BREAKPOINTS,
)
from Asgard.Freya.Responsive.services._breakpoint_tester_checks import (
    check_horizontal_scroll,
    check_content_overflow,
    check_overlapping_elements,
    check_text_truncation,
)


class BreakpointTester:
    """
    Breakpoint testing service.

    Tests responsive layouts across different viewport sizes.
    """

    def __init__(self, output_directory: str = "./breakpoint_tests"):
        """
        Initialize the Breakpoint Tester.

        Args:
            output_directory: Directory for screenshots
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    async def test(
        self,
        url: str,
        breakpoints: Optional[List[Breakpoint]] = None,
        capture_screenshots: bool = True
    ) -> BreakpointReport:
        """
        Test a page across breakpoints.

        Args:
            url: URL to test
            breakpoints: List of breakpoints to test
            capture_screenshots: Whether to capture screenshots

        Returns:
            BreakpointReport with findings
        """
        if breakpoints is None:
            breakpoints = COMMON_BREAKPOINTS

        results = []
        all_issues = {}
        screenshots = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for bp in breakpoints:
                context = await browser.new_context(
                    viewport={"width": bp.width, "height": bp.height},
                    device_scale_factor=bp.device_scale_factor,
                    is_mobile=bp.is_mobile,
                    has_touch=bp.is_mobile,
                )
                page = await context.new_page()

                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)

                    issues = []

                    scroll_issues = await check_horizontal_scroll(page, bp)
                    issues.extend(scroll_issues)

                    overflow_issues = await check_content_overflow(page, bp)
                    issues.extend(overflow_issues)

                    overlap_issues = await check_overlapping_elements(page, bp)
                    issues.extend(overlap_issues)

                    text_issues = await check_text_truncation(page, bp)
                    issues.extend(text_issues)

                    page_width = await page.evaluate(
                        "() => document.documentElement.scrollWidth"
                    )
                    has_scroll = page_width > bp.width

                    screenshot_path = None
                    if capture_screenshots:
                        screenshot_path = str(
                            self.output_directory / f"{bp.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        )
                        await page.screenshot(path=screenshot_path, full_page=True)
                        screenshots[bp.name] = screenshot_path

                    result = BreakpointTestResult(
                        breakpoint=bp,
                        issues=issues,
                        screenshot_path=screenshot_path,
                        page_width=page_width,
                        has_horizontal_scroll=has_scroll,
                    )
                    results.append(result)
                    all_issues[bp.name] = issues

                finally:
                    await context.close()

            await browser.close()

        total_issues = sum(len(issues) for issues in all_issues.values())

        return BreakpointReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            breakpoints_tested=[bp.name for bp in breakpoints],
            total_issues=total_issues,
            results=results,
            breakpoint_issues=all_issues,
            screenshots=screenshots,
        )

    async def _check_horizontal_scroll(
        self,
        page: Page,
        breakpoint: Breakpoint
    ) -> List[BreakpointIssue]:
        """Check for horizontal scrolling."""
        return await check_horizontal_scroll(page, breakpoint)

    async def _check_content_overflow(
        self,
        page: Page,
        breakpoint: Breakpoint
    ) -> List[BreakpointIssue]:
        """Check for content overflow issues."""
        return await check_content_overflow(page, breakpoint)

    async def _check_overlapping_elements(
        self,
        page: Page,
        breakpoint: Breakpoint
    ) -> List[BreakpointIssue]:
        """Check for overlapping interactive elements."""
        return await check_overlapping_elements(page, breakpoint)

    async def _check_text_truncation(
        self,
        page: Page,
        breakpoint: Breakpoint
    ) -> List[BreakpointIssue]:
        """Check for unintended text truncation."""
        return await check_text_truncation(page, breakpoint)
