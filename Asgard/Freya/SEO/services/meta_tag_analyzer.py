"""
Freya Meta Tag Analyzer

Analyzes meta tags for SEO compliance including title, description,
Open Graph, and Twitter Card tags.
"""

from typing import Any, Dict, List, Optional, cast

from playwright.async_api import Page, async_playwright

from Asgard.Freya.SEO.models.seo_models import (
    MetaTag,
    MetaTagReport,
    MetaTagType,
    SEOConfig,
)
from Asgard.Freya.SEO.services._meta_tag_analyzers import (
    analyze_title,
    analyze_description,
    analyze_keywords,
    analyze_canonical,
    analyze_robots,
    analyze_viewport,
    analyze_og_tags,
    analyze_twitter_tags,
    calculate_score,
)


class MetaTagAnalyzer:
    """
    Analyzes meta tags for SEO compliance.

    Checks title, description, canonical, Open Graph, and Twitter Card tags.
    """

    def __init__(self, config: Optional[SEOConfig] = None):
        """
        Initialize the meta tag analyzer.

        Args:
            config: SEO configuration
        """
        self.config = config or SEOConfig()

    async def analyze(self, url: str) -> MetaTagReport:
        """
        Analyze meta tags for a URL.

        Args:
            url: URL to analyze

        Returns:
            MetaTagReport with analysis results
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return await self.analyze_page(page, url)
            finally:
                await browser.close()

    async def analyze_page(self, page: Page, url: str) -> MetaTagReport:
        """
        Analyze meta tags on an already loaded page.

        Args:
            page: Playwright Page object
            url: URL of the page

        Returns:
            MetaTagReport with analysis results
        """
        meta_data = await self._extract_meta_data(page)

        title = analyze_title(meta_data.get("title"), self.config)
        description = analyze_description(meta_data.get("description"), self.config)
        keywords = analyze_keywords(meta_data.get("keywords"))
        canonical = analyze_canonical(meta_data.get("canonical"), url)
        robots = analyze_robots(meta_data.get("robots"))
        viewport = analyze_viewport(meta_data.get("viewport"))

        og_tags = analyze_og_tags(meta_data.get("og", {}), self.config)
        twitter_tags = analyze_twitter_tags(meta_data.get("twitter", {}), self.config)

        all_issues = []
        missing_required = []

        for tag in [title, description, keywords, canonical, robots, viewport]:
            if tag:
                all_issues.extend(tag.issues)

        for tag in og_tags.values():
            all_issues.extend(tag.issues)

        for tag in twitter_tags.values():
            all_issues.extend(tag.issues)

        if not title or not title.is_present:
            missing_required.append("title")
        if not description or not description.is_present:
            missing_required.append("meta description")
        if self.config.require_og_tags:
            if "og:title" not in og_tags or not og_tags["og:title"].is_present:
                missing_required.append("og:title")
            if "og:description" not in og_tags or not og_tags["og:description"].is_present:
                missing_required.append("og:description")
            if "og:image" not in og_tags or not og_tags["og:image"].is_present:
                missing_required.append("og:image")

        valid_count = 0
        total_count = 0
        for tag in [title, description, canonical, viewport]:
            if tag and tag.is_present:
                total_count += 1
                if tag.is_valid:
                    valid_count += 1

        for tag in og_tags.values():
            if tag.is_present:
                total_count += 1
                if tag.is_valid:
                    valid_count += 1

        for tag in twitter_tags.values():
            if tag.is_present:
                total_count += 1
                if tag.is_valid:
                    valid_count += 1

        score = calculate_score(
            title, description, canonical, og_tags, twitter_tags, missing_required
        )

        return MetaTagReport(
            url=url,
            title=title,
            description=description,
            keywords=keywords,
            canonical=canonical,
            robots=robots,
            viewport=viewport,
            og_tags=og_tags,
            twitter_tags=twitter_tags,
            total_tags=total_count,
            valid_tags=valid_count,
            missing_required=missing_required,
            issues=all_issues,
            score=score,
        )

    async def _extract_meta_data(self, page: Page) -> Dict:
        """Extract all meta tag data from the page."""
        return cast(Dict[Any, Any], await page.evaluate("""
            () => {
                const data = {
                    og: {},
                    twitter: {}
                };

                const titleEl = document.querySelector('title');
                data.title = titleEl ? titleEl.textContent : null;

                const metas = document.querySelectorAll('meta');
                for (const meta of metas) {
                    const name = meta.getAttribute('name');
                    const property = meta.getAttribute('property');
                    const content = meta.getAttribute('content');

                    if (name === 'description') {
                        data.description = content;
                    } else if (name === 'keywords') {
                        data.keywords = content;
                    } else if (name === 'robots') {
                        data.robots = content;
                    } else if (name === 'viewport') {
                        data.viewport = content;
                    } else if (property && property.startsWith('og:')) {
                        data.og[property] = content;
                    } else if (name && name.startsWith('twitter:')) {
                        data.twitter[name] = content;
                    }
                }

                const canonical = document.querySelector('link[rel="canonical"]');
                data.canonical = canonical ? canonical.getAttribute('href') : null;

                return data;
            }
        """))

    def _analyze_title(self, value: Optional[str]) -> MetaTag:
        """Analyze the title tag."""
        return analyze_title(value, self.config)

    def _analyze_description(self, value: Optional[str]) -> MetaTag:
        """Analyze the meta description."""
        return analyze_description(value, self.config)

    def _analyze_keywords(self, value: Optional[str]) -> MetaTag:
        """Analyze the meta keywords tag."""
        return analyze_keywords(value)

    def _analyze_canonical(self, value: Optional[str], page_url: str) -> MetaTag:
        """Analyze the canonical URL."""
        return analyze_canonical(value, page_url)

    def _analyze_robots(self, value: Optional[str]) -> MetaTag:
        """Analyze the robots meta tag."""
        return analyze_robots(value)

    def _analyze_viewport(self, value: Optional[str]) -> MetaTag:
        """Analyze the viewport meta tag."""
        return analyze_viewport(value)

    def _analyze_og_tags(self, og_data: Dict[str, str]) -> Dict[str, MetaTag]:
        """Analyze Open Graph tags."""
        return analyze_og_tags(og_data, self.config)

    def _analyze_twitter_tags(self, twitter_data: Dict[str, str]) -> Dict[str, MetaTag]:
        """Analyze Twitter Card tags."""
        return analyze_twitter_tags(twitter_data, self.config)

    def _calculate_score(
        self,
        title: Optional[MetaTag],
        description: Optional[MetaTag],
        canonical: Optional[MetaTag],
        og_tags: Dict[str, MetaTag],
        twitter_tags: Dict[str, MetaTag],
        missing_required: List[str],
    ) -> float:
        """Calculate the SEO score for meta tags."""
        return calculate_score(title, description, canonical, og_tags, twitter_tags, missing_required)
