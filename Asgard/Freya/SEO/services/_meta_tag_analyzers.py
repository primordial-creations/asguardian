"""
Freya Meta Tag Analyzer helper functions.

Helper functions extracted from meta_tag_analyzer.py.
"""

from typing import Dict, List, Optional

from Asgard.Freya.SEO.models.seo_models import (
    MetaTag,
    MetaTagType,
    SEOConfig,
)


def analyze_title(value: Optional[str], config: SEOConfig) -> MetaTag:
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

    if len(value) < config.min_title_length:
        tag.is_valid = False
        tag.issues.append(
            f"Title is too short ({len(value)} chars, "
            f"minimum {config.min_title_length})"
        )
        tag.suggestions.append("Make the title more descriptive")
    elif len(value) > config.max_title_length:
        tag.issues.append(
            f"Title may be truncated in search results ({len(value)} chars, "
            f"maximum {config.max_title_length})"
        )
        tag.suggestions.append("Shorten the title for better display")
    else:
        tag.is_valid = True

    return tag


def analyze_description(value: Optional[str], config: SEOConfig) -> MetaTag:
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

    if len(value) < config.min_description_length:
        tag.is_valid = False
        tag.issues.append(
            f"Description is too short ({len(value)} chars, "
            f"minimum {config.min_description_length})"
        )
        tag.suggestions.append("Expand the description to be more informative")
    elif len(value) > config.max_description_length:
        tag.issues.append(
            f"Description may be truncated ({len(value)} chars, "
            f"maximum {config.max_description_length})"
        )
        tag.suggestions.append("Shorten the description for better display")
    else:
        tag.is_valid = True

    return tag


def analyze_keywords(value: Optional[str]) -> MetaTag:
    """Analyze the meta keywords tag."""
    tag = MetaTag(tag_type=MetaTagType.KEYWORDS)

    if value is None:
        tag.is_present = False
        return tag

    tag.is_present = True
    tag.value = value
    tag.length = len(value)
    tag.is_valid = True

    tag.suggestions.append(
        "Meta keywords are generally ignored by search engines; "
        "focus on content instead"
    )

    return tag


def analyze_canonical(value: Optional[str], page_url: str) -> MetaTag:
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

    if not value.startswith("http"):
        tag.is_valid = False
        tag.issues.append("Canonical URL should be an absolute URL")
    else:
        tag.is_valid = True

    return tag


def analyze_robots(value: Optional[str]) -> MetaTag:
    """Analyze the robots meta tag."""
    tag = MetaTag(tag_type=MetaTagType.ROBOTS)

    if value is None:
        tag.is_present = False
        return tag

    tag.is_present = True
    tag.value = value
    tag.length = len(value)
    tag.is_valid = True

    value_lower = value.lower()
    if "noindex" in value_lower:
        tag.issues.append("Page has noindex directive - will not be indexed")
    if "nofollow" in value_lower:
        tag.issues.append("Page has nofollow directive - links will not be followed")

    return tag


def analyze_viewport(value: Optional[str]) -> MetaTag:
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

    if "width=device-width" not in value.lower():
        tag.issues.append("Viewport should include width=device-width")

    return tag


def analyze_og_tags(og_data: Dict[str, str], config: SEOConfig) -> Dict[str, MetaTag]:
    """Analyze Open Graph tags."""
    og_tags = {}

    required_og = ["og:title", "og:description", "og:image", "og:url", "og:type"]

    for og_key in required_og:
        tag = MetaTag(tag_type=MetaTagType(og_key.replace("og:", "og_")))
        value = og_data.get(og_key)

        if value is None:
            tag.is_present = False
            if config.require_og_tags:
                tag.issues.append(f"{og_key} is missing")
        else:
            tag.is_present = True
            tag.value = value
            tag.length = len(value)
            tag.is_valid = True

        og_tags[og_key] = tag

    return og_tags


def analyze_twitter_tags(twitter_data: Dict[str, str], config: SEOConfig) -> Dict[str, MetaTag]:
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
            if config.require_twitter_cards and tw_key == "twitter:card":
                tag.issues.append(f"{tw_key} is missing")
        else:
            tag.is_present = True
            tag.value = value
            tag.length = len(value)
            tag.is_valid = True

        twitter_tags[tw_key] = tag

    return twitter_tags


def calculate_score(
    title: Optional[MetaTag],
    description: Optional[MetaTag],
    canonical: Optional[MetaTag],
    og_tags: Dict[str, MetaTag],
    twitter_tags: Dict[str, MetaTag],
    missing_required: List[str],
) -> float:
    """Calculate the SEO score for meta tags."""
    score = 100.0

    if not title or not title.is_present:
        score -= 25
    elif not title.is_valid:
        score -= 15

    if not description or not description.is_present:
        score -= 25
    elif not description.is_valid:
        score -= 15

    if not canonical or not canonical.is_present:
        score -= 10

    og_present = sum(1 for t in og_tags.values() if t.is_present)
    og_score = (og_present / max(1, len(og_tags))) * 20
    score -= (20 - og_score)

    tw_present = sum(1 for t in twitter_tags.values() if t.is_present)
    tw_score = (tw_present / max(1, len(twitter_tags))) * 10
    score -= (10 - tw_score)

    score -= len(missing_required) * 5

    return max(0, min(100, score))
