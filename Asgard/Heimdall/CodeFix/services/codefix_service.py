"""
Heimdall CodeFix Service

Generates template-based code fix suggestions for known rule violations.
For rules without a dedicated template, informational guidance is provided.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from Asgard.Heimdall.CodeFix.models.codefix_models import (
    CodeFix,
    CodeFixReport,
    FixConfidence,
    FixSuggestion,
    FixType,
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
        return self._fallback_fix(rule_id, code_snippet)

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

    # ------------------------------------------------------------------
    # Rule-specific fix builders
    # ------------------------------------------------------------------

    def _rule_handlers(self) -> Dict[str, Any]:
        """Return a mapping of rule_id to fix-builder callable."""
        return {
            "quality.lazy_imports": self._fix_lazy_imports,
            "quality.env_fallback": self._fix_env_fallback,
            "quality.cyclomatic_complexity": self._fix_cyclomatic_complexity,
            "quality.long_function": self._fix_long_function,
            "quality.var_declaration": self._fix_var_declaration,
            "security.hardcoded_secret": self._fix_hardcoded_secret,
            "security.eval_injection": self._fix_eval_injection,
            "security.insecure_deserialization": self._fix_insecure_deserialization,
            "shell.missing_set_e": self._fix_shell_missing_set_e,
            "shell.curl_insecure": self._fix_shell_curl_insecure,
            "naming.snake_case_violation": self._fix_snake_case_violation,
            "naming.pascal_case_violation": self._fix_pascal_case_violation,
        }

    def _fix_lazy_imports(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        import_line = code_snippet.strip() if code_snippet.strip().startswith("import") else code_snippet.strip()
        fixed = import_line if import_line else "import <module>"
        return CodeFix(
            rule_id="quality.lazy_imports",
            title="Move import to module level",
            description="Imports found inside a function, method, or conditional block must be moved to the top of the file.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.HIGH,
            original_code=code_snippet,
            fixed_code=fixed,
            explanation=(
                "All imports must appear at module level (PEP 8). "
                "Move the import statement to the top of the file, below any existing imports."
            ),
            references=[
                "https://peps.python.org/pep-0008/#imports",
            ],
        )

    def _fix_env_fallback(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        fixed = re.sub(
            r'os\.environ\.get\((["\'][^"\']+["\'])\s*,\s*[^)]+\)',
            r'os.environ[\1]',
            code_snippet,
        )
        if fixed == code_snippet:
            fixed = code_snippet.replace(", <default_value>", "").replace(",<default>", "")
        return CodeFix(
            rule_id="quality.env_fallback",
            title="Remove default/fallback value from os.environ.get()",
            description="Environment variables must not have fallback values. Use os.environ[] to raise KeyError when the variable is absent.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.HIGH,
            original_code=code_snippet,
            fixed_code=fixed,
            explanation=(
                "Using a fallback value hides misconfiguration. "
                "Replace os.environ.get('KEY', 'default') with os.environ['KEY'] "
                "so that missing variables raise an error at startup."
            ),
            references=[
                "https://12factor.net/config",
            ],
        )

    def _fix_cyclomatic_complexity(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        return CodeFix(
            rule_id="quality.cyclomatic_complexity",
            title="Reduce cyclomatic complexity by extracting helper functions",
            description="The function has too many branches. Extract independent logic blocks into separate, well-named helper functions.",
            fix_type=FixType.SUGGESTED,
            confidence=FixConfidence.LOW,
            original_code=code_snippet,
            fixed_code="",
            explanation=(
                "High cyclomatic complexity makes functions hard to test and maintain. "
                "Identify independent conditional blocks and extract each into a helper function. "
                "Aim for a cyclomatic complexity of 10 or lower per function."
            ),
            references=[
                "https://en.wikipedia.org/wiki/Cyclomatic_complexity",
                "https://refactoring.guru/extract-method",
            ],
        )

    def _fix_long_function(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        return CodeFix(
            rule_id="quality.long_function",
            title="Split long function into smaller functions",
            description="This function exceeds the recommended line length. Break it into smaller, focused functions.",
            fix_type=FixType.SUGGESTED,
            confidence=FixConfidence.LOW,
            original_code=code_snippet,
            fixed_code="",
            explanation=(
                "Functions should do one thing and do it well (Single Responsibility Principle). "
                "Identify logical phases of work (e.g., validation, processing, output) "
                "and extract each phase into its own function."
            ),
            references=[
                "https://refactoring.guru/extract-method",
                "https://peps.python.org/pep-0008/#maximum-line-length",
            ],
        )

    def _fix_var_declaration(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        fixed = re.sub(r'\bvar\b', "const", code_snippet, count=1)
        return CodeFix(
            rule_id="quality.var_declaration",
            title="Replace var with const or let",
            description="var declarations have function scope and are hoisted, which can cause unexpected behaviour. Use const for values that do not change, or let for values that do.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.HIGH,
            original_code=code_snippet,
            fixed_code=fixed,
            explanation=(
                "const and let have block scope, preventing accidental variable shadowing. "
                "Prefer const by default and use let only when reassignment is required."
            ),
            references=[
                "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/const",
                "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/let",
            ],
        )

    def _fix_hardcoded_secret(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        var_name = context.get("variable_name", "SECRET_KEY")
        fixed_code = (
            f"import os\n"
            f"{var_name} = os.environ['{var_name}']\n"
        )
        return CodeFix(
            rule_id="security.hardcoded_secret",
            title="Move secret to environment variable",
            description="Hardcoded secrets must never appear in source code. Store them in environment variables or a secrets manager.",
            fix_type=FixType.SUGGESTED,
            confidence=FixConfidence.MEDIUM,
            original_code=code_snippet,
            fixed_code=fixed_code,
            explanation=(
                "Secrets in source code are exposed in version control history. "
                "Remove the literal value, store it in an environment variable, "
                "and load it with os.environ['KEY']. "
                "Rotate the secret immediately if it has been committed."
            ),
            references=[
                "https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure",
                "https://12factor.net/config",
            ],
        )

    def _fix_eval_injection(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        return CodeFix(
            rule_id="security.eval_injection",
            title="Replace eval() with a safe alternative",
            description="eval() executes arbitrary code and must not be used with untrusted input. Use ast.literal_eval() for data parsing or refactor to remove the need for eval entirely.",
            fix_type=FixType.SUGGESTED,
            confidence=FixConfidence.MEDIUM,
            original_code=code_snippet,
            fixed_code="import ast\nresult = ast.literal_eval(expression)  # safe for literal Python values only",
            explanation=(
                "eval() with untrusted input enables remote code execution. "
                "For parsing Python literals (strings, numbers, lists, dicts), "
                "use ast.literal_eval(). For JSON, use json.loads(). "
                "For structured computation, define an explicit parser."
            ),
            references=[
                "https://owasp.org/www-community/attacks/Code_Injection",
                "https://docs.python.org/3/library/ast.html#ast.literal_eval",
            ],
        )

    def _fix_insecure_deserialization(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        return CodeFix(
            rule_id="security.insecure_deserialization",
            title="Replace pickle with json.loads() for safe deserialization",
            description="pickle.loads() executes arbitrary code during deserialization. Use json.loads() for data interchange or a validated schema library.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.MEDIUM,
            original_code=code_snippet,
            fixed_code="import json\ndata = json.loads(serialized_data)",
            explanation=(
                "pickle deserialization of untrusted data can execute arbitrary Python code. "
                "Replace pickle with json.loads() for simple data structures, "
                "or use a schema-validated format (e.g., protobuf, msgpack with schema) "
                "for complex types. Only use pickle for trusted, internally generated data."
            ),
            references=[
                "https://owasp.org/www-project-top-ten/2017/A8_2017-Insecure_Deserialization",
                "https://docs.python.org/3/library/pickle.html#restricting-globals",
            ],
        )

    def _fix_shell_missing_set_e(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        fixed = "#!/usr/bin/env bash\nset -e\n\n" + code_snippet.lstrip()
        if "#!/" in code_snippet:
            lines = code_snippet.splitlines()
            shebang = lines[0]
            rest = "\n".join(lines[1:]).lstrip()
            fixed = f"{shebang}\nset -e\n\n{rest}"
        return CodeFix(
            rule_id="shell.missing_set_e",
            title="Add 'set -e' to exit on error",
            description="Shell scripts should include 'set -e' to exit immediately when a command fails, preventing silent errors.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.HIGH,
            original_code=code_snippet,
            fixed_code=fixed,
            explanation=(
                "'set -e' causes the script to exit immediately if any command exits with a non-zero status. "
                "This prevents subsequent commands from executing in a broken state. "
                "Add it at the top of the script, after the shebang line."
            ),
            references=[
                "https://www.gnu.org/software/bash/manual/bash.html#The-Set-Builtin",
            ],
        )

    def _fix_shell_curl_insecure(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        fixed = re.sub(r'\s+-k\b', "", code_snippet)
        fixed = re.sub(r'\s+--insecure\b', "", fixed)
        return CodeFix(
            rule_id="shell.curl_insecure",
            title="Remove -k/--insecure flag from curl",
            description="The -k (--insecure) flag disables TLS certificate verification, exposing the connection to man-in-the-middle attacks.",
            fix_type=FixType.AUTOMATED,
            confidence=FixConfidence.HIGH,
            original_code=code_snippet,
            fixed_code=fixed,
            explanation=(
                "Removing -k restores certificate verification. "
                "If the connection fails after removal, fix the underlying certificate issue "
                "(expired, self-signed, or hostname mismatch) rather than disabling verification."
            ),
            references=[
                "https://curl.se/docs/manpage.html#-k",
                "https://owasp.org/www-community/attacks/Man-in-the-middle_attack",
            ],
        )

    def _fix_snake_case_violation(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        name = context.get("identifier", code_snippet.strip())
        # Convert camelCase or PascalCase to snake_case
        snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        snake = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", snake).lower()
        return CodeFix(
            rule_id="naming.snake_case_violation",
            title="Rename identifier to snake_case",
            description="Functions, methods, variables, and module-level names must use snake_case per PEP 8.",
            fix_type=FixType.SUGGESTED,
            confidence=FixConfidence.HIGH,
            original_code=name,
            fixed_code=snake,
            explanation=(
                f"Rename '{name}' to '{snake}'. "
                "Update all references throughout the codebase. "
                "Use your IDE's rename refactoring to avoid missing any call sites."
            ),
            references=[
                "https://peps.python.org/pep-0008/#function-and-variable-names",
            ],
        )

    def _fix_pascal_case_violation(self, code_snippet: str, context: Dict[str, Any]) -> CodeFix:
        name = context.get("identifier", code_snippet.strip())
        # Convert snake_case to PascalCase
        pascal = re.sub(r"(?:^|_)([a-zA-Z])", lambda m: m.group(1).upper(), name)
        return CodeFix(
            rule_id="naming.pascal_case_violation",
            title="Rename class to PascalCase",
            description="Class names must use PascalCase (CapWords) per PEP 8.",
            fix_type=FixType.SUGGESTED,
            confidence=FixConfidence.HIGH,
            original_code=name,
            fixed_code=pascal,
            explanation=(
                f"Rename '{name}' to '{pascal}'. "
                "Update all references and imports throughout the codebase."
            ),
            references=[
                "https://peps.python.org/pep-0008/#class-names",
            ],
        )

    def _fallback_fix(self, rule_id: str, code_snippet: str) -> CodeFix:
        """Return a generic informational fix for unknown rule IDs."""
        return CodeFix(
            rule_id=rule_id,
            title=f"Manual review required for rule: {rule_id}",
            description=(
                f"No automated fix template is available for rule '{rule_id}'. "
                "Review the finding and apply the appropriate correction manually."
            ),
            fix_type=FixType.INFORMATIONAL,
            confidence=FixConfidence.LOW,
            original_code=code_snippet,
            fixed_code="",
            explanation=(
                "Consult the rule documentation for guidance on how to resolve this finding. "
                "Consider suppressing the finding with an inline comment if it is a known false positive."
            ),
            references=[],
        )
