"""
Heimdall Exception Quality Detector

Detects poor exception handling patterns that hide bugs and make debugging harder:
1. Bare `except:` clause — catches EVERYTHING including SystemExit/KeyboardInterrupt (HIGH)
2. Exception swallowing — empty handler body (pass / ...) that silently discards errors (HIGH)
3. Overly broad `except Exception` or `except BaseException` without re-raise (MEDIUM)
4. Missing exception chain — `raise X` inside `except` without `from e` (MEDIUM)
"""

import ast
from pathlib import Path
from typing import List, Optional

from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugCategory,
    BugDetectionConfig,
    BugFinding,
    BugSeverity,
)


def _snippet(lines: List[str], n: int) -> str:
    idx = n - 1
    return lines[idx].strip() if 0 <= idx < len(lines) else ""


def _ast_unparse(node: ast.AST) -> str:
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:
            pass
    if isinstance(node, ast.Name):
        return node.id
    return "..."


def _is_effectively_empty(stmts: list) -> bool:
    """Return True if the handler body does nothing meaningful."""
    if not stmts:
        return True
    if len(stmts) == 1:
        stmt = stmts[0]
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            # `...` or an empty string — treat as empty
            if stmt.value.value is ... or stmt.value.value == "":
                return True
    return False


def _handler_has_bare_reraise(handler: ast.ExceptHandler) -> bool:
    """Return True if the handler contains a bare `raise` (re-raise original)."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise) and node.exc is None:
            return True
    return False


def _handler_has_chained_raise(handler: ast.ExceptHandler) -> bool:
    """Return True if handler has `raise X from e` (explicit chain)."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise) and node.exc is not None and node.cause is not None:
            return True
    return False


def _handler_has_new_raise(handler: ast.ExceptHandler) -> bool:
    """Return True if handler raises a NEW exception (not bare re-raise)."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise) and node.exc is not None:
            return True
    return False


class ExceptionQualityDetector:
    """
    Detects poor exception handling patterns using Python AST analysis.

    Reports:
    - Bare except clauses (catches absolutely everything)
    - Silently swallowed exceptions (empty handler body)
    - Overly broad exception catches without re-raise
    - Missing exception chaining (raise X without from e)
    """

    def __init__(self, config: Optional[BugDetectionConfig] = None) -> None:
        self.config = config or BugDetectionConfig()

    def analyze_file(self, file_path: Path, lines: List[str]) -> List[BugFinding]:
        """Analyse a single Python source file for exception quality issues."""
        source = "\n".join(lines)
        fp = str(file_path)
        try:
            tree = ast.parse(source, filename=fp)
        except SyntaxError:
            return []

        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    findings.extend(self._check_handler(handler, fp, lines))
        return findings

    def _check_handler(
        self, handler: ast.ExceptHandler, fp: str, lines: List[str]
    ) -> List[BugFinding]:
        findings: List[BugFinding] = []

        # ── 1. Bare `except:` ──────────────────────────────────────────────────
        if handler.type is None:
            findings.append(BugFinding(
                file_path=fp,
                line_number=handler.lineno,
                category=BugCategory.EXCEPTION_SWALLOWING,
                severity=BugSeverity.HIGH,
                title="Bare `except:` Clause (Catches Everything)",
                description=(
                    f"Line {handler.lineno}: A bare `except:` clause catches ALL exceptions, "
                    "including `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`. "
                    "This makes it impossible to interrupt the program normally and hides "
                    "unexpected errors that should propagate."
                ),
                code_snippet=_snippet(lines, handler.lineno),
                fix_suggestion=(
                    "Specify the exception type(s) you actually expect: "
                    "`except (ValueError, TypeError):` or at minimum `except Exception:`."
                ),
            ))
            # Still check for empty body even on bare except
            if _is_effectively_empty(handler.body):
                findings.append(BugFinding(
                    file_path=fp,
                    line_number=handler.lineno,
                    category=BugCategory.EXCEPTION_SWALLOWING,
                    severity=BugSeverity.CRITICAL,
                    title="Bare `except: pass` — Exception Completely Swallowed",
                    description=(
                        f"Line {handler.lineno}: A bare `except: pass` catches every possible "
                        "exception and discards it silently. This is one of the most dangerous "
                        "patterns in Python — bugs, crashes, and unexpected states all disappear."
                    ),
                    code_snippet=_snippet(lines, handler.lineno),
                    fix_suggestion=(
                        "At minimum: `except Exception as e: logger.exception('Unexpected error: %s', e)`. "
                        "Better: catch only the specific exception you expect and let others propagate."
                    ),
                ))
            return findings

        exc_name = _ast_unparse(handler.type)

        # ── 2. Empty handler body (swallowed exception) ────────────────────────
        if _is_effectively_empty(handler.body):
            findings.append(BugFinding(
                file_path=fp,
                line_number=handler.lineno,
                category=BugCategory.EXCEPTION_SWALLOWING,
                severity=BugSeverity.HIGH,
                title=f"`except {exc_name}: pass` — Exception Swallowed Silently",
                description=(
                    f"Line {handler.lineno}: `except {exc_name}:` catches the exception "
                    "but does nothing — no logging, no re-raise, no recovery action. "
                    "The error is silently discarded, making debugging extremely difficult."
                ),
                code_snippet=_snippet(lines, handler.lineno),
                fix_suggestion=(
                    "At minimum, log the exception: `logger.exception('Unexpected %s', e)`. "
                    "Or re-raise with `raise` to propagate it. "
                    "Use `pass` only when you can prove the exception is truly ignorable."
                ),
            ))
            return findings

        # ── 3. Overly broad catch without re-raise ─────────────────────────────
        is_broad = (
            isinstance(handler.type, ast.Name)
            and handler.type.id in ("Exception", "BaseException")
        )
        if is_broad and not _handler_has_bare_reraise(handler) and isinstance(handler.type, ast.Name):
            broad_name = handler.type.id
            findings.append(BugFinding(
                file_path=fp,
                line_number=handler.lineno,
                category=BugCategory.EXCEPTION_SWALLOWING,
                severity=BugSeverity.MEDIUM,
                title=f"Overly Broad `except {broad_name}` Without Re-raise",
                description=(
                    f"Line {handler.lineno}: Catching `{broad_name}` is very broad and will "
                    "mask unexpected programming errors (IndexError, AttributeError, etc.). "
                    "Without a bare `raise` at the end, bugs can be silently absorbed."
                ),
                code_snippet=_snippet(lines, handler.lineno),
                fix_suggestion=(
                    "Narrow the exception type to only what you expect, "
                    "or add a bare `raise` after handling to re-propagate unexpected errors."
                ),
            ))

        # ── 4. Missing exception chain (`raise X` without `from e`) ───────────
        if (
            _handler_has_new_raise(handler)
            and not _handler_has_chained_raise(handler)
            and not _handler_has_bare_reraise(handler)
        ):
            findings.append(BugFinding(
                file_path=fp,
                line_number=handler.lineno,
                category=BugCategory.EXCEPTION_CHAINING,
                severity=BugSeverity.MEDIUM,
                title="Missing Exception Chain (`raise X from e`)",
                description=(
                    f"Line {handler.lineno}: A new exception is raised inside an `except` "
                    "block without `from e`. This loses the original traceback context, "
                    "making it much harder to identify the root cause."
                ),
                code_snippet=_snippet(lines, handler.lineno),
                fix_suggestion=(
                    "Preserve the exception chain: `raise NewException('...') from original_exc`. "
                    "Use `raise NewException(...) from None` only when you intentionally "
                    "want to hide the original error (e.g. to avoid leaking internals)."
                ),
            ))

        return findings
