"""
Freya Image Optimization Scanner

Scans web pages for image optimization issues including
accessibility, performance, and best practices.
"""

import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import Page, async_playwright

from Asgard.Freya.Images.models.image_models import (
    ImageConfig,
    ImageFormat,
    ImageInfo,
    ImageIssue,
    ImageReport,
)
from Asgard.Freya.Images.services._image_scanner_checks import (
    build_image_info,
    check_image,
)
from Asgard.Freya.Images.services._image_scanner_report import build_report


class ImageOptimizationScanner:
    """
    Scans web pages for image optimization issues.

    Detects:
    - Missing alt text on images
    - Images without lazy loading
    - Non-optimized formats (should use WebP/AVIF)
    - Missing width/height attributes (causes CLS)
    - Oversized images (larger than display size)
    - Missing srcset for responsive images
    """

    def __init__(self, config: Optional[ImageConfig] = None):
        """
        Initialize the image optimization scanner.

        Args:
            config: Image scanning configuration
        """
        self.config = config or ImageConfig()
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; FreyaBot/1.0; "
                        "+https://github.com/JakeDruett/asgard)"
                    ),
                },
            )
        return self._http_client

    async def scan(self, url: str) -> ImageReport:
        """
        Scan a URL for image optimization issues.

        Args:
            url: URL to scan

        Returns:
            ImageReport with all findings
        """
        start_time = datetime.now()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                report = await self._scan_page(page, url)
            finally:
                await browser.close()

        report.analysis_duration_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return report

    async def scan_page(self, page: Page, url: str) -> ImageReport:
        """
        Scan an already loaded page for image optimization issues.

        Args:
            page: Playwright Page object
            url: URL of the page

        Returns:
            ImageReport with all findings
        """
        start_time = datetime.now()
        report = await self._scan_page(page, url)
        report.analysis_duration_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000
        return report

    async def check_alt_text(self, url: str) -> ImageReport:
        """
        Check alt text only on a URL.

        Args:
            url: URL to check

        Returns:
            ImageReport focused on alt text issues
        """
        config = ImageConfig(
            check_alt_text=True,
            check_lazy_loading=False,
            check_formats=False,
            check_dimensions=False,
            check_oversized=False,
            check_srcset=False,
        )

        original_config = self.config
        self.config = config

        try:
            return await self.scan(url)
        finally:
            self.config = original_config

    async def check_performance(self, url: str) -> ImageReport:
        """
        Check performance issues only on a URL.

        Args:
            url: URL to check

        Returns:
            ImageReport focused on performance issues
        """
        config = ImageConfig(
            check_alt_text=False,
            check_lazy_loading=True,
            check_formats=True,
            check_dimensions=True,
            check_oversized=True,
            check_srcset=True,
        )

        original_config = self.config
        self.config = config

        try:
            return await self.scan(url)
        finally:
            self.config = original_config

    async def _scan_page(self, page: Page, url: str) -> ImageReport:
        """Internal method to scan a page."""
        images_data = await self._extract_images(page, url)

        images: List[ImageInfo] = []
        for data in images_data:
            image_info = build_image_info(data)
            images.append(image_info)

        issues: List[ImageIssue] = []
        for image in images:
            image_issues = check_image(image, self.config)
            issues.extend(image_issues)

        return build_report(url, images, issues, self.config)

    async def _extract_images(self, page: Page, base_url: str) -> List[Dict]:
        """Extract image information from the page."""
        viewport_height = self.config.above_fold_height

        images = await page.evaluate(f"""
            (viewportHeight) => {{
                const images = [];

                document.querySelectorAll('img').forEach((img, index) => {{
                    const rect = img.getBoundingClientRect();
                    const computedStyle = window.getComputedStyle(img);

                    images.push({{
                        type: 'img',
                        src: img.src || img.getAttribute('src') || '',
                        dataSrc: img.dataset.src || '',
                        alt: img.getAttribute('alt'),
                        hasAlt: img.hasAttribute('alt'),
                        width: img.getAttribute('width'),
                        height: img.getAttribute('height'),
                        loading: img.getAttribute('loading'),
                        srcset: img.getAttribute('srcset'),
                        sizes: img.getAttribute('sizes'),
                        naturalWidth: img.naturalWidth,
                        naturalHeight: img.naturalHeight,
                        displayWidth: Math.round(rect.width),
                        displayHeight: Math.round(rect.height),
                        isAboveFold: rect.top < viewportHeight,
                        html: img.outerHTML.substring(0, 500),
                        cssSelector: img.id ? '#' + img.id :
                            (img.className ? 'img.' + img.className.split(' ')[0] :
                                'img:nth-of-type(' + (index + 1) + ')'),
                        role: img.getAttribute('role'),
                        ariaHidden: img.getAttribute('aria-hidden'),
                        isVisible: computedStyle.display !== 'none' &&
                            computedStyle.visibility !== 'hidden' &&
                            rect.width > 0 && rect.height > 0
                    }});
                }});

                document.querySelectorAll('*').forEach((el, index) => {{
                    const style = window.getComputedStyle(el);
                    const bgImage = style.backgroundImage;
                    if (bgImage && bgImage !== 'none' && bgImage.startsWith('url(')) {{
                        const url = bgImage.slice(5, -2).replace(/['"]/g, '');
                        if (url && !url.startsWith('data:')) {{
                            const rect = el.getBoundingClientRect();
                            images.push({{
                                type: 'background',
                                src: url,
                                dataSrc: '',
                                alt: null,
                                hasAlt: false,
                                width: null,
                                height: null,
                                loading: null,
                                srcset: null,
                                sizes: null,
                                naturalWidth: 0,
                                naturalHeight: 0,
                                displayWidth: Math.round(rect.width),
                                displayHeight: Math.round(rect.height),
                                isAboveFold: rect.top < viewportHeight,
                                html: '',
                                cssSelector: el.id ? '#' + el.id : 'element:nth-of-type(' + index + ')',
                                role: null,
                                ariaHidden: null,
                                isVisible: rect.width > 0 && rect.height > 0
                            }});
                        }}
                    }}
                }});

                return images;
            }}
        """, viewport_height)

        filtered_images = []
        for img in images:
            if not img.get("isVisible", False):
                continue

            src = img.get("src", "") or img.get("dataSrc", "")

            if self.config.skip_data_urls and src.startswith("data:"):
                continue

            if not src:
                continue

            if src and not src.startswith(("http://", "https://", "data:")):
                src = urljoin(base_url, src)
                img["src"] = src

            try:
                base_domain = urlparse(base_url).netloc
                img_domain = urlparse(src).netloc
                img["isExternal"] = img_domain != base_domain
            except Exception:
                img["isExternal"] = False

            if self.config.skip_external_images and img.get("isExternal", False):
                continue

            filtered_images.append(img)

        return filtered_images

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
