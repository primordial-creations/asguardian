"""
AST-backed SSRF precision pipeline (plan 07.1).

The line-regex scanner (``ssrf_scanner.py``) still runs first and is the
only detector for non-Python languages -- this module is a Python-only
*refinement* pass (dual-engine: regex stays the ceiling for languages
without an AST path). For each Python file it re-examines the call sites
the regex scanner already flagged as `ssrf`, using the 5-step decision
pipeline from the plan:

    1. Host-control structural check: the URL is an f-string/concat whose
       scheme+host segment is a literal -> reclassify to a low-severity
       "API Path Injection" advisory and suppress the SSRF finding.
    2. Source verification: backward-slice the URL variable (single
       function scope, last-assignment-reaches-here -- intentionally not
       full control-flow-sensitive; documented limitation below) to see
       if it terminates at ``os.environ``/``app.config``/``settings``/an
       ``UPPER_SNAKE_CASE`` module constant -> suppress.
    3. Entry-point tiering: if the URL traces back to a function
       parameter AND the enclosing function is decorated with a
       route/handler decorator -> HIGH confidence; if it traces to a
       parameter of an undecorated ("generic helper") function -> LOW
       confidence, never blocking.
    4. Allowlist dominator check: an enclosing/preceding ``if`` in the
       same function testing the URL/host variable. Strict equality
       (``==``) against a literal -> suppress. ``startswith``/regex/
       ``urlparse(...).hostname`` guards keep the finding at MEDIUM,
       relabeled "Potential SSRF Validation Bypass (parser differential,
       CWE-601-style)" -- per RESEARCH_04, these guards are themselves
       bypassable and must never be trusted as authoritative.
    5. Redirect metadata: annotate whether the call passes
       ``allow_redirects=True`` / ``follow_redirects=True`` (or omits it,
       which defaults to following redirects for ``requests``) so the
       finding can note that redirect-based SSRF is a distinct runtime
       risk even after a URL is nominally validated.

Documented limitations (state honestly, per the adversarial-review
requirement):
  - The backward slice is single-function, syntactic (assignment
    tracking through simple ``Name = expr`` and ``Name: ... = expr``
    statements, one alias hop for ``x = y``), NOT a full dataflow/SSA
    analysis. Reassignment inside branches, loops, or via mutation
    (``dict['url'] = ...`` then read back) is not tracked -> both false
    negatives (missed taint that should suppress/downgrade) and, more
    rarely, false positives (a stale prior assignment picked up as "the"
    source) are possible on complex control flow.
  - Interprocedural flows (the URL enters via a call to another function
    in the same file) are not traced; such cases are left at the
    regex-scanner's original classification.
  - This module never *raises* severity above what the regex layer
    found; it only reclassifies/suppresses/downgrades or documents
    additional context, so it cannot introduce new false positives that
    weren't already flagged by Layer 1.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional, Set

_ROUTER_DECORATOR_HINTS = (
    "route", "get", "post", "put", "patch", "delete", "api_route",
    "endpoint", "handler", "view",
)

_TRUSTED_SOURCE_HINTS = ("environ", "config", "settings", "getenv")


@dataclass
class SSRFRefinement:
    """Outcome of refining one regex-flagged SSRF call site."""
    suppress: bool = False
    reclassify_as: Optional[str] = None      # e.g. "api_path_injection"
    severity_override: Optional[str] = None  # "LOW" | "MEDIUM" | "HIGH" | None (keep original)
    confidence: float = 0.5
    note: str = ""


def _is_upper_snake_case(name: str) -> bool:
    return name.isupper() and "_" in name or (name.isupper() and name.isalpha())


def _contains_literal_scheme_host(node: ast.AST) -> bool:
    """True if a (possibly f-string/concat) expression's LEADING segment
    is a plain string literal that already contains a scheme+host
    (``http://api.internal.example.com``-shaped), meaning only a path
    suffix is attacker-influenced -- the "API Path Injection" case."""
    def leading_literal(n: ast.AST) -> Optional[str]:
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return n.value
        if isinstance(n, ast.JoinedStr) and n.values:
            first = n.values[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value
            return None
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            return leading_literal(n.left)
        return None

    lit = leading_literal(node)
    return bool(lit and ("://" in lit) and len(lit.split("://", 1)[1]) > 0)


def _find_last_assignment(func_body: List[ast.stmt], name: str, before_lineno: int) -> Optional[ast.AST]:
    """Syntactic last-assignment-reaches-here within a flat function body
    scan (documented as non-CFG-aware in the module docstring)."""
    best: Optional[ast.AST] = None
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
            best = value
    return best


def _source_chain_is_trusted(node: Optional[ast.AST]) -> bool:
    """Step 2: slice the URL variable back to os.environ/app.config/
    settings/UPPER_SNAKE_CASE constant."""
    if node is None:
        return False
    if isinstance(node, ast.Name) and _is_upper_snake_case(node.id):
        return True
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in _TRUSTED_SOURCE_HINTS:
            return True
        if isinstance(sub, ast.Name) and sub.id in ("environ",):
            return True
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Attribute) and fn.attr == "getenv":
                return True
    return False


_REQUEST_INPUT_ATTRS = {
    "args", "form", "values", "GET", "POST", "REQUEST", "params", "query",
    "json", "body", "data", "headers", "cookies",
}


def _traces_to_parameter(node: Optional[ast.AST], param_names: Set[str]) -> bool:
    """Step 3 entry-point detection: traces to an explicit function
    parameter, OR to a framework request-object attribute (``request.args``,
    ``req.body``, ``request.GET`` etc.) -- the latter is how Flask/Django/
    FastAPI-style handlers receive attacker input without it being a
    literal parameter of the handler function itself."""
    if node is None:
        return False
    if isinstance(node, ast.Name) and node.id in param_names:
        return True
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in param_names:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in _REQUEST_INPUT_ATTRS:
            return True
    return False


def _is_router_decorated(func: ast.FunctionDef) -> bool:
    for dec in func.decorator_list:
        chain = dec
        if isinstance(chain, ast.Call):
            chain = chain.func
        attr = chain.attr if isinstance(chain, ast.Attribute) else (
            chain.id if isinstance(chain, ast.Name) else ""
        )
        if any(hint in attr.lower() for hint in _ROUTER_DECORATOR_HINTS):
            return True
    return False


def _find_dominating_guard(func_body: List[ast.stmt], var_name: str, before_lineno: int) -> Optional[str]:
    """Step 4: find an `if` in the function testing `var_name` before the
    call. Returns "strict_equality", "prefix_or_regex", or None."""
    result = None
    for stmt in ast.walk(ast.Module(body=func_body, type_ignores=[])):
        if not isinstance(stmt, ast.If) or getattr(stmt, "lineno", 0) >= before_lineno:
            continue
        for sub in ast.walk(stmt.test):
            if isinstance(sub, ast.Compare) and any(
                isinstance(n, ast.Name) and n.id == var_name for n in ast.walk(sub.left)
            ):
                if any(isinstance(op, (ast.Eq,)) for op in sub.ops):
                    result = "strict_equality"
            if isinstance(sub, ast.Call):
                fn = sub.func
                attr = fn.attr if isinstance(fn, ast.Attribute) else ""
                if attr in ("startswith", "match", "search", "fullmatch") and result != "strict_equality":
                    result = "prefix_or_regex"
                if attr == "hostname" or (
                    isinstance(fn, ast.Attribute) and fn.attr == "hostname"
                ):
                    if result != "strict_equality":
                        result = "prefix_or_regex"
    return result


def _redirect_kwarg(call: ast.Call) -> Optional[bool]:
    for kw in call.keywords:
        if kw.arg in ("allow_redirects", "follow_redirects"):
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool):
                return kw.value.value
            return None  # non-literal, can't determine statically
    return None  # not passed -> library default (True for requests)


def refine_ssrf_call(
    call: ast.Call,
    url_arg: ast.AST,
    func: Optional[ast.FunctionDef],
) -> SSRFRefinement:
    """Run the 5-step decision pipeline on one regex-flagged SSRF call site."""
    # Step 1: host-control structural check. This reclassifies+downgrades
    # (not `suppress`, which drops the finding outright) -- the URL is
    # still worth reporting, just as a lower-severity, differently-named
    # issue: only a path/query suffix is attacker-influenced.
    if _contains_literal_scheme_host(url_arg):
        return SSRFRefinement(
            suppress=False,
            reclassify_as="api_path_injection",
            severity_override="LOW",
            confidence=0.3,
            note="URL scheme+host is a literal; only a path/query suffix "
                 "is attacker-influenced (API Path Injection, not SSRF).",
        )

    param_names: Set[str] = set()
    func_body: List[ast.stmt] = []
    if func is not None:
        param_names = {a.arg for a in func.args.args + func.args.kwonlyargs}
        func_body = func.body

    var_name = url_arg.id if isinstance(url_arg, ast.Name) else None
    assigned_value = (
        _find_last_assignment(func_body, var_name, call.lineno) if var_name else None
    )

    # Step 2: source verification against trusted config/env/constants.
    if _source_chain_is_trusted(assigned_value) or _source_chain_is_trusted(url_arg):
        return SSRFRefinement(
            suppress=True,
            confidence=0.1,
            note="URL originates from environment/config/settings or an "
                 "UPPER_SNAKE_CASE constant, not attacker-controlled input.",
        )

    # Step 4: allowlist dominator check (checked before tiering so a
    # strict-equality guard can suppress outright regardless of tier).
    guard = _find_dominating_guard(func_body, var_name, call.lineno) if var_name else None
    if guard == "strict_equality":
        return SSRFRefinement(
            suppress=True,
            confidence=0.15,
            note="Dominating strict-equality allowlist check found before this call.",
        )

    # Step 3: entry-point tiering.
    is_param = _traces_to_parameter(assigned_value, param_names) or (
        var_name in param_names if var_name else False
    )
    if func is not None and is_param and _is_router_decorated(func):
        confidence = 0.85
        tier_note = "URL traces to a parameter of a route-decorated handler (HIGH-confidence entry point)."
    elif is_param:
        confidence = 0.3
        tier_note = "URL traces to a parameter of a generic (non-route) helper function; never gate-blocking."
    else:
        confidence = 0.5
        tier_note = "URL source could not be traced to a specific entry point within this function."

    severity_override = None
    note = tier_note
    if guard == "prefix_or_regex":
        severity_override = "MEDIUM"
        note = (
            "Potential SSRF Validation Bypass (parser differential, CWE-601-style): "
            "a startswith/regex/urlparse().hostname guard is present but such checks "
            "are known to be bypassable and are never treated as authoritative. " + tier_note
        )

    redirects = _redirect_kwarg(call)
    if redirects is True or redirects is None:
        note += " Call allows redirects (default or explicit); redirect-based SSRF " \
                "remains a runtime risk even for an otherwise-validated URL."

    return SSRFRefinement(
        suppress=False,
        severity_override=severity_override,
        confidence=confidence,
        note=note,
    )


def find_enclosing_function(tree: ast.AST, lineno: int) -> Optional[ast.FunctionDef]:
    """Find the innermost FunctionDef/AsyncFunctionDef containing `lineno`."""
    best: Optional[ast.FunctionDef] = None
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


def extract_url_arg(call: ast.Call) -> Optional[ast.AST]:
    """Best-effort extraction of the "URL-shaped" argument from a
    requests/urlopen-style call: first positional arg, or the ``url``
    keyword."""
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg == "url":
            return kw.value
    return None
