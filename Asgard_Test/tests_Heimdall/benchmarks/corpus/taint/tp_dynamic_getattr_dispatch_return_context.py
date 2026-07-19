"""TP regression, context-coverage fix (adversarial review, reviewer's
exact repro): `return getattr(o, request.args['m'])()` -- a dynamic
construct used directly in a RETURN expression. `visit_Return` previously
only ran `_eval` on the return value (to compute a taint state for
inter-procedural summaries) and never dispatched to `visit_Call`, so a
dynamic construct that only ever appeared inside a `return` was silently
never checked -- 0 flows, a structural miss independent of the earlier
ROOT CAUSE (Layer-2/Layer-3 triggering) fix. Must surface a needs-review
dynamic_construct finding (CWE-470)."""


def dispatch(o):
    return getattr(o, request.args["m"])()
