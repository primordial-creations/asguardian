"""
Type Compatibility Matrix - dict[(TypeClass, TypeClass)] -> MatrixVerdict.

Small and exhaustively unit-testable, per plan 07. Verdicts:
- ISOMORPHIC: identical semantics.
- COERCIBLE_IDIOMATIC: safe/expected cross-format convention (e.g. proto
  int64 <-> GraphQL String for IDs, uuid <-> string).
- COERCIBLE_LOSSY: representable but may lose precision/range
  (int64->int32, float64->float32, decimal->float).
- INCOMPATIBLE: no reasonable mapping (string vs bool).

INCOMPATIBLE is symmetric. COERCIBLE_LOSSY is directional (narrowing only);
the widening direction (int32->int64) is ISOMORPHIC (no data loss).
"""

from enum import Enum

from Asgard.Forseti.Alignment.models.ir_models import TypeClass


class MatrixVerdict(str, Enum):
    ISOMORPHIC = "isomorphic"
    COERCIBLE_IDIOMATIC = "coercible_idiomatic"
    COERCIBLE_LOSSY = "coercible_lossy"
    INCOMPATIBLE = "incompatible"


_NUMERIC_ORDER = [TypeClass.INT32, TypeClass.INT64, TypeClass.FLOAT32, TypeClass.FLOAT64, TypeClass.DECIMAL]
_NUMERIC_CAPACITY = {
    TypeClass.INT32: 32,
    TypeClass.INT64: 64,
    TypeClass.FLOAT32: 32,
    TypeClass.FLOAT64: 64,
    TypeClass.DECIMAL: 128,
}

# Explicit idiomatic coercions that are NOT purely numeric-capacity driven.
_IDIOMATIC_PAIRS: set[tuple[TypeClass, TypeClass]] = {
    (TypeClass.INT64, TypeClass.STRING),
    (TypeClass.STRING, TypeClass.INT64),
    (TypeClass.UUID, TypeClass.STRING),
    (TypeClass.STRING, TypeClass.UUID),
    (TypeClass.DATE, TypeClass.STRING),
    (TypeClass.STRING, TypeClass.DATE),
    (TypeClass.DATETIME, TypeClass.STRING),
    (TypeClass.STRING, TypeClass.DATETIME),
}

_STRING_LIKE = {TypeClass.STRING, TypeClass.BYTES}
_NUMERIC = set(_NUMERIC_ORDER)


def classify(source: TypeClass, target: TypeClass) -> MatrixVerdict:
    """Classify the compatibility of assigning a `source`-typed value where `target` is expected."""
    if source == target:
        return MatrixVerdict.ISOMORPHIC

    if (source, target) in _IDIOMATIC_PAIRS:
        return MatrixVerdict.COERCIBLE_IDIOMATIC

    if source in _NUMERIC and target in _NUMERIC:
        src_cap = _NUMERIC_CAPACITY[source]
        tgt_cap = _NUMERIC_CAPACITY[target]
        if src_cap <= tgt_cap:
            return MatrixVerdict.ISOMORPHIC
        return MatrixVerdict.COERCIBLE_LOSSY

    if source in _STRING_LIKE and target in _STRING_LIKE:
        return MatrixVerdict.ISOMORPHIC

    if source == TypeClass.ANY or target == TypeClass.ANY:
        return MatrixVerdict.COERCIBLE_IDIOMATIC

    return MatrixVerdict.INCOMPATIBLE


def is_symmetric_incompatible(a: TypeClass, b: TypeClass) -> bool:
    """INCOMPATIBLE must be symmetric: incompatible(a,b) == incompatible(b,a)."""
    return classify(a, b) == MatrixVerdict.INCOMPATIBLE and classify(b, a) == MatrixVerdict.INCOMPATIBLE
