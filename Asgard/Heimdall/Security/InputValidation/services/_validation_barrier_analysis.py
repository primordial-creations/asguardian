"""
AST-based validation-barrier / sanitization-mutator structural checks
(plan 07.12, RESEARCH_18).

RESEARCH_18's core distinction: **validation** is a control-flow barrier
guard (raises/returns/aborts the request on bad input -- e.g. Django Form
``is_valid()`` + ``cleaned_data``, a Pydantic model boundary) while
**sanitization** is a data mutator (transforms a value in place, e.g.
``escape()``, ``bleach.clean()``) that does not stop execution. Both are
legitimate controls, but conflating them is a common source of bypass: a
value that has only been *sanitized* is not the same guarantee as a value
that passed through a *barrier*, and code that assumes the former gives
the latter is the root of several checks below.

Five structural checks, each independently detectable and independently
shippable:

1. **Raw access bypassing a validation barrier** -- ``request.POST[...]``/
   ``request.GET[...]`` used directly (Django) when a `Form`/`Serializer`
   barrier with `.cleaned_data`/`.validated_data` exists elsewhere in the
   same function, or FastAPI ``await request.body()`` used instead of a
   Pydantic-model request parameter.
2. **Globally disabled Jinja2 autoescape** -- ``Environment(autoescape=False)``
   or ``select_autoescape`` omitted while the constructor lacks the
   default -- flagged as a codebase-wide XSS risk (CRITICAL) since it
   affects every template render, not one call site.
3. **`mark_safe()` on tainted data** -- ``mark_safe(x)`` where `x` is not a
   string literal (i.e. some computed/interpolated value) -- XSS risk
   because it disables Django's autoescaping for that value.
4. **Mass-assignment advisory** -- a Pydantic model class used as an
   update-route parameter (heuristic: class name or function name contains
   "update"/"patch") without ``model_config = ConfigDict(extra='forbid')``
   / ``class Config: extra = 'forbid'`` -- advisory only (LOW,
   `is_advisory=True`), since many APIs intentionally accept partial data.
5. **CWE-179: early validation followed by late mutation** -- a value is
   validated/checked (an `if`/assert barrier referencing the name) and
   then, *after* that check, is decoded/mutated (`.decode()`, `unquote()`,
   `.lower()`, `base64.b64decode()`, etc.) before reaching a sink -- the
   validation ran against the pre-mutation form and may no longer hold for
   the sink-time value.

Honest FP/FN (per CLAUDE.md -- never silently muted):

- FP: check 1's "raw access" flag can trigger even when the raw access is
  itself only used for a non-sensitive read (e.g. logging the raw key
  names) -- this is a structural match on API surface, not a taint
  confirmation to a sink, so it stays MEDIUM/possible, never CRITICAL.
- FN: cross-function/cross-file barrier resolution is out of scope
  (same intra-procedural limitation as this codebase's other AST
  resolvers) -- a barrier applied in a decorator or middleware upstream
  of the function is invisible here.
- FP: check 5's early-validation rule cannot confirm the *specific*
  validation actually constrains the sink-relevant property of the
  mutated value (e.g. a length check followed by a decode does not mean
  the decoded length is unchecked) -- reported as a hotspot (LOW, capped
  confidence), not a confirmed finding.
"""

import ast
from dataclasses import dataclass, field
from typing import List, Optional

_DJANGO_RAW_REQUEST_ATTRS = {"POST", "GET"}
_BARRIER_ATTRS = {"cleaned_data", "validated_data", "is_valid"}
_MUTATOR_METHODS = {
    "decode", "unquote", "lower", "upper", "strip", "b64decode", "unescape",
    "normalize", "loads",
}
_MUTATOR_FUNCS = {"unquote", "b64decode", "loads", "unescape"}


@dataclass
class ValidationBarrierFinding:
    line_number: int
    issue_type: str
    mechanism_id: str
    severity: str
    confidence: float
    description: str
    recommendation: str
    snippet: str
    cwe_id: str = ""
    is_advisory: bool = False


def _line(source_lines: List[str], lineno: int) -> str:
    return source_lines[lineno - 1].strip()[:150] if 0 < lineno <= len(source_lines) else ""


