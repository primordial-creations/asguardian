"""
Heimdall TypeScript Quality Analysis Models

TypeScript analysis reuses the JS models.  This module re-exports them for
import convenience and documents the TypeScript-specific rule IDs.

TypeScript-specific rule IDs:
- ts.no-explicit-any     : ': any' type annotation
- ts.no-any-cast         : 'as any' cast expression
- ts.no-non-null-assertion : Non-null assertion operator (!)
- ts.prefer-interface    : Type alias for object shape (use interface instead)
- ts.no-implicit-any     : Function parameter without explicit type annotation
"""

from Asgard.Bragi.Quality.languages.javascript.models.js_models import (
    JSAnalysisConfig,
    JSFinding,
    JSReport,
    JSRuleCategory,
    JSSeverity,
)

__all__ = [
    "JSAnalysisConfig",
    "JSFinding",
    "JSReport",
    "JSRuleCategory",
    "JSSeverity",
]
