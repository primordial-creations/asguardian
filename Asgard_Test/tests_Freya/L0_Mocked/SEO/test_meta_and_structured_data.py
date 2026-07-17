"""L0 tests: SEO meta-tag analyzers and structured-data (JSON-LD) checks."""

import pytest

from Asgard.Freya.SEO.models.seo_models import MetaTagType, SEOConfig, StructuredDataType
from Asgard.Freya.SEO.services._meta_tag_analyzers import analyze_description, analyze_title
from Asgard.Freya.SEO.services._structured_data_checks import (
    validate_json_ld_item,
    validate_type_specific,
)


class TestAnalyzeTitle:
    def test_missing_title(self):
        tag = analyze_title(None, SEOConfig())
        assert tag.is_present is False
        assert tag.is_valid is False
        assert "missing" in tag.issues[0].lower()

    def test_too_short_title(self):
        tag = analyze_title("Short", SEOConfig(min_title_length=30))
        assert tag.is_present is True
        assert tag.is_valid is False
        assert "too short" in tag.issues[0]

    def test_too_long_title_flagged_but_not_invalid(self):
        tag = analyze_title("x" * 100, SEOConfig(max_title_length=60))
        assert "truncated" in tag.issues[0]

    def test_valid_title_length(self):
        tag = analyze_title("A perfectly reasonable title for this page", SEOConfig())
        assert tag.is_valid is True
        assert tag.tag_type == MetaTagType.TITLE


class TestAnalyzeDescription:
    def test_missing_description(self):
        tag = analyze_description(None, SEOConfig())
        assert tag.is_present is False
        assert "missing" in tag.issues[0].lower()

    def test_valid_description(self):
        text = "A" * 100
        tag = analyze_description(text, SEOConfig(min_description_length=50, max_description_length=160))
        assert tag.is_present is True
        assert tag.length == 100


class TestValidateJsonLdItem:
    def test_valid_article(self):
        data = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Title",
            "author": "Jane",
            "datePublished": "2024-01-01T00:00:00Z",
            "image": "https://example.com/img.png",
        }
        item = validate_json_ld_item(data)
        assert item.is_valid is True
        assert item.schema_type == "Article"
        assert item.data_type == StructuredDataType.JSON_LD
        assert item.errors == []

    def test_missing_context_is_error(self):
        data = {"@type": "Article"}
        item = validate_json_ld_item(data)
        assert item.is_valid is False
        assert any("@context" in e for e in item.errors)

    def test_non_schema_org_context_is_warning(self):
        data = {"@context": "https://example.com/other", "@type": "Article"}
        item = validate_json_ld_item(data)
        assert any("schema.org" in w for w in item.warnings)

    def test_missing_type_is_error(self):
        data = {"@context": "https://schema.org"}
        item = validate_json_ld_item(data)
        assert any("@type" in e for e in item.errors)

    def test_missing_recommended_property_warns(self):
        data = {"@context": "https://schema.org", "@type": "Organization"}
        item = validate_json_ld_item(data)
        assert any("name" in w for w in item.warnings)

    def test_list_type_uses_first_entry(self):
        data = {"@context": "https://schema.org", "@type": ["Article", "NewsArticle"]}
        item = validate_json_ld_item(data)
        assert item.schema_type == "Article"

    def test_unknown_type_no_required_properties(self):
        data = {"@context": "https://schema.org", "@type": "SomeCustomType"}
        item = validate_json_ld_item(data)
        assert item.is_valid is True


class TestValidateTypeSpecific:
    def test_article_invalid_date_published(self):
        errors, warnings = validate_type_specific("Article", {"datePublished": "not-a-date"})
        assert any("datePublished" in e for e in errors)

    def test_article_missing_image_warns(self):
        errors, warnings = validate_type_specific("Article", {"datePublished": "2024-01-01T00:00:00Z"})
        assert any("image" in w for w in warnings)

    def test_product_missing_offers_and_reviews_warns(self):
        errors, warnings = validate_type_specific("Product", {})
        assert any("offers" in w for w in warnings)
        assert any("reviews" in w or "ratings" in w for w in warnings)

    def test_local_business_missing_contact_warns(self):
        errors, warnings = validate_type_specific("LocalBusiness", {})
        assert any("contact" in w for w in warnings)

    def test_unrecognized_type_no_errors(self):
        errors, warnings = validate_type_specific("Unknown", {})
        assert errors == []
        assert warnings == []
