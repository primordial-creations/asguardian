"""
Freya Accessibility Models

Pydantic models for accessibility testing results and configurations.
Based on WCAG 2.1 guidelines.
"""

from Asgard.Freya.Accessibility.models._accessibility_enums import (
    ARIAViolationType,
    AccessibilityCategory,
    ColorBlindnessType,
    ColorInfo,
    KeyboardIssueType,
    ScreenReaderIssueType,
    TextSize,
    ViolationSeverity,
    WCAGLevel,
)
from Asgard.Freya.Accessibility.models._accessibility_report_models import (
    ARIAReport,
    ARIAViolation,
    AccessibilityConfig,
    AccessibilityReport,
    AccessibilityViolation,
    ContrastIssue,
    ContrastReport,
    ContrastResult,
    HeadingInfo,
    KeyboardIssue,
    KeyboardNavigationReport,
    ScreenReaderIssue,
    ScreenReaderReport,
)

__all__ = [
    "WCAGLevel",
    "ViolationSeverity",
    "AccessibilityCategory",
    "TextSize",
    "ColorBlindnessType",
    "ColorInfo",
    "KeyboardIssueType",
    "ARIAViolationType",
    "ScreenReaderIssueType",
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
    "HeadingInfo",
    "ScreenReaderReport",
]
