"""
Heimdall CodeFix Service

Generates template-based code fix suggestions for known rule violations.
For rules without a dedicated template, informational guidance is provided.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from Asgard.Heimdall.CodeFix.models.codefix_models import (
    CodeFix,
    CodeFixReport,
    FixSuggestion,
    FixType,
)
from Asgard.Heimdall.CodeFix.services._codefix_builders import (
    fallback_fix,
    fix_cyclomatic_complexity,
    fix_env_fallback,
    fix_eval_injection,
    fix_hardcoded_secret,
    fix_insecure_deserialization,
    fix_lazy_imports,
    fix_long_function,
    fix_pascal_case_violation,
    fix_shell_curl_insecure,
    fix_shell_missing_set_e,
    fix_snake_case_violation,
    fix_var_declaration,
)


class CodeFixService:
    """
    Generates code fix suggestions for known rule violations.

    Fixes are template-based and rule-specific. For complex issues,
    provides informational guidance rather than automated fixes.
    """

    def get_fix(
        self,
        rule_id: str,
        code_snippet: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[CodeFix]:
        """
        Return a fix suggestion for a given rule violation.

        Args:
            rule_id: The rule identifier string (e.g. "quality.lazy_imports").
            code_snippet: The offending code excerpt, used in fix templates.
            context: Optional extra context (function name, file type, etc.).

        Returns:
            A CodeFix instance, or None if no fix can be determined.
        """
        handler = self._rule_handlers().get(rule_id)
        if handler is not None:
            return handler(code_snippet, context or {})
        return fallback_fix(rule_id, code_snippet)

    def get_fixes_for_report(
        self,
        findings: List[Dict[str, Any]],
    ) -> CodeFixReport:
        """
        Generate fix suggestions for a list of findings.

        Each finding dict must contain the keys:
            rule_id, file_path, line_number, title, code_snippet.

        Args:
            findings: List of finding dicts from analysis results.

        Returns:
            A CodeFixReport with all suggestions populated.
        """
        suggestions: List[FixSuggestion] = []
        automated_count = 0
        suggested_count = 0

        for finding in findings:
            rule_id = finding.get("rule_id", "")
            file_path = finding.get("file_path", "")
            line_number = int(finding.get("line_number", 0))
            title = finding.get("title", "")
            code_snippet = finding.get("code_snippet", "")

            fix = self.get_fix(rule_id, code_snippet, finding)
            if fix is None:
                continue

            suggestion = FixSuggestion(
                file_path=file_path,
                line_number=line_number,
                rule_id=rule_id,
                finding_title=title,
                fix=fix,
            )
            suggestions.append(suggestion)

            fix_type_value = fix.fix_type if isinstance(fix.fix_type, str) else fix.fix_type.value
            if fix_type_value == FixType.AUTOMATED.value:
                automated_count += 1
            elif fix_type_value == FixType.SUGGESTED.value:
                suggested_count += 1

        return CodeFixReport(
            total_suggestions=len(suggestions),
            automated_count=automated_count,
            suggested_count=suggested_count,
            suggestions=suggestions,
            generated_at=datetime.now(),
        )

    def _rule_handlers(self) -> Dict[str, Any]:
        """Return a mapping of rule_id to fix-builder callable."""
        return {
            "quality.lazy_imports": fix_lazy_imports,
            "quality.env_fallback": fix_env_fallback,
            "quality.cyclomatic_complexity": fix_cyclomatic_complexity,
            "quality.long_function": fix_long_function,
            "quality.var_declaration": fix_var_declaration,
            "security.hardcoded_secret": fix_hardcoded_secret,
            "security.eval_injection": fix_eval_injection,
            "security.insecure_deserialization": fix_insecure_deserialization,
            "shell.missing_set_e": fix_shell_missing_set_e,
            "shell.curl_insecure": fix_shell_curl_insecure,
            "naming.snake_case_violation": fix_snake_case_violation,
            "naming.pascal_case_violation": fix_pascal_case_violation,
        }
