"""
Lexical Helpers - tokenization and casing normalization (DEEPTHINK_08 §1).

`orderId`, `order_id`, `ORDER_ID` and `OrderID` must all normalize to the
same token tuple `("order", "id")` so field matching across formats does
not depend on each format's naming convention.
"""

import re

_BOUNDARY_RE = re.compile(r"[_\-\s]+")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def tokenize(name: str) -> tuple[str, ...]:
    """Split an identifier into lowercase tokens regardless of source casing."""
    if not name:
        return ()
    # First split on explicit boundaries (snake_case, kebab-case, spaces).
    parts = _BOUNDARY_RE.split(name)
    tokens: list[str] = []
    for part in parts:
        if not part:
            continue
        # Then split camelCase / PascalCase / acronym boundaries within each part.
        sub_parts = _CAMEL_RE.split(part)
        tokens.extend(p for p in sub_parts if p)
    return tuple(t.lower() for t in tokens)
