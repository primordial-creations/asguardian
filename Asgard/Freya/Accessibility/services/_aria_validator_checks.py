"""
Freya ARIA Validator check functions and constants.

Constants and check functions extracted from aria_validator.py.
"""

from typing import Dict, List, Optional, Set, cast

from playwright.async_api import Page

from Asgard.Freya.Accessibility.models.accessibility_models import (
    ARIAViolation,
    ARIAViolationType,
    ViolationSeverity,
)


VALID_ROLES: Set[str] = {
    "alert", "alertdialog", "application", "article", "banner", "button",
    "cell", "checkbox", "columnheader", "combobox", "complementary",
    "contentinfo", "definition", "dialog", "directory", "document", "feed",
    "figure", "form", "grid", "gridcell", "group", "heading", "img",
    "link", "list", "listbox", "listitem", "log", "main", "marquee",
    "math", "menu", "menubar", "menuitem", "menuitemcheckbox",
    "menuitemradio", "meter", "navigation", "none", "note", "option",
    "presentation", "progressbar", "radio", "radiogroup", "region",
    "row", "rowgroup", "rowheader", "scrollbar", "search", "searchbox",
    "separator", "slider", "spinbutton", "status", "switch", "tab",
    "table", "tablist", "tabpanel", "term", "textbox", "timer",
    "toolbar", "tooltip", "tree", "treegrid", "treeitem",
}

REQUIRED_PARENT_ROLES: Dict[str, List[str]] = {
    "option": ["listbox", "combobox", "menu", "menubar", "radiogroup", "group"],
    "listitem": ["list", "group"],
    "menuitem": ["menu", "menubar", "group"],
    "menuitemcheckbox": ["menu", "menubar", "group"],
    "menuitemradio": ["menu", "menubar", "group"],
    "tab": ["tablist"],
    "tabpanel": ["tablist"],
    "row": ["table", "treegrid", "grid", "rowgroup"],
    "rowgroup": ["table", "grid", "treegrid"],
    "cell": ["row"],
    "gridcell": ["row"],
    "columnheader": ["row"],
    "rowheader": ["row"],
    "treeitem": ["tree", "group", "treeitem"],
}

REQUIRED_ATTRIBUTES: Dict[str, List[str]] = {
    "checkbox": ["aria-checked"],
    "combobox": ["aria-expanded"],
    "heading": ["aria-level"],
    "meter": ["aria-valuenow"],
    "option": [],
    "radio": ["aria-checked"],
    "scrollbar": ["aria-controls", "aria-valuenow", "aria-valuemin", "aria-valuemax"],
    "slider": ["aria-valuenow", "aria-valuemin", "aria-valuemax"],
    "spinbutton": ["aria-valuenow", "aria-valuemin", "aria-valuemax"],
    "switch": ["aria-checked"],
    "tab": ["aria-selected"],
    "tabpanel": ["aria-labelledby"],
    "textbox": [],
    "treeitem": [],
}

VALID_ARIA_ATTRIBUTES: Set[str] = {
    "aria-activedescendant", "aria-atomic", "aria-autocomplete", "aria-busy",
    "aria-checked", "aria-colcount", "aria-colindex", "aria-colspan",
    "aria-controls", "aria-current", "aria-describedby", "aria-description",
    "aria-details", "aria-disabled", "aria-dropeffect", "aria-errormessage",
    "aria-expanded", "aria-flowto", "aria-grabbed", "aria-haspopup",
    "aria-hidden", "aria-invalid", "aria-keyshortcuts", "aria-label",
    "aria-labelledby", "aria-level", "aria-live", "aria-modal", "aria-multiline",
    "aria-multiselectable", "aria-orientation", "aria-owns", "aria-placeholder",
    "aria-posinset", "aria-pressed", "aria-readonly", "aria-relevant",
    "aria-required", "aria-roledescription", "aria-rowcount", "aria-rowindex",
    "aria-rowspan", "aria-selected", "aria-setsize", "aria-sort",
    "aria-valuemax", "aria-valuemin", "aria-valuenow", "aria-valuetext",
}


