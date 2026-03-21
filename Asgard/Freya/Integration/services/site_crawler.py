"""
Freya Site Crawler

Crawls a website discovering all pages and runs comprehensive
tests on each page, generating a consolidated report.
"""

import asyncio
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext

from Asgard.Freya.Integration.models.integration_models import (
    CrawlConfig,
    CrawledPage,
    PageStatus,
    PageTestResult,
    SiteCrawlReport,
)
from Asgard.Freya.Integration.services._crawler_discovery import crawl_site
from Asgard.Freya.Integration.services._crawler_page_tester import test_page
from Asgard.Freya.Integration.services._crawler_report import (
    generate_report,
    save_report,
)


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
        self._auth_storage: Optional[str] = None

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
                await crawl_site(
                    context,
                    self.config,
                    self.discovered_pages,
                    self.base_domain,
                    self._compiled_include,
                    self._compiled_exclude,
                    self._auth_storage,
                    self._report_progress,
                )
                await self._test_all_pages(context)
            finally:
                await browser.close()

        crawl_completed = datetime.now().isoformat()
        total_duration = int((time.time() - start_time) * 1000)

        report = generate_report(
            self.config,
            self.discovered_pages,
            self.tested_pages,
            crawl_started,
            crawl_completed,
            total_duration,
        )

        await save_report(report, self.output_dir)

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

                self._auth_storage = await page.evaluate("() => JSON.stringify(localStorage)")
                self._report_progress("Authentication successful")

        except Exception as e:
            self._report_progress(f"Authentication failed: {e}")
        finally:
            await page.close()

    async def _test_all_pages(self, context: BrowserContext):
        """Run tests on all discovered pages."""
        pages_to_test = [
            p for p in self.discovered_pages.values()
            if p.status == PageStatus.TESTED
        ]

        total = len(pages_to_test)
        self._report_progress(f"Testing {total} pages...")

        for i, page_info in enumerate(pages_to_test, 1):
            self._report_progress(f"Testing: {page_info.url}", i, total)
            result = await test_page(
                context,
                page_info,
                self.output_dir,
                self.config.capture_screenshots,
                self.config.test_categories,
            )
            self.tested_pages[page_info.url] = result

            if self.config.delay_between_requests > 0:
                await asyncio.sleep(self.config.delay_between_requests)

        self._report_progress(f"Testing complete: {total} pages tested", total, total)
