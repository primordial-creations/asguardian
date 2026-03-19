"""
Freya Site Crawler

Crawls a website discovering all pages and runs comprehensive
tests on each page, generating a consolidated report.
"""

import asyncio
import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from Asgard.Freya.Integration.models.integration_models import (
    CrawlConfig,
    CrawledPage,
    PageStatus,
    PageTestResult,
    SiteCrawlReport,
    TestCategory,
)
from Asgard.Freya.Integration.services.unified_tester import UnifiedTester
from Asgard.Freya.Visual.services.screenshot_capture import ScreenshotCapture


class SiteCrawler:
    """
    Site crawler and tester.

    Discovers all pages on a website and runs comprehensive
    accessibility, visual, and responsive tests on each.
    """

    def __init__(self, config: CrawlConfig):
        """
        Initialize the site crawler.

        Args:
            config: Crawl configuration
        """
        self.config = config
        self.discovered_pages: Dict[str, CrawledPage] = {}
        self.tested_pages: Dict[str, PageTestResult] = {}
        self.base_domain = urlparse(config.start_url).netloc
        self.output_dir = Path(config.output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "screenshots").mkdir(exist_ok=True)

        self._compiled_include = [re.compile(p) for p in config.include_patterns]
        self._compiled_exclude = [re.compile(p) for p in config.exclude_patterns]

        self._progress_callback = None
        self._auth_storage: Optional[Dict] = None  # Stores localStorage after auth

    def set_progress_callback(self, callback):
        """Set callback for progress updates."""
        self._progress_callback = callback

    def _report_progress(self, message: str, current: int = 0, total: int = 0):
        """Report progress to callback if set."""
        if self._progress_callback:
            self._progress_callback(message, current, total)

    async def crawl_and_test(self) -> SiteCrawlReport:
        """
        Crawl the site and test all discovered pages.

        Returns:
            SiteCrawlReport with complete results
        """
        start_time = time.time()
        crawl_started = datetime.now().isoformat()

        self._report_progress("Starting crawl...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.config.browser_config.headless
            )

            context = await self._create_context(browser)

            try:
                await self._crawl_site(context)

                await self._test_all_pages(context)

            finally:
                await browser.close()

        crawl_completed = datetime.now().isoformat()
        total_duration = int((time.time() - start_time) * 1000)

        report = self._generate_report(crawl_started, crawl_completed, total_duration)

        await self._save_report(report)

        return report

    async def _create_context(self, browser: Browser) -> BrowserContext:
        """Create browser context with authentication if configured."""
        context_options = {
            "viewport": {
                "width": self.config.browser_config.viewport_width,
                "height": self.config.browser_config.viewport_height,
            },
            "device_scale_factor": self.config.browser_config.device_scale_factor,
        }

        if self.config.browser_config.user_agent:
            context_options["user_agent"] = self.config.browser_config.user_agent

        context = await browser.new_context(**context_options)

        if self.config.auth_config:
            await self._authenticate(context)

        return context

    async def _authenticate(self, context: BrowserContext):
        """Perform authentication if configured."""
        auth = self.config.auth_config
        if not auth:
            return

        page = await context.new_page()

        try:
            login_url = auth.get("login_url", self.config.start_url)
            await page.goto(login_url, wait_until="networkidle", timeout=30000)

            username_selector = auth.get("username_selector", 'input[name="username"]')
            password_selector = auth.get("password_selector", 'input[name="password"]')
            submit_selector = auth.get("submit_selector", 'button[type="submit"]')

            username = auth.get("username", "")
            password = auth.get("password", "")

            if username and password:
                await page.fill(username_selector, username)
                await page.fill(password_selector, password)
                await page.click(submit_selector)

                await page.wait_for_load_state("networkidle")

                if auth.get("wait_for_url"):
                    await page.wait_for_url(auth["wait_for_url"], timeout=10000)
                elif auth.get("wait_for_selector"):
                    await page.wait_for_selector(auth["wait_for_selector"], timeout=10000)
                else:
                    await asyncio.sleep(2)

                # Save localStorage for use in other pages (for SPAs using token-based auth)
                self._auth_storage = await page.evaluate("() => JSON.stringify(localStorage)")
                self._report_progress("Authentication successful")

        except Exception as e:
            self._report_progress(f"Authentication failed: {e}")
        finally:
            await page.close()

    async def _crawl_site(self, context: BrowserContext):
        """Crawl the site discovering all pages."""
        self._add_page(self.config.start_url, depth=0, parent_url=None)

        pages_to_crawl = [self.config.start_url]

        # Add additional routes for SPAs
        base_url = self.config.start_url.rstrip("/")
        for route in self.config.additional_routes:
            # Handle Git Bash path conversion on Windows (e.g., /notes -> E:/Program Files/Git/notes)
            if ":" in route and "/" in route:
                # Extract just the last part after the final /
                route = "/" + route.split("/")[-1]
            route = route if route.startswith("/") else f"/{route}"
            full_url = f"{base_url}{route}"
            if full_url not in self.discovered_pages:
                self._add_page(full_url, depth=1, parent_url=self.config.start_url)
                pages_to_crawl.append(full_url)

        crawled_count = 0

        while pages_to_crawl and crawled_count < self.config.max_pages:
            url = pages_to_crawl.pop(0)
            page_info = self.discovered_pages.get(url)

            if not page_info or page_info.status != PageStatus.PENDING:
                continue

            if page_info.depth >= self.config.max_depth:
                page_info.status = PageStatus.SKIPPED
                continue

            crawled_count += 1
            self._report_progress(
                f"Crawling: {url}",
                crawled_count,
                len(self.discovered_pages)
            )

            page_info.status = PageStatus.CRAWLING

            try:
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)

                page_info.title = await page.title()

                links = await self._extract_links(page, url)
                page_info.links_found = links

                for link in links:
                    if link not in self.discovered_pages:
                        if self._should_crawl(link):
                            self._add_page(link, depth=page_info.depth + 1, parent_url=url)
                            pages_to_crawl.append(link)

                page_info.status = PageStatus.TESTED

                await page.close()

                if self.config.delay_between_requests > 0:
                    await asyncio.sleep(self.config.delay_between_requests)

            except Exception as e:
                page_info.status = PageStatus.ERROR
                page_info.error_message = str(e)

        # Discover SPA items (clickable notes, boards, etc.)
        if self.config.discover_items:
            self._report_progress("Discovering clickable items in SPA...")
            tested_pages = [
                p.url for p in self.discovered_pages.values()
                if p.status == PageStatus.TESTED
            ]

            for page_url in tested_pages:
                if crawled_count >= self.config.max_pages:
                    break

                item_urls = await self._discover_spa_items(context, page_url)
                for item_url in item_urls:
                    if item_url not in self.discovered_pages and crawled_count < self.config.max_pages:
                        # Add discovered item page
                        self._add_page(item_url, depth=2, parent_url=page_url)
                        crawled_count += 1

                        # Mark as tested (we'll test it in _test_all_pages)
                        if item_url in self.discovered_pages:
                            self.discovered_pages[item_url].status = PageStatus.TESTED

        self._report_progress(
            f"Crawl complete: {len(self.discovered_pages)} pages discovered",
            len(self.discovered_pages),
            len(self.discovered_pages)
        )

    async def _extract_links(self, page: Page, current_url: str) -> List[str]:
        """Extract all links from a page."""
        links = await page.evaluate("""
            () => {
                const anchors = document.querySelectorAll('a[href]');
                return Array.from(anchors).map(a => a.href);
            }
        """)

        normalized_links = []
        for link in links:
            normalized = self._normalize_url(link, current_url)
            if normalized and normalized not in normalized_links:
                normalized_links.append(normalized)

        return normalized_links

    async def _discover_spa_items(self, context: BrowserContext, page_url: str) -> List[str]:
        """
        Discover clickable items in SPAs (notes, boards, calendar events, etc.).
        Clicks on the first item of each type to discover detail pages.

        Returns:
            List of discovered detail page URLs
        """
        discovered_urls: List[Any] = []

        # Track which item types we've already discovered
        discovered_types: Set[str] = set()


        page = await context.new_page()
        try:
            # Restore localStorage from auth if available (for SPAs using token-based auth)
            if self._auth_storage:
                # Navigate to the domain first to set localStorage
                await page.goto(page_url.split('?')[0].split('#')[0], wait_until="domcontentloaded", timeout=30000)
                await page.evaluate(f"""
                    (storage) => {{
                        const data = JSON.parse(storage);
                        for (const [key, value] of Object.entries(data)) {{
                            localStorage.setItem(key, value);
                        }}
                    }}
                """, self._auth_storage)
                # Reload the page to apply auth
                await page.reload(wait_until="networkidle", timeout=30000)
            else:
                await page.goto(page_url, wait_until="networkidle", timeout=30000)

            # Wait for React app to fully render
            try:
                # Wait for main content area to appear
                await page.wait_for_selector('main, [role="main"], .main-content', timeout=5000)
            except Exception:
                pass  # Continue even if no main element found

            # Wait for loading indicators to disappear
            try:
                await page.wait_for_function(
                    "() => !document.body.innerText.includes('Loading')",
                    timeout=10000
                )
            except Exception:
                pass  # Continue even if loading check times out

            await asyncio.sleep(2)  # Additional wait for dynamic content


            # Check if we're on a login page (auth might have failed for new page)
            page_content = await page.content()
            if 'login' in page.url.lower() or 'sign in' in page_content.lower()[:500]:
                return discovered_urls

            # Common patterns for clickable list items in SPAs
            item_selectors = [
                # Data-testid patterns (common in React apps)
                '[data-testid*="item"]',
                '[data-testid*="card"]',
                '[data-testid*="note"]',
                '[data-testid*="board"]',
                '[data-testid*="event"]',
                '[data-testid*="task"]',
                '[data-testid*="list-item"]',
                '[data-testid*="row"]',
                # Role-based patterns
                '[role="listitem"]',
                '[role="row"]',
                '[role="option"]',
                # Common class patterns
                '.card',
                '.list-item',
                '.item',
                '.note-item',
                '.board-item',
                '.event-item',
                '.task-item',
                # MUI patterns
                '.MuiCard-root',
                '.MuiListItem-root',
                '.MuiTableRow-root',
                # Generic clickable containers in lists
                'li[class*="item"]',
                'div[class*="card"]',
                'tr[class*="row"]',
                # Sidebar navigation patterns
                'aside div[style*="cursor: pointer"]',
                'nav div[style*="cursor: pointer"]',
                '[class*="sidebar"] div[style*="cursor: pointer"]',
                # Generic clickable divs in sidebars/complementary regions
                'aside [role="button"]',
                'aside button',
                '[role="complementary"] div[style*="cursor"]',
            ]

            for selector in item_selectors:
                try:
                    items = await page.query_selector_all(selector)
                    if not items:
                        continue


                    # Get the item type from the selector
                    item_type = selector.replace('[', '').replace(']', '').replace('*=', '_').replace('"', '')

                    # Skip if we already discovered this type
                    if item_type in discovered_types:
                        continue

                    # Try to click the first visible, clickable item
                    for item in items[:3]:  # Try first 3 items max
                        try:
                            is_visible = await item.is_visible()
                            if not is_visible:
                                continue

                            # Get current URL before click
                            url_before = page.url

                            # Click the item and wait for potential navigation
                            try:
                                async with page.expect_navigation(timeout=5000, wait_until="networkidle"):
                                    await item.click(timeout=5000)
                            except Exception:
                                # No navigation occurred, that's ok - might be a modal
                                await asyncio.sleep(1)

                            # Check if URL changed (navigation to detail page)
                            url_after = page.url

                            if url_after != url_before and url_after not in discovered_urls:
                                discovered_urls.append(url_after)
                                discovered_types.add(item_type)
                                self._report_progress(f"Discovered item page: {url_after}")

                                # Go back to continue discovering
                                await page.goto(page_url, wait_until="networkidle", timeout=30000)
                                await asyncio.sleep(1)
                                break
                            else:
                                # Check if a modal/dialog opened
                                modal_selectors = [
                                    '[role="dialog"]',
                                    '[role="modal"]',
                                    '.MuiDialog-root',
                                    '.MuiModal-root',
                                    '.modal',
                                    '[class*="modal"]',
                                    '[class*="dialog"]',
                                ]

                                for modal_sel in modal_selectors:
                                    modal = await page.query_selector(modal_sel)
                                    if modal and await modal.is_visible():
                                        # Modal detected - this counts as discovering a detail view
                                        modal_url = f"{page_url}#modal-{item_type}"
                                        if modal_url not in discovered_urls:
                                            discovered_urls.append(modal_url)
                                            discovered_types.add(item_type)
                                            self._report_progress(f"Discovered modal: {item_type}")

                                        # Close the modal (try Escape key)
                                        await page.keyboard.press("Escape")
                                        await asyncio.sleep(0.5)
                                        break

                                # If we detected something, break out
                                if item_type in discovered_types:
                                    break

                        except Exception:
                            continue  # Item not clickable, try next

                except Exception:
                    continue  # Selector not found, try next

        except Exception as e:
            self._report_progress(f"Item discovery error on {page_url}: {e}")
        finally:
            await page.close()

        return discovered_urls

    def _normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """Normalize a URL and check if it should be included."""
        if not url:
            return None

        if url.startswith("javascript:") or url.startswith("mailto:"):
            return None

        full_url = urljoin(base_url, url)

        parsed = urlparse(full_url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if normalized.endswith("/"):
            normalized = normalized[:-1]

        return normalized if normalized else None

    def _should_crawl(self, url: str) -> bool:
        """Check if a URL should be crawled."""
        parsed = urlparse(url)
        if self.config.same_domain_only and parsed.netloc != self.base_domain:
            return False

        for pattern in self._compiled_exclude:
            if pattern.match(url):
                return False

        if self._compiled_include:
            for pattern in self._compiled_include:
                if pattern.match(url):
                    return True
            return False

        return True

    def _add_page(self, url: str, depth: int, parent_url: Optional[str]):
        """Add a page to the discovered pages."""
        if url not in self.discovered_pages:
            self.discovered_pages[url] = CrawledPage(
                url=url,
                depth=depth,
                parent_url=parent_url,
                status=PageStatus.PENDING
            )

    async def _test_all_pages(self, context: BrowserContext):
        """Run tests on all discovered pages."""
        pages_to_test = [
            p for p in self.discovered_pages.values()
            if p.status == PageStatus.TESTED
        ]

        total = len(pages_to_test)
        self._report_progress(f"Testing {total} pages...")

        for i, page_info in enumerate(pages_to_test, 1):
            self._report_progress(
                f"Testing: {page_info.url}",
                i,
                total
            )

            result = await self._test_page(context, page_info)
            self.tested_pages[page_info.url] = result

            if self.config.delay_between_requests > 0:
                await asyncio.sleep(self.config.delay_between_requests)

        self._report_progress(f"Testing complete: {total} pages tested", total, total)

    async def _test_page(self, context: BrowserContext, page_info: CrawledPage) -> PageTestResult:
        """Run tests on a single page."""
        start_time = time.time()
        issues = []
        screenshot_path = None

        try:
            page = await context.new_page()
            await page.goto(page_info.url, wait_until="networkidle", timeout=30000)

            title = await page.title()

            if self.config.capture_screenshots:
                screenshot_filename = self._url_to_filename(page_info.url) + ".png"
                screenshot_path = str(self.output_dir / "screenshots" / screenshot_filename)
                await page.screenshot(path=screenshot_path, full_page=True)

            accessibility_score = 100.0
            visual_score = 100.0
            responsive_score = 100.0

            if TestCategory.ALL in self.config.test_categories or \
               TestCategory.ACCESSIBILITY in self.config.test_categories:
                a11y_issues = await self._run_accessibility_checks(page)
                issues.extend(a11y_issues)
                if a11y_issues:
                    accessibility_score = max(0, 100 - len(a11y_issues) * 10)

            if TestCategory.ALL in self.config.test_categories or \
               TestCategory.VISUAL in self.config.test_categories:
                visual_issues = await self._run_visual_checks(page)
                issues.extend(visual_issues)
                if visual_issues:
                    visual_score = max(0, 100 - len(visual_issues) * 5)

            if TestCategory.ALL in self.config.test_categories or \
               TestCategory.RESPONSIVE in self.config.test_categories:
                responsive_issues = await self._run_responsive_checks(page)
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

    async def _run_accessibility_checks(self, page: Page) -> List[Dict]:
        """Run accessibility checks on a page."""
        issues = []

        checks = await page.evaluate("""
            () => {
                const issues = [];

                // Check images without alt text
                document.querySelectorAll('img').forEach(img => {
                    if (!img.alt && !img.getAttribute('role')) {
                        issues.push({
                            type: 'missing-alt',
                            severity: 'serious',
                            element: img.outerHTML.substring(0, 100),
                            message: 'Image missing alt text',
                            wcag: '1.1.1'
                        });
                    }
                });

                // Check form labels
                document.querySelectorAll('input, select, textarea').forEach(input => {
                    if (input.type !== 'hidden' && input.type !== 'submit' && input.type !== 'button') {
                        const id = input.id;
                        const label = id ? document.querySelector(`label[for="${id}"]`) : null;
                        const ariaLabel = input.getAttribute('aria-label');
                        const ariaLabelledBy = input.getAttribute('aria-labelledby');

                        if (!label && !ariaLabel && !ariaLabelledBy) {
                            issues.push({
                                type: 'missing-label',
                                severity: 'serious',
                                element: input.outerHTML.substring(0, 100),
                                message: 'Form input missing label',
                                wcag: '1.3.1'
                            });
                        }
                    }
                });

                // Check heading hierarchy
                const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                let lastLevel = 0;
                headings.forEach(h => {
                    const level = parseInt(h.tagName[1]);
                    if (level > lastLevel + 1 && lastLevel > 0) {
                        issues.push({
                            type: 'heading-skip',
                            severity: 'moderate',
                            element: h.outerHTML.substring(0, 100),
                            message: `Heading level skipped from h${lastLevel} to h${level}`,
                            wcag: '1.3.1'
                        });
                    }
                    lastLevel = level;
                });

                // Check for main landmark
                if (!document.querySelector('main, [role="main"]')) {
                    issues.push({
                        type: 'missing-main',
                        severity: 'moderate',
                        element: 'body',
                        message: 'Page missing main landmark',
                        wcag: '1.3.1'
                    });
                }

                // Check link text
                document.querySelectorAll('a').forEach(a => {
                    const text = a.textContent.trim().toLowerCase();
                    if (['click here', 'here', 'read more', 'learn more', 'more'].includes(text)) {
                        issues.push({
                            type: 'non-descriptive-link',
                            severity: 'moderate',
                            element: a.outerHTML.substring(0, 100),
                            message: `Link text "${a.textContent.trim()}" is not descriptive`,
                            wcag: '2.4.4'
                        });
                    }
                });

                // Check color contrast (basic check for text color)
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (style.color === style.backgroundColor && el.textContent.trim()) {
                        issues.push({
                            type: 'contrast-issue',
                            severity: 'serious',
                            element: el.outerHTML.substring(0, 100),
                            message: 'Text may have insufficient color contrast',
                            wcag: '1.4.3'
                        });
                    }
                });

                // Check focus indicators
                document.querySelectorAll('a, button, input, select, textarea').forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (style.outline === 'none' || style.outline === '0px none') {
                        // Check if there's a :focus style
                    }
                });

                return issues;
            }
        """)

        for check in checks:
            issues.append({
                "category": "accessibility",
                "type": check["type"],
                "severity": check["severity"],
                "message": check["message"],
                "element": check.get("element", ""),
                "wcag": check.get("wcag", ""),
            })

        return issues

    async def _run_visual_checks(self, page: Page) -> List[Dict]:
        """Run visual checks on a page."""
        issues = []

        checks = await page.evaluate("""
            () => {
                const issues = [];

                // Check for broken images
                document.querySelectorAll('img').forEach(img => {
                    if (!img.complete || img.naturalWidth === 0) {
                        issues.push({
                            type: 'broken-image',
                            severity: 'moderate',
                            element: img.src,
                            message: 'Image failed to load'
                        });
                    }
                });

                // Check for horizontal overflow
                if (document.documentElement.scrollWidth > document.documentElement.clientWidth) {
                    issues.push({
                        type: 'horizontal-overflow',
                        severity: 'moderate',
                        element: 'body',
                        message: 'Page has horizontal scroll'
                    });
                }

                // Check for very small text
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const fontSize = parseFloat(style.fontSize);
                    if (fontSize < 12 && el.textContent.trim().length > 0) {
                        issues.push({
                            type: 'small-text',
                            severity: 'minor',
                            element: el.tagName,
                            message: `Text size ${fontSize}px is below recommended minimum`
                        });
                    }
                });

                // Check z-index stacking issues (overlapping elements)
                const highZElements = [];
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const zIndex = parseInt(style.zIndex);
                    if (zIndex > 9999) {
                        highZElements.push({
                            element: el.tagName,
                            zIndex: zIndex
                        });
                    }
                });

                if (highZElements.length > 3) {
                    issues.push({
                        type: 'z-index-complexity',
                        severity: 'minor',
                        element: 'multiple',
                        message: 'Multiple elements with very high z-index values'
                    });
                }

                return issues;
            }
        """)

        for check in checks:
            issues.append({
                "category": "visual",
                "type": check["type"],
                "severity": check["severity"],
                "message": check["message"],
                "element": check.get("element", ""),
            })

        return issues

    async def _run_responsive_checks(self, page: Page) -> List[Dict]:
        """Run responsive design checks on a page."""
        issues = []

        checks = await page.evaluate("""
            () => {
                const issues = [];

                // Check viewport meta tag
                const viewport = document.querySelector('meta[name="viewport"]');
                if (!viewport) {
                    issues.push({
                        type: 'missing-viewport',
                        severity: 'serious',
                        element: 'head',
                        message: 'Missing viewport meta tag'
                    });
                } else {
                    const content = viewport.getAttribute('content') || '';
                    if (!content.includes('width=device-width')) {
                        issues.push({
                            type: 'viewport-config',
                            severity: 'moderate',
                            element: 'viewport',
                            message: 'Viewport meta tag missing width=device-width'
                        });
                    }
                }

                // Check touch targets
                const minTouchSize = 44;
                document.querySelectorAll('a, button, input[type="submit"], input[type="button"]').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < minTouchSize || rect.height < minTouchSize) {
                        if (rect.width > 0 && rect.height > 0) {  // Element is visible
                            issues.push({
                                type: 'small-touch-target',
                                severity: 'moderate',
                                element: el.outerHTML.substring(0, 100),
                                message: `Touch target ${Math.round(rect.width)}x${Math.round(rect.height)}px is below 44x44px minimum`
                            });
                        }
                    }
                });

                // Check for fixed-width elements
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const width = parseInt(style.width);
                    if (width > window.innerWidth && style.position !== 'fixed' && style.position !== 'absolute') {
                        issues.push({
                            type: 'fixed-width',
                            severity: 'moderate',
                            element: el.tagName,
                            message: 'Element has fixed width larger than viewport'
                        });
                    }
                });

                return issues;
            }
        """)

        for check in checks:
            issues.append({
                "category": "responsive",
                "type": check["type"],
                "severity": check["severity"],
                "message": check["message"],
                "element": check.get("element", ""),
            })

        return issues

    def _generate_report(
        self,
        crawl_started: str,
        crawl_completed: str,
        total_duration: int
    ) -> SiteCrawlReport:
        """Generate the final crawl report."""
        page_results = list(self.tested_pages.values())

        pages_discovered = len(self.discovered_pages)
        pages_tested = len([p for p in self.discovered_pages.values() if p.status == PageStatus.TESTED])
        pages_skipped = len([p for p in self.discovered_pages.values() if p.status == PageStatus.SKIPPED])
        pages_errored = len([p for p in self.discovered_pages.values() if p.status == PageStatus.ERROR])

        if page_results:
            avg_accessibility = sum(r.accessibility_score for r in page_results) / len(page_results)
            avg_visual = sum(r.visual_score for r in page_results) / len(page_results)
            avg_responsive = sum(r.responsive_score for r in page_results) / len(page_results)
            avg_overall = sum(r.overall_score for r in page_results) / len(page_results)
        else:
            avg_accessibility = avg_visual = avg_responsive = avg_overall = 0.0

        total_critical = sum(r.critical_issues for r in page_results)
        total_serious = sum(r.serious_issues for r in page_results)
        total_moderate = sum(r.moderate_issues for r in page_results)
        total_minor = sum(r.minor_issues for r in page_results)

        worst_pages = sorted(page_results, key=lambda r: r.overall_score)[:5]
        worst_page_urls = [p.url for p in worst_pages]

        issue_counter: Counter[str] = Counter()
        for result in page_results:
            for issue in result.issues:
                issue_key = f"{issue.get('type', 'unknown')}:{issue.get('message', '')}"
                issue_counter[issue_key] += 1

        common_issues = [
            {"issue": key.split(":")[0], "message": key.split(":", 1)[1], "count": count}
            for key, count in issue_counter.most_common(10)
        ]

        return SiteCrawlReport(
            start_url=self.config.start_url,
            crawl_started=crawl_started,
            crawl_completed=crawl_completed,
            total_duration_ms=total_duration,
            pages_discovered=pages_discovered,
            pages_tested=pages_tested,
            pages_skipped=pages_skipped,
            pages_errored=pages_errored,
            average_accessibility_score=avg_accessibility,
            average_visual_score=avg_visual,
            average_responsive_score=avg_responsive,
            average_overall_score=avg_overall,
            total_critical=total_critical,
            total_serious=total_serious,
            total_moderate=total_moderate,
            total_minor=total_minor,
            page_results=page_results,
            worst_pages=worst_page_urls,
            common_issues=common_issues,
            config=self.config,
        )

    async def _save_report(self, report: SiteCrawlReport):
        """Save the crawl report to files."""
        json_path = self.output_dir / "crawl_report.json"
        with open(json_path, "w") as f:
            f.write(report.model_dump_json(indent=2))

        html_path = self.output_dir / "crawl_report.html"
        html_content = self._generate_html_report(report)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _generate_html_report(self, report: SiteCrawlReport) -> str:
        """Generate HTML report from crawl results."""
        def score_color(score: float) -> str:
            if score >= 90:
                return "#22c55e"
            elif score >= 70:
                return "#eab308"
            elif score >= 50:
                return "#f97316"
            else:
                return "#ef4444"

        def severity_badge(severity: str) -> str:
            colors = {
                "critical": "#ef4444",
                "serious": "#f97316",
                "moderate": "#eab308",
                "minor": "#22c55e",
            }
            color = colors.get(severity, "#6b7280")
            return f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{severity.upper()}</span>'

        page_rows = ""
        for result in sorted(report.page_results, key=lambda r: r.overall_score):
            status = "PASS" if result.passed else "FAIL"
            status_color = "#22c55e" if result.passed else "#ef4444"
            page_rows += f"""
            <tr>
                <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    <a href="{result.url}" target="_blank">{result.url}</a>
                </td>
                <td style="text-align: center; color: {score_color(result.overall_score)}; font-weight: bold;">
                    {result.overall_score:.0f}
                </td>
                <td style="text-align: center;">{result.accessibility_score:.0f}</td>
                <td style="text-align: center;">{result.visual_score:.0f}</td>
                <td style="text-align: center;">{result.responsive_score:.0f}</td>
                <td style="text-align: center; color: {status_color}; font-weight: bold;">{status}</td>
                <td style="text-align: center;">{result.critical_issues + result.serious_issues + result.moderate_issues + result.minor_issues}</td>
            </tr>
            """

        common_issues_html = ""
        for issue in report.common_issues[:10]:
            common_issues_html += f"""
            <tr>
                <td>{issue['issue']}</td>
                <td>{issue['message']}</td>
                <td style="text-align: center; font-weight: bold;">{issue['count']}</td>
            </tr>
            """

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Freya Site Crawl Report - {report.start_url}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 1px solid #334155;
            margin-bottom: 40px;
        }}
        .header h1 {{
            font-size: 2.5rem;
            color: #f8fafc;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #94a3b8;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .summary-card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
        }}
        .summary-card h3 {{
            color: #94a3b8;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .summary-card .value {{
            font-size: 2.5rem;
            font-weight: bold;
        }}
        .score-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .score-card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
        }}
        .score-card h3 {{
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        .score-bar {{
            height: 8px;
            background: #334155;
            border-radius: 4px;
            overflow: hidden;
        }}
        .score-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }}
        .score-value {{
            font-size: 2rem;
            font-weight: bold;
            margin-top: 8px;
        }}
        .section {{
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .section h2 {{
            color: #f8fafc;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid #334155;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
        }}
        tr:hover {{
            background: #334155;
        }}
        a {{
            color: #60a5fa;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            text-align: center;
            padding: 40px 0;
            color: #64748b;
            border-top: 1px solid #334155;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Freya Site Crawl Report</h1>
            <p>{report.start_url}</p>
            <p style="margin-top: 10px; font-size: 14px;">
                Generated: {report.crawl_completed} | Duration: {report.total_duration_ms / 1000:.1f}s
            </p>
        </div>

        <div class="summary-grid">
            <div class="summary-card">
                <h3>Pages Discovered</h3>
                <div class="value" style="color: #60a5fa;">{report.pages_discovered}</div>
            </div>
            <div class="summary-card">
                <h3>Pages Tested</h3>
                <div class="value" style="color: #22c55e;">{report.pages_tested}</div>
            </div>
            <div class="summary-card">
                <h3>Critical Issues</h3>
                <div class="value" style="color: #ef4444;">{report.total_critical}</div>
            </div>
            <div class="summary-card">
                <h3>Total Issues</h3>
                <div class="value" style="color: #f97316;">{report.total_critical + report.total_serious + report.total_moderate + report.total_minor}</div>
            </div>
        </div>

        <div class="score-section">
            <div class="score-card">
                <h3>Overall Score</h3>
                <div class="score-bar">
                    <div class="score-fill" style="width: {report.average_overall_score}%; background: {score_color(report.average_overall_score)};"></div>
                </div>
                <div class="score-value" style="color: {score_color(report.average_overall_score)};">{report.average_overall_score:.0f}/100</div>
            </div>
            <div class="score-card">
                <h3>Accessibility</h3>
                <div class="score-bar">
                    <div class="score-fill" style="width: {report.average_accessibility_score}%; background: {score_color(report.average_accessibility_score)};"></div>
                </div>
                <div class="score-value" style="color: {score_color(report.average_accessibility_score)};">{report.average_accessibility_score:.0f}/100</div>
            </div>
            <div class="score-card">
                <h3>Visual</h3>
                <div class="score-bar">
                    <div class="score-fill" style="width: {report.average_visual_score}%; background: {score_color(report.average_visual_score)};"></div>
                </div>
                <div class="score-value" style="color: {score_color(report.average_visual_score)};">{report.average_visual_score:.0f}/100</div>
            </div>
            <div class="score-card">
                <h3>Responsive</h3>
                <div class="score-bar">
                    <div class="score-fill" style="width: {report.average_responsive_score}%; background: {score_color(report.average_responsive_score)};"></div>
                </div>
                <div class="score-value" style="color: {score_color(report.average_responsive_score)};">{report.average_responsive_score:.0f}/100</div>
            </div>
        </div>

        <div class="section">
            <h2>Common Issues Across Site</h2>
            <table>
                <thead>
                    <tr>
                        <th>Issue Type</th>
                        <th>Description</th>
                        <th>Occurrences</th>
                    </tr>
                </thead>
                <tbody>
                    {common_issues_html if common_issues_html else '<tr><td colspan="3" style="text-align: center;">No issues found</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>All Pages ({report.pages_tested} tested)</h2>
            <table>
                <thead>
                    <tr>
                        <th>URL</th>
                        <th>Overall</th>
                        <th>A11y</th>
                        <th>Visual</th>
                        <th>Responsive</th>
                        <th>Status</th>
                        <th>Issues</th>
                    </tr>
                </thead>
                <tbody>
                    {page_rows if page_rows else '<tr><td colspan="7" style="text-align: center;">No pages tested</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Generated by Freya - Visual and UI Testing</p>
            <p>Named after the Norse goddess of beauty and love</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename."""
        url = url.replace("https://", "").replace("http://", "")
        url = url.replace("/", "_").replace(":", "_").replace("?", "_")
        url = url.replace("&", "_").replace("=", "_").replace("#", "_")
        return url[:100]
