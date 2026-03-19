"""
Freya Mobile Compatibility Tester

Tests mobile device compatibility including performance,
feature detection, and common mobile issues.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    MobileCompatibilityIssue,
    MobileCompatibilityIssueType,
    MobileCompatibilityReport,
    MOBILE_DEVICES,
)


class MobileCompatibilityTester:
    """
    Mobile compatibility testing service.

    Tests pages across multiple mobile devices for
    compatibility issues.
    """

    def __init__(self):
        """Initialize the Mobile Compatibility Tester."""
        pass

    async def test(
        self,
        url: str,
        devices: Optional[List[str]] = None
    ) -> MobileCompatibilityReport:
        """
        Test mobile compatibility.

        Args:
            url: URL to test
            devices: List of device names to test

        Returns:
            MobileCompatibilityReport with findings
        """
        if devices is None:
            devices = ["iphone-14", "pixel-7", "ipad"]

        issues = []
        device_results = {}
        load_time_ms = None
        page_size_bytes = 0
        resource_count = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for device_name in devices:
                if device_name not in MOBILE_DEVICES:
                    continue

                device = MOBILE_DEVICES[device_name]

                context = await browser.new_context(
                    viewport={"width": device.width, "height": device.height},
                    device_scale_factor=device.device_scale_factor,
                    is_mobile=True,
                    has_touch=True,
                )
                page = await context.new_page()

                try:
                    start_time = time.time()
                    response = await page.goto(url, wait_until="networkidle", timeout=30000)
                    load_time = int((time.time() - start_time) * 1000)

                    if load_time_ms is None:
                        load_time_ms = load_time

                    device_issues = []

                    flash_issues = await self._check_flash_content(page)
                    device_issues.extend(flash_issues)

                    hover_issues = await self._check_hover_dependencies(page)
                    device_issues.extend(hover_issues)

                    text_issues = await self._check_small_text(page)
                    device_issues.extend(text_issues)

                    fixed_issues = await self._check_fixed_positioning(page)
                    device_issues.extend(fixed_issues)

                    for issue in device_issues:
                        if device_name not in issue.affected_devices:
                            issue.affected_devices.append(device_name)

                    issues.extend(device_issues)

                    metrics = await page.evaluate("""
                        () => {
                            const resources = performance.getEntriesByType('resource');
                            let totalSize = 0;

                            for (const resource of resources) {
                                totalSize += resource.transferSize || 0;
                            }

                            return {
                                resourceCount: resources.length,
                                totalSize: totalSize
                            };
                        }
                    """)

                    resource_count = max(resource_count, metrics["resourceCount"])
                    page_size_bytes = max(page_size_bytes, metrics["totalSize"])

                    device_results[device_name] = {
                        "load_time_ms": load_time,
                        "viewport": f"{device.width}x{device.height}",
                        "issues_count": len(device_issues),
                    }

                finally:
                    await context.close()

            await browser.close()

        unique_issues = self._deduplicate_issues(issues)

        if load_time_ms and load_time_ms > 3000:
            unique_issues.append(MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.SLOW_LOADING,
                description=f"Page load time ({load_time_ms}ms) exceeds recommended 3 seconds",
                severity="moderate",
                suggested_fix="Optimize images, reduce JavaScript, and leverage caching",
                affected_devices=devices,
            ))

        score = self._calculate_score(unique_issues, load_time_ms, page_size_bytes)

        return MobileCompatibilityReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            devices_tested=devices,
            issues=unique_issues,
            load_time_ms=load_time_ms,
            page_size_bytes=page_size_bytes,
            resource_count=resource_count,
            mobile_friendly_score=score,
            device_results=device_results,
        )

    async def _check_flash_content(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for Flash content."""
        issues = []

        try:
            flash_elements = await page.evaluate("""
                () => {
                    const flash = document.querySelectorAll(
                        'object[type*="flash"], embed[type*="flash"], ' +
                        'object[data*=".swf"], embed[src*=".swf"]'
                    );
                    return flash.length;
                }
            """)

            if flash_elements > 0:
                issues.append(MobileCompatibilityIssue(
                    issue_type=MobileCompatibilityIssueType.FLASH_CONTENT,
                    description=f"Page contains {flash_elements} Flash element(s)",
                    severity="critical",
                    suggested_fix="Replace Flash content with HTML5 alternatives",
                    affected_devices=[],
                ))

        except Exception:
            pass

        return issues

    async def _check_hover_dependencies(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for hover-dependent functionality."""
        issues = []

        try:
            hover_elements = await page.evaluate("""
                () => {
                    const results = [];

                    // Check for elements that only show on hover
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const style = getComputedStyle(el);

                        // Check if element has hover-related styling
                        if (el.matches(':hover') === false) {
                            const hoverRules = Array.from(document.styleSheets).some(sheet => {
                                try {
                                    return Array.from(sheet.cssRules || []).some(rule => {
                                        return rule.selectorText &&
                                               rule.selectorText.includes(':hover') &&
                                               el.matches(rule.selectorText.replace(':hover', ''));
                                    });
                                } catch (e) {
                                    return false;
                                }
                            });
                        }
                    }

                    // Check for dropdown menus that require hover
                    const dropdowns = document.querySelectorAll(
                        '[class*="dropdown"], [class*="menu"], nav ul ul'
                    );

                    for (const dropdown of dropdowns) {
                        const style = getComputedStyle(dropdown);
                        if (style.display === 'none' || style.visibility === 'hidden') {
                            results.push({
                                selector: dropdown.className || dropdown.tagName.toLowerCase(),
                                type: 'hidden-menu'
                            });
                        }
                    }

                    return results.slice(0, 5);
                }
            """)

            for elem in hover_elements:
                issues.append(MobileCompatibilityIssue(
                    issue_type=MobileCompatibilityIssueType.HOVER_DEPENDENT,
                    element_selector=elem["selector"],
                    description="Element appears to require hover interaction",
                    severity="moderate",
                    suggested_fix="Add touch/click alternatives for hover-based interactions",
                    affected_devices=[],
                ))

        except Exception:
            pass

        return issues

    async def _check_small_text(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for text that's too small on mobile."""
        issues = []

        try:
            small_text = await page.evaluate("""
                () => {
                    const results = [];
                    const textElements = document.querySelectorAll('p, span, div, li, a');

                    for (const el of textElements) {
                        const style = getComputedStyle(el);
                        const text = el.textContent || '';

                        if (text.trim().length < 5) continue;

                        const fontSize = parseFloat(style.fontSize);

                        if (fontSize < 12) {
                            const selector = el.id ? '#' + el.id :
                                              el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] :
                                              el.tagName.toLowerCase();

                            results.push({
                                selector: selector,
                                fontSize: fontSize
                            });
                        }
                    }

                    return results.slice(0, 5);
                }
            """)

            if small_text:
                issues.append(MobileCompatibilityIssue(
                    issue_type=MobileCompatibilityIssueType.SMALL_TEXT,
                    description=f"Found {len(small_text)} elements with text smaller than 12px",
                    severity="moderate",
                    suggested_fix="Use a minimum font size of 16px for body text on mobile",
                    affected_devices=[],
                ))

        except Exception:
            pass

        return issues

    async def _check_fixed_positioning(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for problematic fixed positioning."""
        issues = []

        try:
            fixed_elements = await page.evaluate("""
                () => {
                    const results = [];
                    const elements = document.querySelectorAll('*');

                    for (const el of elements) {
                        const style = getComputedStyle(el);

                        if (style.position === 'fixed') {
                            const rect = el.getBoundingClientRect();

                            // Check if fixed element takes significant viewport space
                            const viewportCoverage = (rect.width * rect.height) /
                                                     (window.innerWidth * window.innerHeight);

                            if (viewportCoverage > 0.2) {
                                const selector = el.id ? '#' + el.id :
                                                  el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] :
                                                  el.tagName.toLowerCase();

                                results.push({
                                    selector: selector,
                                    coverage: viewportCoverage
                                });
                            }
                        }
                    }

                    return results;
                }
            """)

            for elem in fixed_elements:
                issues.append(MobileCompatibilityIssue(
                    issue_type=MobileCompatibilityIssueType.FIXED_POSITIONING,
                    element_selector=elem["selector"],
                    description=f"Fixed element covers {elem['coverage']*100:.0f}% of viewport",
                    severity="moderate",
                    suggested_fix="Consider making fixed elements smaller or collapsible on mobile",
                    affected_devices=[],
                ))

        except Exception:
            pass

        return issues

    def _deduplicate_issues(
        self,
        issues: List[MobileCompatibilityIssue]
    ) -> List[MobileCompatibilityIssue]:
        """Remove duplicate issues, merging affected devices."""
        seen: dict[str, MobileCompatibilityIssue] = {}

        for issue in issues:
            key = f"{issue.issue_type}:{issue.element_selector}:{issue.description}"

            if key in seen:
                for device in issue.affected_devices:
                    if device not in seen[key].affected_devices:
                        seen[key].affected_devices.append(device)
            else:
                seen[key] = issue

        return list(seen.values())

    def _calculate_score(
        self,
        issues: List[MobileCompatibilityIssue],
        load_time_ms: Optional[int],
        page_size_bytes: int
    ) -> float:
        """Calculate mobile-friendly score."""
        score = 100.0

        severity_penalties = {
            "critical": 20,
            "serious": 10,
            "moderate": 5,
            "minor": 2,
        }

        for issue in issues:
            penalty = severity_penalties.get(issue.severity, 5)
            score -= penalty

        if load_time_ms:
            if load_time_ms > 5000:
                score -= 15
            elif load_time_ms > 3000:
                score -= 10
            elif load_time_ms > 2000:
                score -= 5

        if page_size_bytes:
            mb = page_size_bytes / (1024 * 1024)
            if mb > 5:
                score -= 10
            elif mb > 2:
                score -= 5

        return max(0, min(100, score))
