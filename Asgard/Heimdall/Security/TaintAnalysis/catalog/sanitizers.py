"""
Sanitizer taxonomy (DEEPTHINK_03 s1) -- replaces the boolean sanitizer flag.

    exact     factor 0.0  : known-complete neutralizers. The flow is dropped.
                            (shlex.quote, html.escape, int(), uuid.UUID, ...)
    heuristic factor 0.4  : looks like a sanitizer by naming convention
                            (clean_*/sanitize_*/validate_*) or is a partial
                            transform (re.sub). The flow is KEPT with its
                            confidence multiplied by 0.4 -- we do not know the
                            custom function actually neutralizes the payload,
                            so we downgrade instead of silently dropping.
"""

from dataclasses import dataclass
from typing import Optional, Sequence

HEURISTIC_SANITIZER_FACTOR = 0.4

# Exact-signature sanitizers: value-domain restriction or context-correct
# escaping with well-understood semantics.
EXACT_SANITIZERS = frozenset({
    # Type/value-domain coercions
    "int", "float", "bool", "abs", "len", "uuid.UUID", "UUID",
    # Shell
    "shlex.quote", "quote",
    # HTML
    "html.escape", "escape", "markupsafe.escape", "Markup.escape",
    "bleach.clean",
    # URL
    "quote_plus", "urllib.parse.quote", "urllib.parse.quote_plus",
    # SQL escaping / parameterization helpers
    "sql.escape", "escape_string", "parameterize", "sqlalchemy.bindparam",
    "bindparam",
})

# JavaScript/TypeScript UNSHADOWABLE exact sanitizers: language builtins and
# module-namespaced calls on receivers that are never plausibly redefined by
# application code without an obvious binding change (no import/binding
# resolution is implemented, so these are trusted as-is). Full-drop (0.0).
JS_EXACT_SANITIZERS = frozenset({
    "parseInt", "parseFloat", "Number", "Boolean", "String",
    "encodeURIComponent", "encodeURI",
    "path.normalize", "path.basename",
    "mysql.escape", "pg.escapeLiteral", "connection.escape",
    "util.escapeRegExp",
})

# JavaScript/TypeScript SHADOWABLE library sanitizers: plausible for a local
# function/const of the same bare name (e.g. `function escapeHtml(x){return
# x}`) to shadow the real library call without our (absent) binding
# resolution being able to tell the difference. A no-op local shadow must
# NOT fully launder a real flow -- downgrade only (heuristic factor),
# never full-drop, until import/binding resolution lands.
JS_LIBRARY_SANITIZERS = frozenset({
    "DOMPurify.sanitize", "sanitize-html", "sanitizeHtml",
    "escapeHtml", "he.encode", "validator.escape",
})

# Java UNSHADOWABLE exact sanitizers (JDBC API / stdlib boxing methods and
# well-known encoder classes are not plausibly shadowed by a same-named
# local method in idiomatic Java -- methods are always receiver-qualified
# and the JDK/JDBC types cannot be redeclared).
JAVA_EXACT_SANITIZERS = frozenset({
    "PreparedStatement", "preparedStatement", "setString", "setInt",
    "Integer.parseInt", "Integer.valueOf", "Long.parseLong", "Double.parseDouble",
    "URLEncoder.encode", "UUID.fromString",
})

# Java SHADOWABLE library sanitizers: third-party encoder helpers where a
# locally-declared same-named static method could plausibly shadow the real
# import without binding resolution catching it. Downgrade only.
JAVA_LIBRARY_SANITIZERS = frozenset({
    "StringEscapeUtils.escapeHtml4", "StringEscapeUtils.escapeSql",
    "ESAPI.encoder", "Encode.forHtml", "Encode.forJavaScript",
})

# Go UNSHADOWABLE exact sanitizers: stdlib functions on package-qualified
# names are not plausibly shadowed by a same-named local declaration in
# idiomatic Go (the package selector makes the binding unambiguous).
GO_EXACT_SANITIZERS = frozenset({
    "strconv.Atoi", "strconv.ParseInt", "strconv.ParseFloat", "strconv.ParseBool",
    "filepath.Clean", "path.Clean", "filepath.Base", "path.Base",
    "html.EscapeString", "url.QueryEscape", "url.PathEscape",
    "template.HTMLEscapeString", "template.JSEscapeString",
    "uuid.Parse", "uuid.MustParse",
})

