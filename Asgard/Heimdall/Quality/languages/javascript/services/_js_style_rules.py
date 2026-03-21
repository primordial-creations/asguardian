import re
from typing import List

from Asgard.Heimdall.Quality.languages.javascript.models.js_models import (
    JSFinding,
    JSRuleCategory,
    JSSeverity,
)
from Asgard.Heimdall.Quality.languages.javascript.services._js_rules import _make_finding


def check_no_var(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-var: use of var instead of let/const."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"\bvar\s+")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-var",
                category=JSRuleCategory.CODE_SMELL,
                severity=JSSeverity.WARNING,
                title="Use let or const instead of var",
                description="var has function scope and hoisting behavior that can cause subtle bugs.",
                code_snippet=line,
                fix_suggestion="Replace var with const (preferred) or let.",
            ))
    return findings


def check_no_empty_block(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-empty-block: empty block {}."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"\{\s*\}")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-empty-block",
                category=JSRuleCategory.CODE_SMELL,
                severity=JSSeverity.INFO,
                title="Empty block statement",
                description="Empty blocks are likely unintentional and may hide incomplete logic.",
                code_snippet=line,
                fix_suggestion="Add a comment or implement the block body.",
            ))
    return findings


def check_no_console(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-console: use of console.log/warn/error/debug."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"console\.(log|warn|error|debug)\s*\(")
    for idx, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if match:
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-console",
                category=JSRuleCategory.CODE_SMELL,
                severity=JSSeverity.INFO,
                title=f"Use of console.{match.group(1)}()",
                description="Console logging should be removed or replaced with a proper logger in production.",
                code_snippet=line,
                fix_suggestion="Remove or replace with a structured logging library.",
            ))
    return findings


def check_max_file_lines(file_path: str, lines: List[str], enabled: bool, max_lines: int) -> List[JSFinding]:
    """js.max-file-lines: file exceeds configured maximum line count."""
    if not enabled:
        return []
    count = len(lines)
    if count > max_lines:
        return [_make_finding(
            file_path=file_path,
            line_number=1,
            rule_id="js.max-file-lines",
            category=JSRuleCategory.CODE_SMELL,
            severity=JSSeverity.WARNING,
            title=f"File exceeds {max_lines} lines ({count} lines)",
            description=(
                f"This file has {count} lines which exceeds the configured maximum of "
                f"{max_lines}. Large files are harder to maintain."
            ),
            fix_suggestion="Split the file into smaller, more focused modules.",
        )]
    return []


def check_complexity(file_path: str, lines: List[str], enabled: bool, max_complexity: int) -> List[JSFinding]:
    """js.complexity: file-level cyclomatic complexity heuristic."""
    if not enabled:
        return []
    source = "\n".join(lines)
    decision_keywords = [
        r"\bif\b",
        r"\belse if\b",
        r"\bfor\b",
        r"\bwhile\b",
        r"\bcase\b",
        r"\bcatch\b",
        r"&&",
        r"\|\|",
        r"\?",
    ]
    total = sum(len(re.findall(kw, source)) for kw in decision_keywords)
    threshold = max_complexity * 5
    if total > threshold:
        return [_make_finding(
            file_path=file_path,
            line_number=1,
            rule_id="js.complexity",
            category=JSRuleCategory.COMPLEXITY,
            severity=JSSeverity.WARNING,
            title=f"High file-level complexity (score: {total})",
            description=(
                f"The file has an estimated complexity score of {total} which exceeds "
                f"the threshold of {threshold} (max_complexity={max_complexity} * 5). "
                "Consider splitting complex logic into smaller functions."
            ),
            fix_suggestion="Extract complex logic into well-named helper functions.",
        )]
    return []


def check_no_trailing_spaces(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.no-trailing-spaces: lines with trailing whitespace."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    pattern = re.compile(r"\s+$")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.no-trailing-spaces",
                category=JSRuleCategory.STYLE,
                severity=JSSeverity.INFO,
                title="Trailing whitespace",
                description="This line has trailing whitespace characters.",
                code_snippet=line,
                fix_suggestion="Remove trailing whitespace.",
            ))
    return findings


def check_max_line_length(file_path: str, lines: List[str], enabled: bool) -> List[JSFinding]:
    """js.max-line-length: lines exceeding 120 characters."""
    if not enabled:
        return []
    findings: List[JSFinding] = []
    for idx, line in enumerate(lines, start=1):
        if len(line) > 120:
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="js.max-line-length",
                category=JSRuleCategory.STYLE,
                severity=JSSeverity.INFO,
                title=f"Line exceeds 120 characters ({len(line)} chars)",
                description=f"This line is {len(line)} characters long, exceeding the 120-character limit.",
                code_snippet=line[:120] + "...",
                fix_suggestion="Break the line into shorter segments.",
            ))
    return findings
