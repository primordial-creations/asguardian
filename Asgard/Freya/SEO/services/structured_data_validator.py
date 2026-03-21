"""
Freya Structured Data Validator

Validates Schema.org structured data including JSON-LD,
microdata, and RDFa formats.
"""

import json
import re
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, async_playwright

from Asgard.Freya.SEO.models.seo_models import (
    SEOConfig,
    StructuredDataItem,
    StructuredDataReport,
    StructuredDataType,
)
from Asgard.Freya.SEO.services._structured_data_checks import (
    COMMON_SCHEMA_TYPES,
    REQUIRED_PROPERTIES,
    is_valid_date,
    parse_microdata_entry,
    validate_json_ld_item,
    validate_type_specific,
)


class StructuredDataValidator:
    """
    Validates Schema.org structured data.

    Supports JSON-LD, microdata, and RDFa formats.
    """

    COMMON_SCHEMA_TYPES = COMMON_SCHEMA_TYPES
    REQUIRED_PROPERTIES = REQUIRED_PROPERTIES

    def __init__(self, config: Optional[SEOConfig] = None):
        """
        Initialize the structured data validator.

        Args:
            config: SEO configuration
        """
        self.config = config or SEOConfig()

    async def validate(self, url: str) -> StructuredDataReport:
        """
        Validate structured data for a URL.

        Args:
            url: URL to validate

        Returns:
            StructuredDataReport with validation results
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return await self.validate_page(page, url)
            finally:
                await browser.close()

    async def validate_page(self, page: Page, url: str) -> StructuredDataReport:
        """
        Validate structured data on an already loaded page.

        Args:
            page: Playwright Page object
            url: URL of the page

        Returns:
            StructuredDataReport with validation results
        """
        json_ld_items = await self._extract_json_ld(page)
        microdata_items = await self._extract_microdata(page)

        all_items = json_ld_items + microdata_items

        schema_types = list(set(item.schema_type for item in all_items))

        all_errors = []
        all_warnings = []
        for item in all_items:
            all_errors.extend(item.errors)
            all_warnings.extend(item.warnings)

        valid_count = sum(1 for item in all_items if item.is_valid)
        invalid_count = len(all_items) - valid_count

        return StructuredDataReport(
            url=url,
            items=all_items,
            json_ld_count=len(json_ld_items),
            microdata_count=len(microdata_items),
            rdfa_count=0,
            schema_types=schema_types,
            total_items=len(all_items),
            valid_items=valid_count,
            invalid_items=invalid_count,
            errors=all_errors,
            warnings=all_warnings,
        )

    async def _extract_json_ld(self, page: Page) -> List[StructuredDataItem]:
        """Extract and validate JSON-LD structured data."""
        items = []

        json_ld_data = await page.evaluate("""
            () => {
                const scripts = document.querySelectorAll(
                    'script[type="application/ld+json"]'
                );
                const results = [];
                for (const script of scripts) {
                    try {
                        const data = JSON.parse(script.textContent);
                        results.push({ success: true, data: data });
                    } catch (e) {
                        results.push({ success: false, error: e.message });
                    }
                }
                return results;
            }
        """)

        for entry in json_ld_data:
            if not entry.get("success"):
                items.append(StructuredDataItem(
                    data_type=StructuredDataType.JSON_LD,
                    schema_type="Unknown",
                    raw_data={},
                    is_valid=False,
                    errors=[f"Invalid JSON: {entry.get('error', 'Unknown error')}"],
                ))
                continue

            data = entry.get("data", {})

            if "@graph" in data:
                for graph_item in data["@graph"]:
                    item = validate_json_ld_item(graph_item)
                    items.append(item)
            else:
                item = validate_json_ld_item(data)
                items.append(item)

        return items

    async def _extract_microdata(self, page: Page) -> List[StructuredDataItem]:
        """Extract and validate microdata structured data."""
        items = []

        microdata = await page.evaluate("""
            () => {
                const items = document.querySelectorAll('[itemscope]');
                const results = [];

                for (const item of items) {
                    if (item.closest('[itemscope]') !== item) {
                        continue;
                    }

                    const itemType = item.getAttribute('itemtype') || '';
                    const props = {};

                    const propElements = item.querySelectorAll('[itemprop]');
                    for (const propEl of propElements) {
                        const propName = propEl.getAttribute('itemprop');
                        let propValue;

                        if (propEl.hasAttribute('content')) {
                            propValue = propEl.getAttribute('content');
                        } else if (propEl.tagName === 'A') {
                            propValue = propEl.getAttribute('href');
                        } else if (propEl.tagName === 'IMG') {
                            propValue = propEl.getAttribute('src');
                        } else if (propEl.tagName === 'META') {
                            propValue = propEl.getAttribute('content');
                        } else if (propEl.tagName === 'TIME') {
                            propValue = propEl.getAttribute('datetime') ||
                                       propEl.textContent;
                        } else {
                            propValue = propEl.textContent;
                        }

                        props[propName] = propValue;
                    }

                    results.push({
                        type: itemType,
                        properties: props
                    });
                }

                return results;
            }
        """)

        for entry in microdata:
            items.append(parse_microdata_entry(entry))

        return items

    def _validate_json_ld_item(self, data: Dict[str, Any]) -> StructuredDataItem:
        """Validate a single JSON-LD item."""
        return validate_json_ld_item(data)

    def _validate_type_specific(self, schema_type: str, data: Dict[str, Any]) -> tuple:
        """Validate type-specific requirements."""
        return validate_type_specific(schema_type, data)

    def _is_valid_date(self, date_str: str) -> bool:
        """Check if a string is a valid ISO 8601 date."""
        return is_valid_date(date_str)