def check_raw_request_access(tree: ast.AST, source_lines: List[str]) -> List[ValidationBarrierFinding]:
    findings: List[ValidationBarrierFinding] = []

    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        has_barrier = any(
            isinstance(n, ast.Attribute) and n.attr in _BARRIER_ATTRS
            for n in ast.walk(func_node)
        )

        for node in ast.walk(func_node):
            # request.POST[...] / request.GET[...]
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
                if node.value.attr in _DJANGO_RAW_REQUEST_ATTRS:
                    receiver = node.value.value
                    receiver_name = receiver.id if isinstance(receiver, ast.Name) else ""
                    if receiver_name.lower() in ("request", "req", "self"):
                        line_number = getattr(node, "lineno", 1)
                        findings.append(ValidationBarrierFinding(
                            line_number=line_number,
                            issue_type="raw_request_access",
                            mechanism_id="input_validation.raw_request_access",
                            severity="MEDIUM" if not has_barrier else "LOW",
                            confidence=0.55 if not has_barrier else 0.35,
                            description=(
                                f"Direct `{receiver_name}.{node.value.attr}[...]` access "
                                "bypasses Django's Form/Serializer validation barrier"
                                + (" (a validation barrier exists elsewhere in this "
                                   "function -- confirm this specific access is not "
                                   "meant to go through it)" if has_barrier else
                                   " -- no `.cleaned_data`/`.validated_data`/`.is_valid()` "
                                   "barrier was found in this function")
                                + "."
                            ),
                            recommendation=(
                                "Route this input through a Django Form/ModelForm or DRF "
                                "Serializer and read from `.cleaned_data`/`.validated_data` "
                                "instead of indexing the raw QueryDict."
                            ),
                            snippet=_line(source_lines, line_number),
                        ))

            # FastAPI: await request.body() as a substitute for a Pydantic param
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "body" and isinstance(node.func.value, ast.Name):
                    if node.func.value.id.lower() in ("request", "req"):
                        line_number = getattr(node, "lineno", 1)
                        findings.append(ValidationBarrierFinding(
                            line_number=line_number,
                            issue_type="raw_body_bypass",
                            mechanism_id="input_validation.raw_body_bypass",
                            severity="MEDIUM",
                            confidence=0.45,
                            description=(
                                "`request.body()` reads the raw request body, bypassing "
                                "FastAPI's Pydantic-model request-parameter validation "
                                "barrier entirely."
                            ),
                            recommendation=(
                                "Declare a Pydantic model as the route's request "
                                "parameter instead of manually reading/parsing "
                                "`request.body()`, so FastAPI enforces the schema barrier."
                            ),
                            snippet=_line(source_lines, line_number),
                        ))

    return findings


