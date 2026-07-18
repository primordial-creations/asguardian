"""
AST-backed deserialization provenance pipeline (plan 07.5, post-review fix).

BLOCKER-1/BLOCKER-2/MAJOR-3 fix (adversarial review): the original scanner
classified provenance by scanning a fixed 15-line *textual* backward
window around the sink line for marker substrings. Three failure modes
followed directly from that design:

  - A real RCE could be laundered by padding the function with >15
    no-op lines between the untrusted assignment and the sink call
    (BLOCKER-1).
  - `open(...)` was *unconditionally* treated as an "internal" marker
    regardless of what path was opened, so `open(sys.argv[1])` or
    `open(<tainted var>)` read straight from an untrusted source but
    was still classified internal (BLOCKER-2).
  - An unrelated untrusted marker merely sitting in the same textual
    window -- with zero actual dataflow to the sink argument --
    produced a false CRITICAL (MAJOR-3).

This module replaces the textual window with real (intraprocedural,
syntactic) AST variable-origin tracking, following the same pattern
already used for SSRF in `SSRF/services/_ssrf_ast_analysis.py`: resolve
the sink argument's *actual* last-assignment chain within the enclosing
function (unbounded by line count, bounded only by a hop-count safety
cap) and classify based on what that chain actually contains.

Three provenance outcomes:
  - "untrusted": the resolved value chain contains a structural
    untrusted-source marker (request/socket/stdin/argv/env/queue/etc,
    or an unresolvable-by-design attacker-input attribute access).
  - "internal": the resolved value chain is fully resolvable and
    contains no untrusted markers and no unresolved names (e.g. a
    literal path, or a chain of local assignments terminating in
    literals).
  - "unknown": the chain could not be fully resolved (external/free
    variable, closure capture, hop-count cap hit, or the sink argument
    is a bare function parameter with no naming signal either way).
    Per the review directive, "unknown" is NEVER treated as safe: it
    must not collapse into the same low-confidence bucket as a
    demonstrated-internal source.

Documented limitations (same class as the SSRF module):
  - Single-function, syntactic backward slice -- not a full dataflow/SSA
    analysis. Reassignment inside branches/loops, or via mutation, is
    not tracked.
  - Interprocedural flows (the value enters via a call to another
    function in the same file) are not traced -- such cases fall
    through to "unknown" rather than being silently marked safe.
"""

from __future__ import annotations

import ast
from typing import List, Optional, Set

# Structural untrusted-source lexicon (BLOCKER-2a: sys.argv and os.environ
# added; both can carry attacker-influenced data -- a CLI arg or an
# env-injected path is not "internal" by default).
_UNTRUSTED_ATTR_NAMES = {
    "args", "form", "values", "GET", "POST", "REQUEST", "params", "query",
    "json", "body", "data", "headers", "cookies", "get_json",
}
_UNTRUSTED_BASE_NAMES = {"request", "req"}
_UNTRUSTED_MODULE_HINTS = ("kafka", "rabbitmq", "celery", "sqs", "websocket")
_UNTRUSTED_NAME_SUBSTRINGS = (
    "user_data", "user_input", "untrusted", "client_data", "raw_input",
)

# Hop-count safety cap for the recursive origin resolution (mirrors the
# taint plan's hop-decay concept without implementing full taint scoring).
_MAX_HOPS = 8


