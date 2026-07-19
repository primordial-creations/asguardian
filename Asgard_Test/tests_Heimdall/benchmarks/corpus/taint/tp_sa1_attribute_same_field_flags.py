"""SA1 field sensitivity, positive case: `x.a = taint; sink(x.a)` -- the
SAME field is written then read -- must flag."""


def handler():
    x = Ctx()
    x.a = request.args["q"]
    cursor.execute(x.a)