async def validate_roles(page: Page) -> tuple[List[ARIAViolation], Dict[str, int]]:
    """Validate ARIA roles."""
    violations = []
    roles_count: Dict[str, int] = {}

    try:
        elements = await page.query_selector_all("[role]")

        for elem in elements:
            role = await elem.get_attribute("role")
            if not role:
                continue

            roles = [r.strip().lower() for r in role.split()]

            for r in roles:
                roles_count[r] = roles_count.get(r, 0) + 1

                if r not in VALID_ROLES:
                    selector = await get_selector(page, elem)
                    element_html = await get_element_html(elem)
                    violations.append(ARIAViolation(
                        violation_type=ARIAViolationType.UNSUPPORTED_ROLE,
                        element_selector=selector,
                        element_html=element_html,
                        description=f'Invalid ARIA role: "{r}"',
                        severity=ViolationSeverity.SERIOUS,
                        wcag_reference="4.1.2",
                        suggested_fix="Use a valid ARIA role from the WAI-ARIA specification",
                        role=r,
                    ))

    except Exception:
        pass

    return violations, roles_count


async def validate_aria_attributes(page: Page) -> tuple[List[ARIAViolation], Dict[str, int]]:
    """Validate ARIA attributes."""
    violations = []
    attrs_count: Dict[str, int] = {}

    try:
        elements = await page.evaluate("""
            () => {
                const results = [];
                const allElements = document.querySelectorAll('*');

                for (const elem of allElements) {
                    const ariaAttrs = {};
                    for (const attr of elem.attributes) {
                        if (attr.name.startsWith('aria-')) {
                            ariaAttrs[attr.name] = attr.value;
                        }
                    }
                    if (Object.keys(ariaAttrs).length > 0) {
                        results.push({
                            tag: elem.tagName.toLowerCase(),
                            id: elem.id,
                            className: elem.className,
                            attrs: ariaAttrs,
                        });
                    }
                }
                return results;
            }
        """)

        for elem_data in elements:
            for attr_name, attr_value in elem_data["attrs"].items():
                attrs_count[attr_name] = attrs_count.get(attr_name, 0) + 1

                if attr_name not in VALID_ARIA_ATTRIBUTES:
                    selector = build_selector(elem_data)
                    violations.append(ARIAViolation(
                        violation_type=ARIAViolationType.INVALID_ATTRIBUTE_VALUE,
                        element_selector=selector,
                        description=f'Invalid ARIA attribute: "{attr_name}"',
                        severity=ViolationSeverity.MODERATE,
                        wcag_reference="4.1.2",
                        suggested_fix="Use a valid ARIA attribute from the WAI-ARIA specification",
                        aria_attribute=attr_name,
                    ))

                if attr_name in ["aria-checked", "aria-pressed", "aria-expanded", "aria-selected"]:
                    if attr_value not in ["true", "false", "mixed"]:
                        selector = build_selector(elem_data)
                        violations.append(ARIAViolation(
                            violation_type=ARIAViolationType.INVALID_ATTRIBUTE_VALUE,
                            element_selector=selector,
                            description=f'{attr_name} has invalid value: "{attr_value}"',
                            severity=ViolationSeverity.SERIOUS,
                            wcag_reference="4.1.2",
                            suggested_fix=f'Use "true", "false", or "mixed" for {attr_name}',
                            aria_attribute=attr_name,
                        ))

    except Exception:
        pass

    return violations, attrs_count


async def validate_parent_roles(page: Page) -> List[ARIAViolation]:
    """Validate that roles have required parent roles."""
    violations = []

    for child_role, parent_roles in REQUIRED_PARENT_ROLES.items():
        try:
            elements = await page.query_selector_all(f'[role="{child_role}"]')

            for elem in elements:
                has_parent = await page.evaluate(f"""
                    (element) => {{
                        const parentRoles = {parent_roles!r};
                        let current = element.parentElement;
                        while (current) {{
                            const role = current.getAttribute('role');
                            if (role && parentRoles.includes(role.toLowerCase())) {{
                                return true;
                            }}
                            current = current.parentElement;
                        }}
                        return false;
                    }}
                """, elem)

                if not has_parent:
                    selector = await get_selector(page, elem)
                    violations.append(ARIAViolation(
                        violation_type=ARIAViolationType.MISSING_PARENT_ROLE,
                        element_selector=selector,
                        description=f'Role "{child_role}" requires a parent with role: {", ".join(parent_roles)}',
                        severity=ViolationSeverity.SERIOUS,
                        wcag_reference="4.1.2",
                        suggested_fix=f"Wrap this element in a parent with one of these roles: {', '.join(parent_roles)}",
                        role=child_role,
                    ))

        except Exception:
            continue

    return violations


