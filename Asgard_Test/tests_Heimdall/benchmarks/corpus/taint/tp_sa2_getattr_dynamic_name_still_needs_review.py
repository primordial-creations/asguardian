"""SA2 residue check: a GENUINELY non-constant attribute name used in the
getattr-dispatch-call shape must still surface as needs-review -- SA2
narrows the dynamic-construct residue, it does not eliminate the
legitimately-unbounded case."""


def handler(method_name):
    o = Ctx()
    return getattr(o, method_name)()
