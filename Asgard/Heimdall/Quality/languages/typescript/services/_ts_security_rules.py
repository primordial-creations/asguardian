"""TypeScript-specific security rules (regex-based)."""

import re
from typing import List

from Asgard.Heimdall.Quality.languages.javascript.models.js_models import (
    JSFinding,
    JSRuleCategory,
    JSSeverity,
)
from Asgard.Heimdall.Quality.languages.javascript.services._js_rules import _make_finding


def check_unsafe_any(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """ts.unsafe-any: 'as any' cast in security-sensitive context."""
    if not enabled:
        return []
    pattern = re.compile(r'\bas\s+any\b')
    context_pattern = re.compile(r'\b(?:fetch|axios|request|query|exec)\b')
    findings: List[JSFinding] = []
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line) and context_pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="ts.unsafe-any",
                category=JSRuleCategory.SECURITY,
                severity=JSSeverity.ERROR,
                title="Unsafe 'as any' cast in security-sensitive context",
                description=(
                    "Casting to 'any' near fetch/axios/request/query/exec bypasses type safety "
                    "and can hide injection or data-integrity vulnerabilities."
                ),
                code_snippet=line,
                fix_suggestion="Use a properly typed interface or validate the data before casting.",
            ))
    return findings


def check_no_unsafe_assertion(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """ts.no-unsafe-assertion: non-null assertion on user-supplied data."""
    if not enabled:
        return []
    pattern = re.compile(r'(?:req\.|request\.|params\.|query\.)\w+!')
    findings: List[JSFinding] = []
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="ts.no-unsafe-assertion",
                category=JSRuleCategory.SECURITY,
                severity=JSSeverity.ERROR,
                title="Non-null assertion on user-supplied data",
                description=(
                    "Using '!' on req./request./params./query. properties asserts the value is "
                    "non-null without validation, which can cause runtime errors or security issues."
                ),
                code_snippet=line,
                fix_suggestion="Validate user-supplied data before accessing it; avoid the '!' operator.",
            ))
    return findings


def check_prototype_pollution(file_path: str, lines: List[str], enabled: bool = True) -> List[JSFinding]:
    """ts.prototype-pollution: __proto__ assignment in TypeScript files."""
    if not enabled:
        return []
    pattern = re.compile(r'__proto__\s*=')
    findings: List[JSFinding] = []
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="ts.prototype-pollution",
                category=JSRuleCategory.SECURITY,
                severity=JSSeverity.ERROR,
                title="Prototype Pollution via __proto__ Assignment",
                description=(
                    "Assigning to __proto__ can pollute the prototype chain and cause security vulnerabilities."
                ),
                code_snippet=line,
                fix_suggestion="Use Object.create(null) for safe property maps and avoid __proto__ assignments.",
            ))
    return findings


_TS_SECURITY_RULES = [
    check_unsafe_any,
    check_no_unsafe_assertion,
    check_prototype_pollution,
]
