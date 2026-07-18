"""
Freya Component Criticality Tests

L0 tests for the dual-axis criticality classifier and impact lookup.
"""

import pytest

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    ComponentCriticality,
    UsabilityImpact,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.services._component_criticality import (
    IMPACT_TABLE,
    classify_element,
    classify_selector,
    derive_impact,
)


class TestClassifyElement:
    def test_submit_button_is_primary(self):
        elem = {"tag": "button", "type": "submit", "visible": True}
        assert classify_element(elem) == ComponentCriticality.PRIMARY_INTERACTIVE

    def test_form_field_is_primary(self):
        elem = {"tag": "input", "type": "text", "in_form": True, "visible": True}
        assert classify_element(elem) == ComponentCriticality.PRIMARY_INTERACTIVE

    def test_nav_link_is_primary(self):
        elem = {"tag": "a", "in_nav": True, "visible": True}
        assert classify_element(elem) == ComponentCriticality.PRIMARY_INTERACTIVE

    def test_checkout_testid_is_primary(self):
        elem = {"tag": "div", "testid": "checkout-button", "visible": True}
        assert classify_element(elem) == ComponentCriticality.PRIMARY_INTERACTIVE

    def test_plain_button_is_interactive(self):
        assert classify_element({"tag": "button", "visible": True}) == ComponentCriticality.INTERACTIVE

    def test_role_button_is_interactive(self):
        elem = {"tag": "div", "role": "button", "visible": True}
        assert classify_element(elem) == ComponentCriticality.INTERACTIVE

    def test_tabindex_is_interactive(self):
        elem = {"tag": "div", "tabindex": "0", "visible": True}
        assert classify_element(elem) == ComponentCriticality.INTERACTIVE

    def test_cursor_pointer_is_interactive(self):
        elem = {"tag": "div", "cursor_pointer": True, "visible": True}
        assert classify_element(elem) == ComponentCriticality.INTERACTIVE

    def test_aria_hidden_is_decorative(self):
        elem = {"tag": "button", "aria_hidden": True}
        assert classify_element(elem) == ComponentCriticality.DECORATIVE

    def test_presentation_subtree_is_decorative(self):
        elem = {"tag": "span", "presentation_subtree": True, "visible": True}
        assert classify_element(elem) == ComponentCriticality.DECORATIVE

    def test_footer_text_is_decorative(self):
        elem = {"tag": "p", "in_footer": True, "visible": True}
        assert classify_element(elem) == ComponentCriticality.DECORATIVE

    def test_invisible_is_decorative(self):
        elem = {"tag": "p", "visible": False}
        assert classify_element(elem) == ComponentCriticality.DECORATIVE

    def test_heading_is_content(self):
        assert classify_element({"tag": "h1", "visible": True}) == ComponentCriticality.CONTENT

    def test_empty_dict_is_content(self):
        assert classify_element({}) == ComponentCriticality.CONTENT


class TestClassifySelector:
    def test_submit_selector_primary(self):
        assert classify_selector(
            "form button", '<button type="submit">Go</button>'
        ) == ComponentCriticality.PRIMARY_INTERACTIVE

    def test_button_selector_interactive(self):
        assert classify_selector("button.save") == ComponentCriticality.INTERACTIVE

    def test_footer_selector_decorative(self):
        assert classify_selector("footer p") == ComponentCriticality.DECORATIVE

    def test_plain_selector_content(self):
        assert classify_selector("h2.title") == ComponentCriticality.CONTENT

    def test_none_selector_content(self):
        assert classify_selector(None) == ComponentCriticality.CONTENT


class TestImpactTable:
    def test_complete_matrix(self):
        """Every severity x criticality pair must map."""
        for severity in ViolationSeverity:
            assert severity in IMPACT_TABLE
            for criticality in ComponentCriticality:
                assert criticality in IMPACT_TABLE[severity]

    def test_contrast_fail_primary_vs_decorative(self):
        """DEEPTHINK_01's canonical example: same ratio, different impact."""
        on_button = derive_impact(
            ViolationSeverity.SERIOUS, ComponentCriticality.PRIMARY_INTERACTIVE
        )
        on_footer = derive_impact(
            ViolationSeverity.SERIOUS, ComponentCriticality.DECORATIVE
        )
        assert on_button == UsabilityImpact.HIGH
        assert on_footer == UsabilityImpact.LOW

    def test_impact_monotonic_in_criticality(self):
        rank = {UsabilityImpact.LOW: 0, UsabilityImpact.MODERATE: 1,
                UsabilityImpact.HIGH: 2, UsabilityImpact.BLOCKER: 3}
        order = [
            ComponentCriticality.DECORATIVE,
            ComponentCriticality.CONTENT,
            ComponentCriticality.INTERACTIVE,
            ComponentCriticality.PRIMARY_INTERACTIVE,
        ]
        for severity in ViolationSeverity:
            impacts = [rank[derive_impact(severity, c)] for c in order]
            assert impacts == sorted(impacts)