def _is_sys_argv(node: ast.AST) -> bool:
    """`sys.argv` (attribute) or `sys.argv[...]` (subscript on it)."""
    if isinstance(node, ast.Subscript):
        return _is_sys_argv(node.value)
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "argv"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_sys_stdin(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "stdin"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_os_environ(node: ast.AST) -> bool:
    if isinstance(node, ast.Subscript):
        return _is_os_environ(node.value)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "get" and _is_os_environ(node.func.value)
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _is_upper_snake_case(name: str) -> bool:
    """Module-level constant naming convention (same trusted-source
    heuristic already used by the SSRF AST refinement pass, plan 07.1
    step 2) -- `LOCAL_TRUSTED_BYTES`, `DEFAULT_CONFIG`, etc."""
    return name.isupper() and any(c.isalpha() for c in name)


def _base_name(node: ast.AST) -> Optional[str]:
    """Innermost `Name` id of an attribute/subscript/call chain."""
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _node_is_direct_untrusted_marker(node: ast.AST) -> bool:
    """Structural (non-recursive) check: is *this specific node* itself an
    untrusted-source shape? Does not walk children -- callers combine this
    with recursion into children so an unrelated marker elsewhere in the
    function can never contribute (MAJOR-3 fix: no textual-window
    co-occurrence, only the actual reaching value is inspected)."""
    if _is_sys_argv(node) or _is_sys_stdin(node) or _is_os_environ(node):
        return True

    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr in ("recv", "accept") and _base_name(fn.value) == "socket":
            return True
        if isinstance(fn, ast.Name) and fn.id in ("urlopen", "urlretrieve", "input"):
            return True
        if isinstance(fn, ast.Attribute) and fn.attr in ("recv",) and "ws" in (_base_name(fn.value) or ""):
            return True

    if isinstance(node, ast.Attribute):
        base = _base_name(node)
        if base in _UNTRUSTED_BASE_NAMES and node.attr in _UNTRUSTED_ATTR_NAMES:
            return True
        if node.attr in _UNTRUSTED_ATTR_NAMES and base and any(
            hint in base.lower() for hint in ("request", "req")
        ):
            return True
        if base and any(hint in base.lower() for hint in _UNTRUSTED_MODULE_HINTS):
            return True

    if isinstance(node, ast.Subscript):
        base = _base_name(node.value)
        if base in _UNTRUSTED_BASE_NAMES:
            return True

    if isinstance(node, ast.Name):
        lowered = node.id.lower()
        if any(sub in lowered for sub in _UNTRUSTED_NAME_SUBSTRINGS):
            return True
        if any(hint in lowered for hint in _UNTRUSTED_MODULE_HINTS):
            return True

    return False


def _find_all_assignments(func_body: List[ast.stmt], name: str, before_lineno: int) -> List[ast.AST]:
    """All syntactic assignments to `name` before `before_lineno`, in
    source order (last element is the reaching definition under a flat,
    non-CFG-aware "last assignment wins" model -- same documented
    limitation as the SSRF module)."""
    hits: List[ast.AST] = []
    for stmt in ast.walk(ast.Module(body=func_body, type_ignores=[])):
        target_name = None
        value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            target_name = stmt.targets[0].id
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            target_name = stmt.target.id
            value = stmt.value
        if target_name == name and getattr(stmt, "lineno", 0) <= before_lineno:
            hits.append(value)
    return hits


def resolve_origin(
    node: Optional[ast.AST],
    func_body: List[ast.stmt],
    before_lineno: int,
    param_names: Set[str],
    depth: int = 0,
    _visited: Optional[Set[int]] = None,
) -> str:
    """
    Resolve the provenance of `node` within the enclosing function.

    Returns one of "untrusted" / "internal" / "unknown". "untrusted"
    dominates (any untrusted sub-expression makes the whole expression
    untrusted); otherwise any unresolved sub-expression makes the whole
    expression "unknown"; only an expression fully resolved to literals
    and known-safe constructs is "internal".
    """
    if node is None:
        return "unknown"
    if _visited is None:
        _visited = set()
    if depth > _MAX_HOPS:
        return "unknown"

    if _node_is_direct_untrusted_marker(node):
        return "untrusted"

    if isinstance(node, ast.Constant):
        return "internal"

    if isinstance(node, ast.Name):
        if node.id in param_names:
            # A bare parameter with no untrusted naming signal: we cannot
            # prove it's attacker input, but we equally cannot prove it's
            # internal -- BLOCKER-1/2 directive: unresolved is NOT safe.
            return "unknown"
        # Avoid infinite loops on `x = x` / mutual recursion.
        key = id(node) ^ hash(node.id)
        if key in _visited:
            return "unknown"
        _visited = _visited | {key}
        assignments = _find_all_assignments(func_body, node.id, before_lineno)
        if not assignments:
            if _is_upper_snake_case(node.id):
                # Module-level constant naming convention: trusted, per the
                # same convention already established for SSRF (plan 07.1).
                return "internal"
            # Free/outer-scope variable -- not a parameter, not assigned
            # in this function. Unresolved, so "unknown", never "internal".
            return "unknown"
        # Union over every syntactic assignment that could reach this use
        # (not just the last one) -- a single untrusted branch is enough
        # to call the variable untrusted; only if EVERY assignment is
        # internal do we call the variable internal.
        results = {
            resolve_origin(v, func_body, before_lineno, param_names, depth + 1, _visited)
            for v in assignments
        }
        if "untrusted" in results:
            return "untrusted"
        if "unknown" in results:
            return "unknown"
        return "internal"

    if isinstance(node, ast.Call):
        results = {resolve_origin(a, func_body, before_lineno, param_names, depth + 1, _visited) for a in node.args}
        results |= {
            resolve_origin(kw.value, func_body, before_lineno, param_names, depth + 1, _visited)
            for kw in node.keywords if kw.value is not None
        }
        results.add(resolve_origin(node.func, func_body, before_lineno, param_names, depth + 1, _visited)
                     if isinstance(node.func, (ast.Attribute, ast.Subscript)) else "internal")
        if "untrusted" in results:
            return "untrusted"
        if "unknown" in results:
            return "unknown"
        return "internal"

    if isinstance(node, ast.Attribute):
        return resolve_origin(node.value, func_body, before_lineno, param_names, depth + 1, _visited)

    if isinstance(node, ast.Subscript):
        base = resolve_origin(node.value, func_body, before_lineno, param_names, depth + 1, _visited)
        key_node = node.slice
        if isinstance(key_node, ast.Index):  # pragma: no cover - old AST shape
            key_node = key_node.value
        key = resolve_origin(key_node, func_body, before_lineno, param_names, depth + 1, _visited)
        results = {base, key}
        if "untrusted" in results:
            return "untrusted"
        if "unknown" in results:
            return "unknown"
        return "internal"

    if isinstance(node, (ast.BinOp,)):
        left = resolve_origin(node.left, func_body, before_lineno, param_names, depth + 1, _visited)
        right = resolve_origin(node.right, func_body, before_lineno, param_names, depth + 1, _visited)
        results = {left, right}
        if "untrusted" in results:
            return "untrusted"
        if "unknown" in results:
            return "unknown"
        return "internal"

    if isinstance(node, ast.JoinedStr):
        results = {resolve_origin(v, func_body, before_lineno, param_names, depth + 1, _visited) for v in node.values}
        if "untrusted" in results:
            return "untrusted"
        if "unknown" in results:
            return "unknown"
        return "internal"

    # Anything else unrecognized (lambda, comprehension, starred, etc) --
    # do not guess; treat as unresolved.
    return "unknown"


def find_enclosing_function(tree: ast.AST, lineno: int):
    """Find the innermost FunctionDef/AsyncFunctionDef containing `lineno`."""
    best = None
    best_span = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", None) or (start + 10_000)
            if start <= lineno <= end:
                span = end - start
                if best_span is None or span < best_span:
                    best, best_span = node, span
    return best


def find_sink_call(tree: ast.AST, line_num: int, expected_attr: Optional[str]):
    """Find the Call node on `line_num` whose function's final attribute
    (or bare name) is `expected_attr` (e.g. "loads", "load", "decode",
    "open"). Returns the first match in AST-walk order."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node, "lineno", None) == line_num:
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else None)
            if expected_attr is None or name == expected_attr:
                return node
    return None


def extract_sink_arg(call: ast.Call):
    """Best-effort extraction of the "payload" argument: first positional
    arg, else first keyword's value."""
    if call.args:
        return call.args[0]
    if call.keywords:
        return call.keywords[0].value
    return None
