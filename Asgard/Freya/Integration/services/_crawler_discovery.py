"""
Freya Site Crawler page discovery.

Site crawl loop and link extraction extracted from site_crawler.py.
"""

import asyncio
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import BrowserContext, Page

from Asgard.Freya.Integration.models.integration_models import (
    CrawlConfig,
    CrawledPage,
    PageStatus,
)
from Asgard.Freya.Integration.services._crawler_spa import discover_spa_items


def normalize_url(url: str, base_url: str) -> Optional[str]:
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


async def extract_links(page: Page, current_url: str) -> List[str]:
    """Extract all links from a page."""
    links = await page.evaluate("""
        () => {
            const anchors = document.querySelectorAll('a[href]');
            return Array.from(anchors).map(a => a.href);
        }
    """)

    normalized_links = []
    for link in links:
        normalized = normalize_url(link, current_url)
        if normalized and normalized not in normalized_links:
            normalized_links.append(normalized)

    return normalized_links


def should_crawl(
    url: str,
    base_domain: str,
    same_domain_only: bool,
    compiled_exclude: list,
    compiled_include: list,
) -> bool:
    """Check if a URL should be crawled."""
    parsed = urlparse(url)
    if same_domain_only and parsed.netloc != base_domain:
        return False
    for pattern in compiled_exclude:
        if pattern.match(url):
            return False
    if compiled_include:
        for pattern in compiled_include:
            if pattern.match(url):
                return True
        return False
    return True


async def crawl_site(
    context: BrowserContext,
    config: CrawlConfig,
    discovered_pages: Dict[str, CrawledPage],
    base_domain: str,
    compiled_include: list,
    compiled_exclude: list,
    auth_storage: Optional[str],
    report_progress: Callable,
) -> None:
    """Crawl the site discovering all pages."""
    def add_page(url: str, depth: int, parent_url: Optional[str]) -> None:
        if url not in discovered_pages:
            discovered_pages[url] = CrawledPage(
                url=url,
                depth=depth,
                parent_url=parent_url,
                status=PageStatus.PENDING,
            )

    add_page(config.start_url, depth=0, parent_url=None)
    pages_to_crawl = [config.start_url]

    base_url = config.start_url.rstrip("/")
    for route in config.additional_routes:
        if ":" in route and "/" in route:
            route = "/" + route.split("/")[-1]
        route = route if route.startswith("/") else f"/{route}"
        full_url = f"{base_url}{route}"
        if full_url not in discovered_pages:
            add_page(full_url, depth=1, parent_url=config.start_url)
            pages_to_crawl.append(full_url)

    crawled_count = 0

    while pages_to_crawl and crawled_count < config.max_pages:
        url = pages_to_crawl.pop(0)
        page_info = discovered_pages.get(url)

        if not page_info or page_info.status != PageStatus.PENDING:
            continue

        if page_info.depth >= config.max_depth:
            page_info.status = PageStatus.SKIPPED
            continue

        crawled_count += 1
        report_progress(f"Crawling: {url}", crawled_count, len(discovered_pages))
        page_info.status = PageStatus.CRAWLING

        try:
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            page_info.title = await page.title()
            links = await extract_links(page, url)
            page_info.links_found = links

            for link in links:
                if link not in discovered_pages:
                    if should_crawl(link, base_domain, config.same_domain_only, compiled_exclude, compiled_include):
                        add_page(link, depth=page_info.depth + 1, parent_url=url)
                        pages_to_crawl.append(link)

            page_info.status = PageStatus.TESTED
            await page.close()

            if config.delay_between_requests > 0:
                await asyncio.sleep(config.delay_between_requests)

        except Exception as e:
            page_info.status = PageStatus.ERROR
            page_info.error_message = str(e)

    if config.discover_items:
        report_progress("Discovering clickable items in SPA...")
        tested_pages = [
            p.url for p in discovered_pages.values()
            if p.status == PageStatus.TESTED
        ]

        for page_url in tested_pages:
            if crawled_count >= config.max_pages:
                break

            item_urls = await discover_spa_items(context, page_url, auth_storage, report_progress)
            for item_url in item_urls:
                if item_url not in discovered_pages and crawled_count < config.max_pages:
                    add_page(item_url, depth=2, parent_url=page_url)
                    crawled_count += 1
                    if item_url in discovered_pages:
                        discovered_pages[item_url].status = PageStatus.TESTED

    report_progress(
        f"Crawl complete: {len(discovered_pages)} pages discovered",
        len(discovered_pages),
        len(discovered_pages),
    )
