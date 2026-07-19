"""SA2 constant/string propagation: `eval(prefix + "1")` where `prefix`
is a Name bound to a literal string is fold-to-constant -- must not be
flagged as a dynamic-construct (needs-review) finding, and (being a
pure literal) is not a tainted eval_exec sink hit either."""


def handler():
    prefix = "1 + "
    return eval(prefix + "1")
