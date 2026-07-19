"""SA2 field precision: `setattr(o, "a", taint)` then `getattr(o, "b")`
(a DIFFERENT constant field) must NOT flag -- getattr/setattr resolution
is field-sensitive, not container-wide."""


def handler():
    o = Ctx()
    setattr(o, "a", request.args["q"])
    cursor.execute(getattr(o, "b"))
