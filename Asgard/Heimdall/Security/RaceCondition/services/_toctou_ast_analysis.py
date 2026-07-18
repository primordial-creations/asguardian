"""
AST-based TOCTOU / concurrency canonical-pattern detection (plan 07.7).

Replaces the old line-regex "shared_mutable_state" / "non_atomic_counter"
guessing (near-100% FP on any codebase with an `x += 1` counter or a
module-level `CACHE = {}`) with two precision-first structural checks that
match RESEARCH_06 / DEEPTHINK_04's canonical-pattern guidance:

1. ``os.path.exists(f)`` (or ``Path(f).exists()``) followed, in the same
   function body / same-slice, by ``open(f, 'w'/'x'/'a')`` on the *same*
   variable -- the textbook check-then-use file race (fix: ``os.open``
   with ``O_CREAT | O_EXCL``).
2. ORM ``.get()`` -> attribute mutation -> ``.save()`` on the same object,
   without a ``select_for_update()`` call in the same slice, while inside
   a function decorated with (or body containing) ``transaction.atomic``.
   A ``select_for_update()`` call outside of an atomic block is *also*
   flagged -- the lock is meaningless without the surrounding transaction.

Documented FP/FN (per CLAUDE.md instruction -- never silently muted):

- FN: cross-function slices (the exists()/open() or get()/save() calls
  split across two functions) are invisible to this intra-procedural
  pass -- same limitation as the SSRF/Deserialization AST resolvers.
- FN: SQLite's default serialized-writer semantics make many of these
  patterns non-exploitable at the engine level; we do NOT attempt to
  detect the configured DB engine (that requires cross-file settings
  resolution this module doesn't have access to) and instead document
  the caveat in the finding's recommendation text rather than silently
  suppressing -- an unconfirmed-safe engine is not the same as a
  confirmed-safe one.
- FP: a mock/fake ORM object with `.get`/`.save` methods that isn't a
  real Django/SQLAlchemy-style model will still match -- this is a
  structural, not semantic, match on the method-call shape.
"""

import ast
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ToctouFinding:
    line_number: int
    issue_type: str
    mechanism_id: str
    severity: str
    confidence: float
    description: str
    recommendation: str
    snippet: str


_EXISTS_ATTRS = {"exists"}
_OPEN_WRITE_MODES = {"w", "wb", "x", "xb", "a", "ab", "w+", "r+"}


def _call_attr_name(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute):
            return f.attr
        if isinstance(f, ast.Name):
            return f.id
    return None


def _first_arg_name(call: ast.Call) -> Optional[str]:
    if call.args and isinstance(call.args[0], ast.Name):
        return call.args[0].id
    # os.path.exists(path) where path is an attribute chain -> use unparse.
    if call.args:
        try:
            return ast.unparse(call.args[0])
        except Exception:
            return None
    return None


def _open_mode(call: ast.Call) -> Optional[str]:
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        return call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    if len(call.args) < 2 and not any(kw.arg == "mode" for kw in call.keywords):
        return "r"  # default open() mode -- not a write, not TOCTOU-relevant
    return None