async def validate_required_attributes(page: Page) -> List[ARIAViolation]:
    """Validate that roles have required attributes."""
    violations = []

    for role, required_attrs in REQUIRED_ATTRIBUTES.items():
        if not required_attrs:
            continue

        try:
            elements = await page.query_selector_all(f'[role="{role}"]')

            for elem in elements:
                for attr in required_attrs:
                    attr_value = await elem.get_attribute(attr)

                    if attr_value is None:
                        selector = await get_selector(page, elem)
                        violations.append(ARIAViolation(
                            violation_type=ARIAViolationType.MISSING_REQUIRED_ATTRIBUTE,
                            element_selector=selector,
                            description=f'Role "{role}" requires {attr} attribute',
                            severity=ViolationSeverity.SERIOUS,
                            wcag_reference="4.1.2",
                            suggested_fix=f"Add the {attr} attribute to this element",
                            role=role,
                            aria_attribute=attr,
                        ))

        except Exception:
            continue

    return violations


async def validate_hidden_focusable(page: Page) -> List[ARIAViolation]:
    """Validate that aria-hidden elements don't contain focusable content."""
    violations = []

    try:
        hidden_elements = await page.query_selector_all('[aria-hidden="true"]')

        for elem in hidden_elements:
            focusable = await elem.query_selector(
                'a[href], button:not([disabled]), input:not([disabled]), '
                'select:not([disabled]), textarea:not([disabled]), '
                '[tabindex]:not([tabindex="-1"])'
            )

            if focusable:
                selector = await get_selector(page, elem)
                violations.append(ARIAViolation(
                    violation_type=ARIAViolationType.HIDDEN_FOCUSABLE,
                    element_selector=selector,
                    description="Element with aria-hidden='true' contains focusable content",
                    severity=ViolationSeverity.CRITICAL,
                    wcag_reference="4.1.2",
                    suggested_fix="Either remove aria-hidden or add tabindex='-1' to focusable children",
                    aria_attribute="aria-hidden",
                ))

    except Exception:
        pass

    return violations


async def validate_aria_ids(page: Page) -> List[ARIAViolation]:
    """Validate that aria-labelledby and aria-describedby reference existing IDs."""
    violations = []

    try:
        elements = await page.query_selector_all(
            "[aria-labelledby], [aria-describedby], [aria-controls], [aria-owns]"
        )

        for elem in elements:
            for attr in ["aria-labelledby", "aria-describedby", "aria-controls", "aria-owns"]:
                id_refs = await elem.get_attribute(attr)
                if not id_refs:
                    continue

                for id_ref in id_refs.split():
                    exists = await page.evaluate(f"""
                        () => document.getElementById("{id_ref}") !== null
                    """)

                    if not exists:
                        selector = await get_selector(page, elem)
                        violations.append(ARIAViolation(
                            violation_type=ARIAViolationType.INVALID_ATTRIBUTE_VALUE,
                            element_selector=selector,
                            description=f'{attr} references non-existent ID: "{id_ref}"',
                            severity=ViolationSeverity.SERIOUS,
                            wcag_reference="4.1.2",
                            suggested_fix=f'Ensure an element with id="{id_ref}" exists',
                            aria_attribute=attr,
                        ))

    except Exception:
        pass

    return violations


async def count_aria_elements(page: Page) -> int:
    """Count total elements with ARIA attributes or roles."""
    try:
        return cast(int, await page.evaluate("""
            () => document.querySelectorAll('[role], [aria-label], [aria-labelledby], [aria-describedby]').length
        """))
    except Exception:
        return 0


async def get_selector(page: Page, element) -> str:
    """Generate a selector for an element."""
    try:
        selector = await page.evaluate("""
            (element) => {
                if (element.id) return '#' + element.id;

                const tag = element.tagName.toLowerCase();
                const role = element.getAttribute('role');
                const classes = Array.from(element.classList).slice(0, 2).join('.');

                if (role) return `[role="${role}"]`;
                if (classes) return tag + '.' + classes;
                return tag;
            }
        """, element)
        return cast(str, selector)
    except Exception:
        return "unknown"


async def get_element_html(element) -> Optional[str]:
    """Get truncated outer HTML."""
    try:
        html = cast(str, await element.evaluate("el => el.outerHTML"))
        return html[:200] + "..." if len(html) > 200 else html
    except Exception:
        return None


def build_selector(elem_data: dict) -> str:
    """Build selector from element data."""
    if elem_data.get("id"):
        return f'#{elem_data["id"]}'
    tag = cast(str, elem_data.get("tag", "div"))
    class_name = elem_data.get("className", "")
    if class_name:
        classes = class_name.split()[:2]
        return f'{tag}.{".".join(classes)}'
    return tag
