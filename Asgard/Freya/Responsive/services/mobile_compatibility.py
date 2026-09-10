"""
Freya Mobile Compatibility Tester

Tests mobile device compatibility including performance,
feature detection, and common mobile issues.
"""

import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Responsive.services._hover_evidence import assess_hover_dependencies

from Asgard.Freya.Responsive.models.responsive_models import (
    Breakpoint,
    MobileCompatibilityIssue,
    MobileCompatibilityIssueType,
    MobileCompatibilityReport,
    MobileCheckOutcome,
    MOBILE_DEVICES,
)
from Asgard.Freya.Responsive.services._mobile_compatibility_checks import (
    check_flash_content,
    check_hover_dependencies,
    check_small_text,
    check_fixed_positioning,
    deduplicate_issues,
    calculate_score,
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

        check_outcomes: dict[str, dict[str, MobileCheckOutcome]] = {}
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for device_name in devices:
                    outcomes = check_outcomes[device_name] = {}
                    if device_name not in MOBILE_DEVICES:
                        outcomes["navigation"] = MobileCheckOutcome(
                            status="failed", diagnostic="Unsupported device")
                        continue
                    device = MOBILE_DEVICES[device_name]
                    context = None
                    try:
                        context = await browser.new_context(
                            viewport={"width": device.width, "height": device.height},
                            device_scale_factor=device.device_scale_factor,
                            is_mobile=True, has_touch=True,
                        )
                        page = await context.new_page()
                        start_time = time.time()
                        from Asgard.Freya.Integration.services._url_safety import safe_goto
                        await safe_goto(page, url, wait_until="networkidle", timeout=30000)
                        load_time = int((time.time() - start_time) * 1000)
                        if load_time_ms is None:
                            load_time_ms = load_time
                        outcomes["navigation"] = MobileCheckOutcome(status="succeeded")
                        device_issues = []
                        for name, check in (("flash", check_flash_content),
                                            ("hover", check_hover_dependencies),
                                            ("text", check_small_text),
                                            ("fixed", check_fixed_positioning)):
                            try:
                                if name == "hover":
                                    assessment = await assess_hover_dependencies(page)
                                    observed = assessment.issues
                                    outcomes[name] = MobileCheckOutcome(
                                        status="incomplete" if assessment.limitations else "succeeded",
                                        limitations=assessment.limitations,
                                        diagnostic="Hover coverage is limited" if assessment.limitations else None,
                                    )
                                else:
                                    observed = await check(page)
                                    outcomes[name] = MobileCheckOutcome(status="succeeded")
                                device_issues.extend(observed)
                            except Exception:
                                outcomes[name] = MobileCheckOutcome(
                                    status="failed", diagnostic="Browser check execution or output validation failed")
                        for issue in device_issues:
                            if device_name not in issue.affected_devices:
                                issue.affected_devices.append(device_name)
                        issues.extend(device_issues)
                        try:
                            metrics = await page.evaluate("""
                                () => {
                                    const resources = performance.getEntriesByType('resource');
                                    return {resourceCount: resources.length,
                                            totalSize: resources.reduce((sum, r) => sum + (r.transferSize || 0), 0)};
                                }
                            """)
                            if (not isinstance(metrics, dict) or any(
                                type(metrics.get(key)) not in (int, float) or
                                not math.isfinite(metrics[key]) or metrics[key] < 0
                                for key in ("resourceCount", "totalSize")
                            )):
                                raise ValueError("Invalid resource measurements")
                            resource_count = max(resource_count, metrics["resourceCount"])
                            page_size_bytes = max(page_size_bytes, metrics["totalSize"])
                            outcomes["resources"] = MobileCheckOutcome(status="succeeded")
                        except Exception:
                            outcomes["resources"] = MobileCheckOutcome(
                                status="failed", diagnostic="Resource measurements unavailable")
                        device_results[device_name] = {
                            "load_time_ms": load_time,
                            "viewport": f"{device.width}x{device.height}",
                            "issues_count": len(device_issues),
                        }
                    except Exception:
                        outcomes["navigation"] = MobileCheckOutcome(
                            status="failed", diagnostic="Device page could not be analyzed")
                    finally:
                        if context is not None:
                            await context.close()
            finally:
                await browser.close()

        unique_issues = deduplicate_issues(issues)

        if load_time_ms and load_time_ms > 3000:
            unique_issues.append(MobileCompatibilityIssue(
                issue_type=MobileCompatibilityIssueType.SLOW_LOADING,
                description=f"Page load time ({load_time_ms}ms) exceeds recommended 3 seconds",
                severity="moderate",
                suggested_fix="Optimize images, reduce JavaScript, and leverage caching",
                affected_devices=devices,
            ))

        score = calculate_score(unique_issues, load_time_ms, page_size_bytes)

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
            check_outcomes=check_outcomes,
        )

    async def _check_flash_content(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for Flash content."""
        return await check_flash_content(page)

    async def _check_hover_dependencies(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for hover-dependent functionality."""
        return await check_hover_dependencies(page)

    async def _check_small_text(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for text that's too small on mobile."""
        return await check_small_text(page)

    async def _check_fixed_positioning(self, page: Page) -> List[MobileCompatibilityIssue]:
        """Check for problematic fixed positioning."""
        return await check_fixed_positioning(page)

    def _deduplicate_issues(
        self,
        issues: List[MobileCompatibilityIssue]
    ) -> List[MobileCompatibilityIssue]:
        """Remove duplicate issues, merging affected devices."""
        return deduplicate_issues(issues)

    def _calculate_score(
        self,
        issues: List[MobileCompatibilityIssue],
        load_time_ms: Optional[int],
        page_size_bytes: int
    ) -> float:
        """Calculate mobile-friendly score."""
        return calculate_score(issues, load_time_ms, page_size_bytes)
