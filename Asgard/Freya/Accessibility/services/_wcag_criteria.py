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