# Go SHADOWABLE library sanitizers: third-party helper packages where a
# locally-declared same-named function could plausibly shadow the import
# without binding resolution catching it. Downgrade only.
GO_LIBRARY_SANITIZERS = frozenset({
    "bluemonday.Sanitize", "bluemonday.SanitizeBytes",
})

# C UNSHADOWABLE exact sanitizers: numeric-coercion libc functions (bare
# identifiers, C has no namespacing so these ARE plausibly shadowable by a
# same-named local function in principle -- but redeclaring a libc symbol
# name is rare enough in practice, and required-declaration conflicts make
# it noisy, that we accept the small risk to match the precedent set by
# Python's bare `int`/`float` in EXACT_SANITIZERS above). Value-domain
# restriction: a numeric string can no longer carry a shell/SQL/format-string
# payload once parsed.
C_EXACT_SANITIZERS = frozenset({
    "atoi", "atol", "atoll", "strtol", "strtoul", "strtoll", "strtoull",
    "strtod", "strtof",
})

# Naming conventions that *suggest* a custom sanitizer.
_HEURISTIC_PREFIXES = ("clean", "sanitize", "sanitise", "validate", "escape_", "strip_")
_HEURISTIC_EXACT = frozenset({"re.sub", "sub"})


@dataclass(frozen=True)
class SanitizerMatch:
    """Result of classifying a call as a sanitizer."""
    name: str
    kind: str       # "exact" or "heuristic"
    factor: float   # multiplier applied to flow confidence (0.0 drops)


def classify_sanitizer(
    call_chain: str,
    custom_sanitizers: Sequence[str] = (),
) -> Optional[SanitizerMatch]:
    """
    Classify a (alias-resolved) call chain as a sanitizer, or None.

    User-supplied ``custom_sanitizers`` are trusted as exact (factor 0.0):
    the user asserted their semantics.
    """
    tail = call_chain.rsplit(".", 1)[-1]
    for custom in custom_sanitizers:
        if call_chain == custom or call_chain.endswith("." + custom) or tail == custom:
            return SanitizerMatch(call_chain, "exact", 0.0)
    if call_chain in EXACT_SANITIZERS or tail in EXACT_SANITIZERS:
        return SanitizerMatch(call_chain, "exact", 0.0)
    if call_chain in JS_EXACT_SANITIZERS or tail in JS_EXACT_SANITIZERS:
        return SanitizerMatch(call_chain, "exact", 0.0)
    if call_chain in JAVA_EXACT_SANITIZERS or tail in JAVA_EXACT_SANITIZERS:
        return SanitizerMatch(call_chain, "exact", 0.0)
    # Shadowable library sanitizers: without binding resolution we cannot
    # tell a real import apart from a locally-declared no-op of the same
    # name, so only downgrade (never fully drop) the flow.
    if call_chain in JS_LIBRARY_SANITIZERS or tail in JS_LIBRARY_SANITIZERS:
        return SanitizerMatch(call_chain, "heuristic", HEURISTIC_SANITIZER_FACTOR)
    if call_chain in JAVA_LIBRARY_SANITIZERS or tail in JAVA_LIBRARY_SANITIZERS:
        return SanitizerMatch(call_chain, "heuristic", HEURISTIC_SANITIZER_FACTOR)
    if call_chain in GO_EXACT_SANITIZERS or tail in GO_EXACT_SANITIZERS:
        return SanitizerMatch(call_chain, "exact", 0.0)
    if call_chain in GO_LIBRARY_SANITIZERS or tail in GO_LIBRARY_SANITIZERS:
        return SanitizerMatch(call_chain, "heuristic", HEURISTIC_SANITIZER_FACTOR)
    if call_chain in C_EXACT_SANITIZERS or tail in C_EXACT_SANITIZERS:
        return SanitizerMatch(call_chain, "exact", 0.0)
    lowered = tail.lower()
    if lowered.startswith(_HEURISTIC_PREFIXES) or call_chain in _HEURISTIC_EXACT:
        return SanitizerMatch(call_chain, "heuristic", HEURISTIC_SANITIZER_FACTOR)
    return None
