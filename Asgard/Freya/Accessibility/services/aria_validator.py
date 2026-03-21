"""
Freya ARIA Validator

Validates ARIA implementation including roles, states,
properties, and their correct usage.
"""

from datetime import datetime
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, Page

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityConfig,
    ARIAReport,
    ARIAViolation,
    ARIAViolationType,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.services._aria_validator_checks import (
    VALID_ROLES,
    REQUIRED_PARENT_ROLES,
    REQUIRED_ATTRIBUTES,
    VALID_ARIA_ATTRIBUTES,
    validate_roles,
    validate_aria_attributes,
    validate_parent_roles,
    validate_required_attributes,
    validate_hidden_focusable,
    validate_aria_ids,
    count_aria_elements,
    get_selector,
    get_element_html,
    build_selector,
)


class ARIAValidator:
    """
    ARIA implementation validator.

    Validates ARIA roles, states, and properties
    for correct implementation.
    """

    def __init__(self, config: AccessibilityConfig):
        """
        Initialize the ARIA Validator.

        Args:
            config: Accessibility configuration
        """
        self.config = config

    async def validate(self, url: str) -> ARIAReport:
        """
        Validate ARIA implementation on a page.

        Args:
            url: URL to validate

        Returns:
            ARIAReport with all findings
        """
        violations = []
        roles_found: Dict[str, int] = {}
        aria_attributes_used: Dict[str, int] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)

                role_violations, roles = await validate_roles(page)
                violations.extend(role_violations)
                roles_found = roles

                attr_violations, attrs = await validate_aria_attributes(page)
                violations.extend(attr_violations)
                aria_attributes_used = attrs

                parent_violations = await validate_parent_roles(page)
                violations.extend(parent_violations)

                req_violations = await validate_required_attributes(page)
                violations.extend(req_violations)

                hidden_violations = await validate_hidden_focusable(page)
                violations.extend(hidden_violations)

                id_violations = await validate_aria_ids(page)
                violations.extend(id_violations)

            finally:
                await browser.close()

        total_aria = await self._count_aria_elements(page) if not browser.is_connected() else sum(roles_found.values())
        valid_count = total_aria - len(violations)

        return ARIAReport(
            url=url,
            tested_at=datetime.now().isoformat(),
            total_aria_elements=total_aria,
            valid_count=max(0, valid_count),
            invalid_count=len(violations),
            violations=violations,
            roles_found=roles_found,
            aria_attributes_used=aria_attributes_used,
        )

    async def _validate_roles(self, page: Page) -> tuple[List[ARIAViolation], Dict[str, int]]:
        """Validate ARIA roles."""
        return await validate_roles(page)

    async def _validate_aria_attributes(self, page: Page) -> tuple[List[ARIAViolation], Dict[str, int]]:
        """Validate ARIA attributes."""
        return await validate_aria_attributes(page)

    async def _validate_parent_roles(self, page: Page) -> List[ARIAViolation]:
        """Validate that roles have required parent roles."""
        return await validate_parent_roles(page)

    async def _validate_required_attributes(self, page: Page) -> List[ARIAViolation]:
        """Validate that roles have required attributes."""
        return await validate_required_attributes(page)

    async def _validate_hidden_focusable(self, page: Page) -> List[ARIAViolation]:
        """Validate that aria-hidden elements don't contain focusable content."""
        return await validate_hidden_focusable(page)

    async def _validate_aria_ids(self, page: Page) -> List[ARIAViolation]:
        """Validate that aria-labelledby and aria-describedby reference existing IDs."""
        return await validate_aria_ids(page)

    async def _count_aria_elements(self, page: Page) -> int:
        """Count total elements with ARIA attributes or roles."""
        return await count_aria_elements(page)

    async def _get_selector(self, page: Page, element) -> str:
        """Generate a selector for an element."""
        return await get_selector(page, element)

    async def _get_element_html(self, element) -> Optional[str]:
        """Get truncated outer HTML."""
        return await get_element_html(element)

    def _build_selector(self, elem_data: dict) -> str:
        """Build selector from element data."""
        return build_selector(elem_data)
