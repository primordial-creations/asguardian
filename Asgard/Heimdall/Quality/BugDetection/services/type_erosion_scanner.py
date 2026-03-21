"""
Heimdall Type Erosion Scanner

Detects patterns that weaken Python's type safety and make type checking less effective:
1. `Any` as a parameter or return type annotation        (MEDIUM)
2. `typing.cast()` calls — runtime type lie              (LOW)
3. `# type: ignore` comments — suppressed type errors   (LOW)
4. `Union` with 4+ types — suggests Protocol or base class (LOW)
5. Public functions/methods missing return type annotation (LOW)
"""

import ast
import re
from pathlib import Path
from typing import List, Optional, Tuple

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugSeverity,
)

_TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore")


def _snippet(lines: List[str], n: int) -> str:
    idx = n - 1
    return lines[idx].strip() if 0 <= idx < len(lines) else ""


def _is_any_annotation(node: Optional[ast.AST]) -> bool:
    """Return True if the annotation node represents `Any` or `typing.Any`."""
    if node is None:
        return False
    if isinstance(node, ast.Name) and node.id == "Any":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "Any":
        return True
    return False


def _union_member_count(node: ast.AST) -> int:
    """
    Return the number of type arguments in a Union annotation,
    or 0 if the node is not a Union.
    """
    if not isinstance(node, ast.Subscript):
        return 0
    name = node.value
    if not (isinstance(name, ast.Name) and name.id == "Union"):
        return 0
    # Python 3.9+: slice is the Tuple/Name directly
    # Python 3.8: slice is wrapped in ast.Index
    slice_node = node.slice
    if hasattr(ast, "Index") and isinstance(slice_node, ast.Index):  # type: ignore[attr-defined]
        slice_node = slice_node.value  # type: ignore[attr-defined]
    if isinstance(slice_node, ast.Tuple):
        return len(slice_node.elts)
    return 1  # Union[X] — degenerate single-type union


