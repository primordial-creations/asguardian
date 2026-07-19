"""SA1 container sensitivity, positive case: `m["a"] = taint; sink(m["a"])`
-- the SAME constant key is written then read -- must flag."""


def handler():
    m = {}
    m["a"] = request.args["q"]
    cursor.execute(m["a"])
