"""
Freya ARIA Automatability Tiers

DEEPTHINK_05: ARIA misuse spans an automatability spectrum, so a binary
pass/fail vocabulary is dishonest. Deterministic checks stay PASS/FAIL;
context-dependent patterns become heuristic WARNINGs; fundamentally
unautomatable claims (live-region salience, composite widget behavior)
get a third verdict - NEEDS_REVIEW - plus a manual test directive.

Detection functions are pure (element metadata dicts in, violations out)
so they are testable without Playwright; collect_aria_tier_elements()
gathers the metadata from a live page in one evaluate call.
"""

from typing import Any, Dict, List

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    ARIAViolationType,
    AutomatabilityTier,
    CheckVerdict,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.models._accessibility_report_models import ARIAViolation

#: HTML-AAM implicit roles: elements whose explicit role attribute is redundant.
IMPLICIT_ROLES: Dict[str, str] = {
    "a": "link",              # when href present (checked via has_href)
    "article": "article",
    "aside": "complementary",
    "body": "document",
    "button": "button",
    "datalist": "listbox",
    "details": "group",
    "dialog": "dialog",
    "fieldset": "group",
    "figure": "figure",
    "footer": "contentinfo",
    "form": "form",
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "h5": "heading",
    "h6": "heading",
    "header": "banner",
    "hr": "separator",
    "img": "img",
    "li": "listitem",
    "main": "main",
    "math": "math",
    "menu": "list",
    "nav": "navigation",
    "ol": "list",
    "option": "option",
    "output": "status",
    "progress": "progressbar",
    "section": "region",
    "select": "combobox",
    "summary": "button",
    "table": "table",
    "tbody": "rowgroup",
    "textarea": "textbox",
    "tfoot": "rowgroup",
    "thead": "rowgroup",
    "tr": "row",
    "ul": "list",
}

#: Composite widget roles automation cannot verify behaviorally.
COMPOSITE_WIDGET_ROLES = {
    "combobox", "listbox", "tablist", "tree", "treegrid", "grid", "menu", "menubar",
}

#: Roles commonly faked on non-native elements.
INTERACTIVE_ROLES_ON_NON_NATIVE = {
    "button", "link", "checkbox", "radio", "switch", "tab", "menuitem",
    "option", "slider", "spinbutton", "textbox",
}

_NATIVE_EQUIVALENT = {
    "button": "<button>",
    "link": '<a href="...">',
    "checkbox": '<input type="checkbox">',
    "radio": '<input type="radio">',
    "switch": '<input type="checkbox">',
    "textbox": "<input> or <textarea>",
    "slider": '<input type="range">',
    "spinbutton": '<input type="number">',
    "option": "<option>",
    "tab": "<button> inside a tablist",
    "menuitem": "<button>",
}

#: Manual QA directives per unautomatable pattern.
MANUAL_TEST_DIRECTIVES: Dict[str, str] = {
    "aria-live": (
        "Manual QA: with a screen reader (e.g. NVDA) running, trigger the "
        "update and verify the announcement is salient - neither silent nor "
        "disruptively verbose."
    ),
    "combobox": (
        "Found role=combobox. Manual QA: with NVDA running, verify focus "
        "containment and Up/Down arrow navigation of options."
    ),
    "listbox": (
        "Found role=listbox. Manual QA: verify arrow-key option navigation, "
        "selection announcement, and type-ahead behavior with a screen reader."
    ),
    "tablist": (
        "Found role=tablist. Manual QA: verify Left/Right arrow moves between "
        "tabs, the active tab is announced, and focus lands in the panel."
    ),
    "tree": (
        "Found role=tree. Manual QA: verify arrow-key expand/collapse and "
        "level announcements with a screen reader."
    ),
    "treegrid": (
        "Found role=treegrid. Manual QA: verify row/cell arrow navigation and "
        "expand/collapse announcements with a screen reader."
    ),
    "grid": (
        "Found role=grid. Manual QA: verify 2D arrow-key cell navigation and "
        "header announcements with a screen reader."
    ),
    "menu": (
        "Found role=menu. Manual QA: verify arrow-key item navigation, Escape "
        "to close, and focus return to the trigger."
    ),
    "menubar": (
        "Found role=menubar. Manual QA: verify horizontal arrow navigation and "
        "submenu open/close behavior with a screen reader."
    ),
}

