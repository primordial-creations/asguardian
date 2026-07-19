"""SA2: `setattr(o, "a", taint)` / `getattr(o, "a")` with a LITERAL name
resolve to plain field access (`o.a`) at full fidelity -- taint must
propagate through the resolved field, same as `o.a = taint; sink(o.a)`."""


def handler():
    o = Ctx()
    setattr(o, "a", request.args["q"])
    cursor.execute(getattr(o, "a"))
