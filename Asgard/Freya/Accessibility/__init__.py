"""
Freya Accessibility Module

Comprehensive accessibility testing for WCAG compliance.

Components:
- WCAGValidator: Full WCAG compliance validation
- ColorContrastChecker: Color contrast ratio checking (AA/AAA)
- KeyboardNavigationTester: Keyboard accessibility testing
- ScreenReaderValidator: Screen reader compatibility testing
- ARIAValidator: ARIA implementation validation

Usage:
    from Asgard.Freya.Accessibility import WCAGValidator, AccessibilityConfig

    config = AccessibilityConfig(wcag_level=WCAGLevel.AA)
    validator = WCAGValidator(config)
    result = await validator.validate("https://example.com")

    for violation in result.violations:
        print(f"{violation.wcag_reference}: {violation.description}")
"""

from Asgard.Freya.Accessibility.models.accessibility_models import (
    WCAGLevel,
    UsabilityImpact,
    ComponentCriticality,
    CheckVerdict,
    AutomatabilityTier,
    ConformanceStatus,
    ViolationSeverity,
    AccessibilityCategory,
    AccessibilityViolation,
    AccessibilityReport,
    AccessibilityConfig,
    ContrastResult,
    ContrastIssue,
    ContrastReport,
    KeyboardIssue,
    KeyboardNavigationReport,
    ARIAViolation,
    ARIAReport,
    ScreenReaderIssue,
    ScreenReaderReport,
)

from Asgard.Freya.Accessibility.services.wcag_validator import WCAGValidator
from Asgard.Freya.Accessibility.services.color_contrast import ColorContrastChecker
from Asgard.Freya.Accessibility.services.keyboard_nav import KeyboardNavigationTester
from Asgard.Freya.Accessibility.services.screen_reader import ScreenReaderValidator
from Asgard.Freya.Accessibility.services.aria_validator import ARIAValidator

__all__ = [
    # Services
    "WCAGValidator",
    "ColorContrastChecker",
    "KeyboardNavigationTester",
    "ScreenReaderValidator",
    "ARIAValidator",
    # Models
    "WCAGLevel",
    "UsabilityImpact",
    "ComponentCriticality",
    "CheckVerdict",
    "AutomatabilityTier",
    "ConformanceStatus",
    "ViolationSeverity",
    "AccessibilityCategory",
    "AccessibilityViolation",
    "AccessibilityReport",
    "AccessibilityConfig",
    "ContrastResult",
    "ContrastIssue",
    "ContrastReport",
    "KeyboardIssue",
    "KeyboardNavigationReport",
    "ARIAViolation",
    "ARIAReport",
    "ScreenReaderIssue",
    "ScreenReaderReport",
]
