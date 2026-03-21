import re
from typing import List

from Asgard.Heimdall.Quality.languages.shell.models.shell_models import (
    ShellFinding,
    ShellRuleCategory,
    ShellSeverity,
)
from Asgard.Heimdall.Quality.languages.shell.services._shell_rules import _make_finding


def check_missing_set_e(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.missing-set-e: file has no 'set -e' or 'set -o errexit'."""
    if not enabled:
        return []
    source = "\n".join(lines)
    has_set_e = bool(re.search(r"set\s+-[a-z]*e[a-z]*", source)) or bool(
        re.search(r"set\s+-o\s+errexit", source)
    )
    if not has_set_e:
        return [_make_finding(
            file_path=file_path,
            line_number=1,
            rule_id="shell.missing-set-e",
            category=ShellRuleCategory.BUG,
            severity=ShellSeverity.INFO,
            title="Missing 'set -e' (errexit)",
            description=(
                "Without 'set -e', the script will continue executing after a command fails, "
                "potentially producing incorrect results silently."
            ),
            fix_suggestion="Add 'set -e' or 'set -o errexit' near the top of the script.",
        )]
    return []


def check_missing_set_u(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.missing-set-u: file has no 'set -u' or 'set -o nounset'."""
    if not enabled:
        return []
    source = "\n".join(lines)
    has_set_u = bool(re.search(r"set\s+-[a-z]*u[a-z]*", source)) or bool(
        re.search(r"set\s+-o\s+nounset", source)
    )
    if not has_set_u:
        return [_make_finding(
            file_path=file_path,
            line_number=1,
            rule_id="shell.missing-set-u",
            category=ShellRuleCategory.BUG,
            severity=ShellSeverity.INFO,
            title="Missing 'set -u' (nounset)",
            description=(
                "Without 'set -u', unset variables expand to an empty string silently, "
                "which can lead to data loss (e.g., 'rm -rf /$UNSET_VAR')."
            ),
            fix_suggestion="Add 'set -u' or 'set -o nounset' near the top of the script.",
        )]
    return []


def check_cd_without_check(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.cd-without-check: cd not followed by || or &&."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r"\bcd\s+[^|&;]*$")
    for idx, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.cd-without-check",
                category=ShellRuleCategory.BUG,
                severity=ShellSeverity.WARNING,
                title="cd without error check",
                description=(
                    "If cd fails (e.g., directory does not exist), subsequent commands will run "
                    "in the wrong directory. Always check the return value of cd."
                ),
                code_snippet=line,
                fix_suggestion="Use 'cd /some/path || exit 1' or 'cd /some/path || { echo \"fail\"; exit 1; }'.",
            ))
    return findings


def check_unquoted_dollar_star(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.unquoted-dollar-star: $* not inside double quotes."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r'(?<!")\$\*(?!")')
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.unquoted-dollar-star",
                category=ShellRuleCategory.BUG,
                severity=ShellSeverity.WARNING,
                title="Unquoted $*",
                description=(
                    "Unquoted $* causes word splitting and glob expansion. "
                    "Use \"$@\" to preserve argument boundaries."
                ),
                code_snippet=line,
                fix_suggestion='Replace $* with "$@" to correctly handle arguments with spaces.',
            ))
    return findings


def check_trailing_whitespace(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.trailing-whitespace: lines with trailing whitespace."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r"\s+$")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.trailing-whitespace",
                category=ShellRuleCategory.STYLE,
                severity=ShellSeverity.INFO,
                title="Trailing whitespace",
                description="This line has trailing whitespace characters.",
                code_snippet=line,
                fix_suggestion="Remove trailing whitespace.",
            ))
    return findings


def check_max_line_length(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.max-line-length: lines exceeding 120 characters."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    for idx, line in enumerate(lines, start=1):
        if len(line) > 120:
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.max-line-length",
                category=ShellRuleCategory.STYLE,
                severity=ShellSeverity.INFO,
                title=f"Line exceeds 120 characters ({len(line)} chars)",
                description=f"This line is {len(line)} characters long, exceeding the 120-character limit.",
                code_snippet=line[:120] + "...",
                fix_suggestion="Break the line with a backslash continuation or refactor the command.",
            ))
    return findings


def check_function_keyword(file_path: str, lines: List[str], enabled: bool) -> List[ShellFinding]:
    """shell.function-keyword: non-POSIX 'function' keyword used."""
    if not enabled:
        return []
    findings: List[ShellFinding] = []
    pattern = re.compile(r"\bfunction\s+\w+\s*\(\)")
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(_make_finding(
                file_path=file_path,
                line_number=idx,
                rule_id="shell.function-keyword",
                category=ShellRuleCategory.PORTABILITY,
                severity=ShellSeverity.INFO,
                title="Non-POSIX 'function' keyword",
                description=(
                    "The 'function' keyword is a bash extension and not POSIX-compliant. "
                    "Scripts intended to be portable should use the 'name() {}' syntax instead."
                ),
                code_snippet=line,
                fix_suggestion="Replace 'function foo()' with 'foo()'.",
            ))
    return findings
