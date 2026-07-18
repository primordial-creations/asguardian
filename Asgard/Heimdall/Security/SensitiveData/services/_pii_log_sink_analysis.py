"""
AST-based PII-to-log-sink taint rule (plan 07.11, RESEARCH_11).

Detects identifiers whose *name* matches a PII lexicon (ssn, dob, email,
password, token, etc.) being passed into a logging sink: ``logging.*`` /
``logger.*`` calls, bare ``print()``, or an exception message
(``raise Exception(f"...{ssn}...")`` / ``str(e)`` interpolation patterns
are out of scope for a name-based intraprocedural pass -- see FN note).

This is a name-based heuristic, not a full taint-tracker: it flags call
arguments (including f-string / %-format / .format() interpolated values)
whose *variable name* matches the lexicon, directly or through a simple
same-function assignment chain (``ssn = user.ssn; logger.info(ssn)``).

Honest FP/FN (per CLAUDE.md -- never silently muted):

- FP: a variable named ``token`` that holds a non-sensitive CSRF nonce or
  pagination cursor will still match the lexicon -- name-based heuristics
  cannot distinguish semantic meaning from spelling. These are reported
  as hotspots (LOW, capped confidence), not confirmed findings.
- FN: PII flowing through a differently-named variable
  (``x = user.ssn; log.info(x)``) is invisible to this pass -- same
  intra-procedural, no-cross-function-slice limitation as the
  Deserialization/SSRF/TOCTOU AST resolvers in this codebase.
- FN: PII embedded in a dict/object passed whole to a logger
  (``logger.info(user.__dict__)``) is not unpacked/inspected.
- Unresolved origin is never treated as safe: a lexicon-name match with an
  unresolved assignment chain is still reported (as a hotspot), never
  dropped.
"""

import ast
from dataclasses import dataclass, field
from typing import List, Optional

_PII_LEXICON = {
    "ssn", "social_security", "socialsecuritynumber",
    "dob", "date_of_birth", "birthdate",
    "email", "email_address",
    "password", "passwd", "pwd",
    "token", "auth_token", "access_token", "refresh_token", "api_key",
    "apikey", "secret", "secret_key",
    "credit_card", "creditcard", "card_number", "cvv", "cvc",
    "phone", "phone_number", "mobile",
    "address", "home_address",
    "passport", "passport_number",
    "national_id", "nationalid", "tax_id", "taxid", "ein",
}

_LOG_CALL_ATTRS = {
    "debug", "info", "warning", "warn", "error", "critical", "exception", "log",
}

_LOG_RECEIVER_HINTS = {"logging", "logger", "log", "LOGGER", "LOG"}

# PII lexicon members that are always CRITICAL (regulated categories) vs
# ones treated as sensitive-but-lower-severity (e.g. "token"/"secret"
# overlap heavily with the Secrets domain's own detection and are
# intentionally kept at MEDIUM here to avoid double-counting severity).
_HIGH_SEVERITY_TERMS = {
    "ssn", "social_security", "socialsecuritynumber", "dob", "date_of_birth",
    "birthdate", "password", "passwd", "pwd", "credit_card", "creditcard",
    "card_number", "cvv", "cvc", "passport", "passport_number",
    "national_id", "nationalid", "tax_id", "taxid", "ein",
}


@dataclass
class PiiLogSinkFinding:
    line_number: int
    identifier: str
    lexicon_term: str
    sink_kind: str
    mechanism_id: str
    severity: str
    confidence: float
    is_hotspot: bool
    description: str
    recommendation: str
    snippet: str
    compliance_tags: List[str] = field(default_factory=list)


def _matches_lexicon(name: str) -> Optional[str]:
    normalized = name.lower().lstrip("_")
    if normalized in _PII_LEXICON:
        return normalized
    for term in _PII_LEXICON:
        if term in normalized and len(normalized) <= len(term) + 6:
            return term
    return None


def _compliance_tags_for(term: str) -> List[str]:
    tags = []
    if term in ("ssn", "social_security", "socialsecuritynumber", "dob",
                "date_of_birth", "birthdate", "email", "email_address",
                "phone", "phone_number", "mobile", "address", "home_address",
                "passport", "passport_number", "national_id", "nationalid"):
        tags.append("GDPR")
    if term in ("credit_card", "creditcard", "card_number", "cvv", "cvc"):
        tags.append("PCI-DSS")
    if term in ("ssn", "social_security", "socialsecuritynumber", "dob",
                "date_of_birth", "birthdate"):
        tags.append("HIPAA")
    return tags or ["GDPR"]