#: ARIA density above which a page smells of over-engineered accessibility.
ARIA_DENSITY_THRESHOLD = 0.6
ARIA_DENSITY_MIN_ELEMENTS = 50

#: Automatability tier per ARIA violation type (existing + new checks).
CHECK_TIERS: Dict[ARIAViolationType, AutomatabilityTier] = {
    ARIAViolationType.MISSING_REQUIRED_ATTRIBUTE: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.INVALID_ATTRIBUTE_VALUE: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.UNSUPPORTED_ROLE: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.CONFLICTING_ROLES: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.MISSING_ACCESSIBLE_NAME: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.HIDDEN_FOCUSABLE: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.IMPROPER_ROLE_USAGE: AutomatabilityTier.PARTIALLY_AUTOMATABLE,
    ARIAViolationType.MISSING_PARENT_ROLE: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.DUPLICATE_ID: AutomatabilityTier.FULLY_AUTOMATABLE,
    ARIAViolationType.REDUNDANT_ROLE: AutomatabilityTier.PARTIALLY_AUTOMATABLE,
    ARIAViolationType.NON_NATIVE_INTERACTIVE: AutomatabilityTier.PARTIALLY_AUTOMATABLE,
    ARIAViolationType.NEEDS_MANUAL_REVIEW: AutomatabilityTier.NEEDS_HUMAN,
    ARIAViolationType.ARIA_DENSITY: AutomatabilityTier.PARTIALLY_AUTOMATABLE,
}


def _selector_of(elem: Dict[str, Any]) -> str:
    if elem.get("id"):
        return f"#{elem['id']}"
    tag = elem.get("tag", "div")
    role = elem.get("role")
    return f'{tag}[role="{role}"]' if role else str(tag)


def detect_redundant_roles(elements: List[Dict[str, Any]]) -> List[ARIAViolation]:
    """
    Redundant explicit roles (e.g. <nav role="navigation">) - a code smell,
    not a failure. Heuristic WARNING.
    """
    violations = []
    for elem in elements:
        tag = str(elem.get("tag", "")).lower()
        role = str(elem.get("role", "") or "").lower()
        if not role or tag not in IMPLICIT_ROLES:
            continue
        if tag == "a" and not elem.get("has_href"):
            continue
        if IMPLICIT_ROLES[tag] == role:
            violations.append(ARIAViolation(
                violation_type=ARIAViolationType.REDUNDANT_ROLE,
                element_selector=_selector_of(elem),
                description=(
                    f'Redundant role: <{tag}> already has implicit role "{role}". '
                    "Code smell - redundant ARIA adds maintenance risk without benefit."
                ),
                severity=ViolationSeverity.MINOR,
                wcag_reference="4.1.2",
                suggested_fix=f'Remove the role="{role}" attribute; the native <{tag}> semantics suffice.',
                role=role,
                verdict=CheckVerdict.WARNING,
                automatability=AutomatabilityTier.PARTIALLY_AUTOMATABLE,
            ))
    return violations


def detect_non_native_interactive(elements: List[Dict[str, Any]]) -> List[ARIAViolation]:
    """
    Interactive roles on generic containers (<div role="button">) -
    syntactically valid, but behaviorally risky. Heuristic WARNING.
    """
    violations = []
    for elem in elements:
        tag = str(elem.get("tag", "")).lower()
        role = str(elem.get("role", "") or "").lower()
        if tag not in ("div", "span") or role not in INTERACTIVE_ROLES_ON_NON_NATIVE:
            continue
        native = _NATIVE_EQUIVALENT.get(role, "a native element")
        violations.append(ARIAViolation(
            violation_type=ARIAViolationType.NON_NATIVE_INTERACTIVE,
            element_selector=_selector_of(elem),
            description=(
                f'<{tag} role="{role}"> is syntactically valid, but requires custom '
                "keyboard handling and carries compatibility risk. "
                f"Prefer {native}."
            ),
            severity=ViolationSeverity.MODERATE,
            wcag_reference="4.1.2",
            suggested_fix=f"Replace with {native}, which provides keyboard and AT behavior natively.",
            role=role,
            verdict=CheckVerdict.WARNING,
            automatability=AutomatabilityTier.PARTIALLY_AUTOMATABLE,
        ))
    return violations


