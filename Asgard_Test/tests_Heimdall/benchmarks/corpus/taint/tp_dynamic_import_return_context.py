"""TP regression, context-coverage fix (adversarial review, reviewer's
exact repro): `return __import__(userVar)` where `userVar` is a bare
function parameter (not a proven taint source). Two things must both
work here: (1) the RETURN-context fix (see
tp_dynamic_getattr_dispatch_return_context.py) so the construct is
checked at all, and (2) a dynamic construct must flag on ANY non-constant
operand -- including an unresolved bare parameter, not only a proven
taint source -- because a dynamic import/dispatch of externally-
influenced input is inherently review-worthy ("unresolved != safe").
Must surface a needs-review dynamic_construct finding (CWE-470)."""


def load(userVar):
    return __import__(userVar)