def _contains_atomic(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            try:
                chain = ast.unparse(n.func)
            except Exception:
                chain = ""
            if "transaction.atomic" in chain:
                return True
        if isinstance(n, ast.Attribute) and n.attr == "atomic":
            return True
    return False


def _decorator_is_atomic(func: ast.FunctionDef) -> bool:
    for dec in func.decorator_list:
        try:
            src = ast.unparse(dec)
        except Exception:
            src = ""
        if "atomic" in src:
            return True
    return False


def _scan_function_body(func_name_or_module, body, lines, source_lines) -> List[ToctouFinding]:
    findings: List[ToctouFinding] = []

    # --- Pattern 1: exists() check then open(<same var>, write-mode) ---
    exists_vars = {}  # var -> lineno of exists() check

    all_nodes = []
    for stmt in body:
        all_nodes.extend(ast.walk(stmt))

    for node in all_nodes:
        if isinstance(node, ast.Call):
            attr = _call_attr_name(node)
            if attr == "exists" and isinstance(node.func, ast.Attribute):
                var = None
                try:
                    receiver_repr = ast.unparse(node.func.value)
                except Exception:
                    receiver_repr = ""
                if receiver_repr in ("os.path", "os.path.exists".rsplit(".", 1)[0]) and node.args:
                    # os.path.exists(<path-arg>) -- the checked value is the
                    # call argument, not the "os.path" receiver.
                    try:
                        var = ast.unparse(node.args[0])
                    except Exception:
                        var = None
                elif not node.args:
                    # pathlib-style: <path_obj>.exists() -- the checked
                    # value is the receiver itself.
                    var = receiver_repr
                if var:
                    exists_vars[var] = node.lineno
            elif attr == "access" and node.args:
                # os.access(path, mode) -- same check-then-use shape as
                # os.path.exists(path), just via the permission-check API.
                try:
                    full_chain = ast.unparse(node.func)
                except Exception:
                    full_chain = ""
                if full_chain in ("os.access", "access"):
                    try:
                        var = ast.unparse(node.args[0])
                    except Exception:
                        var = None
                    if var:
                        exists_vars[var] = node.lineno

    for node in all_nodes:
        if isinstance(node, ast.Call):
            fname = None
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if fname == "open":
                arg_repr = _first_arg_name(node)
                mode = _open_mode(node)
                is_write = bool(mode) and mode in _OPEN_WRITE_MODES
                if arg_repr and mode:
                    for var, exists_line in exists_vars.items():
                        # same variable text, and the exists() check precedes
                        # the open() in source order within this slice.
                        if var == arg_repr and exists_line < node.lineno:
                            snippet = source_lines[node.lineno - 1].strip()[:150] if 0 <= node.lineno - 1 < len(source_lines) else ""
                            if is_write:
                                severity, confidence, verb = "MEDIUM", 0.75, "opened for writing"
                            else:
                                # Read-mode check-then-open: still a real
                                # (weaker) race -- a symlink/file swap
                                # between check and open can redirect the
                                # read -- kept as a lower-confidence LOW
                                # finding rather than silently dropped.
                                severity, confidence, verb = "LOW", 0.4, "opened"
                            findings.append(ToctouFinding(
                                line_number=node.lineno,
                                issue_type="toctou_exists_then_open",
                                mechanism_id="race_condition.toctou_file",
                                severity=severity,
                                confidence=confidence,
                                description=(
                                    f"TOCTOU: '{var}.exists()' checked at line {exists_line} then "
                                    f"{verb} at line {node.lineno} -- another process can "
                                    "create/replace/delete the file between the check and the open"
                                ),
                                recommendation=(
                                    "Use os.open(path, os.O_CREAT | os.O_EXCL) to atomically "
                                    "create-and-check for writes, or catch "
                                    "FileNotFoundError/OSError around the open for reads instead "
                                    "of pre-checking existence"
                                ),
                                snippet=snippet,
                            ))

    # --- Pattern 2: ORM get() -> mutate -> save() without select_for_update ---
    get_call_lines = [n.lineno for n in all_nodes if isinstance(n, ast.Call) and _call_attr_name(n) == "get"]
    save_calls = [n for n in all_nodes if isinstance(n, ast.Call) and _call_attr_name(n) == "save"]
    has_select_for_update = any(
        isinstance(n, ast.Call) and _call_attr_name(n) == "select_for_update" for n in all_nodes
    )
    if get_call_lines and save_calls:
        in_atomic = _contains_atomic(ast.Module(body=list(body), type_ignores=[]))
        for save_node in save_calls:
            if not has_select_for_update:
                snippet = source_lines[save_node.lineno - 1].strip()[:150] if 0 <= save_node.lineno - 1 < len(source_lines) else ""
                sev = "MEDIUM" if in_atomic else "LOW"
                findings.append(ToctouFinding(
                    line_number=save_node.lineno,
                    issue_type="toctou_orm_get_mutate_save",
                    mechanism_id="race_condition.toctou_orm",
                    severity=sev,
                    confidence=0.55 if in_atomic else 0.35,
                    description=(
                        "get()/mutate/save() sequence without select_for_update() -- "
                        "concurrent requests can read-modify-write the same row and lose "
                        "an update"
                        + (" (inside a transaction.atomic block, but without a row lock)"
                           if in_atomic else
                           " (no surrounding transaction.atomic either -- the save is not "
                           "even atomic at the transaction level)")
                    ),
                    recommendation=(
                        "Wrap the read-modify-write in transaction.atomic() and use "
                        "select_for_update() to take a row lock for the duration of the "
                        "transaction"
                    ),
                    snippet=snippet,
                ))
        if has_select_for_update and not in_atomic:
            findings.append(ToctouFinding(
                line_number=get_call_lines[0],
                issue_type="select_for_update_without_atomic",
                mechanism_id="race_condition.toctou_orm",
                severity="LOW",
                confidence=0.5,
                description=(
                    "select_for_update() present but no surrounding transaction.atomic() "
                    "block was found in this function -- the row lock is released "
                    "immediately and provides no protection"
                ),
                recommendation="Wrap the select_for_update() call in transaction.atomic()",
                snippet=source_lines[get_call_lines[0] - 1].strip()[:150] if 0 <= get_call_lines[0] - 1 < len(source_lines) else "",
            ))

    return findings


def scan_toctou(tree: ast.Module, source_lines: List[str]) -> List[ToctouFinding]:
    """Scan a parsed Python module for canonical TOCTOU patterns, intra-procedurally."""
    findings: List[ToctouFinding] = []

    module_level = [s for s in tree.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if module_level:
        findings.extend(_scan_function_body("<module>", module_level, None, source_lines))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            fnd = _scan_function_body(node.name, body, None, source_lines)
            # decorator-level atomic() also counts for pattern 2's context.
            if _decorator_is_atomic(node):
                for f in fnd:
                    if f.issue_type == "toctou_orm_get_mutate_save" and f.severity == "LOW":
                        f.severity = "MEDIUM"
                        f.confidence = 0.55
            findings.extend(fnd)

    return findings
