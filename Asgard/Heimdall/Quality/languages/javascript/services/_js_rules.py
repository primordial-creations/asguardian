import re
from typing import List

from Asgard.Heimdall.Quality.languages.javascript.models.js_models import (
    JSFinding,
    JSRuleCategory,
    JSSeverity,
)


def _make_finding(
    file_path: str,
    line_number: int,
    rule_id: str,
    category: JSRuleCategory,
    severity: JSSeverity,
    title: str,
    description: str,
    code_snippet: str = "",
    fix_suggestion: str = "",
    column: int = 0,
) -> JSFinding:
    """Construct a JSFinding with consistent defaults."""
    return JSFinding(
        file_path=file_path,
        line_number=line_number,
        column=column,
        rule_id=rule_id,
        category=category,
        severity=severity,
        title=title,
        description=description,
        code_snippet=code_snippet.rstrip(),
        fix_suggestion=fix_suggestion,
    )


def check_no_eval(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-eval: direct use of eval()."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"\beval\s*\(")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-eval",
                category=JSRuleCategory.SECURITY,
                severity=JSSeverity.ERROR,
                title="Use of eval()",
                description="eval() executes arbitrary code and is a security risk.",
                code_snippet=line,
                fix_suggestion="Remove eval() and use a safer alternative such as JSON.parse() or Function.",
            ))
    return findings


def check_no_implied_eval(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-implied-eval: setTimeout/setInterval with string literal."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"(setTimeout|setInterval)\s*\(\s*['\"]")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-implied-eval",
                category=JSRuleCategory.SECURITY,
                severity=JSSeverity.WARNING,
                title="Implied eval via setTimeout/setInterval with string",
                description="Passing a string to setTimeout or setInterval evaluates code like eval().",
                code_snippet=line,
                fix_suggestion="Pass a function reference instead of a string.",
            ))
    return findings


def check_no_debugger(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-debugger: debugger; statement."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"\bdebugger\s*;")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-debugger",
                category=JSRuleCategory.BUG,
                severity=JSSeverity.WARNING,
                title="Debugger statement found",
                description="debugger statements should be removed before committing code.",
                code_snippet=line,
                fix_suggestion="Remove the debugger statement.",
            ))
    return findings


def check_eqeqeq(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.eqeqeq: use of == or != instead of === or !==."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    eq_pattern = re.compile(r"[^=!<>]==[^=]")
    neq_pattern = re.compile(r"[^!]!=[^=]")
    for idx, line in enumerate(lines, start=1):
        if eq_pattern.search(line) or neq_pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.eqeqeq",
                category=JSRuleCategory.BUG,
                severity=JSSeverity.WARNING,
                title="Use === and !== instead of == and !=",
                description="Loose equality operators perform type coercion and can produce unexpected results.",
                code_snippet=line,
                fix_suggestion="Replace == with === and != with !==.",
            ))
    return findings


def check_no_alert(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-alert: use of alert()."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"\balert\s*\(")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-alert",
                category=JSRuleCategory.CODE_SMELL,
                severity=JSSeverity.WARNING,
                title="Use of alert()",
                description="alert() is a UI blocking call that should not be used in production code.",
                code_snippet=line,
                fix_suggestion="Remove alert() and use a proper notification mechanism.",
            ))
    return findings