def check_jinja2_autoescape_disabled(tree: ast.AST, source_lines: List[str]) -> List[ValidationBarrierFinding]:
    findings: List[ValidationBarrierFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
            func_name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            if func_name != "Environment":
                continue
            autoescape_kw = next((kw for kw in node.keywords if kw.arg == "autoescape"), None)
            if autoescape_kw is not None and isinstance(autoescape_kw.value, ast.Constant) and autoescape_kw.value.value is False:
                line_number = getattr(node, "lineno", 1)
                findings.append(ValidationBarrierFinding(
                    line_number=line_number,
                    issue_type="jinja2_autoescape_disabled",
                    mechanism_id="input_validation.jinja2_autoescape_disabled",
                    severity="CRITICAL",
                    confidence=0.85,
                    description=(
                        "Jinja2 Environment created with autoescape=False -- this "
                        "disables HTML/XML auto-escaping for every template rendered "
                        "through this environment, a codebase-wide XSS risk, not a "
                        "single call-site issue."
                    ),
                    recommendation=(
                        "Use `autoescape=select_autoescape(['html', 'xml'])` (or "
                        "`autoescape=True` for HTML-only apps) instead of disabling it "
                        "globally."
                    ),
                    snippet=_line(source_lines, line_number),
                ))
    return findings


def check_mark_safe_on_tainted(tree: ast.AST, source_lines: List[str]) -> List[ValidationBarrierFinding]:
    findings: List[ValidationBarrierFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
            func_name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            if func_name != "mark_safe":
                continue
            if not node.args:
                continue
            arg = node.args[0]
            # A plain string literal is not tainted; anything else (Name,
            # JoinedStr/f-string, Call, BinOp/+concatenation) is treated as
            # potentially tainted.
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                continue
            line_number = getattr(node, "lineno", 1)
            findings.append(ValidationBarrierFinding(
                line_number=line_number,
                issue_type="mark_safe_tainted",
                mechanism_id="input_validation.mark_safe_tainted",
                severity="HIGH",
                confidence=0.5,
                description=(
                    "`mark_safe()` called on a non-literal (computed/interpolated) "
                    "value disables Django's autoescaping for that output -- if the "
                    "value contains any user-controlled data, this is a reflected/"
                    "stored XSS sink."
                ),
                recommendation=(
                    "Avoid `mark_safe()` on any value derived from user input. If "
                    "the content must contain HTML, sanitize it first with a "
                    "dedicated HTML sanitizer (e.g. bleach) before marking safe."
                ),
                snippet=_line(source_lines, line_number),
            ))
    return findings


def _pydantic_class_has_extra_forbid(class_node: ast.ClassDef) -> bool:
    for stmt in class_node.body:
        # model_config = ConfigDict(extra="forbid") (Pydantic v2)
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "model_config" for t in stmt.targets
        ):
            if isinstance(stmt.value, ast.Call):
                for kw in stmt.value.keywords:
                    if kw.arg == "extra" and isinstance(kw.value, ast.Constant) and kw.value.value == "forbid":
                        return True
        # class Config: extra = "forbid" (Pydantic v1)
        if isinstance(stmt, ast.ClassDef) and stmt.name == "Config":
            for inner in stmt.body:
                if isinstance(inner, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "extra" for t in inner.targets
                ):
                    if isinstance(inner.value, ast.Constant) and inner.value.value == "forbid":
                        return True
    return False


def check_mass_assignment_advisory(tree: ast.AST, source_lines: List[str]) -> List[ValidationBarrierFinding]:
    """Advisory: a Pydantic BaseModel subclass whose name suggests it's an
    update/patch payload, without extra='forbid'."""
    findings: List[ValidationBarrierFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]
        base_names += [b.attr for b in node.bases if isinstance(b, ast.Attribute)]
        if "BaseModel" not in base_names:
            continue
        name_lower = node.name.lower()
        if not ("update" in name_lower or "patch" in name_lower):
            continue
        if _pydantic_class_has_extra_forbid(node):
            continue
        line_number = getattr(node, "lineno", 1)
        findings.append(ValidationBarrierFinding(
            line_number=line_number,
            issue_type="mass_assignment_advisory",
            mechanism_id="input_validation.mass_assignment_advisory",
            severity="LOW",
            confidence=0.4,
            is_advisory=True,
            description=(
                f"Pydantic model '{node.name}' looks like an update/patch payload "
                "but does not set extra='forbid'. By default Pydantic v2 ignores "
                "unrecognized fields, which can mask a mass-assignment attempt "
                "(e.g. a client submitting `is_admin: true` alongside legitimate "
                "update fields)."
            ),
            recommendation=(
                "Consider `model_config = ConfigDict(extra='forbid')` (Pydantic v2) "
                "or `class Config: extra = 'forbid'` (v1) on update/patch payload "
                "models, and always assign only explicitly-allowed fields onto the "
                "target object rather than `**payload.dict()`."
            ),
            snippet=_line(source_lines, line_number),
        ))
    return findings


def check_early_validation_late_mutation(tree: ast.AST, source_lines: List[str]) -> List[ValidationBarrierFinding]:
    """CWE-179: an `if`/assert barrier references a name, and later in the
    same function a mutator call is applied to that same name before it is
    used further -- the validation ran against the pre-mutation form."""
    findings: List[ValidationBarrierFinding] = []

    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        body = func_node.body
        validated_names: dict = {}  # name -> line of validation
        for idx, stmt in enumerate(body):
            if isinstance(stmt, (ast.If, ast.Assert)):
                test = stmt.test
                for name_node in ast.walk(test):
                    if isinstance(name_node, ast.Name) and isinstance(name_node.ctx, ast.Load):
                        validated_names.setdefault(name_node.id, getattr(stmt, "lineno", 1))

            # Look for a mutator call applied to an already-validated name,
            # appearing textually after the validation statement.
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call):
                    target_name = None
                    method = None
                    if isinstance(node.func, ast.Attribute) and node.func.attr in _MUTATOR_METHODS:
                        if isinstance(node.func.value, ast.Name):
                            target_name = node.func.value.id
                            method = node.func.attr
                    elif isinstance(node.func, ast.Name) and node.func.id in _MUTATOR_FUNCS:
                        if node.args and isinstance(node.args[0], ast.Name):
                            target_name = node.args[0].id
                            method = node.func.id

                    if target_name and target_name in validated_names:
                        call_line = getattr(node, "lineno", 1)
                        if call_line > validated_names[target_name]:
                            findings.append(ValidationBarrierFinding(
                                line_number=call_line,
                                issue_type="early_validation_late_mutation",
                                mechanism_id="input_validation.cwe179_early_validation",
                                severity="LOW",
                                confidence=0.35,
                                cwe_id="CWE-179",
                                description=(
                                    f"'{target_name}' was validated at line "
                                    f"{validated_names[target_name]} but is mutated via "
                                    f"`.{method}()`/`{method}()` afterward (line "
                                    f"{call_line}) before reaching its eventual use -- "
                                    "the validation ran against the pre-mutation form and "
                                    "may not hold for the value actually used downstream "
                                    "(CWE-179: incorrect behavior order, validate before "
                                    "canonicalize)."
                                ),
                                recommendation=(
                                    "Canonicalize/decode the input FIRST, then validate "
                                    "the fully-decoded form, so the validation covers the "
                                    "value that is actually used."
                                ),
                                snippet=_line(source_lines, call_line),
                            ))

    return findings


def scan_validation_barriers(tree: ast.AST, source_lines: List[str]) -> List[ValidationBarrierFinding]:
    findings: List[ValidationBarrierFinding] = []
    findings.extend(check_raw_request_access(tree, source_lines))
    findings.extend(check_jinja2_autoescape_disabled(tree, source_lines))
    findings.extend(check_mark_safe_on_tainted(tree, source_lines))
    findings.extend(check_mass_assignment_advisory(tree, source_lines))
    findings.extend(check_early_validation_late_mutation(tree, source_lines))
    return findings
