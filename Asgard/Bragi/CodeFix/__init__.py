"""
Heimdall CodeFix - Code Fix Suggestion Engine

Generates template-based fix suggestions mapped from rule violation IDs
to concrete remediation steps. For complex issues, provides informational
guidance rather than automated fixes.

Usage:
    from Asgard.Bragi.CodeFix import CodeFixService, CodeFixReport, FixSuggestion

    service = CodeFixService()
    fix = service.get_fix("quality.lazy_imports", code_snippet="    import os")
    print(fix.fixed_code)

    report = service.get_fixes_for_report(findings)
    print(f"Suggestions: {report.total_suggestions}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Bragi.CodeFix.models.codefix_models import (
    CodeFix,
    CodeFixReport,
    FixConfidence,
    FixSuggestion,
    FixType,
)
from Asgard.Bragi.CodeFix.services.codefix_service import CodeFixService

__all__ = [
    # Models
    "CodeFix",
    "CodeFixReport",
    "FixConfidence",
    "FixSuggestion",
    "FixType",
    # Services
    "CodeFixService",
]
