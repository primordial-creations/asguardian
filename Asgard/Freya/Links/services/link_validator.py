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
                follow_redirects=False,  # We'll handle redirects manually
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

        # Extract links from page
        links = await self._extract_links(url)

        # Filter links based on config
        links_to_check = self._filter_links(links, url)

        # Limit links
        if len(links_to_check) > self.config.max_links:
            links_to_check = links_to_check[: self.config.max_links]

        # Check links concurrently
        results = await self._check_links_concurrent(links_to_check, url)

        # Build report
        analysis_duration = (datetime.now() - start_time).total_seconds() * 1000

        return self._build_report(url, links, results, analysis_duration)

    async def validate_page(
        self, page: Page, url: str
    ) -> LinkReport:
        """
        Validate links from an already loaded page.

        Args:
            page: Playwright Page object
            url: URL of the page

        Returns:
            LinkReport with validation results
        """
        start_time = datetime.now()

        # Extract links from page
        links = await self._extract_links_from_page(page, url)

        # Filter links
        links_to_check = self._filter_links(links, url)

        # Limit links
        if len(links_to_check) > self.config.max_links:
            links_to_check = links_to_check[: self.config.max_links]

        # Check links
        results = await self._check_links_concurrent(links_to_check, url)

        analysis_duration = (datetime.now() - start_time).total_seconds() * 1000

        return self._build_report(url, links, results, analysis_duration)

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
                        url: a.href,  // Resolved URL
                        href: href,   // Original href attribute
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
        filtered = []
        seen_urls: Set[str] = set()

        parsed_base = urlparse(base_url)

        for link in links:
            url = link.get("url", "")
            href = link.get("href", "")

            # Skip empty
            if not url and not href:
                continue

            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Determine link type
            link_type = self._get_link_type(url, href, parsed_base)
            link["link_type"] = link_type

            # Apply skip rules
            if link_type == LinkType.MAILTO and self.config.skip_mailto:
                continue
            if link_type == LinkType.TEL and self.config.skip_tel:
                continue
            if link_type == LinkType.JAVASCRIPT and self.config.skip_javascript:
                continue

            # Check internal/external
            if link_type == LinkType.INTERNAL and not self.config.check_internal:
                continue
            if link_type == LinkType.EXTERNAL and not self.config.check_external:
                continue
            if link_type == LinkType.ANCHOR and not self.config.check_anchors:
                continue

            # Check skip patterns
            skip = False
            for pattern in self.config.skip_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    skip = True
                    break

            if not skip:
                filtered.append(link)

        return filtered

    def _get_link_type(
        self, url: str, href: str, parsed_base
    ) -> LinkType:
        """Determine the type of a link."""
        href_lower = href.lower()

        if href.startswith("#"):
            return LinkType.ANCHOR
        if href_lower.startswith("mailto:"):
            return LinkType.MAILTO
        if href_lower.startswith("tel:"):
            return LinkType.TEL
        if href_lower.startswith("javascript:"):
            return LinkType.JAVASCRIPT

        try:
            parsed = urlparse(url)
            if parsed.netloc == parsed_base.netloc:
                return LinkType.INTERNAL
            elif parsed.scheme in ["http", "https"]:
                return LinkType.EXTERNAL
        except Exception:
            pass

        return LinkType.OTHER

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

        # Convert exceptions to error results
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

    async def _check_single_link(
        self, link: Dict, source_url: str
    ) -> LinkResult:
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

        # Handle anchor links specially
        if link_type == LinkType.ANCHOR:
            # Would need to check if anchor exists on page
            result.status = LinkStatus.SKIPPED
            return result

        # Skip non-HTTP links
        if link_type in [LinkType.MAILTO, LinkType.TEL, LinkType.JAVASCRIPT]:
            result.status = LinkStatus.SKIPPED
            return result

        # Check HTTP link
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

            # Determine status
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
        report = LinkReport(
            url=url,
            analysis_duration_ms=analysis_duration,
            results=results if self.config.include_ok_links else [
                r for r in results if r.status != LinkStatus.OK
            ],
            total_links=len(all_links),
        )

        # Count by type
        for result in results:
            if result.link_type == LinkType.INTERNAL:
                report.internal_links += 1
            elif result.link_type == LinkType.EXTERNAL:
                report.external_links += 1
            elif result.link_type == LinkType.ANCHOR:
                report.anchor_links += 1

        # Count by status
        for result in results:
            if result.status == LinkStatus.OK:
                report.ok_count += 1
            elif result.status == LinkStatus.BROKEN:
                report.broken_count += 1
            elif result.status == LinkStatus.REDIRECT:
                report.redirect_count += 1
            elif result.status == LinkStatus.TIMEOUT:
                report.timeout_count += 1
            elif result.status == LinkStatus.ERROR:
                report.error_count += 1
            elif result.status == LinkStatus.SKIPPED:
                report.skipped_count += 1

        # Collect broken links
        for result in results:
            if result.is_broken:
                severity = LinkSeverity.CRITICAL
                if result.status_code and result.status_code in [403, 404]:
                    severity = LinkSeverity.WARNING

                suggested_fix = "Fix or remove the broken link"
                if result.status_code == 404:
                    suggested_fix = "Update link to correct URL or remove"
                elif result.status_code == 403:
                    suggested_fix = "Check access permissions or remove link"
                elif result.status == LinkStatus.TIMEOUT:
                    suggested_fix = "Check if target server is responding"

                report.broken_links.append(BrokenLink(
                    url=result.url,
                    source_url=result.source_url,
                    link_text=result.link_text,
                    status_code=result.status_code,
                    error_message=result.error_message,
                    severity=severity,
                    suggested_fix=suggested_fix,
                ))

        # Collect redirect chains
        if self.config.report_redirects:
            for result in results:
                if result.redirect_count >= self.config.min_redirect_chain:
                    chain = result.redirect_chain + [result.final_url or result.url]
                    report.redirect_chains.append(RedirectChain(
                        start_url=result.url,
                        final_url=result.final_url or result.url,
                        chain=chain,
                        chain_length=result.redirect_count,
                        source_url=result.source_url,
                        total_time_ms=result.response_time_ms or 0,
                    ))

        # Collect unique domains
        domains: Set[str] = set()
        for result in results:
            if result.link_type == LinkType.EXTERNAL:
                try:
                    domain = urlparse(result.url).netloc
                    if domain:
                        domains.add(domain)
                except Exception:
                    pass
        report.unique_domains = sorted(domains)

        # Collect slow links
        for result in results:
            if result.response_time_ms and result.response_time_ms > 1000:
                report.slow_links.append(result.url)

        # Calculate health score
        report.health_score = self._calculate_health_score(report)

        # Generate suggestions
        if report.broken_count > 0:
            report.suggestions.append(
                f"Fix {report.broken_count} broken link(s)"
            )
        if len(report.redirect_chains) > 0:
            report.suggestions.append(
                f"Update {len(report.redirect_chains)} link(s) to use final URLs"
            )
        if len(report.slow_links) > 5:
            report.suggestions.append(
                f"{len(report.slow_links)} links are slow to respond"
            )

        return report

    def _calculate_health_score(self, report: LinkReport) -> float:
        """Calculate link health score (0-100)."""
        if report.total_links == 0:
            return 100

        # Start with 100
        score = 100.0

        # Deduct for broken links (10 points each, max 50)
        broken_penalty = min(50, report.broken_count * 10)
        score -= broken_penalty

        # Deduct for timeouts (5 points each, max 20)
        timeout_penalty = min(20, report.timeout_count * 5)
        score -= timeout_penalty

        # Deduct for excessive redirects (2 points each, max 20)
        redirect_penalty = min(20, len(report.redirect_chains) * 2)
        score -= redirect_penalty

        # Deduct for errors (5 points each, max 10)
        error_penalty = min(10, report.error_count * 5)
        score -= error_penalty

        return cast(float, max(0, score))

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
