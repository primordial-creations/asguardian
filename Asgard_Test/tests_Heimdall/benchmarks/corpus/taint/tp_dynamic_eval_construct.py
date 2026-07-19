"""TP: WS5 dynamic-construct surfacing. `eval(x)` reached with a tainted,
non-constant operand is undecidable for static taint -- must surface an
explicit needs-review dynamic_construct finding (CWE-470)."""


def run():
    code = request.args.get("code")
    eval(code)