def _is_log_call(call: ast.Call) -> Optional[str]:
    """Return 'log' if this call is a logging.*/logger.* sink, 'print' for
    bare print(), else None."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in _LOG_CALL_ATTRS:
        receiver = func.value
        if isinstance(receiver, ast.Name) and (
            receiver.id in _LOG_RECEIVER_HINTS or "log" in receiver.id.lower()
        ):
            return "log"
    if isinstance(func, ast.Name) and func.id == "print":
        return "print"
    return None


def _names_in_node(node: ast.AST) -> List[ast.Name]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]


def scan_pii_log_sinks(tree: ast.AST, source_lines: List[str]) -> List[PiiLogSinkFinding]:
    findings: List[PiiLogSinkFinding] = []
    seen: set = set()

    # Build a simple same-function alias map: var_name -> lexicon term,
    # for direct assignments like `ssn = user.ssn` or `x = record["ssn"]`.
    # NOTE: ast.walk(tree) yields Module + every FunctionDef at every
    # nesting depth, and each is walked again below (including nested
    # functions' bodies), so the same Call node can be visited from
    # multiple enclosing scopes (Module, outer func, inner func) -- the
    # `seen` dedup keyed on (line, identifier, sink_kind) below collapses
    # those duplicate visits into a single finding.
    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            continue

        # Adversarial-review fix (MAJOR-7): this used to be a single pass
        # over assignments, so only a ONE-hop rename was resolved
        # (`ssn = user.ssn` -> alias_terms["ssn"] = "ssn"). A second
        # rename (`x = user.ssn; y = x; logger.info(y)`) was invisible:
        # by the time `y = x` was considered, `x` may not yet have been
        # in `alias_terms` (dict ordering aside, a single pass can't
        # chase `y -> x -> lexicon-term` transitively at all if the
        # simple-Name-to-Name case wasn't even collected). Iterate the
        # assignment scan to a fixed point (bounded at 5 hops so a
        # pathological/cyclic rename chain can't hang the scan) so
        # `y = x; z = y; logger.info(z)`-style multi-hop renames still
        # resolve to the underlying lexicon term.
        assign_stmts = [
            stmt for stmt in ast.walk(func_node)
            if isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
        ]

        alias_terms: dict = {}
        for _hop in range(5):
            changed = False
            for stmt in assign_stmts:
                target_name = stmt.targets[0].id
                if target_name in alias_terms:
                    continue

                term = _matches_lexicon(target_name)
                if term:
                    alias_terms[target_name] = term
                    changed = True
                    continue

                # value-side hint: user.ssn / record["ssn"]
                if isinstance(stmt.value, ast.Attribute):
                    value_term = _matches_lexicon(stmt.value.attr)
                    if value_term:
                        alias_terms[target_name] = value_term
                        changed = True
                        continue
                elif isinstance(stmt.value, ast.Subscript):
                    key = stmt.value.slice
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        value_term = _matches_lexicon(key.value)
                        if value_term:
                            alias_terms[target_name] = value_term
                            changed = True
                            continue
                # multi-hop rename: y = x, where x already resolved
                elif isinstance(stmt.value, ast.Name) and stmt.value.id in alias_terms:
                    alias_terms[target_name] = alias_terms[stmt.value.id]
                    changed = True
                    continue

            if not changed:
                break

        for call_node in ast.walk(func_node):
            if not isinstance(call_node, ast.Call):
                continue
            sink_kind = _is_log_call(call_node)
            if sink_kind is None:
                continue

            all_args = list(call_node.args) + [kw.value for kw in call_node.keywords]
            for arg in all_args:
                for name_node in _names_in_node(arg) if not isinstance(arg, ast.Name) else [arg]:
                    term = _matches_lexicon(name_node.id) or alias_terms.get(name_node.id)
                    if not term:
                        continue

                    # Direct lexicon-name match (e.g. logger.info(ssn)) is
                    # higher confidence than an alias-chain match.
                    direct = _matches_lexicon(name_node.id) is not None
                    severity = "HIGH" if term in _HIGH_SEVERITY_TERMS else "MEDIUM"
                    confidence = 0.55 if direct else 0.4
                    is_hotspot = not direct

                    line_number = getattr(call_node, "lineno", 1)
                    dedup_key = (line_number, name_node.id, sink_kind)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    snippet = source_lines[line_number - 1].strip() if 0 < line_number <= len(source_lines) else ""

                    findings.append(PiiLogSinkFinding(
                        line_number=line_number,
                        identifier=name_node.id,
                        lexicon_term=term,
                        sink_kind=sink_kind,
                        mechanism_id=f"sensitive_data.pii_log_sink.{term}",
                        severity=severity if direct else "LOW",
                        confidence=confidence,
                        is_hotspot=is_hotspot,
                        description=(
                            f"Identifier '{name_node.id}' (matches PII lexicon term "
                            f"'{term}') is passed to a {sink_kind}() sink"
                            + ("" if direct else " via a same-function assignment alias")
                            + ", risking exposure of sensitive data in logs."
                        ),
                        recommendation=(
                            "Remove or mask this value before logging (e.g. log a "
                            "hashed/truncated identifier instead of the raw value). "
                            "For structured PII fields on Pydantic models, use "
                            "`pydantic.SecretStr` so the value is redacted by default "
                            "in `repr()`/`str()` and therefore in most log formatters."
                        ),
                        snippet=snippet[:150],
                        compliance_tags=_compliance_tags_for(term),
                    ))

    return findings


def scan_django_debug_true(tree: ast.AST, source_lines: List[str]) -> List[PiiLogSinkFinding]:
    """Flag Django settings.py-style `DEBUG = True` -- verbose error pages
    leak stack traces, local variables, and request data (RESEARCH_11)."""
    findings: List[PiiLogSinkFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "DEBUG":
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    line_number = getattr(node, "lineno", 1)
                    snippet = source_lines[line_number - 1].strip() if 0 < line_number <= len(source_lines) else ""
                    findings.append(PiiLogSinkFinding(
                        line_number=line_number,
                        identifier="DEBUG",
                        lexicon_term="debug_flag",
                        sink_kind="config",
                        mechanism_id="sensitive_data.django_debug_true",
                        severity="HIGH",
                        confidence=0.8,
                        is_hotspot=False,
                        description=(
                            "Django DEBUG=True leaks detailed stack traces, local "
                            "variable values, and full request data (including "
                            "cookies and POST bodies) on any unhandled exception."
                        ),
                        recommendation=(
                            "Set DEBUG = False in production; read it from an "
                            "environment variable defaulting to False."
                        ),
                        snippet=snippet[:150],
                        compliance_tags=["GDPR"],
                    ))
    return findings
