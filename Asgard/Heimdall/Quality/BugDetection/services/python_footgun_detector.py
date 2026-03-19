"""
Heimdall Python Footgun Detector

Detects classic Python language traps that are easy to introduce and hard to spot:
1. Mutable default arguments: def f(x=[]) — default is shared across ALL calls  (HIGH)
2. Late binding closures: lambda/nested func in for-loop captures loop var by ref (HIGH)
3. Identity comparison with non-singleton literals: x is 1, x is "str"           (MEDIUM)
4. Builtin shadowing: list=[], id=1, type="foo" — breaks built-ins in scope       (MEDIUM)
"""

import ast
import builtins
from pathlib import Path
from typing import List, Optional, Set

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugSeverity,
)

# Built-ins where shadowing causes the most damage
_IMPORTANT_BUILTINS: Set[str] = {
    "list", "dict", "set", "tuple", "str", "int", "float", "bool", "bytes",
    "type", "object", "super", "isinstance", "issubclass", "id", "len",
    "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "print", "input", "open", "abs", "max", "min", "sum", "any", "all",
    "hash", "repr", "iter", "next", "getattr", "setattr", "hasattr", "delattr",
    "callable", "vars", "dir", "property", "classmethod", "staticmethod",
}

_MUTABLE_CALL_NAMES: Set[str] = {
    "list", "dict", "set", "defaultdict", "OrderedDict", "deque", "Counter",
    "array", "bytearray",
}


def _snippet(lines: List[str], n: int) -> str:
    idx = n - 1
    return lines[idx].strip() if 0 <= idx < len(lines) else ""


def _is_mutable_default(node: ast.AST) -> Optional[str]:
    """
    Return a human-readable description if the node is a mutable default value,
    or None if it is safe.
    """
    if isinstance(node, ast.List):
        return "list literal `[]`"
    if isinstance(node, ast.Dict):
        return "dict literal `{}`"
    if isinstance(node, ast.Set):
        return "set literal"
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _MUTABLE_CALL_NAMES:
            return f"`{node.func.id}()` call"
        if isinstance(node.func, ast.Attribute) and node.func.attr in _MUTABLE_CALL_NAMES:
            return f"`{node.func.attr}()` call"
    return None


