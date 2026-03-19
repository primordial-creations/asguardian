"""
Freya Image Optimization Scanner

Scans web pages for image optimization issues including
accessibility, performance, and best practices.
"""

import re
import time
from datetime import datetime
from typing import Dict, List, Optional, cast
from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import Page, async_playwright

from Asgard.Freya.Images.models.image_models import (
    ImageConfig,
    ImageFormat,
    ImageInfo,
    ImageIssue,
    ImageIssueSeverity,
    ImageIssueType,
    ImageReport,
)


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
        # Extract all images from the page
        images_data = await self._extract_images(page, url)

        # Build image info objects
        images: List[ImageInfo] = []
        for data in images_data:
            image_info = self._build_image_info(data)
            images.append(image_info)

        # Check for issues
        issues: List[ImageIssue] = []
        for image in images:
            image_issues = self._check_image(image)
            issues.extend(image_issues)

        # Build report
        return self._build_report(url, images, issues)

    async def _extract_images(self, page: Page, base_url: str) -> List[Dict]:
        """Extract image information from the page."""
        viewport_height = self.config.above_fold_height

        images = await page.evaluate(f"""
            (viewportHeight) => {{
                const images = [];

                // Get all img elements
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

                // Get background images
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

        # Filter out invisible images and resolve URLs
        filtered_images = []
        for img in images:
            if not img.get("isVisible", False):
                continue

            src = img.get("src", "") or img.get("dataSrc", "")

            # Skip data URLs if configured
            if self.config.skip_data_urls and src.startswith("data:"):
                continue

            # Skip empty sources
            if not src:
                continue

            # Resolve relative URLs
            if src and not src.startswith(("http://", "https://", "data:")):
                src = urljoin(base_url, src)
                img["src"] = src

            # Check if external
            try:
                base_domain = urlparse(base_url).netloc
                img_domain = urlparse(src).netloc
                img["isExternal"] = img_domain != base_domain
            except Exception:
                img["isExternal"] = False

            # Skip external if configured
            if self.config.skip_external_images and img.get("isExternal", False):
                continue

            filtered_images.append(img)

        return filtered_images

    def _build_image_info(self, data: Dict) -> ImageInfo:
        """Build ImageInfo from extracted data."""
        src = data.get("src", "")
        format_type = self._detect_format(src)

        # Determine if decorative
        is_decorative = (
            data.get("role") == "presentation" or
            data.get("ariaHidden") == "true" or
            (data.get("hasAlt") and data.get("alt") == "")
        )

        return ImageInfo(
            src=src,
            alt=data.get("alt"),
            has_alt=data.get("hasAlt", False),
            width=self._parse_int(data.get("width")),
            height=self._parse_int(data.get("height")),
            has_dimensions=bool(data.get("width") and data.get("height")),
            loading=data.get("loading"),
            has_lazy_loading=data.get("loading") == "lazy",
            srcset=data.get("srcset"),
            has_srcset=bool(data.get("srcset")),
            sizes=data.get("sizes"),
            format=format_type,
            natural_width=data.get("naturalWidth"),
            natural_height=data.get("naturalHeight"),
            display_width=data.get("displayWidth"),
            display_height=data.get("displayHeight"),
            is_above_fold=data.get("isAboveFold", False),
            element_html=data.get("html"),
            css_selector=data.get("cssSelector"),
            is_decorative=is_decorative,
            is_background_image=data.get("type") == "background",
        )

    def _parse_int(self, value) -> Optional[int]:
        """Safely parse an integer value."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _detect_format(self, src: str) -> ImageFormat:
        """Detect image format from URL."""
        if not src:
            return ImageFormat.UNKNOWN

        src_lower = src.lower()

        # Check URL extension
        for fmt in ImageFormat:
            if fmt == ImageFormat.UNKNOWN:
                continue
            if f".{fmt.value}" in src_lower:
                return fmt

        # Check for common CDN patterns
        if "webp" in src_lower:
            return ImageFormat.WEBP
        if "avif" in src_lower:
            return ImageFormat.AVIF

        return ImageFormat.UNKNOWN

    def _check_image(self, image: ImageInfo) -> List[ImageIssue]:
        """Check a single image for issues."""
        issues: List[ImageIssue] = []

        # Skip background images for most checks
        if image.is_background_image:
            # Only check format for background images
            if self.config.check_formats:
                format_issue = self._check_format(image)
                if format_issue:
                    issues.append(format_issue)
            return issues

        # Check alt text
        if self.config.check_alt_text:
            alt_issue = self._check_alt_text(image)
            if alt_issue:
                issues.append(alt_issue)

        # Check lazy loading
        if self.config.check_lazy_loading:
            lazy_issue = self._check_lazy_loading(image)
            if lazy_issue:
                issues.append(lazy_issue)

        # Check format
        if self.config.check_formats:
            format_issue = self._check_format(image)
            if format_issue:
                issues.append(format_issue)

        # Check dimensions
        if self.config.check_dimensions:
            dim_issue = self._check_dimensions(image)
            if dim_issue:
                issues.append(dim_issue)

        # Check oversized
        if self.config.check_oversized:
            oversized_issue = self._check_oversized(image)
            if oversized_issue:
                issues.append(oversized_issue)

        # Check srcset
        if self.config.check_srcset:
            srcset_issue = self._check_srcset(image)
            if srcset_issue:
                issues.append(srcset_issue)

        return issues

    def _check_alt_text(self, image: ImageInfo) -> Optional[ImageIssue]:
        """Check for alt text issues."""
        # Skip decorative images with empty alt
        if image.is_decorative and image.has_alt and image.alt == "":
            return None

        # Missing alt attribute entirely
        if not image.has_alt:
            return ImageIssue(
                issue_type=ImageIssueType.MISSING_ALT,
                severity=ImageIssueSeverity.CRITICAL,
                image_src=image.src,
                description="Image is missing alt attribute",
                suggested_fix=(
                    "Add an alt attribute describing the image content. "
                    "For decorative images, use alt=\"\""
                ),
                wcag_reference="WCAG 1.1.1 (Non-text Content)",
                impact=(
                    "Screen reader users will not know what the image contains"
                ),
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        # Has alt attribute but it's empty on non-decorative image
        if image.alt == "" and not image.is_decorative:
            # Check if it looks decorative
            if self._appears_decorative(image):
                return None

            return ImageIssue(
                issue_type=ImageIssueType.EMPTY_ALT,
                severity=ImageIssueSeverity.WARNING,
                image_src=image.src,
                description=(
                    "Image has empty alt text but may contain meaningful content"
                ),
                suggested_fix=(
                    "If the image conveys information, add descriptive alt text. "
                    "If purely decorative, empty alt is correct."
                ),
                wcag_reference="WCAG 1.1.1 (Non-text Content)",
                impact=(
                    "Screen reader users may miss important information"
                ),
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        return None

    def _appears_decorative(self, image: ImageInfo) -> bool:
        """Heuristic to detect if image appears decorative."""
        src_lower = image.src.lower()

        # Common decorative patterns
        decorative_patterns = [
            "icon", "logo", "spacer", "dot", "bullet",
            "divider", "separator", "border", "shadow",
            "gradient", "pattern", "texture", "background",
            "arrow", "chevron", "caret",
        ]

        for pattern in decorative_patterns:
            if pattern in src_lower:
                return True

        # Very small images are often decorative
        if image.display_width and image.display_height:
            if image.display_width < 24 and image.display_height < 24:
                return True

        return False

    def _check_lazy_loading(self, image: ImageInfo) -> Optional[ImageIssue]:
        """Check for lazy loading issues."""
        # Above-fold images should NOT have lazy loading
        if image.is_above_fold and image.has_lazy_loading:
            return ImageIssue(
                issue_type=ImageIssueType.MISSING_LAZY_LOADING,
                severity=ImageIssueSeverity.INFO,
                image_src=image.src,
                description=(
                    "Above-fold image has lazy loading which may delay LCP"
                ),
                suggested_fix=(
                    "Remove loading=\"lazy\" from above-fold images "
                    "to improve Largest Contentful Paint"
                ),
                wcag_reference=None,
                impact="May negatively impact Core Web Vitals (LCP)",
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        # Below-fold images SHOULD have lazy loading
        if not image.is_above_fold and not image.has_lazy_loading:
            return ImageIssue(
                issue_type=ImageIssueType.MISSING_LAZY_LOADING,
                severity=ImageIssueSeverity.WARNING,
                image_src=image.src,
                description="Below-fold image does not have lazy loading",
                suggested_fix="Add loading=\"lazy\" to defer loading until needed",
                wcag_reference=None,
                impact=(
                    "Images load immediately, increasing initial page weight "
                    "and slowing page load"
                ),
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        return None

    def _check_format(self, image: ImageInfo) -> Optional[ImageIssue]:
        """Check for non-optimized format."""
        # Skip SVG if configured
        if self.config.skip_svg and image.format == ImageFormat.SVG:
            return None

        # Check if using modern format
        modern_formats = [ImageFormat.WEBP, ImageFormat.AVIF, ImageFormat.SVG]

        if image.format not in modern_formats and image.format != ImageFormat.UNKNOWN:
            return ImageIssue(
                issue_type=ImageIssueType.NON_OPTIMIZED_FORMAT,
                severity=ImageIssueSeverity.WARNING,
                image_src=image.src,
                description=(
                    f"Image uses {image.format.value.upper()} format "
                    f"instead of modern WebP/AVIF"
                ),
                suggested_fix=(
                    "Convert to WebP or AVIF format for better compression. "
                    "Use <picture> element for fallback support."
                ),
                wcag_reference=None,
                impact=(
                    "Modern formats can reduce file size by 25-50% "
                    "without quality loss"
                ),
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        return None

    def _check_dimensions(self, image: ImageInfo) -> Optional[ImageIssue]:
        """Check for missing width/height attributes."""
        if not image.has_dimensions:
            return ImageIssue(
                issue_type=ImageIssueType.MISSING_DIMENSIONS,
                severity=ImageIssueSeverity.WARNING,
                image_src=image.src,
                description="Image is missing width and/or height attributes",
                suggested_fix=(
                    "Add explicit width and height attributes to prevent "
                    "Cumulative Layout Shift (CLS)"
                ),
                wcag_reference=None,
                impact=(
                    "Browser cannot reserve space, causing layout shifts "
                    "when image loads"
                ),
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        return None

    def _check_oversized(self, image: ImageInfo) -> Optional[ImageIssue]:
        """Check for oversized images."""
        if not image.natural_width or not image.display_width:
            return None

        if image.display_width == 0:
            return None

        ratio = image.natural_width / image.display_width

        if ratio > self.config.oversized_threshold:
            wasted_pixels = image.natural_width - image.display_width
            estimated_savings = self._estimate_size_savings(
                image.natural_width,
                image.natural_height or 0,
                image.display_width,
                image.display_height or 0,
            )

            return ImageIssue(
                issue_type=ImageIssueType.OVERSIZED_IMAGE,
                severity=ImageIssueSeverity.WARNING,
                image_src=image.src,
                description=(
                    f"Image is {ratio:.1f}x larger than displayed size "
                    f"({image.natural_width}x{image.natural_height} displayed at "
                    f"{image.display_width}x{image.display_height})"
                ),
                suggested_fix=(
                    f"Resize image to match display size or use srcset. "
                    f"Could save ~{estimated_savings // 1024}KB"
                ),
                wcag_reference=None,
                impact=f"~{wasted_pixels}px of unnecessary width being downloaded",
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        return None

    def _estimate_size_savings(
        self,
        natural_width: int,
        natural_height: int,
        display_width: int,
        display_height: int,
    ) -> int:
        """Estimate bytes saved by resizing."""
        if not natural_height or not display_height:
            return 0

        natural_pixels = natural_width * natural_height
        display_pixels = display_width * display_height

        # Rough estimate: 3 bytes per pixel for compressed image
        bytes_per_pixel = 0.5

        natural_bytes = natural_pixels * bytes_per_pixel
        display_bytes = display_pixels * bytes_per_pixel

        return int(natural_bytes - display_bytes)

    def _check_srcset(self, image: ImageInfo) -> Optional[ImageIssue]:
        """Check for missing srcset on responsive images."""
        # Only check images above certain width
        if (image.display_width or 0) < self.config.min_srcset_width:
            return None

        if not image.has_srcset:
            return ImageIssue(
                issue_type=ImageIssueType.MISSING_SRCSET,
                severity=ImageIssueSeverity.INFO,
                image_src=image.src,
                description="Large image missing srcset for responsive images",
                suggested_fix=(
                    "Add srcset attribute with multiple image sizes "
                    "for different screen resolutions"
                ),
                wcag_reference=None,
                impact=(
                    "Mobile users may download unnecessarily large images"
                ),
                element_html=image.element_html,
                css_selector=image.css_selector,
            )

        return None

    def _build_report(
        self,
        url: str,
        images: List[ImageInfo],
        issues: List[ImageIssue],
    ) -> ImageReport:
        """Build the final report."""
        report = ImageReport(
            url=url,
            images=images if self.config.include_all_images else [],
            total_images=len(images),
            issues=issues,
            total_issues=len(issues),
        )

        # Count by issue type
        for issue in issues:
            if issue.issue_type == ImageIssueType.MISSING_ALT:
                report.missing_alt_count += 1
            elif issue.issue_type == ImageIssueType.EMPTY_ALT:
                report.empty_alt_count += 1
            elif issue.issue_type == ImageIssueType.MISSING_LAZY_LOADING:
                report.missing_lazy_loading_count += 1
            elif issue.issue_type == ImageIssueType.NON_OPTIMIZED_FORMAT:
                report.non_optimized_format_count += 1
            elif issue.issue_type == ImageIssueType.MISSING_DIMENSIONS:
                report.missing_dimensions_count += 1
            elif issue.issue_type == ImageIssueType.OVERSIZED_IMAGE:
                report.oversized_count += 1
            elif issue.issue_type == ImageIssueType.MISSING_SRCSET:
                report.missing_srcset_count += 1

        # Count by severity
        for issue in issues:
            if issue.severity == ImageIssueSeverity.CRITICAL:
                report.critical_count += 1
            elif issue.severity == ImageIssueSeverity.WARNING:
                report.warning_count += 1
            elif issue.severity == ImageIssueSeverity.INFO:
                report.info_count += 1

        # Statistics
        for image in images:
            if image.is_above_fold:
                report.images_above_fold += 1
            if image.has_lazy_loading:
                report.images_with_lazy_loading += 1
            if image.has_srcset:
                report.images_with_srcset += 1
            if image.format in [ImageFormat.WEBP, ImageFormat.AVIF]:
                report.optimized_format_count += 1
            if image.file_size_bytes:
                report.total_image_bytes += image.file_size_bytes

        # Format breakdown
        format_counts: Dict[str, int] = {}
        for image in images:
            fmt = image.format.value
            format_counts[fmt] = format_counts.get(fmt, 0) + 1
        report.format_breakdown = format_counts

        # Calculate score
        report.optimization_score = self._calculate_score(report, len(images))

        # Generate suggestions
        report.suggestions = self._generate_suggestions(report)

        return report

    def _calculate_score(self, report: ImageReport, total_images: int) -> float:
        """Calculate optimization score (0-100)."""
        if total_images == 0:
            return 100.0

        score = 100.0

        # Deduct for critical issues (missing alt)
        critical_penalty = min(40, report.critical_count * 10)
        score -= critical_penalty

        # Deduct for warnings
        warning_penalty = min(30, report.warning_count * 3)
        score -= warning_penalty

        # Deduct for info issues
        info_penalty = min(10, report.info_count * 1)
        score -= info_penalty

        # Bonus for good practices
        if total_images > 0:
            # Bonus for lazy loading usage
            lazy_ratio = report.images_with_lazy_loading / total_images
            score += lazy_ratio * 5

            # Bonus for modern formats
            modern_ratio = report.optimized_format_count / total_images
            score += modern_ratio * 5

        return cast(float, max(0, min(100, score)))

    def _generate_suggestions(self, report: ImageReport) -> List[str]:
        """Generate actionable suggestions."""
        suggestions = []

        if report.missing_alt_count > 0:
            suggestions.append(
                f"Add alt text to {report.missing_alt_count} image(s) "
                f"for accessibility"
            )

        if report.missing_lazy_loading_count > 0:
            suggestions.append(
                f"Add lazy loading to {report.missing_lazy_loading_count} "
                f"below-fold image(s)"
            )

        if report.non_optimized_format_count > 0:
            suggestions.append(
                f"Convert {report.non_optimized_format_count} image(s) "
                f"to WebP/AVIF format"
            )

        if report.missing_dimensions_count > 0:
            suggestions.append(
                f"Add width/height to {report.missing_dimensions_count} "
                f"image(s) to prevent CLS"
            )

        if report.oversized_count > 0:
            suggestions.append(
                f"Resize {report.oversized_count} oversized image(s) "
                f"to match display size"
            )

        if report.missing_srcset_count > 0:
            suggestions.append(
                f"Add srcset to {report.missing_srcset_count} large image(s) "
                f"for responsive loading"
            )

        if not suggestions:
            suggestions.append("Images are well optimized")

        return suggestions

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