def _all_args(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list:
    """Collect all argument nodes (excluding self/cls) from a function definition."""
    args = (
        func.args.args
        + func.args.posonlyargs
        + func.args.kwonlyargs
    )
    if func.args.vararg:
        args = args + [func.args.vararg]
    if func.args.kwarg:
        args = args + [func.args.kwarg]
    return [a for a in args if a.arg not in ("self", "cls")]


class TypeErosionScanner:
    """
    Detects type annotation patterns that weaken the type system.

    Finds Any annotations, cast() calls, type: ignore comments,
    over-wide Union types, and missing return annotations on public APIs.
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None) -> None:
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """Analyse a single Python source file for type erosion patterns."""
        source = "\n".join(lines)
        fp = str(file_path)
        try:
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []

        findings: List[BugFinding] = []
        findings.extend(self._detect_any_annotations(tree, fp, lines))
        findings.extend(self._detect_cast_calls(tree, fp, lines))
        findings.extend(self._detect_type_ignore(lines, fp))
        findings.extend(self._detect_union_sprawl(tree, fp, lines))
        findings.extend(self._detect_missing_return_annotations(tree, fp, lines))
        return findings

    # ── 1. Any annotations ────────────────────────────────────────────────────

    def _detect_any_annotations(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for arg in _all_args(node):
                if _is_any_annotation(arg.annotation):
                    findings.append(BugFinding(
                        file_path=fp,
                        line_number=node.lineno,
                        category=BugCategory.TYPE_EROSION,
                        severity=BugSeverity.MEDIUM,
                        title=f"Parameter `{arg.arg}` Annotated as `Any` in `{node.name}`",
                        description=(
                            f"Line {node.lineno}: Parameter `{arg.arg}` is typed as `Any`, "
                            "which disables all type checking for every operation on this value. "
                            "Callers also lose type safety because the parameter accepts anything."
                        ),
                        code_snippet=_snippet(lines, node.lineno),
                        fix_suggestion=(
                            "Replace `Any` with the most specific type possible. "
                            "Use `Union[A, B]` if multiple types are valid, or a `Protocol` "
                            "if only specific methods/attributes are required."
                        ),
                    ))

            if _is_any_annotation(node.returns):
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=node.lineno,
                    category=BugCategory.TYPE_EROSION,
                    severity=BugSeverity.MEDIUM,
                    title=f"Return Type of `{node.name}` Annotated as `Any`",
                    description=(
                        f"Line {node.lineno}: `{node.name}` declares its return type as `Any`. "
                        "Any expression that consumes this return value immediately loses "
                        "type safety downstream."
                    ),
                    code_snippet=_snippet(lines, node.lineno),
                    fix_suggestion=(
                        "Specify the concrete return type. Use `-> None` for procedures, "
                        "or a union/protocol for polymorphic returns."
                    ),
                ))
        return findings

    # ── 2. cast() calls ───────────────────────────────────────────────────────

    def _detect_cast_calls(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_cast = (
                (isinstance(func, ast.Name) and func.id == "cast")
                or (isinstance(func, ast.Attribute) and func.attr == "cast")
            )
            if is_cast:
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=node.lineno,
                    category=BugCategory.TYPE_EROSION,
                    severity=BugSeverity.LOW,
                    title="`typing.cast()` Bypasses Type Checking",
                    description=(
                        f"Line {node.lineno}: `cast()` tells the type checker to treat a value "
                        "as a different type with NO runtime verification. Each `cast()` call "
                        "is effectively a lie to the type checker that can mask real type errors."
                    ),
                    code_snippet=_snippet(lines, node.lineno),
                    fix_suggestion=(
                        "Consider using an `isinstance()` guard to narrow the type properly, "
                        "or refactoring so the value already has the correct type without casting."
                    ),
                ))
        return findings

    # ── 3. # type: ignore comments ────────────────────────────────────────────

    def _detect_type_ignore(self, lines: List[str], fp: str) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for i, line in enumerate(lines):
            if _TYPE_IGNORE_RE.search(line):
                # Only flag unqualified ignores; `# type: ignore[specific]` is acceptable
                if re.search(r"#\s*type:\s*ignore\s*$", line):
                    severity = BugSeverity.LOW
                    extra = "Consider using `# type: ignore[error-code]` to suppress only the specific error."
                else:
                    severity = BugSeverity.LOW
                    extra = "This is a qualified ignore — still worth reviewing periodically."
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=i + 1,
                    category=BugCategory.TYPE_EROSION,
                    severity=severity,
                    title="`# type: ignore` Suppresses Type Checker Warning",
                    description=(
                        f"Line {i + 1}: `# type: ignore` silences a type checker error. "
                        "Each occurrence is a location where the type system's safety net "
                        "has been disabled, potentially hiding real type mismatches."
                    ),
                    code_snippet=line.strip(),
                    fix_suggestion=(
                        "Fix the underlying type error rather than suppressing it. " + extra
                    ),
                ))
        return findings

    # ── 4. Union with too many members ────────────────────────────────────────

    def _detect_union_sprawl(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            annotations: List[Tuple[ast.AST, int]] = []
            for arg in _all_args(node):
                if arg.annotation:
                    annotations.append((arg.annotation, node.lineno))
            if node.returns:
                annotations.append((node.returns, node.lineno))

            for annotation, lineno in annotations:
                count = _union_member_count(annotation)
                if count >= 4:
                    findings.append(BugFinding(
                        file_path=fp,
                        line_number=lineno,
                        category=BugCategory.TYPE_EROSION,
                        severity=BugSeverity.LOW,
                        title=f"Wide `Union` With {count} Types — Consider Protocol or Base Class",
                        description=(
                            f"Line {lineno}: A `Union` with {count} types handles too many "
                            "unrelated cases in one signature. Wide unions erode type safety "
                            "by accepting an overly broad range of inputs, and make callers "
                            "responsible for managing all the possible types."
                        ),
                        code_snippet=_snippet(lines, lineno),
                        fix_suggestion=(
                            "Define a `Protocol` with the required methods/attributes, "
                            "or introduce a base class/ABC so the union collapses to one type."
                        ),
                    ))
        return findings

    # ── 5. Missing return type annotations on public functions ────────────────

    def _detect_missing_return_annotations(
        self, tree: ast.AST, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Only flag public, non-dunder names
            if node.name.startswith("_"):
                continue
            if node.returns is None:
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=node.lineno,
                    category=BugCategory.TYPE_EROSION,
                    severity=BugSeverity.LOW,
                    title=f"Public Function `{node.name}` Missing Return Type Annotation",
                    description=(
                        f"Line {node.lineno}: `{node.name}` has no return type annotation. "
                        "Without it, the return type implicitly becomes `Any`, disabling "
                        "type checking for all callers of this function."
                    ),
                    code_snippet=_snippet(lines, node.lineno),
                    fix_suggestion=(
                        f"Add a return annotation: `def {node.name}(...) -> ReturnType:`. "
                        "Use `-> None` for procedures that do not return a meaningful value."
                    ),
                ))
        return findings