class PythonFootgunDetector:
    """
    Detects classic Python language pitfalls using AST analysis.

    These patterns do not cause syntax errors but introduce subtle, hard-to-find
    bugs that only manifest at runtime, often non-deterministically.
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None) -> None:
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """Analyse a single Python source file for common footguns."""
        source = "\n".join(lines)
        fp = str(file_path)
        try:
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []

        findings: List[BugFinding] = []
        findings.extend(self._detect_mutable_defaults(tree, fp, lines))
        findings.extend(self._detect_late_binding(tree, fp, lines))
        findings.extend(self._detect_is_literal(tree, fp, lines))
        findings.extend(self._detect_builtin_shadow(tree, fp, lines))
        return findings

    # ── 1. Mutable default arguments ──────────────────────────────────────────

    def _detect_mutable_defaults(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Positional defaults (right-aligned to args list)
            all_defaults = list(node.args.defaults)
            # Keyword-only defaults
            all_defaults += [d for d in node.args.kw_defaults if d is not None]

            for default in all_defaults:
                desc = _is_mutable_default(default)
                if desc:
                    findings.append(BugFinding(
                        file_path=fp,
                        line_number=node.lineno,
                        category=BugCategory.MUTABLE_DEFAULT_ARG,
                        severity=BugSeverity.HIGH,
                        title=f"Mutable Default Argument in `{node.name}`",
                        description=(
                            f"Line {node.lineno}: `{node.name}` uses a {desc} as a default "
                            "argument. Default values are evaluated ONCE at function definition "
                            "time and shared across every call. Mutations to the default "
                            "accumulate across calls — a frequent source of hard-to-trace bugs."
                        ),
                        code_snippet=_snippet(lines, node.lineno),
                        fix_suggestion=(
                            f"Use `None` as the default and create the mutable object inside "
                            f"the function: `def {node.name}(x=None): x = x if x is not None else []`"
                        ),
                    ))
        return findings

    # ── 2. Late-binding closures in loops ─────────────────────────────────────

    def _detect_late_binding(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue

            # Collect loop variable names
            loop_vars: Set[str] = set()
            for child in ast.walk(node.target):
                if isinstance(child, ast.Name):
                    loop_vars.add(child.id)

            if not loop_vars:
                continue

            # Find lambdas or nested functions in the loop body that capture loop vars
            for body_node in ast.walk(node):
                if body_node is node:
                    continue
                if not isinstance(body_node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                # Check if the closure references any loop variable as a free variable
                # (i.e. a Name Load that is NOT a parameter of the closure itself)
                closure_params: Set[str] = set()
                if isinstance(body_node, ast.Lambda):
                    for arg in body_node.args.args:
                        closure_params.add(arg.arg)
                    for arg in body_node.args.kwonlyargs:
                        closure_params.add(arg.arg)
                    for arg in body_node.args.defaults:
                        pass  # defaults evaluated at def time — not free vars
                else:
                    for arg in body_node.args.args:
                        closure_params.add(arg.arg)

                captured: Set[str] = set()
                for name_node in ast.walk(body_node):
                    if (
                        isinstance(name_node, ast.Name)
                        and isinstance(name_node.ctx, ast.Load)
                        and name_node.id in loop_vars
                        and name_node.id not in closure_params
                    ):
                        captured.add(name_node.id)

                if captured:
                    line = body_node.lineno if hasattr(body_node, "lineno") else node.lineno
                    func_type = "lambda" if isinstance(body_node, ast.Lambda) else "nested function"
                    var_list = ", ".join(sorted(captured))
                    findings.append(BugFinding(
                        file_path=fp,
                        line_number=line,
                        category=BugCategory.LATE_BINDING_CLOSURE,
                        severity=BugSeverity.HIGH,
                        title=f"Late-Binding Closure Captures Loop Variable `{var_list}`",
                        description=(
                            f"Line {line}: A {func_type} inside a `for` loop references loop "
                            f"variable(s) `{var_list}` by reference. All closures created in "
                            "the loop will see the FINAL value of the loop variable(s), not the "
                            "value at the time each closure was created."
                        ),
                        code_snippet=_snippet(lines, line),
                        fix_suggestion=(
                            f"Capture the current value using a default argument: "
                            f"`lambda {var_list}={var_list}: ...` or "
                            f"`def f({var_list}={var_list}): ...`"
                        ),
                    ))
        return findings

    # ── 3. Identity comparison with non-singleton literals ────────────────────

    def _detect_is_literal(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for op, comparator in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.Is, ast.IsNot)):
                    continue
                if not isinstance(comparator, ast.Constant):
                    continue
                # None, True, False are singletons — `is` is correct for them
                if comparator.value in (None, True, False):
                    continue
                op_str = "is not" if isinstance(op, ast.IsNot) else "is"
                eq_str = "!=" if isinstance(op, ast.IsNot) else "=="
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=node.lineno,
                    category=BugCategory.IS_LITERAL_COMPARISON,
                    severity=BugSeverity.MEDIUM,
                    title=f"Identity Comparison (`{op_str}`) With Value Literal `{comparator.value!r}`",
                    description=(
                        f"Line {node.lineno}: `{op_str} {comparator.value!r}` uses identity "
                        "comparison (memory address) instead of value equality. Small integers "
                        "and interned strings may pass by coincidence due to CPython's interning, "
                        "but this is an implementation detail — not guaranteed by the language spec."
                    ),
                    code_snippet=_snippet(lines, node.lineno),
                    fix_suggestion=(
                        f"Replace `{op_str} {comparator.value!r}` with "
                        f"`{eq_str} {comparator.value!r}` for value comparison."
                    ),
                ))
        return findings

    # ── 4. Builtin shadowing ───────────────────────────────────────────────────

    def _detect_builtin_shadow(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id in _IMPORTANT_BUILTINS
                ):
                    findings.append(BugFinding(
                        file_path=fp,
                        line_number=node.lineno,
                        category=BugCategory.BUILTIN_SHADOWING,
                        severity=BugSeverity.MEDIUM,
                        title=f"Built-in `{target.id}` Shadowed by Local Assignment",
                        description=(
                            f"Line {node.lineno}: The name `{target.id}` is assigned a value, "
                            "shadowing the built-in of the same name. Code in the same scope "
                            "that relies on the built-in `{name}` will receive this value "
                            "instead, causing confusing AttributeError or TypeError bugs."
                        ).replace("{name}", target.id),
                        code_snippet=_snippet(lines, node.lineno),
                        fix_suggestion=(
                            f"Rename the variable to something that does not shadow "
                            f"the `{target.id}` built-in (e.g. `{target.id}_value` or `_{target.id}`)."
                        ),
                    ))
        return findings
