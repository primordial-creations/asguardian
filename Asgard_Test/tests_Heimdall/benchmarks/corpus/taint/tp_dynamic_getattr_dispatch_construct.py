"""TP: WS5 dynamic-construct surfacing. `getattr(obj, userinput)(...)` --
the callee itself is a getattr() call whose attribute-name argument is
attacker-influenced -- reflective dispatch to an arbitrary method, must
surface a needs-review dynamic_construct finding (CWE-470)."""


def run():
    action = request.args.get("action")
    getattr(handlers, action)()
