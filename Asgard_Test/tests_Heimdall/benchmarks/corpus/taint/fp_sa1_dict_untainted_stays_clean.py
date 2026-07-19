"""SA1 sanity: no taint ever enters the container -- must stay clean
regardless of field/container tracking."""


def handler():
    m = {}
    m["a"] = "constant"
    cursor.execute(m["a"])
