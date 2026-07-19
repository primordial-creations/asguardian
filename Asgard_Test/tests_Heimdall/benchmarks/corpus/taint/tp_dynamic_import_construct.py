"""TP: WS5 dynamic-construct surfacing. `__import__(userVar)` imports an
attacker-influenced module name -- undecidable for static taint -- must
surface a needs-review dynamic_construct finding (CWE-470)."""


def run():
    mod_name = request.args.get("mod")
    m = __import__(mod_name)
    return m
