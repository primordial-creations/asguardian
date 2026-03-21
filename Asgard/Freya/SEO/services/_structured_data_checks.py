"""
Freya Structured Data Validator check functions.

Check functions extracted from structured_data_validator.py.
"""

import re
from typing import Any, Dict, List, Set, Tuple

from Asgard.Freya.SEO.models.seo_models import (
    StructuredDataItem,
    StructuredDataType,
)


COMMON_SCHEMA_TYPES: Set[str] = {
    "Article",
    "NewsArticle",
    "BlogPosting",
    "Product",
    "Organization",
    "LocalBusiness",
    "Person",
    "Event",
    "Recipe",
    "Review",
    "FAQPage",
    "BreadcrumbList",
    "WebSite",
    "WebPage",
    "ItemList",
    "HowTo",
    "Course",
    "Book",
    "Movie",
    "VideoObject",
    "ImageObject",
}

REQUIRED_PROPERTIES: Dict[str, List[str]] = {
    "Article": ["headline", "author", "datePublished"],
    "Product": ["name", "description"],
    "Organization": ["name"],
    "LocalBusiness": ["name", "address"],
    "Person": ["name"],
    "Event": ["name", "startDate", "location"],
    "Recipe": ["name", "recipeIngredient", "recipeInstructions"],
    "Review": ["itemReviewed", "reviewRating"],
    "FAQPage": ["mainEntity"],
    "BreadcrumbList": ["itemListElement"],
    "WebSite": ["name", "url"],
}


def validate_json_ld_item(data: Dict[str, Any]) -> StructuredDataItem:
    """Validate a single JSON-LD item."""
    errors = []
    warnings = []

    schema_type = data.get("@type", "Unknown")
    if isinstance(schema_type, list):
        schema_type = schema_type[0] if schema_type else "Unknown"

    context = data.get("@context", "")
    if not context:
        errors.append("Missing @context")
    elif "schema.org" not in str(context):
        warnings.append("@context should reference schema.org")

    if "@type" not in data:
        errors.append("Missing @type")

    if schema_type in REQUIRED_PROPERTIES:
        required = REQUIRED_PROPERTIES[schema_type]
        for prop in required:
            if prop not in data or data[prop] is None or data[prop] == "":
                warnings.append(f"Missing recommended property: {prop}")

    type_errors, type_warnings = validate_type_specific(schema_type, data)
    errors.extend(type_errors)
    warnings.extend(type_warnings)

    is_valid = len(errors) == 0

    return StructuredDataItem(
        data_type=StructuredDataType.JSON_LD,
        schema_type=schema_type,
        raw_data=data,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
    )


def validate_type_specific(schema_type: str, data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Validate type-specific requirements."""
    errors = []
    warnings = []

    if schema_type == "Article" or schema_type == "NewsArticle":
        if "datePublished" in data:
            if not is_valid_date(data["datePublished"]):
                errors.append("datePublished is not in valid ISO 8601 format")

        if "dateModified" in data:
            if not is_valid_date(data["dateModified"]):
                warnings.append("dateModified is not in valid ISO 8601 format")

        if "image" not in data:
            warnings.append("Article should have an image")

    elif schema_type == "Product":
        if "offers" not in data:
            warnings.append("Product should have offers/pricing information")

        if "aggregateRating" not in data and "review" not in data:
            warnings.append("Product should have reviews or ratings")

    elif schema_type == "LocalBusiness":
        if "telephone" not in data and "email" not in data:
            warnings.append("LocalBusiness should have contact information")

        if "openingHoursSpecification" not in data and "openingHours" not in data:
            warnings.append("LocalBusiness should have opening hours")

    elif schema_type == "Event":
        if "endDate" not in data:
            warnings.append("Event should have an endDate")

        if "startDate" in data:
            if not is_valid_date(data["startDate"]):
                errors.append("startDate is not in valid ISO 8601 format")

    elif schema_type == "FAQPage":
        main_entity = data.get("mainEntity", [])
        if not main_entity:
            errors.append("FAQPage must have mainEntity with questions")
        elif isinstance(main_entity, list):
            for qa in main_entity:
                if "@type" not in qa or qa["@type"] != "Question":
                    warnings.append("FAQPage mainEntity should be Question type")
                if "acceptedAnswer" not in qa:
                    errors.append("Question must have acceptedAnswer")

    elif schema_type == "BreadcrumbList":
        items = data.get("itemListElement", [])
        if not items:
            errors.append("BreadcrumbList must have itemListElement")
        else:
            for i, item in enumerate(items):
                if "position" not in item:
                    warnings.append(f"Breadcrumb item {i+1} missing position")
                if "item" not in item and "name" not in item:
                    errors.append(f"Breadcrumb item {i+1} missing item or name")

    return errors, warnings


def is_valid_date(date_str: str) -> bool:
    """Check if a string is a valid ISO 8601 date."""
    if not isinstance(date_str, str):
        return False

    patterns = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
    ]

    for pattern in patterns:
        if re.match(pattern, date_str):
            return True

    return False


def parse_microdata_entry(entry: Dict[str, Any]) -> StructuredDataItem:
    """Parse and validate a single microdata entry."""
    item_type = entry.get("type", "")
    properties = entry.get("properties", {})

    schema_type = "Unknown"
    if item_type:
        match = re.search(r"schema\.org/(\w+)", item_type)
        if match:
            schema_type = match.group(1)

    errors = []
    warnings = []

    if not item_type:
        errors.append("Missing itemtype attribute")
    elif "schema.org" not in item_type:
        warnings.append("itemtype should reference schema.org")

    is_valid = len(errors) == 0

    return StructuredDataItem(
        data_type=StructuredDataType.MICRODATA,
        schema_type=schema_type,
        raw_data={"@type": schema_type, **properties},
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
    )
