"""
Freya ARIA Automatability Tier Tests

L0 tests for redundant roles, non-native interactive roles, NEEDS_REVIEW
escalation, density smell, and tier tagging (DEEPTHINK_05).
"""

import pytest

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    ARIAViolationType,
    AutomatabilityTier,
    CheckVerdict,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.models._accessibility_report_models import ARIAViolation
from Asgard.Freya.Accessibility.services._aria_validator_tiers import (
    CHECK_TIERS,
    COMPOSITE_WIDGET_ROLES,
    IMPLICIT_ROLES,
    MANUAL_TEST_DIRECTIVES,
    detect_aria_density_smell,
    detect_needs_review,
    detect_non_native_interactive,
    detect_redundant_roles,
    tag_violation_tier,
)


class TestRedundantRoles:
    def test_nav_navigation_is_redundant(self):
        violations = detect_redundant_roles([{"tag": "nav", "role": "navigation"}])
        assert len(violations) == 1
        assert violations[0].violation_type == ARIAViolationType.REDUNDANT_ROLE
        assert violations[0].verdict == CheckVerdict.WARNING
        assert "code smell" in violations[0].description.lower()

    def test_button_button_is_redundant(self):
        violations = detect_redundant_roles([{"tag": "button", "role": "button"}])
        assert len(violations) == 1

    def test_anchor_without_href_not_redundant(self):
        violations = detect_redundant_roles([{"tag": "a", "role": "link", "has_href": False}])
        assert violations == []

    def test_anchor_with_href_redundant(self):
        violations = detect_redundant_roles([{"tag": "a", "role": "link", "has_href": True}])
        assert len(violations) == 1

    def test_non_redundant_role_ok(self):
        violations = detect_redundant_roles([{"tag": "div", "role": "button"}])
        assert violations == []

    def test_implicit_role_table_size(self):
        assert len(IMPLICIT_ROLES) >= 30


class TestNonNativeInteractive:
    def test_div_button_warns(self):
        violations = detect_non_native_interactive([{"tag": "div", "role": "button"}])
        assert len(violations) == 1
        assert violations[0].verdict == CheckVerdict.WARNING
        assert "syntactically valid" in violations[0].description.lower()
        assert "<button>" in violations[0].description

    def test_span_link_warns(self):
        violations = detect_non_native_interactive([{"tag": "span", "role": "link"}])
        assert len(violations) == 1

    def test_native_button_ok(self):
        assert detect_non_native_interactive([{"tag": "button", "role": "button"}]) == []

    def test_div_with_structural_role_ok(self):
        assert detect_non_native_interactive([{"tag": "div", "role": "main"}]) == []


class TestNeedsReview:
    @pytest.mark.parametrize("role", sorted(COMPOSITE_WIDGET_ROLES))
    def test_composite_roles_escalate(self, role):
        violations = detect_needs_review([{"tag": "div", "role": role}])
        assert len(violations) == 1
        item = violations[0]
        assert item.verdict == CheckVerdict.NEEDS_REVIEW
        assert item.automatability == AutomatabilityTier.NEEDS_HUMAN
        assert item.manual_test_directive == MANUAL_TEST_DIRECTIVES[role]
        assert item.manual_test_directive  # directive text present

    def test_aria_live_escalates(self):
        violations = detect_needs_review([{"tag": "div", "aria_live": "polite"}])
        assert len(violations) == 1
        assert violations[0].verdict == CheckVerdict.NEEDS_REVIEW
        assert "screen reader" in violations[0].manual_test_directive.lower()

    def test_plain_role_not_escalated(self):
        assert detect_needs_review([{"tag": "div", "role": "button"}]) == []

    def test_every_composite_role_has_directive(self):
        for role in COMPOSITE_WIDGET_ROLES:
            assert role in MANUAL_TEST_DIRECTIVES


class TestDensitySmell:
    def test_high_density_warns(self):
        violations = detect_aria_density_smell(80, 100)
        assert len(violations) == 1
        assert violations[0].verdict == CheckVerdict.WARNING
        assert "aria soup" in violations[0].description.lower()

    def test_low_density_ok(self):
        assert detect_aria_density_smell(10, 100) == []

    def test_small_page_ignored(self):
        assert detect_aria_density_smell(30, 40) == []


class TestTierTagging:
    def test_all_violation_types_have_tiers(self):
        for violation_type in ARIAViolationType:
            assert violation_type in CHECK_TIERS

    def test_deterministic_checks_fully_automatable(self):
        assert CHECK_TIERS[ARIAViolationType.UNSUPPORTED_ROLE] == AutomatabilityTier.FULLY_AUTOMATABLE
        assert CHECK_TIERS[ARIAViolationType.MISSING_REQUIRED_ATTRIBUTE] == AutomatabilityTier.FULLY_AUTOMATABLE

    def test_tag_violation_tier_fills_missing(self):
        violation = ARIAViolation(
            violation_type=ARIAViolationType.DUPLICATE_ID,
            element_selector="#x",
            description="dup",
            severity=ViolationSeverity.SERIOUS,
            wcag_reference="4.1.1",
            suggested_fix="fix",
        )
        assert violation.automatability is None
        tag_violation_tier(violation)
        assert violation.automatability == AutomatabilityTier.FULLY_AUTOMATABLE

    def test_tag_violation_tier_preserves_existing(self):
        violation = ARIAViolation(
            violation_type=ARIAViolationType.DUPLICATE_ID,
            element_selector="#x",
            description="dup",
            severity=ViolationSeverity.SERIOUS,
            wcag_reference="4.1.1",
            suggested_fix="fix",
            automatability=AutomatabilityTier.NEEDS_HUMAN,
        )
        tag_violation_tier(violation)
        assert violation.automatability == AutomatabilityTier.NEEDS_HUMAN


class TestARIAReportSemantics:
    def test_needs_review_blocks_fully_passing(self):
        from Asgard.Freya.Accessibility.models._accessibility_report_models import ARIAReport
        item = ARIAViolation(
            violation_type=ARIAViolationType.NEEDS_MANUAL_REVIEW,
            element_selector="[role=combobox]",
            description="combobox",
            severity=ViolationSeverity.INFO,
            wcag_reference="4.1.2",
            suggested_fix="manual test",
            verdict=CheckVerdict.NEEDS_REVIEW,
        )
        report = ARIAReport(url="https://example.com", needs_review=[item], needs_review_count=1)
        assert not report.has_violations
        assert not report.fully_passing

    def test_backward_compat_old_json_parses(self):
        from Asgard.Freya.Accessibility.models._accessibility_report_models import ARIAReport
        report = ARIAReport.model_validate({"url": "https://example.com"})
        assert report.needs_review == []
        assert report.tier_counts == {}
        assert report.fully_passing
