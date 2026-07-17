"""
Freya Conformance Ledger Tests

L0 tests for the Axis-1 statutory WCAG conformance ledger.
"""

import pytest

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    AccessibilityCategory,
    UsabilityImpact,
    ViolationSeverity,
)
from Asgard.Freya.Accessibility.models._accessibility_report_models import (
    AccessibilityReport,
    AccessibilityViolation,
    compliance_debt_framing,
)
from Asgard.Freya.Accessibility.services._wcag_criteria import (
    ALL_WCAG_21_CRITERIA,
    WCAG_CRITERIA,
    build_conformance_ledger,
)


def _violation(reference: str) -> AccessibilityViolation:
    return AccessibilityViolation(
        id=f"v-{reference}",
        wcag_reference=reference,
        category=AccessibilityCategory.CONTRAST,
        severity=ViolationSeverity.SERIOUS,
        description="d",
        element_selector="p",
        suggested_fix="f",
    )


class TestCatalog:
    def test_wcag_21_has_78_criteria(self):
        assert len(ALL_WCAG_21_CRITERIA) == 78

    def test_checked_set_is_subset(self):
        assert set(WCAG_CRITERIA.keys()) <= set(ALL_WCAG_21_CRITERIA)


class TestLedger:
    def test_ledger_covers_all_criteria(self):
        ledger = build_conformance_ledger([])
        assert set(ALL_WCAG_21_CRITERIA) <= set(ledger.keys())

    def test_unchecked_criteria_explicit(self):
        """Coverage honesty: criteria we don't check must say so."""
        ledger = build_conformance_ledger([])
        not_checked = [k for k, v in ledger.items() if v == "not_checked"]
        assert len(not_checked) == len(ALL_WCAG_21_CRITERIA) - len(WCAG_CRITERIA)
        assert "1.2.1" in not_checked  # media alternatives are not automated

    def test_checked_without_violation_is_pass(self):
        ledger = build_conformance_ledger([])
        assert ledger["1.4.3"] == "pass"

    def test_violation_marks_fail(self):
        ledger = build_conformance_ledger([_violation("1.4.3")])
        assert ledger["1.4.3"] == "fail"

    def test_needs_review_status(self):
        ledger = build_conformance_ledger([], needs_review_refs={"4.1.3"})
        assert ledger["4.1.3"] == "needs_review"

    def test_fail_beats_needs_review(self):
        ledger = build_conformance_ledger([_violation("4.1.2")], needs_review_refs={"4.1.2"})
        assert ledger["4.1.2"] == "fail"


class TestReportModelCompat:
    def test_old_json_still_parses(self):
        report = AccessibilityReport.model_validate({
            "url": "https://example.com",
            "wcag_level": "AA",
        })
        assert report.conformance_ledger == {}
        assert report.needs_review_count == 0

    def test_violation_new_fields_default(self):
        violation = _violation("1.4.3")
        assert violation.usability_impact is None
        assert violation.criticality is None
        assert violation.verdict.value == "fail"
        assert violation.framing is None


class TestComplianceDebtFraming:
    def test_low_impact_gets_framing(self):
        text = compliance_debt_framing(ViolationSeverity.MINOR, UsabilityImpact.LOW)
        assert text is not None
        assert "Micro-barrier" in text
        assert "Strict WCAG Violation" in text

    def test_high_impact_no_framing(self):
        assert compliance_debt_framing(ViolationSeverity.SERIOUS, UsabilityImpact.HIGH) is None

    def test_no_impact_no_framing(self):
        assert compliance_debt_framing(ViolationSeverity.MINOR, None) is None
