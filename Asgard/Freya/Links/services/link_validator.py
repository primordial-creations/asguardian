"""
Freya Link Validator

Validates links on a page, detecting broken links
and problematic redirect chains.
"""

import asyncio
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, cast
from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import Page, async_playwright

from Asgard.Freya.Links.models.link_models import (
    BrokenLink,
    LinkConfig,
    LinkReport,
    LinkResult,
    LinkSeverity,
    LinkStatus,
    LinkType,
    RedirectChain,
)
from Asgard.Freya.Links.services._link_validator_helpers import (
    build_report,
    calculate_health_score,
    filter_links,
    get_link_type,
)


class LinkValidator:
    """
    Validates links on a web page.

    Detects broken links, redirect chains, and other link issues.
    """

    def __init__(self, config: Optional[LinkConfig] = None):
        """
        Initialize the link validator.

        Args:
            config: Link validation configuration
        """
        self.config = config or LinkConfig()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout_ms / 1000,
                follow_redirects=False,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; FreyaBot/1.0; "
                        "+https://github.com/JakeDruett/asgard)"
                    ),
                },
            )
        return self._http_client

    async def validate(self, url: str) -> LinkReport:
        """
        Validate all links on a URL.

        Args:
            url: URL to validate

        Returns:
            LinkReport with validation results
        """
        start_time = datetime.now()

        links = await self._extract_links(url)
        links_to_check = filter_links(links, url, self.config)

        if len(links_to_check) > self.config.max_links:
            links_to_check = links_to_check[: self.config.max_links]

        results = await self._check_links_concurrent(links_to_check, url)

        analysis_duration = (datetime.now() - start_time).total_seconds() * 1000

        return build_report(url, links, results, analysis_duration, self.config)

    async def validate_page(self, page: Page, url: str) -> LinkReport:
        """
        Validate links from an already loaded page.

        Args:
            page: Playwright Page object
            url: URL of the page

        Returns:
            LinkReport with validation results
        """
        start_time = datetime.now()

        links = await self._extract_links_from_page(page, url)
        links_to_check = filter_links(links, url, self.config)

        if len(links_to_check) > self.config.max_links:
            links_to_check = links_to_check[: self.config.max_links]

        results = await self._check_links_concurrent(links_to_check, url)

        analysis_duration = (datetime.now() - start_time).total_seconds() * 1000

        return build_report(url, links, results, analysis_duration, self.config)

    async def _extract_links(self, url: str) -> List[Dict]:
        """Extract all links from a URL."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return await self._extract_links_from_page(page, url)
            finally:
                await browser.close()

    async def _extract_links_from_page(self, page: Page, base_url: str) -> List[Dict]:
        """Extract links from a Playwright page."""
        links = await page.evaluate("""
            () => {
                const links = [];
                const anchors = document.querySelectorAll('a[href]');

                for (const a of anchors) {
                    const href = a.getAttribute('href');
                    if (!href) continue;

                    links.push({
                        url: a.href,
                        href: href,
                        text: a.textContent?.trim().substring(0, 100) || '',
                        html: a.outerHTML.substring(0, 200)
                    });
                }

                return links;
            }
        """)

        return cast(List[Dict[Any, Any]], links)

    def _filter_links(self, links: List[Dict], base_url: str) -> List[Dict]:
        """Filter links based on configuration."""
        return filter_links(links, base_url, self.config)

    def _get_link_type(self, url: str, href: str, parsed_base: Any) -> LinkType:
        """Determine the type of a link."""
        return get_link_type(url, href, parsed_base)

    async def _check_links_concurrent(
        self, links: List[Dict], source_url: str
    ) -> List[LinkResult]:
        """Check multiple links concurrently."""
        semaphore = asyncio.Semaphore(self.config.concurrent_requests)

        async def check_with_semaphore(link: Dict) -> LinkResult:
            async with semaphore:
                return await self._check_single_link(link, source_url)

        tasks = [check_with_semaphore(link) for link in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(LinkResult(
                    url=links[i].get("url", ""),
                    source_url=source_url,
                    link_type=LinkType(links[i].get("link_type", LinkType.OTHER)),
                    status=LinkStatus.ERROR,
                    error_message=str(result),
                    is_broken=True,
                ))
            else:
                processed.append(result)

        return processed

    async def _check_single_link(self, link: Dict, source_url: str) -> LinkResult:
        """Check a single link."""
        url = link.get("url", "")
        link_type = LinkType(link.get("link_type", LinkType.OTHER))

        result = LinkResult(
            url=url,
            source_url=source_url,
            link_text=link.get("text"),
            link_type=link_type,
            status=LinkStatus.OK,
            element_html=link.get("html"),
        )

        if link_type == LinkType.ANCHOR:
            result.status = LinkStatus.SKIPPED
            return result

        if link_type in [LinkType.MAILTO, LinkType.TEL, LinkType.JAVASCRIPT]:
            result.status = LinkStatus.SKIPPED
            return result

        start_time = time.time()

        try:
            client = await self._get_client()
            redirect_chain = []
            current_url = url
            redirect_count = 0

            while redirect_count < self.config.max_redirects:
                response = await client.head(current_url)
                result.status_code = response.status_code

                if response.status_code in [301, 302, 303, 307, 308]:
                    redirect_chain.append(current_url)
                    location = response.headers.get("location")

                    if not location:
                        break

                    current_url = urljoin(current_url, location)
                    redirect_count += 1
                else:
                    break

            result.response_time_ms = (time.time() - start_time) * 1000
            result.redirect_chain = redirect_chain
            result.redirect_count = redirect_count
            result.final_url = current_url if redirect_count > 0 else None

            if result.status_code is None:
                result.status = LinkStatus.ERROR
                result.is_broken = True
            elif result.status_code >= 400:
                result.status = LinkStatus.BROKEN
                result.is_broken = True
            elif redirect_count > 0:
                result.status = LinkStatus.REDIRECT
            else:
                result.status = LinkStatus.OK

        except httpx.TimeoutException:
            result.status = LinkStatus.TIMEOUT
            result.is_broken = True
            result.error_message = "Request timed out"
            result.response_time_ms = (time.time() - start_time) * 1000

        except httpx.HTTPError as e:
            result.status = LinkStatus.ERROR
            result.is_broken = True
            result.error_message = str(e)
            result.response_time_ms = (time.time() - start_time) * 1000

        return result

    def _build_report(
        self,
        url: str,
        all_links: List[Dict],
        results: List[LinkResult],
        analysis_duration: float,
    ) -> LinkReport:
        """Build the link validation report."""
        return build_report(url, all_links, results, analysis_duration, self.config)

    def _calculate_health_score(self, report: LinkReport) -> float:
        """Calculate link health score (0-100)."""
        return calculate_health_score(report)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
