"""
Freya Accessibility Enums and Base Models

Enums and simple models used across accessibility modules.
"""

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, Field


class WCAGLevel(str, Enum):
    """WCAG conformance levels."""
    A = "A"
    AA = "AA"
    AAA = "AAA"


class ViolationSeverity(str, Enum):
    """Severity levels for accessibility violations."""
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"
    INFO = "info"


class AccessibilityCategory(str, Enum):
    """Categories of accessibility requirements."""
    PERCEIVABLE = "perceivable"
    OPERABLE = "operable"
    UNDERSTANDABLE = "understandable"
    ROBUST = "robust"
    CONTRAST = "contrast"
    KEYBOARD = "keyboard"
    ARIA = "aria"
    FORMS = "forms"
    IMAGES = "images"
    LINKS = "links"
    STRUCTURE = "structure"
    LANGUAGE = "language"
    NAVIGATION = "navigation"


class TextSize(str, Enum):
    """Text size categories for contrast requirements."""
    NORMAL = "normal"
    LARGE = "large"


class ColorBlindnessType(str, Enum):
    """Types of color vision deficiency."""
    PROTANOPIA = "protanopia"
    DEUTERANOPIA = "deuteranopia"
    TRITANOPIA = "tritanopia"
    PROTANOMALY = "protanomaly"
    DEUTERANOMALY = "deuteranomaly"
    TRITANOMALY = "tritanomaly"
    MONOCHROMACY = "monochromacy"


class KeyboardIssueType(str, Enum):
    """Types of keyboard accessibility issues."""
    NO_FOCUS_INDICATOR = "no_focus_indicator"
    NOT_FOCUSABLE = "not_focusable"
    FOCUS_TRAP = "focus_trap"
    SKIP_LINK_MISSING = "skip_link_missing"
    TAB_ORDER_ISSUE = "tab_order_issue"
    NO_KEYBOARD_ACCESS = "no_keyboard_access"
    MISSING_FOCUS_MANAGEMENT = "missing_focus_management"


class ARIAViolationType(str, Enum):
    """Types of ARIA violations."""
    MISSING_REQUIRED_ATTRIBUTE = "missing_required_attribute"
    INVALID_ATTRIBUTE_VALUE = "invalid_attribute_value"
    UNSUPPORTED_ROLE = "unsupported_role"
    CONFLICTING_ROLES = "conflicting_roles"
    MISSING_ACCESSIBLE_NAME = "missing_accessible_name"
    HIDDEN_FOCUSABLE = "hidden_focusable"
    IMPROPER_ROLE_USAGE = "improper_role_usage"
    MISSING_PARENT_ROLE = "missing_parent_role"
    DUPLICATE_ID = "duplicate_id"


class ScreenReaderIssueType(str, Enum):
    """Types of screen reader compatibility issues."""
    MISSING_ALT_TEXT = "missing_alt_text"
    EMPTY_ALT_TEXT = "empty_alt_text"
    MISSING_LABEL = "missing_label"
    EMPTY_BUTTON = "empty_button"
    EMPTY_LINK = "empty_link"
    MISSING_HEADING_STRUCTURE = "missing_heading_structure"
    SKIPPED_HEADING_LEVEL = "skipped_heading_level"
    MISSING_LANDMARK = "missing_landmark"
    MISSING_LANG_ATTRIBUTE = "missing_lang_attribute"
    INACCESSIBLE_CONTENT = "inaccessible_content"


class ColorInfo(BaseModel):
    """Color information."""
    hex_value: str = Field(..., description="Hex color value (e.g., '#ffffff')")
    rgb: Tuple[int, int, int] = Field(..., description="RGB values (0-255)")
    luminance: float = Field(..., description="Relative luminance (0-1)")
