"""
Heimdall Common - Shared utilities for the Heimdall analysis system.

Provides shared models and services used across Heimdall subpackages,
including the new code period detection system.
"""

from Asgard.Shared.common.new_code_period import (
    NewCodePeriodConfig,
    NewCodePeriodDetector,
    NewCodePeriodResult,
    NewCodePeriodType,
)
from Asgard.Shared.common.language_registry import (
    LANGUAGE_EXTENSIONS,
    EXTENSION_TO_LANGUAGE,
    ALL_CODE_EXTENSIONS,
    WEB_LANGUAGES,
    AST_SUPPORTED_LANGUAGES,
    SECURITY_SCAN_EXTENSIONS,
    QUALITY_SCAN_EXTENSIONS,
    LANG_EXTENSIONS,
    get_language,
    get_extensions_for_languages,
    is_scannable,
)

__all__ = [
    "NewCodePeriodConfig",
    "NewCodePeriodDetector",
    "NewCodePeriodResult",
    "NewCodePeriodType",
    "LANGUAGE_EXTENSIONS",
    "EXTENSION_TO_LANGUAGE",
    "ALL_CODE_EXTENSIONS",
    "WEB_LANGUAGES",
    "AST_SUPPORTED_LANGUAGES",
    "SECURITY_SCAN_EXTENSIONS",
    "QUALITY_SCAN_EXTENSIONS",
    "LANG_EXTENSIONS",
    "get_language",
    "get_extensions_for_languages",
    "is_scannable",
]
