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
        # Extract all meta data
        meta_data = await self._extract_meta_data(page)

        # Analyze core tags
        title = self._analyze_title(meta_data.get("title"))
        description = self._analyze_description(meta_data.get("description"))
        keywords = self._analyze_keywords(meta_data.get("keywords"))
        canonical = self._analyze_canonical(meta_data.get("canonical"), url)
        robots = self._analyze_robots(meta_data.get("robots"))
        viewport = self._analyze_viewport(meta_data.get("viewport"))

        # Analyze OG tags
        og_tags = self._analyze_og_tags(meta_data.get("og", {}))

        # Analyze Twitter tags
        twitter_tags = self._analyze_twitter_tags(meta_data.get("twitter", {}))

        # Build report
        all_issues = []
        missing_required = []

        # Collect issues
        for tag in [title, description, keywords, canonical, robots, viewport]:
            if tag:
                all_issues.extend(tag.issues)

        for tag in og_tags.values():
            all_issues.extend(tag.issues)

        for tag in twitter_tags.values():
            all_issues.extend(tag.issues)

        # Check required tags
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

        # Count valid tags
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

        # Calculate score
        score = self._calculate_score(
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

                // Get title
                const titleEl = document.querySelector('title');
                data.title = titleEl ? titleEl.textContent : null;

                // Get meta tags
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

                // Get canonical
                const canonical = document.querySelector('link[rel="canonical"]');
                data.canonical = canonical ? canonical.getAttribute('href') : null;

                return data;
            }
        """))

    def _analyze_title(self, value: Optional[str]) -> MetaTag:
        """Analyze the title tag."""
        tag = MetaTag(tag_type=MetaTagType.TITLE)

        if value is None:
            tag.is_present = False
            tag.is_valid = False
            tag.issues.append("Title tag is missing")
            tag.suggestions.append("Add a unique, descriptive title tag")
            return tag

        tag.is_present = True
        tag.value = value
        tag.length = len(value)

        # Check length
        if len(value) < self.config.min_title_length:
            tag.is_valid = False
            tag.issues.append(
                f"Title is too short ({len(value)} chars, "
                f"minimum {self.config.min_title_length})"
            )
            tag.suggestions.append("Make the title more descriptive")
        elif len(value) > self.config.max_title_length:
            tag.issues.append(
                f"Title may be truncated in search results ({len(value)} chars, "
                f"maximum {self.config.max_title_length})"
            )
            tag.suggestions.append("Shorten the title for better display")
        else:
            tag.is_valid = True

        return tag

    def _analyze_description(self, value: Optional[str]) -> MetaTag:
        """Analyze the meta description."""
        tag = MetaTag(tag_type=MetaTagType.DESCRIPTION)

        if value is None:
            tag.is_present = False
            tag.is_valid = False
            tag.issues.append("Meta description is missing")
            tag.suggestions.append("Add a compelling meta description")
            return tag

        tag.is_present = True
        tag.value = value
        tag.length = len(value)

        # Check length
        if len(value) < self.config.min_description_length:
            tag.is_valid = False
            tag.issues.append(
                f"Description is too short ({len(value)} chars, "
                f"minimum {self.config.min_description_length})"
            )
            tag.suggestions.append("Expand the description to be more informative")
        elif len(value) > self.config.max_description_length:
            tag.issues.append(
                f"Description may be truncated ({len(value)} chars, "
                f"maximum {self.config.max_description_length})"
            )
            tag.suggestions.append("Shorten the description for better display")
        else:
            tag.is_valid = True

        return tag

    def _analyze_keywords(self, value: Optional[str]) -> MetaTag:
        """Analyze the meta keywords tag."""
        tag = MetaTag(tag_type=MetaTagType.KEYWORDS)

        if value is None:
            tag.is_present = False
            # Keywords are not required, just informational
            return tag

        tag.is_present = True
        tag.value = value
        tag.length = len(value)
        tag.is_valid = True

        # Note: Keywords are generally ignored by search engines now
        tag.suggestions.append(
            "Meta keywords are generally ignored by search engines; "
            "focus on content instead"
        )

        return tag

    def _analyze_canonical(self, value: Optional[str], page_url: str) -> MetaTag:
        """Analyze the canonical URL."""
        tag = MetaTag(tag_type=MetaTagType.CANONICAL)

        if value is None:
            tag.is_present = False
            tag.issues.append("Canonical URL is missing")
            tag.suggestions.append("Add a canonical URL to prevent duplicate content")
            return tag

        tag.is_present = True
        tag.value = value
        tag.length = len(value)

        # Validate URL format
        if not value.startswith("http"):
            tag.is_valid = False
            tag.issues.append("Canonical URL should be an absolute URL")
        else:
            tag.is_valid = True

        return tag

    def _analyze_robots(self, value: Optional[str]) -> MetaTag:
        """Analyze the robots meta tag."""
        tag = MetaTag(tag_type=MetaTagType.ROBOTS)

        if value is None:
            tag.is_present = False
            # Robots is optional
            return tag

        tag.is_present = True
        tag.value = value
        tag.length = len(value)
        tag.is_valid = True

        # Check for noindex/nofollow
        value_lower = value.lower()
        if "noindex" in value_lower:
            tag.issues.append("Page has noindex directive - will not be indexed")
        if "nofollow" in value_lower:
            tag.issues.append("Page has nofollow directive - links will not be followed")

        return tag

    def _analyze_viewport(self, value: Optional[str]) -> MetaTag:
        """Analyze the viewport meta tag."""
        tag = MetaTag(tag_type=MetaTagType.VIEWPORT)

        if value is None:
            tag.is_present = False
            tag.is_valid = False
            tag.issues.append("Viewport meta tag is missing - not mobile-friendly")
            tag.suggestions.append(
                'Add <meta name="viewport" content="width=device-width, initial-scale=1">'
            )
            return tag

        tag.is_present = True
        tag.value = value
        tag.length = len(value)
        tag.is_valid = True

        # Check for recommended values
        if "width=device-width" not in value.lower():
            tag.issues.append("Viewport should include width=device-width")

        return tag

    def _analyze_og_tags(self, og_data: Dict[str, str]) -> Dict[str, MetaTag]:
        """Analyze Open Graph tags."""
        og_tags = {}

        required_og = ["og:title", "og:description", "og:image", "og:url", "og:type"]

        for og_key in required_og:
            tag = MetaTag(tag_type=MetaTagType(og_key.replace("og:", "og_")))
            value = og_data.get(og_key)

            if value is None:
                tag.is_present = False
                if self.config.require_og_tags:
                    tag.issues.append(f"{og_key} is missing")
            else:
                tag.is_present = True
                tag.value = value
                tag.length = len(value)
                tag.is_valid = True

            og_tags[og_key] = tag

        return og_tags

    def _analyze_twitter_tags(self, twitter_data: Dict[str, str]) -> Dict[str, MetaTag]:
        """Analyze Twitter Card tags."""
        twitter_tags = {}

        twitter_keys = [
            "twitter:card",
            "twitter:title",
            "twitter:description",
            "twitter:image",
        ]

        for tw_key in twitter_keys:
            tag_type_str = tw_key.replace("twitter:", "twitter_")
            try:
                tag = MetaTag(tag_type=MetaTagType(tag_type_str))
            except ValueError:
                tag = MetaTag(tag_type=MetaTagType.TWITTER_CARD)

            value = twitter_data.get(tw_key)

            if value is None:
                tag.is_present = False
                if self.config.require_twitter_cards and tw_key == "twitter:card":
                    tag.issues.append(f"{tw_key} is missing")
            else:
                tag.is_present = True
                tag.value = value
                tag.length = len(value)
                tag.is_valid = True

            twitter_tags[tw_key] = tag

        return twitter_tags

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
        score = 100.0

        # Title: 25 points
        if not title or not title.is_present:
            score -= 25
        elif not title.is_valid:
            score -= 15

        # Description: 25 points
        if not description or not description.is_present:
            score -= 25
        elif not description.is_valid:
            score -= 15

        # Canonical: 10 points
        if not canonical or not canonical.is_present:
            score -= 10

        # OG tags: 20 points
        og_present = sum(1 for t in og_tags.values() if t.is_present)
        og_score = (og_present / max(1, len(og_tags))) * 20
        score -= (20 - og_score)

        # Twitter cards: 10 points
        tw_present = sum(1 for t in twitter_tags.values() if t.is_present)
        tw_score = (tw_present / max(1, len(twitter_tags))) * 10
        score -= (10 - tw_score)

        # Each missing required tag: -5 points
        score -= len(missing_required) * 5

        return max(0, min(100, score))