def detect_needs_review(elements: List[Dict[str, Any]]) -> List[ARIAViolation]:
    """
    Fundamentally unautomatable claims: live regions and composite widgets.
    Verdict NEEDS_REVIEW plus a manual test directive - never PASS or FAIL.
    """
    violations = []
    for elem in elements:
        role = str(elem.get("role", "") or "").lower()
        aria_live = elem.get("aria_live")

        if aria_live:
            violations.append(ARIAViolation(
                violation_type=ARIAViolationType.NEEDS_MANUAL_REVIEW,
                element_selector=_selector_of(elem),
                description=(
                    f'aria-live="{aria_live}" region found. Automation can verify the '
                    "syntax but not the salience of announcements."
                ),
                severity=ViolationSeverity.INFO,
                wcag_reference="4.1.3",
                suggested_fix="Run the manual test directive; no automated fix applies.",
                aria_attribute="aria-live",
                verdict=CheckVerdict.NEEDS_REVIEW,
                automatability=AutomatabilityTier.NEEDS_HUMAN,
                manual_test_directive=MANUAL_TEST_DIRECTIVES["aria-live"],
            ))

        if role in COMPOSITE_WIDGET_ROLES:
            violations.append(ARIAViolation(
                violation_type=ARIAViolationType.NEEDS_MANUAL_REVIEW,
                element_selector=_selector_of(elem),
                description=(
                    f'Composite widget role="{role}" found. Automation cannot verify '
                    "its keyboard interaction model or AT announcements."
                ),
                severity=ViolationSeverity.INFO,
                wcag_reference="4.1.2",
                suggested_fix="Run the manual test directive; no automated fix applies.",
                role=role,
                verdict=CheckVerdict.NEEDS_REVIEW,
                automatability=AutomatabilityTier.NEEDS_HUMAN,
                manual_test_directive=MANUAL_TEST_DIRECTIVES[role],
            ))
    return violations


def detect_aria_density_smell(
    aria_attribute_count: int,
    element_count: int,
    threshold: float = ARIA_DENSITY_THRESHOLD,
    min_elements: int = ARIA_DENSITY_MIN_ELEMENTS,
) -> List[ARIAViolation]:
    """
    ARIA-density smell (DEEPTHINK_01): pages drowning in ARIA correlate
    with broken AT experiences. Heuristic WARNING.
    """
    if element_count < min_elements:
        return []
    density = aria_attribute_count / element_count
    if density <= threshold:
        return []
    return [ARIAViolation(
        violation_type=ARIAViolationType.ARIA_DENSITY,
        element_selector="body",
        description=(
            f"ARIA soup: {aria_attribute_count} ARIA attributes across "
            f"{element_count} elements (density {density:.2f} > {threshold}). "
            "Over-engineered accessibility correlates with broken AT experiences."
        ),
        severity=ViolationSeverity.MODERATE,
        wcag_reference="4.1.2",
        suggested_fix="Prefer native HTML semantics; remove ARIA that restates or fights them.",
        verdict=CheckVerdict.WARNING,
        automatability=AutomatabilityTier.PARTIALLY_AUTOMATABLE,
    )]


def tag_violation_tier(violation: ARIAViolation) -> ARIAViolation:
    """Tag an existing violation with its automatability tier (in place)."""
    if violation.automatability is None:
        violation.automatability = CHECK_TIERS.get(
            violation.violation_type, AutomatabilityTier.FULLY_AUTOMATABLE
        )
    return violation


async def collect_aria_tier_elements(page) -> Dict[str, Any]:
    """
    Collect the metadata the pure detectors need, in one page.evaluate call.

    Returns {"elements": [...], "aria_attribute_count": int, "element_count": int}.
    """
    try:
        return await page.evaluate("""
            () => {
                const elements = [];
                const all = document.querySelectorAll('*');
                let ariaAttributeCount = 0;
                for (const el of all) {
                    for (const attr of el.attributes) {
                        if (attr.name.startsWith('aria-')) ariaAttributeCount++;
                    }
                    const role = el.getAttribute('role');
                    const ariaLive = el.getAttribute('aria-live');
                    if (role || ariaLive) {
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            id: el.id,
                            role: role,
                            aria_live: ariaLive,
                            has_href: el.hasAttribute('href'),
                        });
                    }
                }
                return {
                    elements: elements,
                    aria_attribute_count: ariaAttributeCount,
                    element_count: all.length,
                };
            }
        """)
    except Exception:
        return {"elements": [], "aria_attribute_count": 0, "element_count": 0}
