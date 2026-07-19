"""FP sibling of tp_dynamic_getattr_dispatch_return_context.py: same
RETURN-context shape, but the attribute-name argument is a constant
string literal -- ordinary, decidable code. Must stay clean even now that
`visit_Return` dispatches into the return expression's Call nodes."""


def dispatch_const(o):
    return getattr(o, "fixed")
