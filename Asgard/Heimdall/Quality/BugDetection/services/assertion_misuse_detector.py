"""
Heimdall Assertion Misuse Detector

Detects incorrect or dangerous use of Python's assert statement:
1. assert (condition, "msg") — tuple is always truthy, assertion NEVER fails
2. assert with always-falsy constant (assert False, assert None, assert 0)
3. assert isinstance(param, Type) in __init__ — disabled by -O optimise flag
4. assert with method call side-effects — call disappears in optimised mode
"""

import ast
from pathlib import Path
from typing import List, Optional, Tuple

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugSeverity,
)


def _snippet(lines: List[str], n: int) -> str:
    idx = n - 1
    return lines[idx].strip() if 0 <= idx < len(lines) else ""


def _is_always_falsy(node: ast.AST) -> bool:
    """Return True if the node is a constant that always evaluates to False."""
    return isinstance(node, ast.Constant) and not node.value and node.value is not True


def _ast_unparse(node: ast.AST) -> str:
    """Safe unparse — falls back to '...' on older Python."""
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:
            pass
    return "..."


class _AssertContextVisitor(ast.NodeVisitor):
    """Collect every Assert node, annotating whether it lives inside __init__."""

    def __init__(self) -> None:
        self.asserts: List[Tuple[ast.Assert, bool]] = []  # (node, in_init)
        self._in_init: bool = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev = self._in_init
        if node.name == "__init__":
            self._in_init = True
        self.generic_visit(node)
        self._in_init = prev

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Assert(self, node: ast.Assert) -> None:
        self.asserts.append((node, self._in_init))
        # Do not recurse — there are no nested Assert nodes worth visiting.


class AssertMisuseDetector:
    """
    Detects misuse of Python assert statements using AST analysis.

    Checks:
    - Tuple trap: assert (cond, msg) is ALWAYS True
    - Always-falsy constant: assert False / None / 0
    - Type validation in __init__: assert isinstance(x, T) silenced by -O
    - Side-effect call: assert obj.mutating_method() vanishes in optimised mode
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None) -> None:
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """Analyse a single Python source file for assertion misuse."""
        source = "\n".join(lines)
        fp = str(file_path)
        try:
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []

        visitor = _AssertContextVisitor()
        visitor.visit(tree)

        findings: List[BugFinding] = []
        for node, in_init in visitor.asserts:
            findings.extend(self._check(node, in_init, fp, lines))
        return findings

    def _check(
        self,
        node: ast.Assert,
        in_init: bool,
        fp: str,
        lines: List[str],
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []

        # ── 1. assert (expr, msg) — tuple is always truthy ────────────────────
        if isinstance(node.test, ast.Tuple):
            findings.append(BugFinding(
                file_path=fp,
                line_number=node.lineno,
                category=BugCategory.ASSERTION_MISUSE,
                severity=BugSeverity.CRITICAL,
                title="Assert Tuple Trap (Never Fails)",
                description=(
                    f"Line {node.lineno}: `assert ({_ast_unparse(node.test)})` passes a tuple "
                    "as the test expression. Tuples are always truthy in Python, so this "
                    "assertion NEVER raises AssertionError — even when the condition is False. "
                    "The message argument is most likely being wrapped in the tuple accidentally."
                ),
                code_snippet=_snippet(lines, node.lineno),
                fix_suggestion=(
                    "Separate condition and message without wrapping them in a tuple: "
                    "`assert condition, 'message'` — note the comma, not parentheses around both."
                ),
            ))
            return findings  # No further checks apply to the tuple trap.

        # ── 2. assert False / None / 0 — always raises AssertionError ─────────
        if _is_always_falsy(node.test):
            findings.append(BugFinding(
                file_path=fp,
                line_number=node.lineno,
                category=BugCategory.ASSERTION_MISUSE,
                severity=BugSeverity.HIGH,
                title="Assert With Always-Falsy Constant (Always Fails)",
                description=(
                    f"Line {node.lineno}: The assertion condition is always falsy and will "
                    "unconditionally raise AssertionError. This is typically a debugging "
                    "remnant that was never removed."
                ),
                code_snippet=_snippet(lines, node.lineno),
                fix_suggestion=(
                    "Remove the statement if it is dead code, or replace with an explicit "
                    "`raise AssertionError('reason')` if the intent is to always fail."
                ),
            ))

        # ── 3. assert isinstance(param, T) in __init__ — disabled by -O ───────
        if in_init and isinstance(node.test, ast.Call):
            call = node.test
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "isinstance"
                and call.args
                and isinstance(call.args[0], ast.Name)
            ):
                param = call.args[0].id
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=node.lineno,
                    category=BugCategory.ASSERTION_MISUSE,
                    severity=BugSeverity.MEDIUM,
                    title="Assert Used for Runtime Type Validation in __init__",
                    description=(
                        f"Line {node.lineno}: `assert isinstance({param}, ...)` in __init__ "
                        "performs runtime validation that is silently removed when Python runs "
                        "with the -O (optimise) flag. This makes the type check disappear in "
                        "production optimised builds, leaving the code unprotected."
                    ),
                    code_snippet=_snippet(lines, node.lineno),
                    fix_suggestion=(
                        f"Use explicit validation instead: "
                        f"`if not isinstance({param}, ExpectedType): "
                        f"raise TypeError(f'Expected ExpectedType, got {{type({param}).__name__}}')`"
                    ),
                ))

        # ── 4. assert obj.method() — side effects removed by -O ───────────────
        if (
            isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Attribute)
        ):
            findings.append(BugFinding(
                file_path=fp,
                line_number=node.lineno,
                category=BugCategory.ASSERTION_MISUSE,
                severity=BugSeverity.MEDIUM,
                title="Assert With Method-Call Side Effects (Removed in Optimised Mode)",
                description=(
                    f"Line {node.lineno}: The assert expression calls a method as its test. "
                    "When Python runs with -O, all assert statements are completely elided — "
                    "any side effects of the method call vanish silently."
                ),
                code_snippet=_snippet(lines, node.lineno),
                fix_suggestion=(
                    "Separate the call from the assertion: capture the result first, then "
                    "assert on it (`result = obj.method(); assert result, 'reason'`), "
                    "or use explicit validation with raise."
                ),
            ))

        return findings
