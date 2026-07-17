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
    lowered = tail.lower()
    if lowered.startswith(_HEURISTIC_PREFIXES) or call_chain in _HEURISTIC_EXACT:
        return SanitizerMatch(call_chain, "heuristic", HEURISTIC_SANITIZER_FACTOR)
    return None
