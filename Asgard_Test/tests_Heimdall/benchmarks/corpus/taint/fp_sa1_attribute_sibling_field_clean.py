"""SA1 field sensitivity, negative case: `x.a = taint; sink(x.b)` -- a
DIFFERENT field is read -- must NOT flag (this is the core precision gain;
must not mute the sibling case above, which stays a real flow)."""


def handler():
    x = Ctx()
    x.a = request.args["q"]
    cursor.execute(x.b)
