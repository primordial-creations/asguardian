"""
Freya Component Criticality Classifier

DEEPTHINK_01 dual-axis support: weight findings by how critical the
affected component is. A 4.3:1 contrast ratio on a footer date and the
same ratio on a submit button are identical on the statutory axis and
far apart on the usability axis.

The classifier is a pure function over element metadata dicts so it can
be tested without Playwright; CRITICALITY_JS collects the same metadata
in-page for validators that have a live Page.
"""

from typing import Any, Dict, Optional

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    ComponentCriticality,
    UsabilityImpact,
    ViolationSeverity,
)

_INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "summary", "details"}
_INTERACTIVE_ROLES = {
    "button", "link", "checkbox", "radio", "textbox", "searchbox", "combobox",
    "listbox", "menu", "menubar", "menuitem", "option", "slider", "spinbutton",
    "switch", "tab", "gridcell", "treeitem",
}
_PRIMARY_TESTID_HINTS = ("submit", "login", "checkout", "cta")


def classify_element(elem: Dict[str, Any]) -> ComponentCriticality:
    """
    Classify an element's criticality from collected metadata.

    Recognized keys (all optional): tag, role, type, tabindex, in_form,
    in_nav, in_footer, aria_hidden, presentation_subtree, has_onclick,
    cursor_pointer, testid, visible.
    """
    tag = str(elem.get("tag", "")).lower()
    role = str(elem.get("role", "") or "").lower()
    input_type = str(elem.get("type", "") or "").lower()
    testid = str(elem.get("testid", "") or "").lower()

    # 3. DECORATIVE (checked first: aria-hidden trees are out of the AT tree)
    if (
        elem.get("aria_hidden")
        or elem.get("presentation_subtree")
        or role in ("presentation", "none")
        or elem.get("visible") is False
    ):
        return ComponentCriticality.DECORATIVE

    has_focusable_tabindex = elem.get("tabindex") is not None and _as_int(elem.get("tabindex")) >= 0
    focusable = (
        tag in _INTERACTIVE_TAGS
        or role in _INTERACTIVE_ROLES
        or has_focusable_tabindex
    )
    clickable = bool(elem.get("has_onclick")) or bool(elem.get("cursor_pointer"))

    # 1. PRIMARY_INTERACTIVE
    if (
        (tag == "button" and input_type == "submit")
        or (tag == "input" and input_type == "submit")
        or (elem.get("in_form") and focusable)
        or (elem.get("in_nav") and tag == "a")
        or any(hint in testid for hint in _PRIMARY_TESTID_HINTS)
    ):
        return ComponentCriticality.PRIMARY_INTERACTIVE

    # 2. INTERACTIVE
    if focusable or clickable:
        return ComponentCriticality.INTERACTIVE

    # Footer content is decorative-weight unless interactive (handled above).
    if elem.get("in_footer"):
        return ComponentCriticality.DECORATIVE

    # 4. CONTENT
    return ComponentCriticality.CONTENT


def classify_selector(selector: Optional[str], element_html: Optional[str] = None) -> ComponentCriticality:
    """
    Best-effort criticality from a CSS selector and optional HTML snippet,
    for call sites that no longer have the live element.
    """
    text = f"{selector or ''} {element_html or ''}".lower()
    if not text.strip():
        return ComponentCriticality.CONTENT
    if 'type="submit"' in text or any(h in text for h in _PRIMARY_TESTID_HINTS):
        return ComponentCriticality.PRIMARY_INTERACTIVE
    if "footer" in text or 'aria-hidden="true"' in text or 'role="presentation"' in text:
        return ComponentCriticality.DECORATIVE
    for token in ("button", "input", "select", "textarea", "<a ", "a[href]", "a.", "a#",
                  'role="button"', 'role="link"', "tabindex", "onclick"):
        if token in text:
            return ComponentCriticality.INTERACTIVE
    return ComponentCriticality.CONTENT


#: Two-key lookup: (base check severity, criticality) -> usability impact.
#: Data, not logic, so calibration can change without code churn.
IMPACT_TABLE: Dict[ViolationSeverity, Dict[ComponentCriticality, UsabilityImpact]] = {
    ViolationSeverity.CRITICAL: {
        ComponentCriticality.PRIMARY_INTERACTIVE: UsabilityImpact.BLOCKER,
        ComponentCriticality.INTERACTIVE: UsabilityImpact.BLOCKER,
        ComponentCriticality.CONTENT: UsabilityImpact.HIGH,
        ComponentCriticality.DECORATIVE: UsabilityImpact.MODERATE,
    },
    ViolationSeverity.SERIOUS: {
        ComponentCriticality.PRIMARY_INTERACTIVE: UsabilityImpact.HIGH,
        ComponentCriticality.INTERACTIVE: UsabilityImpact.HIGH,
        ComponentCriticality.CONTENT: UsabilityImpact.MODERATE,
        ComponentCriticality.DECORATIVE: UsabilityImpact.LOW,
    },
    ViolationSeverity.MODERATE: {
        ComponentCriticality.PRIMARY_INTERACTIVE: UsabilityImpact.HIGH,
        ComponentCriticality.INTERACTIVE: UsabilityImpact.MODERATE,
        ComponentCriticality.CONTENT: UsabilityImpact.LOW,
        ComponentCriticality.DECORATIVE: UsabilityImpact.LOW,
    },
    ViolationSeverity.MINOR: {
        ComponentCriticality.PRIMARY_INTERACTIVE: UsabilityImpact.MODERATE,
        ComponentCriticality.INTERACTIVE: UsabilityImpact.LOW,
        ComponentCriticality.CONTENT: UsabilityImpact.LOW,
        ComponentCriticality.DECORATIVE: UsabilityImpact.LOW,
    },
    ViolationSeverity.INFO: {
        ComponentCriticality.PRIMARY_INTERACTIVE: UsabilityImpact.LOW,
        ComponentCriticality.INTERACTIVE: UsabilityImpact.LOW,
        ComponentCriticality.CONTENT: UsabilityImpact.LOW,
        ComponentCriticality.DECORATIVE: UsabilityImpact.LOW,
    },
}


def derive_impact(
    severity: ViolationSeverity,
    criticality: ComponentCriticality,
) -> UsabilityImpact:
    """Axis-2 usability impact = f(check severity, component criticality)."""
    return IMPACT_TABLE[severity][criticality]


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


#: In-page metadata collector matching classify_element's expected keys.
#: Usage: page.evaluate(f"(el) => {{ {CRITICALITY_JS} return collect(el); }}", handle)
CRITICALITY_JS = """
function collect(el) {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return {
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role'),
        type: el.getAttribute('type'),
        tabindex: el.getAttribute('tabindex'),
        in_form: !!el.closest('form'),
        in_nav: !!el.closest('nav, [role="navigation"]'),
        in_footer: !!el.closest('footer, [role="contentinfo"]'),
        aria_hidden: !!el.closest('[aria-hidden="true"]'),
        presentation_subtree: !!el.closest('[role="presentation"], [role="none"]'),
        has_onclick: el.hasAttribute('onclick'),
        cursor_pointer: style.cursor === 'pointer',
        testid: el.getAttribute('data-testid'),
        visible: style.display !== 'none' && style.visibility !== 'hidden'
                 && rect.width > 0 && rect.height > 0,
    };
}
"""
