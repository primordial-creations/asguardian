"""
Freya WCAG criteria definitions.

WCAG 2.1 success criteria mapping extracted from wcag_validator.py.
"""

from Asgard.Freya.Accessibility.models.accessibility_models import (
    AccessibilityCategory,
    ViolationSeverity,
    WCAGLevel,
)


WCAG_CRITERIA = {
    "1.1.1": {
        "name": "Non-text Content",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.IMAGES,
        "severity": ViolationSeverity.CRITICAL,
    },
    "1.3.1": {
        "name": "Info and Relationships",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.3.2": {
        "name": "Meaningful Sequence",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.4.1": {
        "name": "Use of Color",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.CONTRAST,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.4.3": {
        "name": "Contrast (Minimum)",
        "level": WCAGLevel.AA,
        "category": AccessibilityCategory.CONTRAST,
        "severity": ViolationSeverity.SERIOUS,
    },
    "1.4.6": {
        "name": "Contrast (Enhanced)",
        "level": WCAGLevel.AAA,
        "category": AccessibilityCategory.CONTRAST,
        "severity": ViolationSeverity.MODERATE,
    },
    "2.1.1": {
        "name": "Keyboard",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.CRITICAL,
    },
    "2.1.2": {
        "name": "No Keyboard Trap",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.CRITICAL,
    },
    "2.4.1": {
        "name": "Bypass Blocks",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.NAVIGATION,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.2": {
        "name": "Page Titled",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.3": {
        "name": "Focus Order",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.4": {
        "name": "Link Purpose (In Context)",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.LINKS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "2.4.6": {
        "name": "Headings and Labels",
        "level": WCAGLevel.AA,
        "category": AccessibilityCategory.STRUCTURE,
        "severity": ViolationSeverity.MODERATE,
    },
    "2.4.7": {
        "name": "Focus Visible",
        "level": WCAGLevel.AA,
        "category": AccessibilityCategory.KEYBOARD,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.1.1": {
        "name": "Language of Page",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.LANGUAGE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.2.1": {
        "name": "On Focus",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.OPERABLE,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.2.2": {
        "name": "On Input",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.FORMS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.3.1": {
        "name": "Error Identification",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.FORMS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "3.3.2": {
        "name": "Labels or Instructions",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.FORMS,
        "severity": ViolationSeverity.SERIOUS,
    },
    "4.1.1": {
        "name": "Parsing",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.ROBUST,
        "severity": ViolationSeverity.MODERATE,
    },
    "4.1.2": {
        "name": "Name, Role, Value",
        "level": WCAGLevel.A,
        "category": AccessibilityCategory.ARIA,
        "severity": ViolationSeverity.CRITICAL,
    },
}


#: All WCAG 2.1 success criteria (A, AA, AAA). Used by the conformance
#: ledger to be explicit about the criteria this tool does NOT check
#: (coverage honesty, DEEPTHINK_03).
ALL_WCAG_21_CRITERIA = [
    "1.1.1",
    "1.2.1", "1.2.2", "1.2.3", "1.2.4", "1.2.5", "1.2.6", "1.2.7", "1.2.8", "1.2.9",
    "1.3.1", "1.3.2", "1.3.3", "1.3.4", "1.3.5", "1.3.6",
    "1.4.1", "1.4.2", "1.4.3", "1.4.4", "1.4.5", "1.4.6", "1.4.7", "1.4.8", "1.4.9",
    "1.4.10", "1.4.11", "1.4.12", "1.4.13",
    "2.1.1", "2.1.2", "2.1.3", "2.1.4",
    "2.2.1", "2.2.2", "2.2.3", "2.2.4", "2.2.5", "2.2.6",
    "2.3.1", "2.3.2", "2.3.3",
    "2.4.1", "2.4.2", "2.4.3", "2.4.4", "2.4.5", "2.4.6", "2.4.7", "2.4.8", "2.4.9", "2.4.10",
    "2.5.1", "2.5.2", "2.5.3", "2.5.4", "2.5.5", "2.5.6",
    "3.1.1", "3.1.2", "3.1.3", "3.1.4", "3.1.5", "3.1.6",
    "3.2.1", "3.2.2", "3.2.3", "3.2.4", "3.2.5",
    "3.3.1", "3.3.2", "3.3.3", "3.3.4", "3.3.5", "3.3.6",
    "4.1.1", "4.1.2", "4.1.3",
]


def build_conformance_ledger(violations, needs_review_refs=None) -> dict:
    """
    Build the Axis-1 conformance ledger: every WCAG 2.1 success criterion
    mapped to pass/fail/needs_review/not_checked.

    - Criteria in WCAG_CRITERIA (the checked set) default to "pass".
    - Criteria with at least one violation become "fail".
    - Criteria in needs_review_refs become "needs_review" (unless failed).
    - All other WCAG 2.1 criteria are explicitly "not_checked".
    """
    needs_review_refs = set(needs_review_refs or [])
    failed = set()
    for violation in violations:
        reference = getattr(violation, "wcag_reference", None) or getattr(violation, "wcag_criterion", None)
        if reference:
            failed.add(str(reference))

    ledger = {}
    checked = set(WCAG_CRITERIA.keys())
    for criterion in ALL_WCAG_21_CRITERIA:
        if criterion in failed:
            ledger[criterion] = "fail"
        elif criterion in needs_review_refs:
            ledger[criterion] = "needs_review"
        elif criterion in checked:
            ledger[criterion] = "pass"
        else:
            ledger[criterion] = "not_checked"
    # Keep any failed criteria outside the 2.1 catalog visible too.
    for criterion in sorted(failed - set(ALL_WCAG_21_CRITERIA)):
        ledger[criterion] = "fail"
    return ledger
