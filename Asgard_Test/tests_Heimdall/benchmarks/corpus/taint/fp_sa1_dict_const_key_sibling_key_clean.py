"""SA1 container sensitivity, negative case: `m["a"] = taint;
sink(m["b"])` -- a DIFFERENT constant key -- must NOT flag."""


def handler():
    m = {}
    m["a"] = request.args["q"]
    cursor.execute(m["b"])
